# test_randomization.py
#
# 測試 randomization.py 的區塊隨機化分派邏輯，純 Python、不需要開瀏覽器或金鑰。
# 涵蓋：
#   - 封存的清單本身是否符合「每 3 人一區塊、區塊內 A/B/C 各一」的設計
#   - 依序分派是否正確消耗清單位置
#   - 同一參與者編號重複呼叫是否回傳相同組別（不重複消耗位置）
#   - 清單用完之後是否會擋下超額分派，而不是悄悄分到別的組
#   - 用暫時的假清單測試，不動到專案正式封存的 randomization_list.json

import os
import shutil
import tempfile

import randomization as r


def run():
    # 用暫存目錄跑測試，完全不碰專案正式的 randomization_list.json /
    # data/participant_assignments.json，避免測試不小心消耗到正式清單。
    tmp_dir = tempfile.mkdtemp(prefix="randomization_test_")
    try:
        list_path = os.path.join(tmp_dir, "test_list.json")

        # 1. 產生清單：驗證每個區塊都是 A/B/C 各一（順序隨機）
        seq = r.generate_randomization_list(n=9, seed=1234)
        assert len(seq) == 9
        for i in range(0, 9, 3):
            block = seq[i:i + 3]
            assert sorted(block) == ["A", "B", "C"], f"第 {i} 個區塊不是 A/B/C 各一：{block}"
        print("[OK] 產生的清單每個區塊都是 A/B/C 各一（區塊隨機化正確）")

        # 2. 同樣的 seed 要能重現一模一樣的清單（可稽核）
        seq_again = r.generate_randomization_list(n=9, seed=1234)
        assert seq == seq_again, "相同 seed 應該產生完全相同的清單，才能稽核"
        print("[OK] 固定 seed 可重現同一份清單")

        # 3. 封存清單，並驗證不能重複封存到同一個路徑（避免收案中途誤換清單）
        r.save_randomization_list(seq, seed=1234, path=list_path)
        try:
            r.save_randomization_list(seq, seed=1234, path=list_path)
            raise AssertionError("清單已存在時，不應該允許再次封存覆蓋")
        except FileExistsError:
            pass
        print("[OK] 分派清單一旦封存，不能被重複覆寫")

        # 4. 依序分派：3 位參與者應該剛好拿到清單前 3 個位置，且三組各一
        # 暫時指向這份測試專用的 assignments 檔，不去動正式的 data/ 目錄
        real_assignments_path = r.ASSIGNMENTS_PATH
        r.ASSIGNMENTS_PATH = os.path.join(tmp_dir, "test_assignments.json")
        try:
            g1 = r.assign_group("T001", list_path=list_path)
            g2 = r.assign_group("T002", list_path=list_path)
            g3 = r.assign_group("T003", list_path=list_path)
            assert [g1, g2, g3] == seq[0:3], "分派結果應該完全照清單順序，不能跳號或亂序"
            assert sorted([g1, g2, g3]) == ["A", "B", "C"]
            print("[OK] 依清單順序分派，前 3 位參與者剛好三組各一")

            # 5. 同一參與者重複呼叫（模擬重新整理頁面）要回傳相同組別，不消耗新位置
            g1_again = r.assign_group("T001", list_path=list_path)
            assert g1_again == g1, "同一參與者重複分派應該回傳原本的組別"
            summary = r.assignment_summary(list_path=list_path)
            assert summary["assigned_count"] == 3, "重複呼叫不應該多消耗清單位置"
            print("[OK] 同一參與者重複觸發不會被分到不同組、也不會多消耗清單位置")

            # 6. 清單用完（第 4~9 位補滿，第 10 位應該被擋下來）
            for i in range(4, 10):
                r.assign_group(f"T{i:03d}", list_path=list_path)
            summary = r.assignment_summary(list_path=list_path)
            assert summary["assigned_count"] == 9
            assert summary["counts_by_group"] == {"A": 3, "B": 3, "C": 3}, (
                f"9 人跑完後三組人數應該剛好都是 3，實際是 {summary['counts_by_group']}"
            )
            try:
                r.assign_group("T999", list_path=list_path)
                raise AssertionError("清單已用完時，不應該還能分派成功")
            except RuntimeError:
                pass
            print("[OK] 清單用完後第 10 位參與者會被正確擋下，不會悄悄分到別的組")
        finally:
            r.ASSIGNMENTS_PATH = real_assignments_path

        print("\n全部隨機分派測試通過 ✅")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    run()
