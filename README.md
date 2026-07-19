# HSR Story Auto Skipper

崩壞：星穹鐵道（Honkai: Star Rail）**視窗模式**劇情自動跳過工具。  
以影像模板比對偵測「跳過」與「確認」按鈕並自動點擊，支援多語系。

> **注意**：自動點擊可能違反遊戲服務條款，僅建議個人使用，風險自負。

**Repo：** [luszechai/HSR-Story-Auto-Skipper](https://github.com/luszechai/HSR-Story-Auto-Skipper)

---

## 推薦用法：下載 Release（一般使用者）

不必安裝 Python，直接下載已打包的 Windows 應用程式：

1. 開啟最新版本頁面：  
   **[Releases](https://github.com/luszechai/HSR-Story-Auto-Skipper/releases/latest)**
2. 下載 **`HSR-Auto-Skip-windows-x64.zip`**
3. 解壓縮整個資料夾（請保留 `_internal` 等檔案，不要只複製單一 `.exe`）
4. 執行 **`HSR Auto Skip.exe`**
5. Windows 會要求**系統管理員權限**（UAC）— 請允許，以便點擊／截圖較穩定

### 第一次使用

1. 以**視窗模式**開啟崩鐵（勿最小化）
2. 開啟本程式 → **擷取模板**：分別框選「跳過」與「確認」
3. 在 **設定** 確認解析度（例如 1600×900）與**偵測目標 FPS**（1–30）
4. 按 **開始偵測**（或熱鍵）

---

## 功能摘要

- 鎖定遊戲視窗客戶區截圖（不掃整螢幕）
- 多語系模板：繁中 / 簡中 / 英文 / 日文
- 流程：偵測 Skip → 點擊 → 等待 → 偵測確認 → 點擊
- 暗色介面、即時預覽、無邊框浮動 Overlay
- **設定在同一視窗**（可捲動），數值以固定間隔調整（例如 FPS step = 1）
- 強化模板、誤判黑名單、確認文字二次驗證
- 點擊使用 **pydirectinput**（螢幕座標）

---

## 開發者：從原始碼執行

需要 Windows 10/11、Python 3.10+。

```bash
git clone https://github.com/luszechai/HSR-Story-Auto-Skipper.git
cd HSR-Story-Auto-Skipper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

重新打包 `.exe`：

```bash
build_app.bat
```

產物在 `dist\HSR Auto Skip\`（請勿提交 `dist/`、`.venv/`）。

---

## 模板目錄

```
assets/templates/
  skip/{zh_tw,zh_cn,en,jp}/*.png
  confirm/{zh_tw,zh_cn,en,jp}/*.png
```

請在平常使用的視窗大小下擷取，之後盡量維持相同解析度。

---

## 疑難排解

| 狀況 | 建議 |
|------|------|
| 找不到視窗 | 確認標題含「崩壞：星穹鐵道」或 `Honkai: Star Rail` |
| FPS 很低 | 到設定提高「偵測目標 FPS」（1–30） |
| 從不點擊 | 降低閾值、重新擷取模板、固定視窗大小 |
| 誤點擊 | 提高閾值、開啟確認文字檢測／黑名單 |
| 點擊無效 | 以系統管理員執行；遊戲保持前景視窗模式 |
| `python310.dll` / 從 build 開啟失敗 | 請執行 **`dist\HSR Auto Skip\HSR Auto Skip.exe`**，或下載 Release zip |

---

## 社群標準

請閱讀並遵守：

- [行為準則](CODE_OF_CONDUCT.md)
- [貢獻指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
- [取得協助](SUPPORT.md)

問題與建議請開 [GitHub Issues](https://github.com/luszechai/HSR-Story-Auto-Skipper/issues)。

---

## 專案結構

```
main.py
app/           # UI、worker、detector、截圖、點擊、設定頁
assets/        # 模板、品牌圖示
build_app.bat  # PyInstaller 打包
```
