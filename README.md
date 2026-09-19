# 情緒表達 AI 互動平台 — 完整流程原型

## 目前狀態（一條龍完整流程，A／B／C 三組皆已完成）

- 參與者輸入編號 → 系統依封存的隨機分派清單自動分組（區塊隨機化，見 `randomization.py`）
- 基本資料／前測問卷 → 三情境角色扮演對話 → 後測問卷 → 完成畫面
- 前測、後測問卷共用同一組介面，依序跑完 `questionnaires.py` 裡定義的問卷清單
  （EES／IRI／ERQ／DDI 皆為正式題目，非佔位文字）
- 對話部分：
  - A 組（情緒鷹架型 AI）、B 組（基線型 AI）：即時呼叫 Gemini API
  - C 組（人類／WoZ）：`app.py` 的「操作員（研究者專用）」分頁，由研究者本人
    即時看到參與者訊息、從 `reply_bank.py` 的預寫回覆庫手動挑選最貼合的一句送出
- 三種紀錄檔分開存放，完成畫面可以直接下載：對話紀錄、歷程時間戳記、問卷作答紀錄

## 部署平台：Render.com（免費方案）

原本規劃部署到 Hugging Face Spaces，但 Hugging Face 從 2026 年中開始，免費帳號
已經不能建立 Gradio／Docker Space（需要 PRO 訂閱才能建立，即使硬體本身是免費
規格），因此改用 Render.com 的免費 Web Service。`render.yaml` 已經寫好對應的
部署設定；`app.py` 的啟動方式（`server_name="0.0.0.0"`、讀取 `PORT` 環境變數）
也已經配合 Render 的需求調整過。

免費方案有一個限制：閒置 15 分鐘後服務會「睡著」，下一個請求進來時需要
30-50 秒喚醒——如果參與者剛好是第一個在一段時間後進來的人，畫面可能會卡個
幾十秒才跑出來，屬於免費方案正常現象，不是壞掉。

## 部署前，你需要在 Render 的 Environment 分頁設定

| 名稱 | 說明 |
|---|---|
| `GEMINI_API_KEY` | A、B 組對話用，到 https://aistudio.google.com/apikey 申請 |
| `WOZ_OPERATOR_PASSWORD` | C 組操作員後台的登入密碼，自己設一組，不要跟參與者分享 |
| `HF_TOKEN` | 用於自動備份資料（見下方「資料備份」），到 https://huggingface.co/settings/tokens 申請，Token type 選「Write」|
| `HF_BACKUP_DATASET_REPO` | 備份資料要存到哪個 Dataset，格式「你的帳號/repo名稱」（例如 `kurou/emotion-ai-backup-data`），第一次備份時會自動建立為 private |

這四個都不要寫進 `render.yaml` 或任何會上傳到 GitHub 的檔案裡，只透過 Render
網頁介面的 Environment 分頁貼上實際的值，這樣才不會被任何人看到。

## 資料備份（因為免費版服務重啟時可能清空執行期間寫入的檔案）

Render 免費方案完全沒有「持久化硬碟」——只要服務閒置 15 分鐘後被喚醒，執行期間
寫入的檔案就可能被清空重置，不是只有重新部署才會這樣。因應方式有兩層：

1. **備份頻率**：只要設定了 `HF_TOKEN` 和 `HF_BACKUP_DATASET_REPO`，系統會在
   三個時間點自動備份，不是只有參與者跑完全部流程才備份：分派到組別的當下
   （保護分派紀錄，這是最不能弄丟的資料——弄丟的話，參與者重新整理頁面會
   被當成新的人，可能拿到跟原本不同的組別）、前測問卷跑完進入對話階段時、
   三個情境對話跑完進入後測問卷時、以及全部完成時。這樣就算服務在某位
   參與者填答中途被重置，最多只會漏掉「最近一個階段」的資料，不會整份不見。
2. **降低重置的發生頻率**：建議用免費的 [UptimeRobot](https://uptimerobot.com/)
   之類的服務，每 10-14 分鐘 ping 一次你的 Space 網址，讓它幾乎不會真的閒置到
   被喚醒重置。這不是 Render 官方保證支援的做法，但社群普遍在用，能大幅降低
   實際發生重置的機率。收案期間開著就好，收案結束後記得關掉，避免不必要的
   使用量。
3. **服務啟動時自動還原分派紀錄**：這是最關鍵的一層保護。就算前兩層都沒發揮
   作用、服務真的被重置了，程式啟動時會自動把上一次備份的分派紀錄
   （`participant_assignments.json`）從 Hugging Face Dataset 抓回來還原，
   不會出現「服務重啟一次，下一位參與者就被系統當成全新的第一位、重新從
   分派清單最前面開始分」的問題，不需要你手動介入分配。

沒有設定 `HF_TOKEN`／`HF_BACKUP_DATASET_REPO` 的話，系統會直接跳過備份，不影響
其他任何功能——但這代表你需要自己更頻繁地手動下載資料備份。

## 操作員（研究者本人）使用方式

部署後，把 Space 的網址分享給參與者即可（他們只會用到「參與者」分頁）。
你自己收案期間，打開同一個網址、切到「操作員（研究者專用）」分頁，
輸入 `WOZ_OPERATOR_PASSWORD` 登入後台，就能看到所有正在等待回覆的 C 組參與者。

## 檔案說明

| 檔案 | 內容 |
|---|---|
| `app.py` | **主程式**，完整流程的 Gradio 介面（參與者分頁＋操作員分頁）|
| `system_prompts.py` | A、B 兩組的 system prompt |
| `scenarios.py` | 三個角色扮演情境的文字（含 A/B 版「對方（AI）」與 C 版「對方（同儕）」開場白）、最少／最多回合數 |
| `questionnaires.py` | 前測、後測要用到的所有問卷定義（EES／IRI／ERQ／DDI 正式題目）|
| `survey.py` | 問卷「依序作答、記錄時間」的核心邏輯，不依賴 Gradio |
| `logger.py` | 對話紀錄、問卷歷程記錄、作答記錄，三種 CSV 的寫入邏輯 |
| `randomization.py` | 參與者隨機分派（區塊隨機化，區塊大小 3）|
| `randomization_list.json` | 封存的正式分派清單（90 人份，一次性產生，不要刪除或重新產生）|
| `reply_bank.py` | C 組操作員的預寫回覆庫（依情境分類＋通用回覆）|
| `woz_session.py` | C 組參與者端與操作員端之間的共用同步機制 |
| `backup.py` | 參與者完成流程時，自動把資料備份到 Hugging Face Dataset |
| `render.yaml` | Render.com 的部署設定（不含任何金鑰實際內容）|

## 測試

```
export GEMINI_API_KEY="任意測試字串"
export WOZ_OPERATOR_PASSWORD="任意測試字串"
python3 test_randomization.py
python3 test_woz_session.py
python3 test_survey.py
python3 test_merged.py
python3 test_woz_flow.py
python3 test_backup.py
```

全部應該顯示「全部測試通過 ✅」。
