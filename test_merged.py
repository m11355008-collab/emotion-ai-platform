# test_merged.py
#
# 測試合併後的完整流程（前測 → 對話 → 後測 → 完成），全部用純 Python
# 直接呼叫 app.py 裡的函式，不開瀏覽器、不開 Gradio 伺服器。
# AI 的部分一樣用假的 client 取代，不需要金鑰。

import os
import shutil

os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-testing")

import google.genai as genai


class FakeChatResponse:
    def __init__(self, text):
        self.text = text


class FakeChat:
    def __init__(self):
        self.n = 0

    def send_message(self, message):
        self.n += 1
        return FakeChatResponse(f"（假AI第{self.n}次回覆）")


class FakeChats:
    def create(self, model, config):
        return FakeChat()


class FakeClient:
    def __init__(self, api_key=None):
        self.chats = FakeChats()


genai.Client = FakeClient

import app  # noqa: E402


def count_expected_outputs():
    return len(app.MAX_ITEMS * ["x"]) * 2 + 3 + 4 + 4


def fill_and_submit_current_questionnaire(state):
    """模擬把目前這份問卷全部填完並送出，回傳送出後的 state。"""
    survey = state["survey"]
    q = survey.current_questionnaire
    radio_vals = [None] * app.MAX_ITEMS
    textbox_vals = [None] * app.MAX_ITEMS
    for i, item in enumerate(q.items):
        if item.qtype == "open_text":
            textbox_vals[i] = "測試作答內容"
        elif item.qtype == "single_choice":
            radio_vals[i] = item.choices[0]
        else:
            radio_vals[i] = str(item.scale_min)
    result = app.on_survey_submit(state, *radio_vals, *textbox_vals)
    return result[0]  # 新的 state


def run():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if os.path.isdir(data_dir):
        shutil.rmtree(data_dir)

    expected_len = count_expected_outputs()

    # 0. 回歸測試：問卷漏填題目時，已填的內容要保留（先前的 bug：整頁被清空）
    result = app.on_start_experiment("P001A")
    state0 = result[0]
    q0 = state0["survey"].current_questionnaire
    radio_vals = [None] * app.MAX_ITEMS
    textbox_vals = [None] * app.MAX_ITEMS
    # 故意只填第一題，其餘留空
    first_item = q0.items[0]
    filled_value = "已填的答案" if first_item.qtype == "open_text" else str(first_item.scale_min)
    if first_item.qtype == "open_text":
        textbox_vals[0] = filled_value
    else:
        radio_vals[0] = filled_value
    result = app.on_survey_submit(state0, *radio_vals, *textbox_vals)
    state0_after = result[0]
    assert state0_after["survey"].q_index == 0, "題目沒填完，不應該前進到下一份問卷"
    # 檢查回傳的 update 裡，第一題的值有沒有被保留住
    slot_updates = result[1:1 + app.MAX_ITEMS * 2]
    first_slot_update = slot_updates[0] if first_item.qtype != "open_text" else slot_updates[app.MAX_ITEMS]
    kept_value = first_slot_update.get("value") if isinstance(first_slot_update, dict) else None
    assert kept_value == filled_value, f"漏填其他題目時，第一題已填的值應該被保留，但變成了 {kept_value!r}"
    print("[OK] 回歸測試：問卷漏填題目時，已填過的題目內容有被正確保留（不會整頁清空）")

    # 0c. 回歸測試：模擬「重複送出」（例如連續點擊、網路延遲重送）
    #     不應該讓答案被記錄到錯誤的問卷代號底下，也不應該讓 q_index 被多推進。
    #     這是這次測試中發現的真實 bug：CSV 裡出現「問卷代號:COVARIATES、
    #     題目代號:DEMO_01」這種對不起來的錯誤記錄。
    result = app.on_start_experiment("P001C")
    stateC = result[0]
    qC = stateC["survey"].current_questionnaire
    radio_vals = [None] * app.MAX_ITEMS
    textbox_vals = [None] * app.MAX_ITEMS
    for i, item in enumerate(qC.items):
        if item.qtype == "open_text":
            textbox_vals[i] = "測試值"
        elif item.qtype == "single_choice":
            radio_vals[i] = item.choices[0]
        else:
            radio_vals[i] = str(item.scale_min)
    # 模擬第一次送出「正在處理中」尚未結束時，第二次重複送出馬上又進來
    stateC["_survey_submitting"] = True
    dup_result = app.on_survey_submit(stateC, *radio_vals, *textbox_vals)
    assert dup_result[0]["survey"].q_index == 0, "鎖定期間收到的重複送出，不應該讓問卷往前推進"
    stateC["_survey_submitting"] = False  # 還原，模擬第一次真正的送出現在才處理
    real_result = app.on_survey_submit(stateC, *radio_vals, *textbox_vals)
    assert real_result[0]["survey"].q_index == 1, "鎖定解除後，正常送出應該要能正確前進到下一份問卷"
    print("[OK] 回歸測試：防連點鎖正確擋下重複送出，不會造成問卷代號與題目代號錯位")

    # 0b. 回歸測試：對話階段送出空白訊息不應該讓整個系統壞掉
    result = app.on_start_experiment("P001B")
    stateB = result[0]
    for _ in range(app.PRETEST_QUESTIONNAIRES.__len__()):
        stateB = fill_and_submit_current_questionnaire(stateB)
    assert stateB["phase"] == "chat"
    blank_result = app.on_send_message("", stateB, [{"role": "assistant", "content": "情境開場"}])
    assert len(blank_result) - 2 == expected_len, (
        f"送出空白訊息時，輸出數量應該跟正常送出一致（{expected_len}），"
        f"實際是 {len(blank_result) - 2}——數量對不起來就是先前系統壞掉的原因"
    )
    print("[OK] 回歸測試：對話階段送出空白訊息，輸出數量正確，不會讓系統壞掉")

    # 1. 開始實驗，檢查初始狀態與 render_all 輸出長度
    result = app.on_start_experiment("P001")
    state = result[0]
    assert state["phase"] == "pretest"
    assert len(result) - 1 == expected_len, f"on_start_experiment 輸出數量不對：{len(result)-1} vs {expected_len}"
    print(f"[OK] on_start_experiment：phase=pretest，輸出數量正確（{expected_len}）")

    # 2. 跑完所有前測問卷
    n_pretest = len(app.PRETEST_QUESTIONNAIRES)
    for _ in range(n_pretest):
        state = fill_and_submit_current_questionnaire(state)
    assert state["phase"] == "chat", f"前測跑完後應該進入 chat 階段，實際是 {state['phase']}"
    assert state["chat_scenario_index"] == 0
    print(f"[OK] 跑完全部 {n_pretest} 份前測問卷後，正確進入對話階段")

    # 3. 跑對話：三個情境，每個情境跑到最少回合數再切換
    chat_history = [{"role": "assistant", "content": "情境開場"}]
    for scenario_i in range(len(app.SCENARIOS)):
        for _ in range(app.MIN_TURNS_PER_SCENARIO):
            msg_clear, state, *_ = app.on_send_message("測試訊息", state, chat_history)
            chat_history = _[1] if False else chat_history  # chatbot history update 在 render_all 裡，這裡簡化不追蹤顯示內容
        # 直接用 render_all 確認可以切換了
        updates = app.render_all(state, chat_history=chat_history)
        # next_btn 是 chat 區塊第 4 個（status, chatbot, msg_input, next_btn）之中最後一個
        # 用 on_next_scenario_or_posttest 直接觸發切換
        result = app.on_next_scenario_or_posttest(state, chat_history)
        state = result[0]

    assert state["phase"] == "posttest", f"三情境跑完後應該進入 posttest，實際是 {state['phase']}"
    print(f"[OK] 三個情境都跑完最少回合數後，正確進入後測問卷階段")

    # 4. 跑完所有後測問卷
    n_posttest = len(app.POSTTEST_QUESTIONNAIRES)
    for _ in range(n_posttest):
        state = fill_and_submit_current_questionnaire(state)
    assert state["phase"] == "done", f"後測跑完後應該進入 done，實際是 {state['phase']}"
    print(f"[OK] 跑完全部 {n_posttest} 份後測問卷後，正確進入完成階段")

    # 5. 檢查三種紀錄檔都有正確產生
    # 組別現在是系統自動分派的（不再是測試裡手動指定的 "A"），
    # 所以對話紀錄檔名要用這個參與者實際拿到的組別，而不是寫死 "A"。
    dialogue_path = app.get_log_path_for_display("P001", state["group"])
    process_path = app.get_process_log_path_for_display("P001")
    answers_path = app.get_answers_log_path_for_display("P001")
    for label, path in [("對話紀錄", dialogue_path), ("歷程紀錄", process_path), ("作答紀錄", answers_path)]:
        assert os.path.isfile(path), f"{label} 檔案沒有產生：{path}"
        with open(path, encoding="utf-8-sig") as f:
            n_lines = len(f.readlines())
        print(f"[OK] {label}正確產生：{path}（{n_lines} 行，含表頭）")

    print("\n全部測試通過 ✅")


if __name__ == "__main__":
    run()
