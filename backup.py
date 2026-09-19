# -*- coding: utf-8 -*-
"""
自動備份到 Hugging Face 私人 Dataset。

背景：Hugging Face Spaces 免費版執行期間寫入的檔案（也就是 data/ 資料夾裡
逐步累積的對話紀錄、問卷紀錄、分派狀態）不保證持久——Space 因為閒置重啟、
或之後又更新一次程式碼，data/ 都有可能被清空重置。只有直接放在程式碼庫
（git）裡的檔案才確定會保留。

因應方式：每位參與者完成全部流程（進入 done 階段）的當下，把他的三份 CSV
加上目前的分派狀態檔，一起上傳到一個私人 Hugging Face Dataset repo，多一層
保險。就算 Space 之後真的被重置，最多只會漏掉「正在進行中、還沒完成」的
那一兩位，不會整批不見。

需要兩個環境變數（在 Space 的 Settings → Variables and secrets 設定，
兩個都要設成 Secret）：
  - HF_TOKEN：具備寫入權限的 Hugging Face token。到
    https://huggingface.co/settings/tokens 申請，Token type 選「Write」。
  - HF_BACKUP_DATASET_REPO：備份用的 Dataset repo 名稱，格式「你的帳號/repo名稱」
    （例如 "kurou/emotion-ai-backup-data"）。第一次備份時如果這個 repo 還
    不存在，程式會自動建立（建立為 private，其他人看不到）。

沒有設定這兩個環境變數時，is_configured() 回傳 False，app.py 會直接跳過
備份，不影響原本的流程——本機／Space 上的 data/ 資料夾照樣正常寫入，備份
純粹是「多一份」，不是取代原本的紀錄機制。
"""

import logging
import os

logger = logging.getLogger(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_BACKUP_DATASET_REPO = os.environ.get("HF_BACKUP_DATASET_REPO")

_repo_ready = False


def is_configured() -> bool:
    return bool(HF_TOKEN and HF_BACKUP_DATASET_REPO)


def _ensure_repo(api) -> None:
    global _repo_ready
    if _repo_ready:
        return
    api.create_repo(repo_id=HF_BACKUP_DATASET_REPO, repo_type="dataset", private=True, exist_ok=True)
    _repo_ready = True


def backup_files(file_paths: list) -> bool:
    """把一份或多份檔案上傳到備份 Dataset，用原本的檔名存放在 repo 根目錄
    （同檔名會直接覆蓋成最新版本，這是我們要的行為——每次備份都是最新完整內容）。

    回傳是否成功；備份失敗只記錄警告、不會丟出例外——呼叫端（app.py）不應該
    讓備份失敗擋住參與者看到完成畫面，資料本來就還留在本機 data/ 資料夾，
    備份失敗頂多下次有人完成流程時再試一次，不构成資料遺失。"""
    if not is_configured():
        return False
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=HF_TOKEN)
        _ensure_repo(api)
        for path in file_paths:
            if not path or not os.path.isfile(path):
                continue
            api.upload_file(
                path_or_fileobj=path,
                path_in_repo=os.path.basename(path),
                repo_id=HF_BACKUP_DATASET_REPO,
                repo_type="dataset",
                commit_message=f"backup {os.path.basename(path)}",
            )
        return True
    except Exception as e:  # 備份是額外保險，任何原因失敗都不能影響參與者的流程
        logger.warning(f"備份到 Hugging Face Dataset 失敗（不影響參與者當下的流程，資料仍在本機 data/ 內）：{e}")
        return False
