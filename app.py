# -*- coding: utf-8 -*-
"""
Emotion-AI role-play platform — 完整流程整合版
（基本資料／前測問卷 → 三情境角色扮演對話 → 後測問卷 → 完成）

這個版本把原本各自獨立、都已經測試過能動的兩塊拼在一起：
  - 對話部分：邏輯完全承襲自舊版 app.py（現存檔為 app_chat_only.py.bak），沒有改動核心行為。
  - 問卷部分：邏輯完全承襲自 survey_ui.py 的固定插槽版本，沒有改動核心行為。
拼接方式：用「同一組固定元件、切換顯示/隱藏」的做法（跟兩邊原本的寫法一致），
故意不用 gr.render，因為上一輪測試證實 gr.render 在這個環境裡不穩定。

執行方式：
    export GEMINI_API_KEY="your-key-here"
    python app.py
"""

import os
import re
import time
import gradio as gr
from google import genai
from google.genai import types

from system_prompts import SYSTEM_PROMPTS
from scenarios import SCENARIOS, MIN_TURNS_PER_SCENARIO, MAX_TURNS_PER_SCENARIO, get_opening
from logger import (
    log_turn,
    get_log_path_for_display,
    get_process_log_path_for_display,
    get_answers_log_path_for_display,
)
from questionnaires import PRETEST_QUESTIONNAIRES, POSTTEST_QUESTIONNAIRES
from survey import SurveySession
import randomization
import woz_session
import reply_bank
import backup

WOZ_POLL_INTERVAL_SECONDS = 3  # 參與者畫面輪詢操作員回覆的頻率
OPERATOR_PASSWORD = os.environ.get("WOZ_OPERATOR_PASSWORD")  # None＝操作員頁面暫時無法登入，須先設定

# 服務啟動時，先嘗試把分派紀錄從備份還原回來（見 backup.restore_file 的說明）。
# 這裡刻意放在模組載入時、gr.Blocks 建構之前執行一次，確保第一位參與者連進來
# 之前，本機的分派紀錄就已經是最新狀態，不會出現「服務重啟後從頭分派」的問題。
backup.restore_file(os.path.basename(randomization.ASSIGNMENTS_PATH), randomization.ASSIGNMENTS_PATH)

MODEL_NAME = "gemini-2.5-flash"
# 提醒（2026年9月查證）：gemini-2.5-flash 目前是穩定版，但 Google 已公告
# 2026/10/16 起會停用整個 2.5 系列。如果正式收案時間會晚於這個日期，
# 建議改用沒有停用時程的穩定版本，例如 "gemini-3.1-flash-lite"。
# 正式跑實驗前，請先到 https://ai.google.dev/gemini-api/docs/models
# 確認當下可用的模型名稱，避免收案到一半模型被下架。

MAX_ITEMS = 30  # 問卷題目插槽上限，理由同 survey_ui.py


def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "找不到 GEMINI_API_KEY 環境變數。請先在終端機執行：\n"
            "  export GEMINI_API_KEY=\"你的金鑰\"\n"
            "再重新啟動 app.py。"
        )
    return genai.Client(api_key=api_key)


def build_system_instruction(group: str, scenario: dict) -> str:
    base = SYSTEM_PROMPTS[group]
    context_note = (
        f"\n\n【目前情境】{scenario['title']}。"
        f"{scenario['opening']}\n"
        "以上情境資訊僅供你理解對話脈絡，不需要在回覆中覆述情境內容，"
        "直接針對使用者說的話回應即可。"
    )
    return base + context_note


def _create_scenario_chat(client, group, scenario):
    return client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=build_system_instruction(group, scenario),
            temperature=0.9,
            # thinking_budget=0：關閉 Gemini 2.5 系列的「思考過程」，
            # 否則回覆內容可能會把模型內部推理過程也一起顯示給使用者看到，
            # 這是你這次測試看到「回答出現整個AI思考過程」的原因。
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )


def _send_with_retry(chat, message, max_retries=2):
    """呼叫 Gemini。如果遇到「額度用盡」(429 RESOURCE_EXHAUSTED)，
    立刻回報清楚的訊息，不在伺服器裡卡住等待。
    （前一版本會在這裡用 time.sleep() 等待重試，最長可能卡住 120 秒，
    從畫面上看就是「一直加載沒反應」，而且卡住期間如果使用者按了其他
    按鈕，兩個請求會同時處理、互相干擾狀態，就是這次回報「切換情境後
    無法繼續對話」的成因。改成不等待、立刻回報，使用者自己決定要不要
    等一下再送一次，比伺服器自己悶著卡住更清楚、更不會壞掉。）
    正式收案前務必升級成付費方案，這裡不再自動重試，只是把錯誤訊息講清楚，
    不能取代真正需要的額度。"""
    try:
        return chat.send_message(message).text, None
    except Exception as e:
        error_str = str(e)
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
            wait_hint = "一段時間"
            match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)", error_str)
            if match:
                wait_hint = f"約 {int(match.group(1)) + 2} 秒"
            friendly = (f"（系統提示：目前 Gemini API 額度已用盡，這是免費方案的每分鐘請求數限制。"
                        f"請等待{wait_hint}後，重新輸入剛才的內容再送出一次。"
                        f"正式收案前請務必升級為付費方案，避免此狀況頻繁發生。）")
        else:
            friendly = f"（系統錯誤，未取得 AI 回覆：{error_str}）"
        return friendly, e


# ============================================================
# 整體實驗狀態
#
# 用一個 dict 貫穿全流程，取代原本 app.py／survey_ui.py 各自的 state，
# phase 決定畫面現在該顯示哪一塊：
#   "pretest"  → 顯示問卷區（跑 PRETEST_QUESTIONNAIRES）
#   "chat"     → 顯示對話區（跑三個情境）
#   "posttest" → 顯示問卷區（跑 POSTTEST_QUESTIONNAIRES）
#   "done"     → 顯示完成畫面
# ============================================================

def new_experiment_state(participant_id: str, group: str) -> dict:
    return {
        "participant_id": participant_id,
        "group": group,
        "phase": "pretest",
        "survey": SurveySession(
            participant_id=participant_id, group=group,
            session="pre", questionnaires=PRETEST_QUESTIONNAIRES,
        ),
        "chat_scenario_index": 0,
        "chat_turn_index": 0,
        "chat": None,
        "client": None,
        # C 組專用：目前已經顯示到 woz_session 訊息清單的第幾筆，見 on_woz_poll()。
        "woz_shown_count": 0,
    }


def render_all(state, chat_history=None, survey_error=None, preserve_survey_values=None):
    """整個實驗畫面在任何時間點『該長什麼樣子』，統一從這裡算出來。
    回傳順序必須跟下面 Blocks 裡宣告的 ALL_OUTPUTS 完全一致。

    preserve_survey_values：可選，格式 {題目索引: 使用者已經填的值}。
    用在「使用者送出問卷但有題目沒填」的情況——重新畫面時，
    要把「已經填過的題目」的值原封不動地保留住，只清空／標記沒填的題目，
    不能整頁重置，不然使用者等於要重填一次。"""
    updates = []
    preserve_survey_values = preserve_survey_values or {}

    # ---- 問卷插槽（前測／後測共用） ----
    if state is not None and state["phase"] in ("pretest", "posttest"):
        survey: SurveySession = state["survey"]
        if survey.is_finished:
            for _ in range(MAX_ITEMS):
                updates.append(gr.update(visible=False))  # radio
            for _ in range(MAX_ITEMS):
                updates.append(gr.update(visible=False))  # textbox
            updates.append(gr.update(visible=False))        # survey_submit_btn
            updates.append(gr.update(visible=False))        # survey_progress_md
            updates.append(gr.update(visible=False))        # survey_error_md
        else:
            survey.start_current()
            q = survey.current_questionnaire
            if len(q.items) > MAX_ITEMS:
                raise RuntimeError(
                    f"問卷 {q.id} 有 {len(q.items)} 題，超過系統上限 {MAX_ITEMS} 題，"
                    f"請把 app.py 裡的 MAX_ITEMS 調高。"
                )
            for i in range(MAX_ITEMS):
                if i < len(q.items) and q.items[i].qtype != "open_text":
                    item = q.items[i]
                    if item.qtype == "single_choice":
                        choices, label = item.choices, item.text
                    else:
                        choices = [str(x) for x in range(item.scale_min, item.scale_max + 1)]
                        label = (f"{item.text}　（{item.scale_min}＝{item.scale_min_label}　"
                                 f"～　{item.scale_max}＝{item.scale_max_label}）")
                    updates.append(gr.update(visible=True, choices=choices, label=label,
                                              value=preserve_survey_values.get(i)))
                else:
                    updates.append(gr.update(visible=False))
            for i in range(MAX_ITEMS):
                if i < len(q.items) and q.items[i].qtype == "open_text":
                    updates.append(gr.update(visible=True, label=q.items[i].text,
                                              value=preserve_survey_values.get(i, "")))
                else:
                    updates.append(gr.update(visible=False))
            is_last = survey.q_index + 1 >= len(survey.questionnaires)
            updates.append(gr.update(visible=True, interactive=True,
                                      value="提交，完成問卷" if is_last else "提交，前往下一份問卷"))
            stage_label = "前測" if state["phase"] == "pretest" else "後測"
            updates.append(gr.update(
                value=f"## {stage_label}：{q.name}\n（第 {survey.q_index + 1} / {len(survey.questionnaires)} 份）",
                visible=True,
            ))
            updates.append(gr.update(value=survey_error or "", visible=bool(survey_error)))
    else:
        for _ in range(MAX_ITEMS * 2):
            updates.append(gr.update(visible=False))
        updates.append(gr.update(visible=False))
        updates.append(gr.update(visible=False))
        updates.append(gr.update(visible=False))

    # ---- 對話區 ----
    if state is not None and state["phase"] == "chat":
        scenario = SCENARIOS[state["chat_scenario_index"]]
        reached_min = state["chat_turn_index"] >= MIN_TURNS_PER_SCENARIO
        is_last_scenario = state["chat_scenario_index"] == len(SCENARIOS) - 1

        # C 組：輸入框在「等待操作員回覆」期間要鎖住，避免參與者連續送出
        # 好幾句話疊在同一個 WoZ 回合裡。A/B 組沒有這個等待狀態，永遠可輸入。
        awaiting_operator = False
        if state["group"] == "C":
            woz = woz_session.load_session(state["participant_id"])
            awaiting_operator = bool(woz and woz["awaiting_operator"])

        status = (f"進行中：情境 {scenario['id']}／{scenario['title']}　"
                  f"（本情境已進行 {state['chat_turn_index']} 回合，"
                  + (f"滿 {MIN_TURNS_PER_SCENARIO} 回合後可切換）" if not reached_min else "已達最少回合數，可切換）"))
        if awaiting_operator:
            status += "\n\n⏳ 訊息已送出，對方正在輸入中，請稍候…"
        updates.append(gr.update(value=status))
        updates.append(gr.update() if chat_history is None else gr.update(value=chat_history))
        updates.append(gr.update(interactive=not awaiting_operator))
        show_next = (reached_min and not awaiting_operator
                     and not (is_last_scenario and state["chat_turn_index"] >= MAX_TURNS_PER_SCENARIO))
        updates.append(gr.update(visible=show_next, interactive=True, value="切換下一情境 ➜"))
    else:
        updates.append(gr.update())
        updates.append(gr.update())
        updates.append(gr.update(interactive=False))
        updates.append(gr.update(visible=False))

    # ---- 區塊顯示切換 ----
    phase = None if state is None else state["phase"]
    updates.append(gr.update(visible=phase in ("pretest", "posttest")))  # survey_col
    updates.append(gr.update(visible=phase == "chat"))                    # chat_col
    updates.append(gr.update(visible=phase == "done"))                    # done_col
    updates.append(gr.update(visible=state is None))                      # setup_row

    return updates


def on_start_experiment(pid_val):
    if not pid_val.strip():
        raise gr.Error("請先輸入參與者編號")
    pid = pid_val.strip()
    try:
        group_val = randomization.assign_group(pid)
    except RuntimeError as e:
        # 分派清單用完（超過規劃的 90 人）——不能悄悄退回手動分組，直接擋下來讓研究者處理。
        raise gr.Error(str(e))
    # 分派紀錄立刻備份（不等到參與者跑完全部流程）：這是所有資料裡最不能
    # 弄錯的一份——萬一免費方案的服務在這位參與者填答中途被重置，分派紀錄
    # 沒了的話，他重新整理頁面會被系統當成新的人，拿到跟原本不同的組別，
    # 會直接破壞隨機分派的正確性。backup.backup_files() 本身已經處理過
    # 「沒設定就跳過、連線失敗就記警告」，這裡不需要額外包 try/except。
    backup.backup_files([randomization.ASSIGNMENTS_PATH])
    state = new_experiment_state(pid, group_val)
    return [state] + render_all(state)


def _backup_participant_data(participant_id: str, group: str) -> None:
    """參與者完成全部流程時呼叫：把他的三份 CSV 加上目前的分派狀態檔一起
    備份到 Hugging Face Dataset（見 backup.py）。沒設定 HF_TOKEN／
    HF_BACKUP_DATASET_REPO 時 backup.is_configured() 會是 False，直接跳過。"""
    if not backup.is_configured():
        return
    paths = [
        get_log_path_for_display(participant_id, group),
        get_process_log_path_for_display(participant_id),
        get_answers_log_path_for_display(participant_id),
        randomization.ASSIGNMENTS_PATH,
    ]
    backup.backup_files(paths)


def on_survey_submit(state, *values):
    # 防呆鎖：如果這個 state 目前已經有一次送出正在處理中，這次呼叫視為
    # 重複觸發（例如連續點擊、網路延遲造成的重送），直接忽略、不做任何事，
    # 避免同一批答案被記錄兩次、或記錄到錯的問卷代號底下。
    # 這是搭配畫面上「送出後鎖住按鈕」的第二層防護，就算 UI 鎖定沒生效，
    # 這裡還是能擋住重複寫入。
    if state.get("_survey_submitting"):
        return [state] + render_all(state)
    state["_survey_submitting"] = True
    try:
        radio_vals = values[:MAX_ITEMS]
        textbox_vals = values[MAX_ITEMS:2 * MAX_ITEMS]
        survey: SurveySession = state["survey"]
        q = survey.current_questionnaire
        if q is None:
            return [state] + render_all(state)

        collected = []
        for i, item in enumerate(q.items):
            val = textbox_vals[i] if item.qtype == "open_text" else radio_vals[i]
            collected.append((item, val))

        empty_items = [item.text for item, val in collected if val is None or str(val).strip() == ""]
        if empty_items:
            msg = "⚠️ 以下題目尚未作答：" + "、".join(empty_items)
            # 把使用者已經填過的題目的值保留住，重新畫面時不要清空，
            # 只有真的沒填的題目才會維持空白（原本這裡沒有保留，導致整頁被清空）。
            preserve = {i: val for i, (item, val) in enumerate(collected) if val not in (None, "")}
            return [state] + render_all(state, survey_error=msg, preserve_survey_values=preserve)

        for item, val in collected:
            survey.record_answer(item.id, str(val))
        survey.advance()

        if survey.is_finished:
            if state["phase"] == "pretest":
                # 前測問卷全部跑完 → 進入對話階段
                state["phase"] = "chat"
                state["chat_scenario_index"] = 0
                state["chat_turn_index"] = 0
                scenario = SCENARIOS[0]
                opening = get_opening(scenario, state["group"])
                if state["group"] == "C":
                    # C 組：不建立 Gemini chat，改建立共用的 WoZ session，
                    # 讓操作員畫面之後能透過輪詢看到這位參與者。
                    woz_session.create_session(state["participant_id"], scenario["id"], scenario["title"])
                    state["woz_shown_count"] = 0
                else:
                    state["client"] = get_client()
                    state["chat"] = _create_scenario_chat(state["client"], state["group"], scenario)
                chat_history = [{"role": "assistant",
                                  "content": f"### 🎬 情境 1／{scenario['title']}\n{opening}"}]
                log_turn(state["participant_id"], state["group"], scenario["id"], scenario["title"],
                          0, "system", opening)
                # 前測剛結束就備份一次（不等到全部跑完）：免費主機的服務隨時可能
                # 因為閒置被重置，備份頻率愈高，單次真的遺失的資料量就愈小。
                _backup_participant_data(state["participant_id"], state["group"])
                return [state] + render_all(state, chat_history=chat_history)
            else:
                # 後測問卷全部跑完 → 完成
                state["phase"] = "done"
                _backup_participant_data(state["participant_id"], state["group"])
                return [state] + render_all(state)

        return [state] + render_all(state)
    finally:
        state["_survey_submitting"] = False


def on_send_message(user_message, state, chat_history):
    if state is None or state["phase"] != "chat":
        raise gr.Error("目前不在對話階段。")
    if not user_message.strip():
        # 這裡原本只回傳 3 個值，但畫面實際上需要對應到全部元件（73 個），
        # 數量對不起來，Gradio 就會整個壞掉——這是「送出空白內容後系統壞掉」的真正原因。
        # 修正為：不做任何事，但回傳的格式跟正常送出時完全一致。
        return ["", state] + render_all(state, chat_history=chat_history)

    # 防重疊鎖：跟問卷那邊同樣的道理。如果上一次的訊息還在處理中
    # （例如剛好卡在等待 API 回應），這次呼叫直接忽略，避免兩次呼叫
    # 交錯寫入 chat_turn_index、chat_history，造成狀態互相干擾。
    if state.get("_chat_processing"):
        return ["", state] + render_all(state, chat_history=chat_history)
    state["_chat_processing"] = True
    try:
        scenario = SCENARIOS[state["chat_scenario_index"]]

        if state["group"] == "C":
            # C 組：訊息寫入共用的 WoZ session，等操作員回覆後由 on_woz_poll()
            # 接手更新畫面——這裡不呼叫任何模型，回合數也還不 +1
            # （回合要等操作員實際回覆之後才算數，見 woz_session.append_operator_message）。
            try:
                woz = woz_session.append_participant_message(state["participant_id"], user_message)
            except RuntimeError as e:
                raise gr.Error(str(e))
            turn_no = woz["scenario_turn_index"] + 1
            chat_history = chat_history + [{"role": "user", "content": user_message}]
            log_turn(state["participant_id"], state["group"], scenario["id"], scenario["title"],
                      turn_no, "participant", user_message)
            state["woz_shown_count"] = len(woz["messages"])
            return ["", state] + render_all(state, chat_history=chat_history)

        state["chat_turn_index"] += 1

        chat_history = chat_history + [{"role": "user", "content": user_message}]
        log_turn(state["participant_id"], state["group"], scenario["id"], scenario["title"],
                  state["chat_turn_index"], "participant", user_message)

        ai_text, _ = _send_with_retry(state["chat"], user_message)

        chat_history = chat_history + [{"role": "assistant", "content": ai_text}]
        log_turn(state["participant_id"], state["group"], scenario["id"], scenario["title"],
                  state["chat_turn_index"], "ai", ai_text)

        return ["", state] + render_all(state, chat_history=chat_history)
    finally:
        state["_chat_processing"] = False


def _noop_render_outputs():
    """回傳跟 render_all() 輸出數量、順序完全一致，但每一個都是『維持原樣、
    什麼都不改』的 no-op 更新（gr.update() 不帶任何參數時，前端會保留該元件
    目前顯示的內容，不會被重置）。

    用在計時器（Timer）觸發、但這次事件其實跟目前畫面無關的情況——例如
    輪詢當下使用者根本不在對話階段。如果這時候還是呼叫 render_all()，
    它會依「目前 state」重新算出所有元件該長什麼樣子，包含把問卷欄位
    重設回『尚未填答』的狀態，這樣會把使用者正在填、還沒送出的表單內容
    整個清空——這正是之前發生過的真實 bug（計時器每隔幾秒觸發一次，
    悄悄把還在填的前測問卷清空重填）。"""
    return [gr.update()] * (MAX_ITEMS * 2 + 3 + 4 + 4)


def on_woz_poll(state, chat_history):
    """C 組專用：畫面上的計時器（gr.Timer）每隔幾秒呼叫一次，檢查操作員是否
    已經回覆，一旦有新回覆就補進聊天畫面、解除輸入鎖定。A/B 組、或目前不在
    對話階段時，這裡什麼都不做，回傳全部 no-op（見 _noop_render_outputs），
    讓 Timer 可以放心對所有 group、所有階段共用，不會不小心動到跟這次事件
    無關的畫面內容（例如使用者正在填的問卷）。

    這裡只負責更新畫面；operator 端的回覆在 on_operator_send() 送出的當下就
    已經寫進 CSV 了（見該函式），這裡不重複記錄，避免同一句操作員回覆被記
    兩次，也不會因為參與者剛好沒開著頁面輪詢，就漏記操作員已經送出的回覆。
    """
    if state is None or state["phase"] != "chat" or state["group"] != "C":
        return [state] + _noop_render_outputs()

    session = woz_session.load_session(state["participant_id"])
    if session is None or len(session["messages"]) <= state["woz_shown_count"]:
        return [state] + _noop_render_outputs()

    new_entries = session["messages"][state["woz_shown_count"]:]
    for entry in new_entries:
        if entry["who"] == "operator":
            chat_history = chat_history + [{"role": "assistant", "content": entry["text"]}]

    state["woz_shown_count"] = len(session["messages"])
    state["chat_turn_index"] = session["scenario_turn_index"]

    return [state] + render_all(state, chat_history=chat_history)


def on_next_scenario_or_posttest(state, chat_history):
    if state is None or state["phase"] != "chat":
        raise gr.Error("目前不在對話階段。")
    if state.get("_chat_processing"):
        # 上一則訊息還在處理中就按了切換，直接忽略這次點擊，
        # 等訊息處理完、畫面更新後，使用者可以再按一次。
        return [state] + render_all(state, chat_history=chat_history)
    if state["group"] == "C":
        woz = woz_session.load_session(state["participant_id"])
        if woz and woz["awaiting_operator"]:
            # 還有一則訊息在等操作員回覆時不能切換情境，否則這句回覆之後
            # 會寫進「下一個情境」的訊息清單，跟畫面上看到的情境對不起來。
            raise gr.Error("目前還有一則訊息在等待對方回覆，請稍候片刻再切換情境。")

    is_last_scenario = state["chat_scenario_index"] >= len(SCENARIOS) - 1
    reached_max = state["chat_turn_index"] >= MAX_TURNS_PER_SCENARIO

    if is_last_scenario:
        # 三個情境都跑完了 → 進入後測問卷
        state["phase"] = "posttest"
        state["survey"] = SurveySession(
            participant_id=state["participant_id"], group=state["group"],
            session="post", questionnaires=POSTTEST_QUESTIONNAIRES,
        )
        # 三情境對話跑完就備份一次，不等到後測問卷也填完——理由同前測結束時的備份。
        _backup_participant_data(state["participant_id"], state["group"])
        return [state] + render_all(state)

    state["chat_scenario_index"] += 1
    state["chat_turn_index"] = 0
    scenario = SCENARIOS[state["chat_scenario_index"]]
    opening = get_opening(scenario, state["group"])
    if state["group"] == "C":
        woz_session.advance_scenario(state["participant_id"], scenario["id"], scenario["title"])
    else:
        state["chat"] = _create_scenario_chat(state["client"], state["group"], scenario)

    chat_history = chat_history + [{"role": "assistant",
                                     "content": f"\n\n---\n\n### 🔄 情境切換：情境 {scenario['id']}／{scenario['title']}\n{opening}"}]
    log_turn(state["participant_id"], state["group"], scenario["id"], scenario["title"],
              0, "system", opening)

    return [state] + render_all(state, chat_history=chat_history)


def get_dialogue_log(state):
    if state is None:
        raise gr.Error("尚未開始任何對話。")
    path = get_log_path_for_display(state["participant_id"], state["group"])
    if not os.path.isfile(path):
        raise gr.Error("目前還沒有對話紀錄。")
    return path


def get_process_log(state):
    if state is None:
        raise gr.Error("尚未開始任何流程。")
    path = get_process_log_path_for_display(state["participant_id"])
    if not os.path.isfile(path):
        raise gr.Error("目前還沒有歷程紀錄。")
    return path


def get_answers_log(state):
    if state is None:
        raise gr.Error("尚未開始任何流程。")
    path = get_answers_log_path_for_display(state["participant_id"])
    if not os.path.isfile(path):
        raise gr.Error("目前還沒有作答紀錄。")
    return path


# ============================================================
# C 組操作員後台（半結構化 WoZ）
#
# 這裡的畫面只給研究者（或受訓操作員）自己使用，跟上面參與者看到的畫面
# 完全分開，靠密碼（環境變數 WOZ_OPERATOR_PASSWORD）保護，避免參與者不小心
# 點進「操作員」分頁看到不該看到的東西。密碼只是基本防護，實際部署時，
# 參與者連結跟操作員密碼都不應該對外公開。
# ============================================================

def on_operator_login(password_val):
    """回傳 (是否已登入, 登入區塊的顯示狀態, 後台區塊的顯示狀態, 訊息文字)。"""
    if OPERATOR_PASSWORD is None:
        return (False, gr.update(visible=True), gr.update(visible=False),
                "⚠️ 尚未設定操作員密碼（環境變數 WOZ_OPERATOR_PASSWORD），"
                "暫時無法登入操作員後台，請先設定後再重新啟動程式。")
    if password_val == OPERATOR_PASSWORD:
        return True, gr.update(visible=False), gr.update(visible=True), ""
    return False, gr.update(visible=True), gr.update(visible=False), "❌ 密碼錯誤，請再試一次。"


def _format_pending_markdown(pending: list) -> str:
    if not pending:
        return "目前沒有參與者在等待回覆。"
    lines = ["| 參與者編號 | 情境 | 最新訊息 | 等待開始時間（UTC）|", "|---|---|---|---|"]
    for p in pending:
        preview = p["latest_message"][:40] + ("…" if len(p["latest_message"]) > 40 else "")
        lines.append(f"| {p['participant_id']} | {p['scenario_title']} | {preview} | {p['waiting_since']} |")
    return "\n".join(lines)


def on_operator_refresh_pending():
    """畫面上的計時器定期呼叫，更新『待回覆清單』，讓操作員知道誰在等、
    等了多久，方便優先處理快超過 3 分鐘時限的人。"""
    return _format_pending_markdown(woz_session.list_pending_sessions())


def _format_transcript_markdown(session: dict) -> str:
    if not session or not session["messages"]:
        return "（目前還沒有對話內容）"
    lines = []
    for m in session["messages"]:
        speaker = {"participant": "參與者", "operator": "你（操作員）"}.get(m["who"], m["who"])
        lines.append(f"**{speaker}**：{m['text']}")
    return "\n\n".join(lines)


def on_operator_load(pid_val):
    """操作員輸入參與者編號、按下載入：顯示對話紀錄，並依該參與者目前所在
    的情境，把對應的預寫回覆庫（情境專屬 + 通用）組成選單。"""
    pid = (pid_val or "").strip()
    if not pid:
        raise gr.Error("請先輸入參與者編號")
    session = woz_session.load_session(pid)
    if session is None:
        raise gr.Error(f"找不到參與者 {pid} 的 WoZ session（可能還沒開始對話，或編號打錯了）")

    specific, universal = reply_bank.get_reply_bank(session["scenario_id"])
    choices = specific + ["—— 以下為通用回覆 ——"] + universal

    status = f"已載入 {pid}｜情境：{session['scenario_title']}"
    status += "｜⏳ 正在等待你回覆" if session["awaiting_operator"] else "｜目前沒有等待中的訊息"

    return pid, _format_transcript_markdown(session), gr.update(choices=choices, value=None), status, session["scenario_id"]


def on_operator_poll_loaded(selected_pid, loaded_scenario_id):
    """操作員畫面的計時器除了刷新待回覆清單，也順便刷新『目前已載入這位
    參與者』的對話紀錄，不用手動按「載入」才看得到參與者切換情境、或送出
    新訊息後的最新狀態。這是為了修正一個真實發生過的問題：參與者切換到
    下一個情境後，如果操作員沒有重新手動載入，回覆選單會停在舊情境，
    可能選到跟新情境語境不符的句子。

    只有在偵測到情境真的換了（session 的 scenario_id 跟上次載入時不一樣）
    才會重新整理回覆選單、並清空目前選取的值；情境沒變的話，選單維持
    原樣，避免操作員正在選的內容被每 3 秒就平白清掉一次。"""
    if not selected_pid:
        return gr.update(), gr.update(), loaded_scenario_id
    session = woz_session.load_session(selected_pid)
    if session is None:
        return gr.update(), gr.update(), loaded_scenario_id

    transcript_update = gr.update(value=_format_transcript_markdown(session))

    if session["scenario_id"] != loaded_scenario_id:
        specific, universal = reply_bank.get_reply_bank(session["scenario_id"])
        choices = specific + ["—— 以下為通用回覆 ——"] + universal
        return transcript_update, gr.update(choices=choices, value=None), session["scenario_id"]

    return transcript_update, gr.update(), loaded_scenario_id


def on_operator_send(pid, reply_text):
    """操作員選一句預寫回覆、按下送出：寫入共用 session（參與者畫面輪詢後
    會看到），同時立刻寫進 CSV（不依賴參與者端是否還開著頁面在輪詢）。"""
    if not pid:
        raise gr.Error("請先載入一位參與者")
    if not reply_text or reply_text == "—— 以下為通用回覆 ——":
        raise gr.Error("請先選一句要送出的回覆（分隔線本身不能送出）")
    try:
        session = woz_session.append_operator_message(pid, reply_text)
    except RuntimeError as e:
        raise gr.Error(str(e))

    last_msg = session["messages"][-1]
    log_turn(pid, "C", session["scenario_id"], session["scenario_title"],
              session["scenario_turn_index"], "operator", reply_text,
              reply_latency_seconds=last_msg.get("latency_seconds"))

    status = f"✅ 已送出給 {pid}（回覆花了 {last_msg.get('latency_seconds')} 秒）"
    specific, universal = reply_bank.get_reply_bank(session["scenario_id"])
    choices = specific + ["—— 以下為通用回覆 ——"] + universal

    return (_format_transcript_markdown(session), gr.update(choices=choices, value=None), status,
            _format_pending_markdown(woz_session.list_pending_sessions()))


with gr.Blocks(title="情緒表達 AI 互動平台（完整流程）") as demo:
    with gr.Tabs():
        with gr.Tab("參與者"):
            gr.Markdown("## 生成式 AI 情緒表達學習支架 — 完整流程原型")
            gr.Markdown(
                "流程：輸入參與者編號 → 系統自動依隨機分派清單指定組別 → "
                "基本資料／前測問卷 → 三情境角色扮演對話 → 後測問卷 → 完成。"
            )

            exp_state = gr.State(None)

            with gr.Row() as setup_row:
                pid_input = gr.Textbox(label="參與者編號", placeholder="例如 P001")
                start_btn = gr.Button("開始實驗", variant="primary")
                gr.Markdown(
                    "組別由系統依封存的隨機分派清單自動指定（區塊隨機化，區塊大小 3），"
                    "不再由畫面手動選擇。"
                )

            # ---- 問卷區（前測、後測共用） ----
            with gr.Column(visible=False) as survey_col:
                survey_progress_md = gr.Markdown(visible=False)
                survey_radio_slots, survey_textbox_slots = [], []
                for i in range(MAX_ITEMS):
                    r = gr.Radio(visible=False, label=f"slot_{i}")
                    t = gr.Textbox(visible=False, label=f"slot_{i}", lines=2)
                    survey_radio_slots.append(r)
                    survey_textbox_slots.append(t)
                survey_submit_btn = gr.Button("提交，前往下一份問卷", visible=False)
                survey_error_md = gr.Markdown(visible=False)

            # ---- 對話區 ----
            with gr.Column(visible=False) as chat_col:
                status_box = gr.Markdown()
                chatbot = gr.Chatbot(label="對話", height=420)
                with gr.Row():
                    msg_input = gr.Textbox(label="輸入訊息", placeholder="輸入後按 Enter 送出", interactive=False, scale=4)
                    send_btn = gr.Button("送出", scale=1)
                next_btn = gr.Button("切換下一情境 ➜", visible=False)

            # ---- 完成畫面 ----
            with gr.Column(visible=False) as done_col:
                gr.Markdown("## ✅ 全部流程已完成，感謝參與！")
                with gr.Row():
                    dl_dialogue_btn = gr.Button("下載對話紀錄（CSV）")
                    dl_process_btn = gr.Button("下載歷程時間戳記（CSV）")
                    dl_answers_btn = gr.Button("下載問卷作答紀錄（CSV）")
                download_file = gr.File(label="下載檔案")

            ALL_OUTPUTS = (
                survey_radio_slots + survey_textbox_slots
                + [survey_submit_btn, survey_progress_md, survey_error_md]
                + [status_box, chatbot, msg_input, next_btn]
                + [survey_col, chat_col, done_col, setup_row]
            )

            # ------------------------------------------------------------
            # 防連點機制：按下按鈕的當下先立刻鎖住（disabled），處理完再解鎖。
            #
            # 這是為了修正一個真實發生過的資料錯亂問題：使用者連續點兩次「提交」
            # （例如網路稍微延遲、畫面還沒更新就又點了一次），會導致同一份問卷的
            # 送出邏輯被觸發兩次，第二次觸發時系統已經切換到下一份問卷，卻仍拿著
            # 上一份問卷的題目內容去記錄，造成 CSV 裡「問卷代號」和「題目代號」對不起來。
            # 鎖住按鈕可以確保處理完成前，不會有第二次點擊被送進來。
            # ------------------------------------------------------------
            def _lock_button(msg="處理中，請稍候…"):
                return gr.update(interactive=False, value=msg)

            start_btn.click(on_start_experiment, inputs=[pid_input], outputs=[exp_state] + ALL_OUTPUTS)

            survey_submit_btn.click(
                lambda: _lock_button(), inputs=None, outputs=[survey_submit_btn],
            ).then(
                on_survey_submit,
                inputs=[exp_state] + survey_radio_slots + survey_textbox_slots,
                outputs=[exp_state] + ALL_OUTPUTS,
            )

            msg_input.submit(
                lambda: (gr.update(interactive=False), gr.update(interactive=False)),
                inputs=None, outputs=[msg_input, send_btn],
            ).then(
                on_send_message, inputs=[msg_input, exp_state, chatbot], outputs=[msg_input, exp_state] + ALL_OUTPUTS,
            ).then(
                lambda: gr.update(interactive=True), inputs=None, outputs=[send_btn],
            )
            send_btn.click(
                lambda: (gr.update(interactive=False), gr.update(interactive=False)),
                inputs=None, outputs=[msg_input, send_btn],
            ).then(
                on_send_message, inputs=[msg_input, exp_state, chatbot], outputs=[msg_input, exp_state] + ALL_OUTPUTS,
            ).then(
                lambda: gr.update(interactive=True), inputs=None, outputs=[send_btn],
            )

            next_btn.click(
                lambda: _lock_button("處理中，請稍候…"), inputs=None, outputs=[next_btn],
            ).then(
                on_next_scenario_or_posttest, inputs=[exp_state, chatbot], outputs=[exp_state] + ALL_OUTPUTS,
            )

            dl_dialogue_btn.click(get_dialogue_log, inputs=[exp_state], outputs=[download_file])
            dl_process_btn.click(get_process_log, inputs=[exp_state], outputs=[download_file])
            dl_answers_btn.click(get_answers_log, inputs=[exp_state], outputs=[download_file])

            # C 組專用輪詢：每隔幾秒檢查一次操作員是否已經回覆。A/B 組、或不在
            # 對話階段時，on_woz_poll() 內部會直接原樣返回，這裡不用另外判斷組別。
            woz_poll_timer = gr.Timer(WOZ_POLL_INTERVAL_SECONDS)
            woz_poll_timer.tick(
                on_woz_poll, inputs=[exp_state, chatbot], outputs=[exp_state] + ALL_OUTPUTS,
            )

        with gr.Tab("操作員（研究者專用）"):
            gr.Markdown(
                "## WoZ 操作員後台\n"
                "⚠️ 此頁僅供研究者本人（或受訓操作員）操作，**請勿把這個分頁的連結"
                "或密碼提供給參與者**。參與者應該只使用「參與者」分頁。"
            )

            operator_authed = gr.State(False)
            with gr.Row() as operator_login_row:
                operator_password_input = gr.Textbox(label="操作員密碼", type="password")
                operator_login_btn = gr.Button("登入")
            operator_login_status = gr.Markdown()

            with gr.Column(visible=False) as operator_dashboard:
                gr.Markdown("### 待回覆清單（依等待時間排序，等最久的排最上面）")
                pending_display = gr.Markdown("目前沒有參與者在等待回覆。")

                with gr.Row():
                    operator_pid_input = gr.Textbox(label="要回覆的參與者編號（從上面清單複製）")
                    operator_load_btn = gr.Button("載入這位參與者")
                operator_selected_pid = gr.State(None)
                operator_loaded_scenario_id = gr.State(None)
                operator_load_status = gr.Markdown()

                gr.Markdown("### 對話紀錄（唯讀）")
                operator_transcript = gr.Markdown("（尚未載入任何參與者）")

                gr.Markdown(
                    "### 選一句預寫回覆送出\n"
                    "請務必只從下面清單挑選，不要自己臨場編寫——標準化檢核會抽查 10% 對話。"
                )
                operator_reply_radio = gr.Radio(label="預寫回覆庫", choices=[])
                operator_send_btn = gr.Button("送出這句回覆", variant="primary")

            operator_login_btn.click(
                on_operator_login, inputs=[operator_password_input],
                outputs=[operator_authed, operator_login_row, operator_dashboard, operator_login_status],
            )
            operator_load_btn.click(
                on_operator_load, inputs=[operator_pid_input],
                outputs=[operator_selected_pid, operator_transcript, operator_reply_radio, operator_load_status,
                         operator_loaded_scenario_id],
            )
            operator_send_btn.click(
                on_operator_send, inputs=[operator_selected_pid, operator_reply_radio],
                outputs=[operator_transcript, operator_reply_radio, operator_load_status, pending_display],
            )

            # 待回覆清單定期自動更新，操作員不用一直手動重新整理才看得到新進來的訊息。
            operator_poll_timer = gr.Timer(WOZ_POLL_INTERVAL_SECONDS)
            operator_poll_timer.tick(on_operator_refresh_pending, inputs=None, outputs=[pending_display])
            operator_poll_timer.tick(
                on_operator_poll_loaded, inputs=[operator_selected_pid, operator_loaded_scenario_id],
                outputs=[operator_transcript, operator_reply_radio, operator_loaded_scenario_id],
            )


if __name__ == "__main__":
    # server_name="0.0.0.0" 讓外部連線進得來（不是只能在同一台機器上用瀏覽器連
    # localhost）；PORT 環境變數是 Render.com 等平台指定連接埠的標準做法，
    # 本機測試沒設定這個環境變數時，預設用 Gradio 原本的 7860。
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
