# test_woz_flow.py
#
# C 組端對端測試：參與者送訊息 → 操作員回覆 → 參與者輪詢收到 → 跑完三情境
# → 後測 → 完成，並檢查 CSV 內容正確（含 reply_latency_seconds）。
# 沿用 test_merged.py 的假 Gemini client（C 組流程用不到，但 app.py import 時需要）。

import os
import shutil

os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-testing")
os.environ.setdefault("WOZ_OPERATOR_PASSWORD", "test-password")

import google.genai as genai


class FakeClient:
    def __init__(self, api_key=None):
        pass


genai.Client = FakeClient

import app  # noqa: E402
from scenarios import SCENARIOS, MIN_TURNS_PER_SCENARIO  # noqa: E402


def fill_and_submit_current_questionnaire(state):
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
    return result[0]


def run():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if os.path.isdir(data_dir):
        shutil.rmtree(data_dir)

    # 分派清單重置後的第一位參與者一定拿到 C（見 randomization_list.json 開頭 = C,A,B,...）
    result = app.on_start_experiment("TWOZ001")
    state = result[0]
    assert state["group"] == "C", f"預期第一位參與者是 C 組，實際：{state['group']}"
    print("[OK] 第一位參與者確實被分到 C 組")

    # 跑完前測，進入對話階段
    while state["phase"] == "pretest":
        state = fill_and_submit_current_questionnaire(state)
    assert state["phase"] == "chat"
    print("[OK] 前測跑完，正確進入對話階段（C 組）")

    pid = state["participant_id"]
    chat_history = [{"role": "assistant", "content": "（情境開場，內容略）"}]

    for scenario_idx, scenario in enumerate(SCENARIOS):
        for round_no in range(MIN_TURNS_PER_SCENARIO):
            # 1. 參與者送訊息
            send_result = app.on_send_message(f"參與者訊息 第{round_no+1}輪", state, chat_history)
            state = send_result[1]
            chat_history = send_result[2 + 64]["value"]
            msg_input_update = send_result[2 + 65]
            assert msg_input_update.get("interactive") is False, "送出訊息後輸入框應該被鎖住，等操作員回覆"

            # 2. 操作員載入這位參與者、挑一句回覆送出
            load_result = app.on_operator_load(pid)
            loaded_pid, transcript_md, reply_choices_update, load_status = load_result
            assert loaded_pid == pid
            choices = reply_choices_update["choices"]
            first_reply = choices[0]  # 一定是情境專屬回覆（見 reply_bank 順序），不是分隔線
            send_op_result = app.on_operator_send(pid, first_reply)
            op_transcript, op_choices_update, op_status, pending_md = send_op_result
            assert "已送出" in op_status

            # 3. 參與者輪詢，收到操作員回覆
            poll_result = app.on_woz_poll(state, chat_history)
            state = poll_result[0]
            chat_history = poll_result[1 + 64]["value"]
            assert state["chat_turn_index"] == round_no + 1, (
                f"第 {round_no+1} 輪輪詢後 chat_turn_index 應該是 {round_no+1}，實際 {state['chat_turn_index']}"
            )
        print(f"[OK] 情境 {scenario['id']}／{scenario['title']} 跑完 {MIN_TURNS_PER_SCENARIO} 回合，"
              f"每輪都正確經過「參與者送出 → 操作員回覆 → 參與者輪詢收到」")

        # next_btn 應該可見了（reached_min）
        render = app.render_all(state, chat_history=chat_history)
        next_btn_update = render[66]
        assert next_btn_update.get("visible") is True, "跑完最少回合數後，next_btn 應該顯示"

        next_result = app.on_next_scenario_or_posttest(state, chat_history)
        state = next_result[0]
        if scenario_idx < len(SCENARIOS) - 1:
            chat_history = next_result[1 + 64]["value"]
            assert state["phase"] == "chat"
            assert state["chat_scenario_index"] == scenario_idx + 1
        else:
            assert state["phase"] == "posttest", "三個情境都跑完後應該進入後測"
    print("[OK] 三個情境全部跑完，正確進入後測問卷階段")

    while state["phase"] == "posttest":
        state = fill_and_submit_current_questionnaire(state)
    assert state["phase"] == "done"
    print("[OK] 後測跑完，正確進入完成階段")

    # 檢查 CSV：對話紀錄裡應該有 speaker="operator" 的列，且都有 reply_latency_seconds
    dialogue_path = app.get_log_path_for_display(pid, "C")
    assert os.path.isfile(dialogue_path)
    import csv
    with open(dialogue_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    operator_rows = [r for r in rows if r["speaker"] == "operator"]
    participant_rows = [r for r in rows if r["speaker"] == "participant"]
    expected_rounds = len(SCENARIOS) * MIN_TURNS_PER_SCENARIO
    assert len(operator_rows) == expected_rounds, (
        f"operator 列數應該是 {expected_rounds}（3 情境 × {MIN_TURNS_PER_SCENARIO} 回合），實際 {len(operator_rows)}"
    )
    assert len(participant_rows) == expected_rounds
    for r in operator_rows:
        assert r["reply_latency_seconds"] not in (None, ""), "每一列 operator 回覆都應該有 reply_latency_seconds"
        assert float(r["reply_latency_seconds"]) >= 0
    print(f"[OK] 對話紀錄正確產生：{len(operator_rows)} 則操作員回覆，全部都有 reply_latency_seconds")

    print("\n全部 C 組端對端測試通過 ✅")


if __name__ == "__main__":
    run()
