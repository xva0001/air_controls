# Hand Landmark Model Backends

AirCanvas recognises 21 hand landmarks per hand. The model that produces those landmarks is selectable, so you can trade setup complexity against the model family you prefer.

MediaPipe is the bundled default. RTMPose-Hand and YOLO Pose are optional adapters that load lazily and report a clear status when their dependencies or weights are missing.

---

## 1. What is selectable

| Backend | Key | Landmarks | Extra install | Model file |
| --- | --- | --- | --- | --- |
| MediaPipe Hands | `mediapipe` | 21 | none | Bundled `aircanvas/assets/hand_landmarker.task`; optional custom `.task` |
| RTMPose-Hand | `rtmpose` | 21 | `pip install rtmlib onnxruntime` | Optional local `.onnx`/`.zip` or URL; rtmlib downloads the hand detector + pose model on first use |
| YOLO Pose | `yolo_pose` | 21 (custom hand model only) | `pip install ultralytics` | Required `.pt` hand-pose weights |

The desktop UI exposes **System → Hand landmark model**, with a **Choose model…** button and a readiness line. The browser UI exposes the same selectors under **System**; the path is a path on the Python server, not on the browser machine.

Command line:

```powershell
# bundled default
python run_desktop.py --hand-backend mediapipe

# RTMPose-Hand, rtmlib default models
python run_desktop.py --hand-backend rtmpose

# RTMPose-Hand with a local pose model / detector
python run_desktop.py --hand-backend rtmpose --hand-model models\rtmpose-hand.onnx --hand-detector models\rtmdet-hand.onnx

# YOLO Pose with a custom 21-keypoint hand model
python run_desktop.py --hand-backend yolo_pose --hand-model models\hand-pose-21.pt
```

`--hand-device auto|cpu|cuda|mps` selects the inference device for RTMPose/YOLO. MediaPipe remains CPU-only in this project.

---

## 2. RTMPose-Hand

RTMPose-Hand is a **top-down** 21-keypoint model. It needs a hand bounding box first, then runs the pose model on the crop. `rtmlib` provides that complete solution:

- hand detector: RTMDet hand ONNX;
- pose model: RTMPose-m SimCC hand (21 keypoints, 256×256);
- `Hand(to_openpose=False)` returns MMPose-ordered keypoints, which match the wrist → thumb → index → middle → ring → pinky order used by AirCanvas.

The adapter uses `rtmlib.Hand` and handles the detector/crop internally. On first run it downloads the default ONNX bundle (RTMPose-m hand); for offline deployment or a compatible larger hand checkpoint, pass a local path/URL with `--hand-model`.

```powershell
python -m pip install -r requirements-rtmpose.txt
```

### Important distinction: RTMPose-m/l body is not a hand model

RTMPose-m and RTMPose-l are commonly **body** pose checkpoints. They output body keypoints (including a wrist), not 21 finger joints. Selecting a body checkpoint as `--hand-model` will not produce hand landmarks. Whole-body RTMW checkpoints (133 keypoints) do contain hand points, but need an index-mapping adapter; they are not handled by this RTMPose-Hand adapter.

Use one of these instead:

- the RTMPose-Hand model family (the default `rtmlib` hand bundle);
- a hand checkpoint converted to ONNX with the same SimCC 21-keypoint output contract;
- a custom 21-keypoint YOLO hand model (below).

The RTMPose-Hand LiteRT model card documents the 21-keypoint topology and SimCC output shape: [RTMPose-Hand LiteRT](https://huggingface.co/litert-community/RTMPose-Hand-LiteRT). The upstream solution code is [rtmlib hand.py](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/hand.py).

---

## 3. YOLO Pose

Ultralytics YOLOv8/YOLO11 Pose is a strong pose framework, but the stock `yolov8*-pose.pt` and `yolo11*-pose.pt` weights are trained on **17 COCO body keypoints**. They cannot provide 21 hand landmarks.

AirCanvas therefore supports YOLO Pose as a **custom 21-keypoint hand model** adapter:

1. Train (or obtain) a YOLO Pose model with `kpt_shape: [21, 3]` on a 21-keypoint hand dataset. Ultralytics documents a hand-keypoints dataset: [Hand Keypoints Dataset](https://docs.ultralytics.com/datasets/pose/hand-keypoints).
2. Install `ultralytics` in the Python environment that runs AirCanvas:
   ```powershell
   python -m pip install -r requirements-yolo.txt
   ```
3. Select **YOLO Pose (21-kp)** and choose the `.pt` file, or pass `--hand-model`.

The adapter rejects a model whose keypoint count is not 21 and explains that stock body-pose weights are not usable. This is intentional: silently mapping 17 body keypoints into 21 hand points would produce meaningless gestures.

The dataset page is a dataset/training resource, not an official pretrained hand-landmark checkpoint. You must supply weights trained for the 21-keypoint hand task.

---

## 4. Status and failure behaviour

Model availability is reported in the shared session snapshot:

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

- The UI shows **● ready** or **○ unavailable + reason**.
- RTMPose and YOLO adapters do not expose handedness, so `dominant_hand=left/right` cannot filter them; the highest-confidence hand is selected. Use MediaPipe if strict handedness filtering matters.
- If a selected model cannot initialise, AirCanvas keeps the camera and UI running, shows an error, and retries at most every 5 seconds instead of logging on every frame.
- It does **not** silently switch to MediaPipe. A silent fallback would make model comparison misleading. Switch explicitly in the UI or with `--hand-backend`.

## 5. Configuration file

```json
{
  "camera_index": 0,
  "hand_backend": "rtmpose",
  "hand_model_path": "",
  "hand_detector_path": "",
  "hand_device": "auto"
}
```

For YOLO:

```json
{
  "hand_backend": "yolo_pose",
  "hand_model_path": "models/hand-pose-21.pt",
  "hand_device": "cuda"
}
```

## 6. Choosing a model

| Priority | Recommendation |
| --- | --- |
| Lowest setup, robust local demo | MediaPipe |
| 21-keypoint RTMPose family | `rtmpose` + `rtmlib`; do not use RTMPose body m/l |
| Existing 21-keypoint YOLO hand weights | `yolo_pose` |
| Reproducible research comparison | Record backend, model path/hash, device, input size, confidence threshold and FPS |

The selected backend affects landmark quality and latency, but it does **not** change gesture mapping, drawing, tracking or navigation. Those remain in the shared Python core.

## 7. Adding another model family

Implement `HandLandmarkBackend` in `aircanvas/hand_models.py`:

- `status()` returns a `BackendStatus` (label, availability, missing dependency/weight reason, install hint);
- `initialize()` loads the model once;
- `detect(frame_bgr, now, dominant_hand)` returns a `HandObservation` or `None`;
- `close()` releases resources.

Then add the key to `create_hand_backend()` and `backend_catalog()`, plus a select option in the desktop/web UI. RTMW-133 or a future 21-keypoint checkpoint can be added this way without touching the gesture, drawing or tracking engines.
