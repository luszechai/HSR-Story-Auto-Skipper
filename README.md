# HSR Story Auto Skipper

[![CI](https://github.com/luszechai/HSR-Story-Auto-Skipper/actions/workflows/ci.yml/badge.svg)](https://github.com/luszechai/HSR-Story-Auto-Skipper/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/luszechai/HSR-Story-Auto-Skipper)](https://github.com/luszechai/HSR-Story-Auto-Skipper/releases/latest)
[![Windows](https://img.shields.io/badge/platform-Windows-0078D4)](#)

[繁體中文](#繁體中文) · [English](#english)

Windows-only visual automation tool that detects and clicks the **Skip** and
**Confirm** buttons in windowed Honkai: Star Rail.

> [!WARNING]
> Automated input may violate the game's terms of service. Use this project
> only at your own risk. This project is not affiliated with HoYoverse.

### Demo / 示範

https://github.com/luszechai/HSR-Story-Auto-Skipper/raw/main/assets/demo/hsr-auto-skip-demo.mp4

[Download demo video / 下載示範影片](assets/demo/hsr-auto-skip-demo.mp4)

---

## 繁體中文

### 功能

- 只擷取遊戲視窗客戶區，不掃描整個螢幕
- OpenCV 多尺度模板比對；Skip 圖示不分語言，確認按鈕依「遊戲語言」載入繁中／簡中／日文／英文模板
- 設定可分別選擇介面語言（UI）與遊戲語言（偵測模板）；各為單一語系下拉選單
- 使用筆劃輪廓遮罩，降低動態場景背景對 Skip 分數的干擾
- Skip 固定區域存在檢查與 2/3 多幀穩定確認
- Skip／確認偵測到後立即點擊（不做第二次截圖驗證）
- 點擊後確認 Skip／確認按鈕消失，失敗時限制重試次數
- 「確認」文字二次驗證，缺少文字模板時採安全拒絕
- 即時預覽、浮動 Overlay、全域開始／停止熱鍵
- 設定以原子方式儲存；錯誤或異常數值會回復安全預設值

### 下載與安裝

1. 前往 [最新 Release](https://github.com/luszechai/HSR-Story-Auto-Skipper/releases/latest)。
2. 下載 `HSR-Auto-Skip-windows-x64.zip`。
3. 解壓縮**整個**資料夾；請保留 `_internal`，不要只複製 `.exe`。
4. 執行 `HSR Auto Skip.exe`。
5. 接受 Windows UAC 系統管理員權限提示。

需求：Windows 10/11、崩壞：星穹鐵道視窗模式。

### 使用方式

1. 以視窗模式開啟遊戲，且不要最小化。
2. 啟動本程式，確認已找到正確遊戲視窗。
3. 在設定中選擇遊戲客戶區解析度；預設模板以 1600×900 校準。
4. 在設定中分別選擇「語言」（介面）與「遊戲語言」（確認／確認文字模板）。
5. 按「開始偵測」或使用設定的開始熱鍵。
6. 若內建模板不適合目前語言或 UI 比例，再使用「擷取模板」建立模板。

> 遊戲必須保持前景且不可被其他視窗遮住。`mss` 擷取的是螢幕上實際可見
> 像素，遮住遊戲會導致分數下降或偵測失敗。

### 疑難排解

- **找不到視窗：**確認視窗標題含「崩壞：星穹鐵道」、
  「崩壊：スターレイル」或 `Honkai: Star Rail`。
- **Skip 分數不足：**確認解析度／UI 比例、保持遊戲前景、重新擷取同一語言
  的模板；不要先任意降低門檻。
- **誤點擊：**提高門檻，並保持 Skip 存在檢查與確認文字檢查啟用。
- **點擊無效：**以系統管理員身分執行，並使用視窗模式。
- **缺少 `python310.dll`：**從完整解壓縮的 Release 資料夾執行，不要單獨
  移動 `.exe`。

### 從原始碼執行

需要 Windows 10/11 與 Python 3.10+：

```powershell
git clone https://github.com/luszechai/HSR-Story-Auto-Skipper.git
cd HSR-Story-Auto-Skipper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

建置 Windows 應用程式：

```powershell
.\build_app.bat
```

`requirements.txt` 是直接執行依賴；`requirements-lock.txt` 鎖定已驗證的
Python 3.10 Windows 建置環境。產物位於 `dist\HSR Auto Skip\`。

---

## English

### Features

- Captures only the game client area instead of scanning the entire desktop
- OpenCV multi-scale template matching; Skip is language-independent, while
  Confirm templates load for a single selected game language (zh_tw / zh_cn / jp / en)
- Separate Settings dropdowns for UI language and game (detection) language
- Stroke-refined masks reduce interference from animated backgrounds
- Fixed-region Skip presence check with 2-of-3-frame spatial consensus
- Clicks Skip/Confirm immediately when detected (no second capture/detect)
- Verifies that Skip/Confirm disappears and limits failed click retries
- Secondary Confirm-text validation that fails closed when its template is missing
- Live preview, floating overlay, and global start/stop hotkeys
- Atomic configuration saves with validation and safe defaults

### Download and install

1. Open the [latest release](https://github.com/luszechai/HSR-Story-Auto-Skipper/releases/latest).
2. Download `HSR-Auto-Skip-windows-x64.zip`.
3. Extract the **entire** folder. Keep `_internal`; do not copy only the `.exe`.
4. Run `HSR Auto Skip.exe`.
5. Accept the Windows UAC administrator prompt.

Requirements: Windows 10/11 and Honkai: Star Rail in windowed mode.

### Usage

1. Start the game in windowed mode and do not minimize it.
2. Launch the tool and verify that it finds the correct game window.
3. Select the game client resolution in Settings. The bundled Skip template is
   calibrated for 1600×900 by default.
4. Choose **UI language** and **Game language** separately in Settings.
5. Select **Start Detection** or press the configured start hotkey.
6. Use **Capture Template** only when the bundled template does not match your
   language or UI scale.

> The game must remain visible and in the foreground. `mss` captures the pixels
> currently visible on screen, so another window covering the game lowers the
> score or prevents detection.

### Troubleshooting

- **Window not found:** ensure the title contains `Honkai: Star Rail`,
  `崩壊：スターレイル`, or one of the supported Chinese titles.
- **Low Skip score:** check resolution/UI scale, keep the game visible, and
  capture a matching-language template before lowering the threshold.
- **False click:** raise the threshold and keep Skip-presence and Confirm-text
  validation enabled.
- **Click has no effect:** run as administrator and keep the game in windowed mode.
- **Missing `python310.dll`:** run from the complete extracted Release folder;
  do not move the executable by itself.

### Run from source

Windows 10/11 and Python 3.10+ are required:

```powershell
git clone https://github.com/luszechai/HSR-Story-Auto-Skipper.git
cd HSR-Story-Auto-Skipper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Build the Windows package:

```powershell
.\build_app.bat
```

`requirements.txt` contains direct runtime dependencies.
`requirements-lock.txt` pins the verified Python 3.10 Windows build environment.
Build output is written to `dist\HSR Auto Skip\`.

---

## Templates / 模板

```text
assets/templates/
  skip/*.png                              # language-independent |>| icon
  confirm/{zh_tw,zh_cn,en,jp}/*.png       # Confirm button
  confirm_text/{zh_tw,zh_cn,en,jp}/*.png  # Confirm label text per language
```

Capture templates at the resolution normally used for play and keep the same
client resolution when possible. Skip is shared across languages; Confirm button
and Confirm-text glyphs are per language (`zh_tw` / `zh_cn` / `en` / `jp`).
Skip templates may use a matching `<name>_mask.png` sidecar.

## Development / 開發

```text
main.py              Application entry point / 程式進入點
app/                 UI, worker, detector, capture and click logic
assets/              Templates, branding, and demo video / 模板、品牌與示範影片
assets/demo/         README demo recording / README 示範錄影
build_app.bat         Reproducible PyInstaller build
```

Run checks with:

```powershell
python -m compileall -q app main.py
```

Please read [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md), and
[SUPPORT.md](SUPPORT.md). Report bugs or request features through
[GitHub Issues](https://github.com/luszechai/HSR-Story-Auto-Skipper/issues).
