# test_woz_session.py
#
# 測試 woz_session.py（C 組共用會話狀態）與 reply_bank.py，純 Python、
# 不需要開瀏覽器。涵蓋：
#   - 建立 session、參與者送訊息、操作員回覆的基本流程
#   - awaiting_operator 狀態正確切換，且會擋下「不照順序」的操作
#     （參與者連續送兩句、操作員在沒有新訊息時亂回）
#   - latency_seconds 有正確算出來
#   - 切換情境會重置回合數、但保留完整訊息歷程
#   - list_pending_sessions 依等待時間排序
#   - reply_bank 每個情境都有回覆、且情境 id 不對會報錯

import os
import shutil
import time

import woz_session as w
import reply_bank
from scenarios import SCENARIOS


def run():
    # 讓這次測試完全使用獨立的 data 目錄，不去動專案正式的 data/。
    test_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_test_woz")
    if os.path.isdir(test_data_dir):
        shutil.rmtree(test_data_dir)
    w.DATA_DIR = test_data_dir
    w.SESSIONS_DIR = os.path.join(test_data_dir, "woz_sessions")

    try:
        # 1. 建立 session、參與者送訊息
        s = w.create_session("T001", scenario_id=1, scenario_title="與朋友發生衝突")
        assert s["awaiting_operator"] is False
        assert s["scenario_turn_index"] == 0

        s = w.append_participant_message("T001", "我今天跟朋友吵架了")
        assert s["awaiting_operator"] is True
        assert len(s["messages"]) == 1
        print("[OK] 建立 session、參與者送出第一句訊息，awaiting_operator 正確變成 True")

        # 2. 參與者在還沒收到回覆前不能再送訊息
        try:
            w.append_participant_message("T001", "還有後續")
            raise AssertionError("上一句還沒回覆時，不應該能再送新訊息")
        except RuntimeError:
            pass
        print("[OK] 上一則訊息還沒被回覆時，擋下參與者連續送出新訊息")

        # 3. 操作員回覆，latency_seconds 有正確算出來，且回合數 +1
        time.sleep(1.1)
        s = w.append_operator_message("T001", "聽起來真的滿難受的，跟好朋友吵架這種事很不好受。")
        assert s["awaiting_operator"] is False
        assert s["scenario_turn_index"] == 1
        latency = s["messages"][-1]["latency_seconds"]
        assert latency is not None and latency >= 1.0, f"latency_seconds 應該 >= 1.0，實際：{latency}"
        print(f"[OK] 操作員回覆後 awaiting_operator 變回 False，回合數 +1，latency_seconds={latency} 正確算出")

        # 4. 沒有等待中的訊息時，操作員不能亂回
        try:
            w.append_operator_message("T001", "亂回一句")
            raise AssertionError("沒有等待中的訊息時，不應該能送出操作員回覆")
        except RuntimeError:
            pass
        print("[OK] 沒有等待回覆中的訊息時，擋下操作員多送訊息")

        # 5. 切換情境：回合數歸零，但訊息歷程還在
        s = w.advance_scenario("T001", scenario_id=2, scenario_title="考試失利的情緒表達")
        assert s["scenario_turn_index"] == 0
        assert s["scenario_id"] == 2
        assert len(s["messages"]) == 2, "切換情境不應該清空過去的訊息歷程"
        print("[OK] 切換情境後回合數歸零、情境資訊更新，但過去訊息歷程完整保留")

        # 6. list_pending_sessions：建立第二位參與者，驗證等待時間排序
        w.create_session("T002", scenario_id=1, scenario_title="與朋友發生衝突")
        w.append_participant_message("T002", "我今天考試考差了")  # T002 現在在等回覆

        pending = w.list_pending_sessions()
        pending_ids = [p["participant_id"] for p in pending]
        assert pending_ids == ["T002"], f"應該只有 T002 在等待中，實際：{pending_ids}"
        print("[OK] list_pending_sessions 正確只列出目前在等待操作員回覆的參與者")

        # T001 也送一句進入等待，確認兩人都出現、且排序是「等最久的在前面」
        s = w.append_participant_message("T001", "後來有比較好一點")
        pending = w.list_pending_sessions()
        pending_ids = [p["participant_id"] for p in pending]
        assert pending_ids == ["T002", "T001"], f"應該依等待時間排序（T002 先等）：{pending_ids}"
        print("[OK] 兩位參與者同時等待時，list_pending_sessions 依等待時間先後正確排序")

        # 7. reply_bank：每個情境都要有回覆可選，情境 id 不存在要報錯
        for scenario in SCENARIOS:
            specific, universal = reply_bank.get_reply_bank(scenario["id"])
            assert len(specific) >= 5, f"情境 {scenario['id']} 的專屬回覆數量太少：{len(specific)}"
            assert len(universal) >= 5
        print("[OK] 三個情境都各自有足夠的預寫回覆，通用回覆庫也有內容")

        try:
            reply_bank.get_reply_bank(999)
            raise AssertionError("不存在的情境 id 應該要報錯")
        except ValueError:
            pass
        print("[OK] 不存在的情境 id 會正確報錯，不會悄悄回傳空清單")

        print("\n全部 WoZ session／回覆庫測試通過 ✅")
    finally:
        shutil.rmtree(test_data_dir, ignore_errors=True)


if __name__ == "__main__":
    run()
