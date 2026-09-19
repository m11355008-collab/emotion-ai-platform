# -*- coding: utf-8 -*-
"""
參與者隨機分派邏輯（區塊隨機化，block randomization）。

設計依據（與研究者討論確定）：
  - 分派清單必須在招募開始「之前」就用真正的隨機過程產生一次、封存下來，
    之後嚴格照清單順序分派，過程中不得因任何理由調整順序（allocation
    concealment）。清單一旦產生並存檔，就是這份研究正式的分派清單。
  - 採區塊隨機化，區塊大小 = 3（每 3 位參與者之中，必定 A/B/C 各一位，
    但區塊內的排列順序是隨機的）。這樣不管研究者哪天收了幾個人、收案被
    打斷幾次，任一時間點累積的三組人數都不會差超過 2 人，適合本研究
    「分好幾天收案、每天人數不多」的執行方式。
  - 每位參與者「編號」只消耗清單上的下一個位置一次：同一個參與者編號
    重複觸發「開始實驗」（例如重新整理頁面）不會被分到不同組，而是回傳
    他第一次拿到的組別。

檔案：
  - randomization_list.json：封存的 1~N 號分派清單（只產生一次，之後只讀
    不寫，除非要重新設計一批新的研究才重新產生）。
  - data/participant_assignments.json：記錄「哪個參與者編號 → 拿到清單第
    幾號 → 被分到哪一組」，用於避免重複消耗清單位置，也留下分派歷程可稽核。
"""

import json
import os
import random
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RANDOMIZATION_LIST_PATH = os.path.join(BASE_DIR, "randomization_list.json")
ASSIGNMENTS_PATH = os.path.join(DATA_DIR, "participant_assignments.json")

GROUPS = ["A", "B", "C"]
BLOCK_SIZE = 3  # 每區塊人數 = 組別數，確保每區塊三組各一

# 同一個 process 內的分派要串行化，避免兩個參與者「同時」點開始實驗時
# 搶到同一個清單位置（race condition）。這是進程內鎖；若未來改成多 worker
# 部署，需改用檔案鎖或資料庫交易，屆時再擴充。
_assign_lock = threading.Lock()


def generate_randomization_list(n=90, seed=None):
    """
    產生一份區塊隨機化清單，長度 n（須為 BLOCK_SIZE 的倍數）。
    每個區塊固定包含 GROUPS 中每個組別各一次，但區塊內順序隨機排列。

    seed 固定的話，重新執行會得到一模一樣的清單（可重現、可稽核）；
    正式產生封存清單時應該指定一個 seed 並把 seed 一併記錄下來。
    """
    if n % BLOCK_SIZE != 0:
        raise ValueError(f"n（{n}）必須是區塊大小（{BLOCK_SIZE}）的倍數")

    rng = random.Random(seed)
    n_blocks = n // BLOCK_SIZE
    sequence = []
    for _ in range(n_blocks):
        block = GROUPS.copy()
        rng.shuffle(block)
        sequence.extend(block)
    return sequence


def save_randomization_list(sequence, seed, path=RANDOMIZATION_LIST_PATH):
    """封存分派清單。一旦封存，招募期間不應再覆寫這個檔案。"""
    if os.path.exists(path):
        raise FileExistsError(
            f"{path} 已存在——分派清單只能封存一次，若要重新產生，"
            "請先手動確認並備份/刪除舊檔，避免正式收案中途換清單。"
        )
    payload = {
        "n": len(sequence),
        "block_size": BLOCK_SIZE,
        "groups": GROUPS,
        "seed": seed,
        "sequence": sequence,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load_randomization_list(path=RANDOMIZATION_LIST_PATH):
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"找不到封存的分派清單 {path}。正式收案前，"
            "須先呼叫 generate_randomization_list() + save_randomization_list() 產生並封存一次。"
        )
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["sequence"]


def _load_assignments():
    if not os.path.isfile(ASSIGNMENTS_PATH):
        return {}
    with open(ASSIGNMENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_assignments(assignments):
    # 先確保目錄存在——data/ 有可能在程式啟動後才被清空或重建（例如測試
    # 每次執行前會整個刪掉 data/ 目錄），單靠模組載入時的 os.makedirs 不夠。
    os.makedirs(DATA_DIR, exist_ok=True)
    # 再寫暫存檔後 replace，避免寫到一半就被中斷（例如伺服器重啟）造成檔案損毀。
    tmp_path = ASSIGNMENTS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(assignments, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, ASSIGNMENTS_PATH)


def assign_group(participant_id: str, list_path=RANDOMIZATION_LIST_PATH) -> str:
    """
    依封存的分派清單，取得這位參與者的組別。

    - 若這個參與者編號先前已經分派過（重複呼叫、重新整理頁面等），
      直接回傳原本的組別，不消耗清單上的下一個位置。
    - 否則，取清單上「尚未被任何人拿走」的下一個位置分給他，並記錄下來。
    - 清單用完（超過 n 人）會丟出例外，避免超收後悄悄分派到不存在的位置。
    """
    with _assign_lock:
        assignments = _load_assignments()

        if participant_id in assignments:
            return assignments[participant_id]["group"]

        sequence = load_randomization_list(list_path)
        used_indices = {rec["index"] for rec in assignments.values()}
        next_index = len(used_indices)  # 位置是依序消耗的，下一個沒被用過的位置

        if next_index >= len(sequence):
            raise RuntimeError(
                f"分派清單（共 {len(sequence)} 個位置）已全部用完，"
                "此參與者無法再分派。若樣本數需要超過原規劃，"
                "須先決定是否擴增清單，而非直接分派到清單外的組別。"
            )

        group = sequence[next_index]
        assignments[participant_id] = {"index": next_index, "group": group}
        _save_assignments(assignments)
        return group


def assignment_summary(list_path=RANDOMIZATION_LIST_PATH):
    """回傳目前已分派人數統計，方便研究者隨時檢查各組人數是否如預期平衡。"""
    assignments = _load_assignments()
    counts = {g: 0 for g in GROUPS}
    for rec in assignments.values():
        counts[rec["group"]] = counts.get(rec["group"], 0) + 1
    total_slots = len(load_randomization_list(list_path)) if os.path.isfile(list_path) else None
    return {
        "assigned_count": len(assignments),
        "counts_by_group": counts,
        "total_slots": total_slots,
    }


if __name__ == "__main__":
    # 手動執行這個檔案 = 正式封存一份新的分派清單（僅在專案初始化時做一次）。
    SEED = 20260918  # 固定 seed：對應本研究正式定案分派清單的產生日期，供稽核追溯
    seq = generate_randomization_list(n=90, seed=SEED)
    path = save_randomization_list(seq, seed=SEED)
    print(f"已封存分派清單：{path}")
    print(f"前 9 個位置（3 個區塊）：{seq[:9]}")
    counts = {g: seq.count(g) for g in GROUPS}
    print(f"90 人總計各組人數：{counts}")
