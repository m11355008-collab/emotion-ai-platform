# -*- coding: utf-8 -*-
"""
Conversation logging.

Writes one row per message (both participant and AI turns) to a CSV file,
tagged with participant_id / group / scenario / turn order / timestamp.

This structure is what makes the （八）歷程質性資料與縱貫式紮根理論分析
section of the research design possible later: you can always reconstruct
one participant's full chronological path through all three scenarios by
filtering + sorting this CSV on participant_id, scenario_id, turn_index.

One CSV file per participant is created under data/, named
<participant_id>_<group>.csv — easy to eyeball individually, and easy to
concatenate later with pandas for analysis.
"""

import csv
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

FIELDNAMES = [
    "participant_id",
    "group",
    "scenario_id",
    "scenario_title",
    "turn_index",
    "speaker",       # "participant"、"ai"（A/B 組模型回覆），或 "operator"（C 組 WoZ 操作員回覆）
    "timestamp_utc",
    "message",
    "reply_latency_seconds",  # 僅 C 組 speaker="operator" 才會有值：距參與者送出訊息經過幾秒，
                               # 供半結構化 WoZ 的「3 分鐘回覆時限」標準化稽核直接核對，
                               # 其餘列一律留空。
]


def _log_path(participant_id: str, group: str) -> str:
    safe_pid = "".join(c for c in participant_id if c.isalnum() or c in ("-", "_")) or "unknown"
    return os.path.join(DATA_DIR, f"{safe_pid}_{group}.csv")


def log_turn(participant_id: str, group: str, scenario_id: int, scenario_title: str,
             turn_index: int, speaker: str, message: str,
             reply_latency_seconds=None) -> None:
    """Append one turn to this participant's CSV log. Creates the file
    (with header) on first write. Also re-creates the data/ folder if it's
    missing, so the app doesn't crash if that folder gets moved or deleted
    while it's running.

    reply_latency_seconds is optional and only meaningful for C 組
    speaker="operator" rows (see woz_session.append_operator_message);
    every other row leaves it blank."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _log_path(participant_id, group)
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "participant_id": participant_id,
            "group": group,
            "scenario_id": scenario_id,
            "scenario_title": scenario_title,
            "turn_index": turn_index,
            "speaker": speaker,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "message": message,
            "reply_latency_seconds": "" if reply_latency_seconds is None else reply_latency_seconds,
        })


def get_log_path_for_display(participant_id: str, group: str) -> str:
    """Used by the UI to show/download the current session's log file."""
    return _log_path(participant_id, group)


# ============================================================
# 歷程執行資料 (Process/Execution Log)
#
# 教授第四輪意見明確要求：「保留每次過程的所有歷程執行資料」，
# 範圍不限於對話文本。這裡新增兩個獨立的記錄檔：
#   1. process log   — 每個階段（問卷／情境）的開始、結束時間戳記
#   2. answers log    — 每一題問卷的實際作答內容
# 跟對話紀錄（log_turn）分開存放，避免欄位混雜在同一個檔案裡。
# ============================================================

PROCESS_FIELDNAMES = [
    "participant_id",
    "group",
    "phase",          # 例如 "pretest_demographics", "scenario_1", "posttest_ERQ"
    "event",           # "start" 或 "end"
    "timestamp_utc",
]

ANSWER_FIELDNAMES = [
    "participant_id",
    "group",
    "session",        # "pre" 或 "post"
    "questionnaire_id",
    "item_id",
    "response",
    "timestamp_utc",
]


def _process_log_path(participant_id: str) -> str:
    safe_pid = "".join(c for c in participant_id if c.isalnum() or c in ("-", "_")) or "unknown"
    return os.path.join(DATA_DIR, f"{safe_pid}_process.csv")


def _answers_log_path(participant_id: str) -> str:
    safe_pid = "".join(c for c in participant_id if c.isalnum() or c in ("-", "_")) or "unknown"
    return os.path.join(DATA_DIR, f"{safe_pid}_answers.csv")


def log_process_event(participant_id: str, group: str, phase: str, event: str) -> None:
    """Record that a phase (a questionnaire section, or a role-play scenario)
    started or ended. event must be 'start' or 'end'.

    Call this at the beginning and end of every pretest questionnaire,
    every scenario, and every posttest questionnaire — this is what lets
    you later verify each session ran for a reasonable, standardized
    amount of time, and supports the longitudinal grounded-theory analysis
    in（八）of the design document.
    """
    if event not in ("start", "end"):
        raise ValueError(f"event must be 'start' or 'end', got: {event!r}")
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _process_log_path(participant_id)
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PROCESS_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "participant_id": participant_id,
            "group": group,
            "phase": phase,
            "event": event,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def log_questionnaire_response(participant_id: str, group: str, session: str,
                                questionnaire_id: str, item_id: str, response: str) -> None:
    """Record one answered item from a pre/post questionnaire.
    session must be 'pre' or 'post'."""
    if session not in ("pre", "post"):
        raise ValueError(f"session must be 'pre' or 'post', got: {session!r}")
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _answers_log_path(participant_id)
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ANSWER_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "participant_id": participant_id,
            "group": group,
            "session": session,
            "questionnaire_id": questionnaire_id,
            "item_id": item_id,
            "response": response,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def get_process_log_path_for_display(participant_id: str) -> str:
    return _process_log_path(participant_id)


def get_answers_log_path_for_display(participant_id: str) -> str:
    return _answers_log_path(participant_id)
