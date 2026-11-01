# 交付項目對照表

每一項要求的交付項目，以及其所在位置。

| # | 交付項目 | 位置／證據 |
| ---: | --- | --- |
| 1 | 系統架構圖 | [`architecture_diagram.png`](architecture_diagram.png) · 原始碼 [`scripts/generate_architecture.py`](../scripts/generate_architecture.py) |
| 2 | 專案資料夾結構 | [`PROJECT_STRUCTURE_CN.md`](PROJECT_STRUCTURE_CN.md) · README 目錄樹 |
| 3 | 手勢映射表 | [`GESTURE_MAP_CN.md`](GESTURE_MAP_CN.md) |
| 4 | 桌面應用程式實作 | [`aircanvas/desktop/`](../aircanvas/desktop) · 啟動 `python run_desktop.py` |
| 5 | 網頁應用程式實作 | [`aircanvas/web/`](../aircanvas/web) · 啟動 `python run_web.py` |
| 6 | 共用 Python 核心模組 | [`aircanvas/`](../aircanvas) · 架構說明於 [`ARCHITECTURE_CN.md`](ARCHITECTURE_CN.md) |
| 7 | 可選手部特徵點模型 | [`HAND_MODEL_BACKENDS_CN.md`](HAND_MODEL_BACKENDS_CN.md) · `aircanvas/hand_models.py` |
| 8 | 完整原始碼 | 本儲存庫（`aircanvas/`、`tests/`、`scripts/`、各啟動器） |
| 9 | 安裝與執行說明 | [`README_CN.md`](../README_CN.md) · [`USER_GUIDE_CN.md`](USER_GUIDE_CN.md) |
| 10 | 測試程序 | [`TESTING_CN.md`](TESTING_CN.md) · 自動化測試於 [`tests/`](../tests) |
| 11 | 桌面版與網頁版介面比較報告 | [`INTERFACE_COMPARISON_CN.md`](INTERFACE_COMPARISON_CN.md) |
| 12 | 兩個介面的螢幕截圖 | [`screenshots/`](screenshots) — 桌面螢幕/鏡像、網頁螢幕/鏡像、行動版 |
| 13 | 已知限制與未來改善 | [`KNOWN_LIMITATIONS_CN.md`](KNOWN_LIMITATIONS_CN.md) |

## 支援性交付項目

| 主題 | 位置 |
| --- | --- |
| 瀏覽器安全限制 | [`BROWSER_LIMITATIONS_CN.md`](BROWSER_LIMITATIONS_CN.md) |
| 攝影機疑難排解／診斷 | [`CAMERA_TROUBLESHOOTING_CN.md`](CAMERA_TROUBLESHOOTING_CN.md) · [`scripts/diagnose_camera.py`](../scripts/diagnose_camera.py) |
| 全局 Python 3.15 驗證 | [`scripts/smoke_global_python.py`](../scripts/smoke_global_python.py) · `run_desktop_global.cmd` |
| 人機互動（HCI）原則與啟發式評估 | [`INTERFACE_COMPARISON_CN.md`](INTERFACE_COMPARISON_CN.md) §12–13 |
| 功能比較矩陣 | [`INTERFACE_COMPARISON_CN.md`](INTERFACE_COMPARISON_CN.md) §8.3 |
| 需求／安裝設定 | [`README_CN.md`](../README_CN.md) §2 |
| 示範模式螢幕截圖與可重現性 | [`TESTING_CN.md`](TESTING_CN.md) · [`scripts/capture_desktop.py`](../scripts/capture_desktop.py)、[`scripts/capture_web.py`](../scripts/capture_web.py) |
| 模型下載工具 | [`scripts/fetch_model.py`](../scripts/fetch_model.py) |
| 效能基準證據 | [`TESTING_CN.md`](TESTING_CN.md) §5 · README_CN.md §6 |
| 隱私與第三方聲明 | README_CN.md §7–8 |
| 繁體中文翻譯 | [`README_CN.md`](../README_CN.md) 與 [`docs/`](.) 內對應的 `*_CN.md` 文件 |
