# 手部特徵點模型後端

AirCanvas 每隻手需要 21 個手部特徵點。產生這些特徵點的模型可以選擇，讓你在設定複雜度與偏好的模型家族之間取捨。

MediaPipe 是內建預設。RTMPose-Hand 與 YOLO Pose 是選用轉接器，採惰性載入；缺少依賴或權重時會回報清楚的狀態。

---

## 1. 可選擇的後端

| 後端 | 鍵值 | 特徵點 | 額外安裝 | 模型檔案 |
| --- | --- | --- | --- | --- |
| MediaPipe Hands | `mediapipe` | 21 | 無 | 內建 `aircanvas/assets/hand_landmarker.task`；可選自訂 `.task` |
| RTMPose-Hand | `rtmpose` | 21 | `pip install rtmlib onnxruntime` | 可選本機 `.onnx`／`.zip` 或 URL；首次使用時 rtmlib 會下載手部偵測器與姿態模型 |
| YOLO Pose | `yolo_pose` | 21（僅限自訂手部模型） | `pip install ultralytics` | 必須提供 `.pt` 手部姿態權重 |

桌面版介面位於 **System → Hand landmark model**，提供 **Choose model…** 按鈕與可用狀態列。瀏覽器版在 **System** 下有相同選項；路徑是 **Python 伺服器**上的路徑，不是瀏覽器電腦上的路徑。

命令列：

```powershell
# 內建預設
python run_desktop.py --hand-backend mediapipe

# RTMPose-Hand，使用 rtmlib 預設模型
python run_desktop.py --hand-backend rtmpose

# RTMPose-Hand，指定本機姿態模型／偵測器
python run_desktop.py --hand-backend rtmpose --hand-model models\rtmpose-hand.onnx --hand-detector models\rtmdet-hand.onnx

# YOLO Pose，使用自訂 21 特徵點手部模型
python run_desktop.py --hand-backend yolo_pose --hand-model models\hand-pose-21.pt
```

`--hand-device auto|cpu|cuda|mps` 可指定 RTMPose／YOLO 的推論裝置。MediaPipe 在此專案中仍只使用 CPU。

---

## 2. RTMPose-Hand

RTMPose-Hand 是**由上而下（top-down）**的 21 特徵點模型：先取得手部邊界框，再對裁切影像執行姿態模型。`rtmlib` 已提供完整流程：

- 手部偵測器：RTMDet hand ONNX；
- 姿態模型：RTMPose-m SimCC hand（21 特徵點、256×256）；
- `Hand(to_openpose=False)` 回傳 MMPose 順序的特徵點，與 AirCanvas 使用的「手腕 → 拇指 → 食指 → 中指 → 無名指 → 小指」順序一致。

轉接器使用 `rtmlib.Hand`，內部處理偵測與裁切。首次執行會下載預設 ONNX 組合（RTMPose-m hand）；離線部署或使用相容的較大手部 checkpoint 時，請以 `--hand-model` 傳入本機路徑／URL。

```powershell
python -m pip install -r requirements-rtmpose.txt
```

### 重要區別：RTMPose-m/l 的 body 模型不是手部模型

RTMPose-m 與 RTMPose-l 通常是**身體**姿態 checkpoint，輸出身體關鍵點（包含手腕），而不是 21 個手指關節。把 body checkpoint 當成 `--hand-model` 使用，不會產生手部特徵點。Whole-body RTMW checkpoint（133 關鍵點）雖然包含手部點，但需要額外的索引映射轉接器；目前的 RTMPose-Hand 轉接器不處理它。

請改用：

- RTMPose-Hand 模型家族（`rtmlib` 的預設手部組合）；
- 轉換成 ONNX、且輸出契約相同（SimCC、21 特徵點）的手部 checkpoint；
- 自訂的 21 特徵點 YOLO 手部模型（見下節）。

RTMPose-Hand LiteRT 模型卡說明了 21 特徵點拓撲與 SimCC 輸出形狀：[RTMPose-Hand LiteRT](https://huggingface.co/litert-community/RTMPose-Hand-LiteRT)。上游解決方案程式碼：[rtmlib hand.py](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/hand.py)。

---

## 3. YOLO Pose

Ultralytics YOLOv8/YOLO11 Pose 是強大的姿態框架，但官方 `yolov8*-pose.pt` 與 `yolo11*-pose.pt` 權重是在 **17 個 COCO 身體關鍵點**上訓練，無法提供 21 個手部特徵點。

因此 AirCanvas 將 YOLO Pose 支援為**自訂 21 特徵點手部模型**轉接器：

1. 在 21 特徵點手部資料集上訓練（或取得）`kpt_shape: [21, 3]` 的 YOLO Pose 模型。Ultralytics 有手部關鍵點資料集說明：[Hand Keypoints Dataset](https://docs.ultralytics.com/datasets/pose/hand-keypoints)。
2. 在執行 AirCanvas 的 Python 環境安裝 `ultralytics`：
   ```powershell
   python -m pip install -r requirements-yolo.txt
   ```
3. 選擇 **YOLO Pose (21-kp)** 並挑選 `.pt`，或傳入 `--hand-model`。

若模型的關鍵點數不是 21，轉接器會拒絕載入並說明官方 body pose 權重不可用。這是刻意的：把 17 個身體關鍵點硬映射成 21 個手部點，會產生沒有意義的手勢。

該資料集頁面是資料集／訓練資源，不是官方預訓練手部特徵點 checkpoint；你必須自行提供針對 21 特徵點手部任務訓練的權重。

---

## 4. 狀態與失敗行為

模型可用性會出現在共用 session snapshot：

```json
"status": {
  "hand_backend": {
    "key": "rtmpose",
    "label": "RTMPose-Hand",
    "available": false,
    "reason": "rtmlib is not installed",
    "requires": "pip install rtmlib onnxruntime",
    "note": "Top-down RTMPose-Hand ..."
  },
  "hand_backends": ["...catalog..."]
}
```

- 介面會顯示 **● ready** 或 **○ unavailable + 原因**。
- RTMPose 與 YOLO 轉接器不提供左右手判定，因此 `dominant_hand=left/right` 無法過濾它們；系統會選擇信心最高的手。若需要嚴格的慣用手過濾，請使用 MediaPipe。
- 若所選模型無法初始化，AirCanvas 會讓相機與 UI 繼續運作、顯示錯誤，最多每 5 秒重試一次，不會每一幀都寫入日誌。
- **不會**靜默切換回 MediaPipe；靜默後備會讓模型比較失去意義。請在介面明確切換，或使用 `--hand-backend`。

## 5. 設定檔

```json
{
  "camera_index": 0,
  "hand_backend": "rtmpose",
  "hand_model_path": "",
  "hand_detector_path": "",
  "hand_device": "auto"
}
```

YOLO 範例：

```json
{
  "hand_backend": "yolo_pose",
  "hand_model_path": "models/hand-pose-21.pt",
  "hand_device": "cuda"
}
```

## 6. 如何選擇

| 優先順序 | 建議 |
| --- | --- |
| 最低設定成本、穩定的本機示範 | MediaPipe |
| 想用 RTMPose 家族的 21 特徵點模型 | `rtmpose` + `rtmlib`；不要使用 RTMPose body m/l |
| 已有 21 特徵點 YOLO 手部權重 | `yolo_pose` |
| 可重現的研究比較 | 記錄後端、模型路徑／雜湊、裝置、輸入尺寸、信心閾值與 FPS |

所選後端會影響特徵點品質與延遲，但**不會**改變手勢映射、繪圖、追蹤或導覽；那些仍由共用的 Python 核心負責。

## 7. 新增其他模型家族

在 `aircanvas/hand_models.py` 實作 `HandLandmarkBackend`：

- `status()` 回傳 `BackendStatus`（標籤、可用性、缺少依賴／權重的原因、安裝提示）；
- `initialize()` 只載入一次模型；
- `detect(frame_bgr, now, dominant_hand)` 回傳 `HandObservation` 或 `None`；
- `close()` 釋放資源。

接著把鍵值加入 `create_hand_backend()`、`backend_catalog()`，以及桌面／網頁介面的選項。RTMW-133 或未來的 21 特徵點 checkpoint 可以用這種方式加入，不必改動手勢、繪圖或追蹤引擎。
