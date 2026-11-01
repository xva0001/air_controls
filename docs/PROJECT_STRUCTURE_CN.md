# 專案資料夾結構

```text
air_controls/
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── run_desktop.py                 # 便利啟動器（venv 或全局 Python）
├── run_desktop_global.cmd         # 以全局 Python 啟動（已驗證相機路徑）
├── run_web.py                     # 便利啟動器
├── aircanvas/
│   ├── __init__.py
│   ├── assets/
│   │   └── hand_landmarker.task   # MediaPipe float16 模型（7.8 MB）
│   ├── config.py                  # AppConfig、GestureSettings、持久化
│   ├── geometry.py                # Point、BBox、正規化座標輔助函式
│   ├── smoothing.py               # One Euro 濾波器、停留穩定器
│   ├── models.py                  # Hand/Gesture/Stroke/Marker/Event 模型
│   ├── gestures.py                # HandTracker、姿勢規則、穩定器
│   ├── mapping.py                 # GestureMapper、NavigationController、MouseController
│   ├── hand_models.py             # MediaPipe / RTMPose / YOLO 後端註冊
│   ├── drawing.py                 # 筆畫儲存、復原/重做、形狀提交
│   ├── shapes.py                  # 圓擬合、迴圈選取
│   ├── tracking.py                # CSRT + 外觀恢復 + 視野（FOV）狀態
│   ├── session.py                 # InteractionSession 門面（共用狀態）
│   ├── camera.py                  # OpenCV 擷取 + 桌面管線
│   ├── native.py                  # Windows 作業系統輸入橋接
│   ├── synthetic.py               # 確定性的合成特徵點
│   ├── demo.py                    # 模擬攝影機場景 + 示範管線
│   ├── resources.py               # 模型/靜態資源路徑輔助函式
│   ├── desktop/
│   │   ├── app.py                 # 桌面 CLI 與啟動載入
│   │   ├── main_window.py         # 原生外殼、檢視器、設定、攝影機生命週期
│   │   ├── stage.py               # QPainter 畫布/視訊/覆蓋層
│   │   ├── overlay.py             # 可點擊穿透的透明覆蓋層 + 工具列
│   │   ├── widgets.py             # 自訂無障礙控制項
│   │   ├── icons.py               # 向量圖示
│   │   ├── dialogs.py             # 引導、說明、同意
│   │   └── theme.py               # 設計變數（design tokens）+ 樣式表
│   └── web/
│       ├── __init__.py
│       ├── server.py              # FastAPI、WebSocket、安全性、示範迴圈
│       └── static/
│           ├── index.html         # 語意化介面與對話框
│           ├── styles.css         # 響應式設計系統
│           ├── app.js             # 瀏覽器攝影機、狀態、Canvas 2D 渲染器
│           └── favicon.svg
├── tests/
│   ├── conftest.py
│   ├── test_camera.py
│   ├── test_hand_models.py
│   ├── test_shapes.py
│   ├── test_gestures.py
│   ├── test_mapping.py
│   ├── test_tracking.py
│   ├── test_session.py
│   ├── test_web.py
│   └── test_desktop_smoke.py
├── scripts/
│   ├── fetch_model.py             # 缺少模型時下載
│   ├── diagnose_camera.py         # 探測攝影機索引/後端
│   ├── smoke_global_python.py     # 驗證全局 Python 3.15 + Qt + MediaPipe
│   ├── generate_architecture.py   # 產生 PNG 架構圖
│   ├── capture_desktop.py         # 離屏螢幕截圖
│   └── capture_web.py             # Playwright/CDP 螢幕截圖
├── docs/
│   ├── ARCHITECTURE.md
│   ├── GESTURE_MAP.md
│   ├── HAND_MODEL_BACKENDS.md
│   ├── INTERFACE_COMPARISON.md
│   ├── BROWSER_LIMITATIONS.md
│   ├── CAMERA_TROUBLESHOOTING.md
│   ├── TESTING.md
│   ├── USER_GUIDE.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── DELIVERABLES.md
│   ├── PROJECT_STRUCTURE.md
│   ├── architecture_diagram.png
│   └── screenshots/
│       ├── desktop-screen.png
│       ├── desktop-mirror.png
│       ├── web-screen.png
│       ├── web-mirror.png
│       └── web-mobile.png
└── data/                           # 本機執行/測試產物（已列入 gitignore）
```

每份英文文件旁都有對應的 `_CN.md` 中文版本（`README_CN.md` 位於儲存庫根目錄）；`CAMERA_TROUBLESHOOTING_CN.md` 與其他中文指南可直接從中文 README 進入。

執行時期快取（`.venv/`、`.uv-cache/`、`.cache/`、瀏覽器設定檔、下載的測試影像、`pytest-cache-files-*`）僅供開發使用，且已列入 gitignore。

---

## 1. 各項變更應修改的位置

| 工作項目 | 在此修改 | 不要重複實作於 |
| --- | --- | --- |
| 新增/調整姿勢 | `aircanvas/gestures.py`（`classify_hand`）+ `config.GESTURE_POSES` | desktop/widgets 或 app.js |
| 變更手勢角色/預設值 | `aircanvas/config.py`（`GestureSettings`）與 `docs/GESTURE_MAP.md` | 僅限介面的程式碼 |
| 調整導覽 | `aircanvas/mapping.py`（`NavigationController`） | 桌面版/JS 計時器 |
| 新增形狀 | `aircanvas/shapes.py` + `desktop/stage.py` 與 `web/static/app.js` 的渲染分支 | 在 JS 中進行辨識 |
| 變更追蹤器策略 | `aircanvas/tracking.py`（`TrackerParams`） | 介面程式碼 |
| 新增繪圖操作 | `aircanvas/drawing.py` + 一個桌面/網頁動作綁定 | 重複的筆畫演算法 |
| 變更狀態結構（schema） | `aircanvas/session.py`（`snapshot`）+ 兩個渲染器 | 協定變體 |
| 新增原生作業系統動作 | `aircanvas/native.py` + 桌面事件路由；絕不對網頁暴露 | app.js |
| 新增網頁端點/訊息 | `aircanvas/web/server.py` + `app.js` 用戶端 | 桌面版 |
| 變更視覺變數 | `desktop/theme.py` 與 `web/static/styles.css`（兩者保持同步） | 各元件寫死的數值 |
| 重新產生螢幕截圖 | `scripts/capture_desktop.py`、`scripts/capture_web.py` | 手動裁切 |
| 重新產生架構圖 | `scripts/generate_architecture.py` | 僅以手動編輯架構圖 |

---

## 2. 模組相依方向

```text
desktop/*  ─┐
            ├──► session ──► gestures ──► models/geometry/config
web/*      ─┘         ├────► drawing ──► shapes
                      ├────► tracking
                      ├────► mapping ──► smoothing
                      └────► native（僅桌面版）
```

沒有任何共用核心模組會匯入 `desktop`、`web`、PySide6、FastAPI 或 JavaScript。這讓核心可以在沒有介面的情況下測試，並避免平台之間出現循環相依。`session` 是唯一的協調者；各介面轉接層絕不會存取另一個轉接層的狀態。

---

## 3. 新增第三種前端

未來的 CLI、行動裝置包裝層或 Electron 外殼需要：

1. 建立一個 `InteractionSession`。
2. 將 BGR 影格（或合成觀測）餵入 `process_frame`。
3. 渲染 `snapshot()` 並消費語意化事件清單。
4. 使用相同的手勢映射與安全策略，轉譯平台輸入/動作。

它不得重新實作閾值、繪圖或追蹤。web/desktop 程式碼是此契約的參考轉接層。
