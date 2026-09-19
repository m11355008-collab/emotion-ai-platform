# diagnose.py
# 這個檔案跟 Gradio 介面完全無關，純粹測試「這台電腦連不連得到 Gemini」。
# 用意是把問題切成兩半：如果這個都卡住，代表是網路或金鑰的問題；
# 如果這個很快就成功，代表是 app.py 裡面的邏輯要再檢查。

import os
import time
from google import genai

print("1) 檢查金鑰是否讀得到...")
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 沒有讀到 GEMINI_API_KEY，請確認你是在同一個 PowerShell 視窗，")
    print("   先執行過 $env:GEMINI_API_KEY=\"你的新金鑰\" 再跑這個檔案。")
    raise SystemExit(1)
print(f"✅ 讀到金鑰，開頭是 {api_key[:6]}...（共 {len(api_key)} 個字元）")

print("\n2) 嘗試連線並跟 Gemini 說一句話（最多會等 20 秒左右）...")
start = time.time()
try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="請用一句話跟我打招呼",
    )
    elapsed = time.time() - start
    print(f"✅ 成功！花了 {elapsed:.1f} 秒")
    print("AI 回覆：", response.text)
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ 失敗，等了 {elapsed:.1f} 秒後出現錯誤")
    print("錯誤內容：", repr(e))
