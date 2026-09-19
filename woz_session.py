# -*- coding: utf-8 -*-
"""
半結構化 WoZ 之共用會話狀態（C 組專用；A、B 組不會用到這個檔案）。

因為整個實驗要遠端進行，參與者與操作員是兩個分開的瀏覽器連線，各自的
Gradio session/state 彼此看不到對方。這裡改用「共用的 JSON 檔案 + 輪詢
（polling）」來同步，跟 randomization.py／logger.py 用同一套「先寫暫存檔
再 os.replace」的作法，確保寫到一半被中斷也不會壞檔：

  - 參與者送出訊息 → append_participant_message()：寫入這個參與者的共用
    session 檔案，標記 awaiting_operator=True。
  - 操作員畫面輪詢 list_pending_sessions()：列出所有還在等回覆的參與者，
    依「等待開始的時間」由久到近排序，幫助操作員掌握 3 分鐘時限、優先
    處理等最久的人。
  - 操作員挑一句預寫回覆送出 → append_operator_message()：寫入同一個
    session 檔案，標記 awaiting_operator=False，並自動算出這次回覆花了
    幾秒（latency_seconds），供事後 10% 標準化抽查時直接核對是否符合
    3 分鐘時限，不用再手動比對時間戳記。
  - 參與者畫面輪詢 load_session()：一旦看到新的操作員回覆就更新聊天畫面、
    解除輸入鎖定。

跟 randomization.py 一樣用 threading.Lock 讓同一個 process 內的讀寫互斥；
若未來部署改成多 worker，需要換成跨行程的檔案鎖，屆時再擴充。
"""

import json
import os
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "woz_sessions")

_lock = threading.Lock()


def _safe_pid(participant_id: str) -> str:
    return "".join(c for c in participant_id if c.isalnum() or c in ("-", "_")) or "unknown"


def _session_path(participant_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{_safe_pid(participant_id)}.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save(session: dict) -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = _session_path(session["participant_id"])
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def load_session(participant_id: str):
    """回傳這位參與者目前的 session dict，不存在則回傳 None。"""
    path = _session_path(participant_id)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_session(participant_id: str, scenario_id: int, scenario_title: str) -> dict:
    """開始一段新的 WoZ 對話（進入 chat 階段、情境 1 開始時呼叫一次）。"""
    with _lock:
        session = {
            "participant_id": participant_id,
            "scenario_id": scenario_id,
            "scenario_title": scenario_title,
            "scenario_turn_index": 0,  # 這個情境已完成幾回合（參與者+操作員各一句算一回合）
            "awaiting_operator": False,
            "messages": [],  # [{who, text, ts, [latency_seconds]}], who: participant/operator/system
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        _save(session)
        return session


def append_participant_message(participant_id: str, text: str) -> dict:
    """參與者送出一則訊息。上一句若還沒被操作員回覆，會直接擋下來——
    畫面上應該已經鎖住輸入框，這裡是第二層防護。"""
    with _lock:
        session = load_session(participant_id)
        if session is None:
            raise RuntimeError(f"找不到參與者 {participant_id} 的 WoZ session，須先呼叫 create_session()")
        if session["awaiting_operator"]:
            raise RuntimeError("上一則訊息尚未收到操作員回覆，暫時無法送出新訊息")
        session["messages"].append({"who": "participant", "text": text, "ts": _now_iso()})
        session["awaiting_operator"] = True
        session["updated_at"] = _now_iso()
        _save(session)
        return session


def append_operator_message(participant_id: str, text: str) -> dict:
    """操作員送出一句預寫回覆。回傳的 session 裡，這則訊息會附上
    latency_seconds（距離參與者送出訊息經過了幾秒），供標準化稽核使用。"""
    with _lock:
        session = load_session(participant_id)
        if session is None:
            raise RuntimeError(f"找不到參與者 {participant_id} 的 WoZ session")
        if not session["awaiting_operator"]:
            raise RuntimeError("目前沒有等待回覆中的訊息，不需要（也不應該）送出操作員回覆")

        last_participant_msg = next(
            (m for m in reversed(session["messages"]) if m["who"] == "participant"), None
        )
        latency_seconds = None
        if last_participant_msg is not None:
            sent_at = datetime.fromisoformat(last_participant_msg["ts"])
            latency_seconds = round((datetime.now(timezone.utc) - sent_at).total_seconds(), 1)

        session["messages"].append({
            "who": "operator", "text": text, "ts": _now_iso(), "latency_seconds": latency_seconds,
        })
        session["awaiting_operator"] = False
        session["scenario_turn_index"] += 1
        session["updated_at"] = _now_iso()
        _save(session)
        return session


def advance_scenario(participant_id: str, scenario_id: int, scenario_title: str) -> dict:
    """切換到下一個情境：沿用同一個 session 檔案（完整訊息歷程都保留），
    只把回合數歸零、換上新情境資訊。行為對應 A/B 組 on_next_scenario_or_posttest
    裡對 chat_scenario_index / chat_turn_index 的重置邏輯。"""
    with _lock:
        session = load_session(participant_id)
        if session is None:
            raise RuntimeError(f"找不到參與者 {participant_id} 的 WoZ session")
        session["scenario_id"] = scenario_id
        session["scenario_title"] = scenario_title
        session["scenario_turn_index"] = 0
        session["awaiting_operator"] = False
        session["updated_at"] = _now_iso()
        _save(session)
        return session


def list_pending_sessions() -> list:
    """操作員儀表板用：列出所有『正在等待操作員回覆』的參與者，
    依等待開始的時間由久到近排序（等最久的排最前面），方便操作員
    優先處理快超過 3 分鐘時限的人。"""
    if not os.path.isdir(SESSIONS_DIR):
        return []
    pending = []
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        pid = fname[:-len(".json")]
        session = load_session(pid)
        if not session or not session.get("awaiting_operator"):
            continue
        last_msg = session["messages"][-1] if session["messages"] else None
        pending.append({
            "participant_id": pid,
            "scenario_id": session["scenario_id"],
            "scenario_title": session["scenario_title"],
            "latest_message": last_msg["text"] if last_msg else "",
            "waiting_since": last_msg["ts"] if last_msg else session["updated_at"],
        })
    pending.sort(key=lambda p: p["waiting_since"])
    return pending
