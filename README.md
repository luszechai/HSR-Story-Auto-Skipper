# HSR Auto Skip

崩壞：星穹鐵道（Honkai: Star Rail）**視窗模式**劇情自動跳過工具。  
以影像模板比對偵測「跳過」與「確認」按鈕並自動點擊，支援多語系同時比對。

> **注意**：自動點擊可能違反遊戲服務條款，僅建議個人單機使用，風險自負。

## 功能

- 鎖定遊戲視窗客戶區截圖（不掃整螢幕）
- 多語系模板並行：繁中 / 簡中 / 英文 / 日文
- 流程：偵測 Skip → 點擊 → 等待（預設 0.5 秒）→ 偵測確認 → 點擊
- CustomTkinter 暗色控制台、即時預覽、熱鍵 F6 / F7
- 內建「擷取模板」：從遊戲畫面框選按鈕並存檔

## 環境需求

- Windows 10/11
- Python 3.10+
- 遊戲以**視窗模式**執行（勿最小化、勿完全遮擋）

## 安裝

```bash
cd HSR-detectSkipButton
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 啟動

```bash
python main.py
```

若全螢幕遊戲攔截點擊失敗，可嘗試「以系統管理員身分執行」。

## 使用步驟

1. 以視窗模式開啟崩鐵。
2. 執行 `python main.py`。
3. 點 **擷取模板**：
   - 類型選 `skip`，語系選目前遊戲語言，框選畫面上的「跳過」按鈕。
   - 再選 `confirm`，框選確認對話框上的「確認」按鈕。
   - 若會切換語言，請為每個語系各擷取一次。
4. 點 **設定** 確認解析度為 **1600 × 900**（或你的實際視窗大小），並在相同解析度下擷取模板。
5. 調整閾值、掃描間隔、確認等待、點擊方式、語系。
6. 按 **開始偵測** 或熱鍵；停止用 **停止** 或對應熱鍵。
7. 緊急停止：把滑鼠移到螢幕角落（pyautogui FAILSAFE）。

## 模板目錄

```
assets/templates/
  skip/{zh_tw,zh_cn,en,jp}/*.png
  confirm/{zh_tw,zh_cn,en,jp}/*.png
```

建議：在平常使用的視窗大小下擷取，之後盡量維持相同大小；模板盡量只含按鈕本體。

## 設定

首次執行會產生 `config.json`（閾值、間隔、等待、啟用語系等）。可在介面調整後按「儲存設定」。

## 疑難排解

| 狀況 | 建議 |
|------|------|
| 找不到視窗 | 確認視窗標題含「崩壞：星穹鐵道」或 `Honkai: Star Rail` |
| 從不點擊 | 降低閾值、重新擷取更乾淨的模板、固定視窗大小 |
| 誤點擊 | 提高閾值、縮小模板範圍 |
| 點擊偏移 | 關閉 Windows 顯示縮放異常／以 100% DPI 測試 |
| 游標能動但遊戲聚焦時點不到 | 已改為對視窗送點擊訊息（不必移動滑鼠）；請重開程式。若仍無效，試「以系統管理員執行」 |

## 專案結構

```
main.py
app/
  ui.py
  worker.py
  detector.py
  window_capture.py
  clicker.py
  config.py
  template_capture.py
assets/templates/...
```
