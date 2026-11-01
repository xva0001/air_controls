# Camera Troubleshooting

## The exact error

```text
[ WARN] VIDEOIO(DSHOW): backend is generally available but can't be used to capture by index
[ WARN] VIDEOIO/FFMPEG: OpenCV should be configured with libavdevice to open a camera device
[ERROR] obsensor::getStreamChannelGroup Camera index out of range
```

This is not proof that the webcam is broken. It means OpenCV's **DirectShow** path did not find a usable camera at the requested index, the **FFmpeg** fallback was not built with camera-device support, and OpenCV's **Obsensor** probe found no depth/camera stream at that index. The three messages commonly appear together when **no camera device is exposed to the Python process**.

In the coding-agent sandbox used for this project, Windows exposed **no Camera-class device** to the process, so every index/backend correctly failed there. The same **global Python 3.15.1** process run outside the sandbox opened the camera through MSMF at 1280×720. Always run the final camera path in a normal desktop session. The labelled simulated feed was used for screenshots.

## Diagnose first

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\diagnose_camera.py --max-index 3
```

Run the probe in the same context in which you launch AirCanvas. Some coding-agent/AppContainer sandboxes block camera device access; a normal PowerShell/desktop session may work even when a sandboxed probe fails. On this machine, the global Python 3.15.1 can open the camera while the sandboxed tool process cannot.

The probe tries cameras 0–3 with **MSMF → DSHOW → OpenCV auto**, reads a frame from each opened device, and prints timings. Interpret it like this:

| Probe result | Meaning | Next step |
| --- | --- | --- |
| MSMF opens and delivers a frame | Media Foundation works | Choose **Media Foundation** in System → Camera backend |
| DSHOW opens and delivers a frame | DirectShow works | Choose **DirectShow** |
| All backends fail to open | No device is visible to this Python session | Check Device Manager/privacy/remote session; try browser camera |
| Opens but delivers no frame | Virtual/busy/empty camera | Close other apps; try another index/backend |
| Works only in browser | Browser has camera permission/device, OpenCV does not | Use the web interface, or fix desktop camera access |

You can also run it from the desktop **Camera is not active** card with the **Diagnose** button.

## Fixes in order

1. **Try Media Foundation.** The desktop app already prefers MSMF, but you can force it:
   ```powershell
   $env:AIRCANVAS_CAMERA_BACKEND="msmf"
   python run_desktop.py --no-onboarding
   ```
   Or use **System → Camera backend → Media Foundation**. Also try another **Camera index** (0, 1, 2, 3). On the current machine, use the global Python 3.15.1 and run outside the coding sandbox:
   ```powershell
   python run_desktop.py --camera-backend msmf --no-onboarding
   # or: run_desktop_global.cmd
   ```
2. **Check Windows camera privacy.** Settings → Privacy & security → Camera → allow desktop apps. If you are in a managed/remote environment, the organization may block camera access.
3. **Close camera users.** Teams, Zoom, OBS Virtual Camera, Windows Camera and some browser tabs can hold the device. Close them and retry.
4. **Check Device Manager.** The camera should appear under **Cameras** or **Imaging devices**, with no warning icon. If it does not appear, reconnect it; if it is a laptop camera, check the hardware privacy shutter/function key.
5. **Test the browser.** Open the local web app:
   ```powershell
   python run_web.py --open
   ```
   Click **Enable camera**. If the browser can use the camera but OpenCV cannot, use the web interface; browser frames are sent to the same local Python core. This can be the simplest workaround in remote/virtualized Windows sessions.
6. **Remote sessions.** Some remote-desktop/VM sessions redirect only the browser's camera, not DirectShow/MSMF. Use the web interface or forward the USB camera to the VM.

## Why the web interface may work when desktop capture does not

The desktop uses `cv2.VideoCapture` through Windows media backends. The web version uses `navigator.mediaDevices.getUserMedia()` in the browser and sends JPEG frames to the local FastAPI service. The browser owns the camera permission and may have access to a redirected camera that the Python process cannot see. Recognition, drawing and tracking still run in the shared Python core.

## What was changed in this build

- Backend order on Windows is now **MSMF → DSHOW → ANY**, not DSHOW-only.
- Each open is validated by requiring an actual frame, so “opened but empty” virtual cameras do not silently break the app.
- The backend probe does not pass unsupported MSMF open-timeout properties (OpenCV 5.0 property 53); each device is validated by reading a real frame instead.
- The backend can be selected in the UI or with `AIRCANVAS_CAMERA_BACKEND`.
- The UI has a **Diagnose** action, and `scripts/diagnose_camera.py` prints a full table.
- Failure messages now explain the backend attempts and offer the simulated/web fallbacks.

If the probe says **no camera delivered a frame** and Windows Device Manager also shows no camera, the limitation is environmental; no Python library can open a device that the operating system does not expose.
