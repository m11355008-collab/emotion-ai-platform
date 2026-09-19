# test_survey.py
#
# 測試 survey.py 的核心邏輯，完全不需要開瀏覽器、不需要 API 金鑰。
# 用一組簡單的假問卷（不是正式的 EES/IRI），純粹驗證「流程規則」對不對：
#   - 問卷要照順序跑
#   - 沒填完不能跳到下一份
#   - 每份問卷開始/結束時間有沒有正確記錄
#   - 每一題的作答有沒有正確記錄

import os
import shutil

from questionnaires import Questionnaire, QuestionnaireItem
from survey import SurveySession
import logger


def make_fake_questionnaires():
    q1 = Questionnaire(
        id="FAKE1", name="假問卷一", administer_at=["pre"],
        items=[
            QuestionnaireItem(id="F1_01", text="題目1"),
            QuestionnaireItem(id="F1_02", text="題目2"),
        ],
    )
    q2 = Questionnaire(
        id="FAKE2", name="假問卷二", administer_at=["pre"],
        items=[QuestionnaireItem(id="F2_01", text="題目1", qtype="open_text")],
    )
    return [q1, q2]


def run():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if os.path.isdir(data_dir):
        shutil.rmtree(data_dir)

    questionnaires = make_fake_questionnaires()
    session = SurveySession(
        participant_id="TEST01", group="A", session="pre", questionnaires=questionnaires
    )

    # 1. 一開始應該在第一份問卷，還沒結束
    assert session.current_questionnaire.id == "FAKE1"
    assert not session.is_finished
    print("[OK] 初始狀態：停在第一份問卷")

    # 2. 沒填完不能 advance
    session.start_current()
    session.record_answer("F1_01", "3")  # 只填第一題，還有 F1_02 沒填
    try:
        session.advance()
        raise AssertionError("應該要因為題目沒填完而失敗，但沒有")
    except RuntimeError as e:
        assert "F1_02" in str(e)
        print("[OK] 題目沒填完時，advance() 正確擋下來了")

    # 3. 填完全部題目後才能 advance
    session.record_answer("F1_02", "4")
    session.advance()
    assert session.current_questionnaire.id == "FAKE2"
    print("[OK] 填完所有題目後，正確前進到下一份問卷")

    # 4. 跑完最後一份問卷
    session.start_current()
    session.record_answer("F2_01", "這是開放式作答的內容")
    session.advance()
    assert session.is_finished
    assert session.current_questionnaire is None
    print("[OK] 跑完所有問卷後，is_finished 正確回傳 True")

    # 5. 檢查歷程記錄檔（process log）：應該有 FAKE1 的 start/end、FAKE2 的 start/end，共 4 筆
    process_path = logger.get_process_log_path_for_display("TEST01")
    assert os.path.isfile(process_path), "應該要產生歷程記錄檔"
    with open(process_path, encoding="utf-8-sig") as f:
        rows = f.readlines()
    assert len(rows) == 1 + 4, f"歷程記錄應該有表頭+4筆，實際有 {len(rows)} 行"
    assert "pretest_FAKE1,start" in rows[1]
    assert "pretest_FAKE1,end" in rows[2]
    assert "pretest_FAKE2,start" in rows[3]
    assert "pretest_FAKE2,end" in rows[4]
    print(f"[OK] 歷程記錄檔正確：{process_path}（4 筆 start/end 記錄，順序正確）")

    # 6. 檢查作答記錄檔（answers log）：應該有 3 筆作答（F1_01, F1_02, F2_01）
    answers_path = logger.get_answers_log_path_for_display("TEST01")
    assert os.path.isfile(answers_path), "應該要產生作答記錄檔"
    with open(answers_path, encoding="utf-8-sig") as f:
        rows = f.readlines()
    assert len(rows) == 1 + 3, f"作答記錄應該有表頭+3筆，實際有 {len(rows)} 行"
    print(f"[OK] 作答記錄檔正確：{answers_path}（3 筆作答記錄）")

    print("\n全部測試通過 ✅")


if __name__ == "__main__":
    run()
