# 相機疑難排解

## 你看到的錯誤

```text
[ WARN] VIDEOIO(DSHOW): backend is generally available but can't be used to capture by index
[ WARN] VIDEOIO/FFMPEG: OpenCV should be configured with libavdevice to open a camera device
[ERROR] obsensor::getStreamChannelGroup Camera index out of range
```

這不代表網路攝影機壞掉。這代表：

- OpenCV 的 **DirectShow** 後端在指定索引找不到可用的相機；
- **FFmpeg** 備援後端在編譯時沒有加入相機裝置支援（`libavdevice`）；
- OpenCV 的 **Obsensor** 探測在該索引找不到相機／深度串流。

這三條訊息通常會一起出現，原因是**目前這個 Python 程序看不到任何相機裝置**。在本次使用的程式代理沙箱中，Windows 沒有向該程序暴露 Camera class 裝置，所以每個索引與後端都正確地失敗；同一個**全局 Python 3.15.1** 程序在沙箱外則可透過 MSMF 以 1280×720 開啟相機。最終相機路徑請務必在一般桌面工作階段執行。螢幕截圖仍使用有標示的模擬攝影機。

## 先做診斷

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\diagnose_camera.py --max-index 3
```

請在與啟動 AirCanvas 相同的情境中執行。部分程式代理／AppContainer 沙箱會封鎖相機裝置存取；一般 PowerShell／桌面工作階段可能可以，即使沙箱內的診斷失敗。本機的全局 Python 3.15.1 可以開啟相機，但沙箱工具程序不行。

這個工具會用 **MSMF → DSHOW → OpenCV auto** 嘗試相機 0–3，並且真正讀取一張影像，最後印出耗時。判讀方式：

| 診斷結果 | 意義 | 下一步 |
| --- | --- | --- |
| MSMF 可開啟且能取得影像 | Media Foundation 正常 | 在「System → Camera backend」選 **Media Foundation** |
| DSHOW 可開啟且能取得影像 | DirectShow 正常 | 選 **DirectShow** |
| 所有後端都打不開 | 這個 Python 工作階段看不到相機 | 檢查裝置管理員／隱私權／遠端工作階段；改用瀏覽器相機 |
| 有開啟但沒有影像 | 虛擬相機、被占用或空裝置 | 關閉其他相機程式；換索引／後端 |
| 只有瀏覽器能用 | 瀏覽器有權限／裝置，OpenCV 沒有 | 使用網頁版，或修正桌面相機權限 |

桌面版的「Camera is not active」卡片也有 **Diagnose** 按鈕可以直接執行。

## 依序嘗試的修正

1. **改用 Media Foundation。** 桌面版已優先使用 MSMF，也可以強制指定：
   ```powershell
   $env:AIRCANVAS_CAMERA_BACKEND="msmf"
   python run_desktop.py --no-onboarding
   ```
   或在 **System → Camera backend → Media Foundation** 選擇。也可以試試不同的 **Camera index**（0、1、2、3）。本機請使用全局 Python 3.15.1，並在程式代理沙箱外執行：
   ```powershell
   python run_desktop.py --camera-backend msmf --no-onboarding
   # 或：run_desktop_global.cmd
   ```
2. **檢查 Windows 相機隱私權。** 設定 → 隱私權與安全性 → 相機 → 允許桌面應用程式。若在受管理的公司／遠端環境，組織政策可能封鎖相機。
3. **關閉占用相機的程式。** Teams、Zoom、OBS Virtual Camera、Windows 相機、部分瀏覽器分頁都可能佔用裝置。關閉後重試。
4. **檢查裝置管理員。** 相機應出現在「相機」或「成像裝置」底下，且沒有警告圖示。若沒有出現，重新插拔；筆電請確認實體隱私遮罩或功能鍵。
5. **用瀏覽器測試。** 啟動本機網頁版：
   ```powershell
   python run_web.py --open
   ```
   按 **Enable camera**。若瀏覽器可以用相機、但 OpenCV 不行，改用網頁版即可；瀏覽器影像會送到同一個本機 Python 核心。這在遠端／虛擬 Windows 工作階段通常是最簡單的解法。
6. **遠端工作階段。** 有些遠端桌面／VM 只轉送瀏覽器相機，不轉送 DirectShow／MSMF。請使用網頁版，或把 USB 相機轉送到 VM。

## 為什麼瀏覽器可用、桌面版卻不行

桌面版透過 Windows 媒體後端使用 `cv2.VideoCapture`。網頁版使用瀏覽器的 `navigator.mediaDevices.getUserMedia()`，再把 JPEG 影像送到本機 FastAPI 服務。相機權限由瀏覽器管理，而瀏覽器可能看得到被轉送的相機，Python 程序卻看不到。手勢辨識、繪圖與追蹤仍然全部由共用的 Python 核心處理。

## 本次建置已做的修正

- Windows 後端順序改為 **MSMF → DSHOW → ANY**，不再只嘗試 DSHOW。
- 每次開啟都必須真正取得一張影像；「有開啟但沒有畫面」的虛擬相機不會再讓程式誤判成功。
- 不再傳遞 MSMF 不支援的開啟逾時 property 53；改以實際讀取一張影格來驗證裝置。
- 可在 UI 或透過 `AIRCANVAS_CAMERA_BACKEND` 選擇後端。
- UI 新增 **Diagnose**，且 `scripts/diagnose_camera.py` 會印出完整表格。
- 失敗訊息會說明嘗試過的後端，並提供模擬相機／網頁版備援。

如果診斷顯示 **no camera delivered a frame**，而且 Windows 裝置管理員也看不到相機，那就是環境限制；任何 Python 函式庫都無法開啟作業系統沒有暴露的裝置。
