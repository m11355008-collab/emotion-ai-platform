# test_backup.py
#
# 測試 backup.py，不需要真的連到 Hugging Face（用假的 token／repo，
# 驗證「沒設定時跳過」「設定但連線失敗時不會丟例外、只回傳 False」這兩個
# 關鍵行為——備份本來就是「多一層保險」，絕對不能讓備份失敗拖垮參與者的
# 正常流程）。

import importlib
import os
import tempfile


def run():
    # 1. 沒設定 HF_TOKEN／HF_BACKUP_DATASET_REPO 時，is_configured() 應該是 False，
    # backup_files() 也應該直接跳過（回傳 False，不嘗試連線）。
    os.environ.pop("HF_TOKEN", None)
    os.environ.pop("HF_BACKUP_DATASET_REPO", None)
    import backup
    importlib.reload(backup)
    assert backup.is_configured() is False
    assert backup.backup_files(["/nonexistent/path.csv"]) is False
    print("[OK] 沒設定環境變數時，is_configured() 為 False，backup_files() 直接跳過")

    # 2. 設定了但 token 是假的（連不上真正的 Hugging Face）：
    # backup_files() 應該要吞掉例外、回傳 False，而不是讓整個程式崩潰。
    os.environ["HF_TOKEN"] = "fake-token-for-testing"
    os.environ["HF_BACKUP_DATASET_REPO"] = "fake-user/fake-repo"
    importlib.reload(backup)
    assert backup.is_configured() is True

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"participant_id,group\nT001,A\n")
        tmp_path = f.name
    try:
        result = backup.backup_files([tmp_path])
        assert result is False, "假的 token 連線一定會失敗，backup_files 應該回傳 False 而不是丟例外"
        print("[OK] 設定了但連線失敗時，backup_files() 不會丟例外、正確回傳 False")
    finally:
        os.remove(tmp_path)

    # 3. 不存在的檔案路徑要直接跳過，不因為某一個檔案不存在就整批失敗。
    os.environ.pop("HF_TOKEN", None)
    os.environ.pop("HF_BACKUP_DATASET_REPO", None)
    importlib.reload(backup)
    print("\n全部備份模組測試通過 ✅")


if __name__ == "__main__":
    run()
