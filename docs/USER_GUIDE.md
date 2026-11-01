# AirCanvas — User Guide

Welcome to AirCanvas. You can draw in the air, annotate a camera feed, move a cursor, navigate with deliberate swipes, and circle an object to track it. Everything runs locally.

This guide covers both the desktop application and the browser interface.

---

## 1. Start the app

### Desktop

On this workstation, use the verified **global Python 3.15.1** path in a normal PowerShell window:

```powershell
run_desktop_global.cmd
# equivalent:
python run_desktop.py --camera-backend msmf --no-onboarding
```

For a fresh machine with a venv:

```powershell
python run_desktop.py
```

- **Camera** opens automatically. If no camera exists, choose **Use simulated feed** or draw with the mouse.
- Choose **System → Camera backend** if MSMF/DSHOW needs switching.
- Choose **System → Hand landmark model** to switch between MediaPipe, RTMPose-Hand and a custom 21-keypoint YOLO Pose `.pt`. The readiness line tells you what is missing; see [HAND_MODEL_BACKENDS.md](HAND_MODEL_BACKENDS.md).
- `--demo` starts the labelled simulated feed immediately.
- `--mode mirror --tool track --demo` jumps straight to object tracking.
- Camera access must happen outside a coding-agent sandbox; otherwise Windows may hide the device from the process.

### Web

```powershell
python run_web.py --open
```

- Allow the browser camera when prompted.
- No camera? Choose **Simulated feed** or **Draw with mouse**.
- Camera access requires `localhost` or HTTPS. Do not open the service through a LAN IP over plain HTTP.

---

## 2. The 30-second version

1. Pick **Screen** or **Mirror** at the top.
2. Pick a tool on the left.
3. Show your hand to the camera. Wait for the hand skeleton and pose name to appear.
4. **Point** to draw. Make a deliberate loop and stop briefly; Smart shapes will clean it into a circle.
5. **Pinch** to click, drag or remove a marker.
6. **Open palm, hold, then swipe** to navigate.
7. In Mirror → Track, draw a loop around an object and hold still to start tracking.
8. Use `Ctrl+Z` whenever something goes wrong.

---

## 3. Modes

### Screen Mode

- **Built-in canvas** (desktop and web): draw on the cream artboard.
- **Desktop overlay** (desktop only): draws over other applications in a transparent, click-through layer. The small floating toolbar controls Undo, Clear and Exit.
- **Navigate**: open-palm swipes; two-finger page swipes.
- **Mouse**: virtual/OS cursor, pinch click/drag.

### Mirror Mode

- **Annotate**: draw directly over the camera feed. Annotations stay aligned with the video.
- **Track**: draw a loop around an object, hold to select, then move the object and watch the marker follow. Occlusion is handled; leaving the frame stops tracking.

---

## 4. Tools at a glance

| Tool | Gesture | What happens |
| --- | --- | --- |
| Draw | Point | Freehand stroke |
| Navigate | Open palm + hold + swipe | Scroll / back / forward |
| Navigate | Two fingers + hold + horizontal swipe | Previous / next page |
| Mouse | Pinch | Left click; keep pinched to drag |
| Mouse | Two fingers held | Right click |
| Annotate | Point | Draw on the camera image |
| Track | Point loop + hold | Select and track an object |
| Track | Pinch on a marker | Remove it |

Shortcuts: `1` Screen, `2` Mirror, `D` Draw, `N` Navigate, `M` Mouse, `A` Annotate, `T` Track, `F1` help, `Ctrl+Z` undo, `Ctrl+Shift+Z` redo, `Ctrl+S` export.

---

## 5. Tips for reliable recognition

- Use even, front lighting; avoid a bright window directly behind you.
- Keep your whole hand in the frame, roughly 40–100 cm from the camera.
- Hold a pose for a moment. The stabiliser deliberately ignores one-frame flicker.
- Do not move your hand while arming navigation; move only after the ring fills.
- For a circle, draw one continuous loop and stop briefly. Overshoot is tolerated.
- For tracking, circle the whole object and hold still until the marker appears.
- If the hand feels mirrored, toggle **Mirror camera** in the inspector.
- Left-handed? Enable **Left-handed layout** to move the controls to your preferred side.

---

## 6. Tuning

Open the inspector (desktop right panel; web **Controls** at narrow widths).

| Control | What to change |
| --- | --- |
| Pinch sensitivity | Increase if pinch does not trigger; decrease if it triggers too easily |
| Pointer smoothing | Higher is calmer but laggier; lower is snappier |
| Navigation hold | Increase if swipes fire accidentally; decrease if navigation feels slow |
| Pose stability | More frames = fewer false activations, more delay |
| Draw / click / right-click / nav / page mappings | Assign the poses you find comfortable |
| Dominant hand | Auto, left or right |
| Mirror camera | Selfie view and annotation alignment |
| Show landmarks | Skeleton overlay only; detection continues when hidden |

Desktop OS mouse and system navigation are off by default. Enabling them shows a confirmation that explains the risk. Browser sessions cannot enable OS control.

---

## 7. Undo, clear, export

- Undo/redo covers strokes, shape corrections, erase and clear. History is per surface (Screen vs Mirror).
- Clear is reversible: if you clear by mistake, press `Ctrl+Z`.
- Export PNG (`Ctrl+S`) renders the artwork at 1920×1080 without UI chrome. In Mirror mode, the current camera frame and annotations/markers are included.
- Tracking markers are removed explicitly, not by undo; use the × in the tracked-objects list or pinch over a marker.

---

## 8. Camera troubleshooting

If the desktop app cannot open a camera, first run the standalone probe:

```powershell
python scripts/diagnose_camera.py --max-index 3
```

It tries every relevant OpenCV backend for cameras 0–3 and shows whether the device opens and actually delivers a frame. This build tries **MSMF → DSHOW → OpenCV auto** on Windows; the exact error is also written to the app log. The camera backend can be changed in **System → Camera backend** without restarting the app.

| Problem | What to do |
| --- | --- |
| `VIDEOIO(DSHOW) ... can't be used to capture by index` | Usually means no DirectShow device is exposed. Try backend **Media Foundation**, then **OpenCV auto**; run the probe |
| No camera found | Check Windows Settings → Privacy & security → Camera; check Device Manager; close other camera apps; use Simulated feed |
| Camera works in the browser but not desktop | OpenCV/Windows cannot see the device in this session. Use the web interface, or fix the desktop camera privacy/backend; run the probe |
| Permission denied (web) | Click the camera icon in the address bar and allow, then Retry |
| Page opened via LAN HTTP | Use `http://localhost:8765` or `https://`; camera requires a secure context |
| Camera busy | Close Teams/Zoom/OBS virtual camera; retry |
| Camera opened but no frame | Try a different backend/index; some virtual cameras report opened but never deliver frames |
| Hand not detected | Improve lighting, show the whole hand, move closer, check dominant hand setting |
| Gesture fires too easily | Lower sensitivity, increase stability/navigation hold |
| Gesture does not fire | Raise pinch sensitivity, hold the pose longer, check mapping |
| Tracking loses the object | Avoid full occlusion; keep the object in frame; re-select |
| Desktop overlay covers everything | Use the floating toolbar's Exit; the canvas is click-through by design |
| Web service disconnected | Restart `run_web.py`; the page reconnects automatically |

---

## 9. Privacy

AirCanvas processes camera frames in memory on your computer. It does not upload or store them. The web service binds to loopback and has no telemetry. Simulated feeds are always labelled `SIMULATED` so screenshots and demonstrations cannot be mistaken for live camera input.

If you expose the web service to a network, you take on authentication, TLS and privacy responsibilities that this local-first project does not provide.

---

## 10. Keyboard and mouse fallbacks

You do not need a camera to use the app:

- Use the mouse to draw/annotate.
- Use keyboard shortcuts for modes, tools, undo/redo, help and export.
- Use the tracking list × buttons to remove markers.
- Choose the simulated feed to see the full gesture feedback and tracking pipeline.

If gestures are difficult due to motor fatigue or lighting, adjust sensitivity/hold times or switch to mouse drawing. The app is designed for that combination, not as an afterthought.
