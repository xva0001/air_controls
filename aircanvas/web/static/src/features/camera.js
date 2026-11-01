'use strict';

import { state } from '../core/state.js';
import { els, captureCtx, setText, setPill, toast } from '../core/ui.js';
import { send } from '../core/bridge.js';

/** Browser camera capture, simulated-feed handoff and start-panel state. */
/* ------------------------------------------------------------------ camera */
export function secureCameraContext() {
  if (!window.isSecureContext && !['localhost', '127.0.0.1', '::1'].includes(location.hostname)) {
    return 'Camera access requires a secure context. Open this app through localhost or HTTPS.';
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    return 'This browser does not expose the camera API. Try a current Chrome, Edge or Firefox build.';
  }
  return '';
}

export async function enableCamera(deviceId = '') {
  const problem = secureCameraContext();
  if (problem) {
    state.cameraStatus = 'error';
    state.cameraError = problem;
    updateCameraPill();
    updateStartPanel();
    send({ type: 'camera_status', status: 'error', message: problem });
    return;
  }
  state.manualOnly = false;
  if (state.demo) {
    state.demo = false;
    state.wantDemo = false;
    send({ type: 'demo', enabled: false });
  }
  await stopCamera(false);
  try {
    const constraints = {
      audio: false,
      video: {
        width: { ideal: 1280 }, height: { ideal: 720 },
        facingMode: 'user',
        ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
      },
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    state.cameraStream = stream;
    state.cameraStatus = 'live';
    state.cameraError = '';
    els.cameraVideo.srcObject = stream;
    await els.cameraVideo.play().catch(() => {});
    hideStartPanel();
    updateCameraPill();
    startCaptureLoop();
    const track = stream.getVideoTracks()[0];
    const settings = track?.getSettings?.() || {};
    state.cameraDeviceId = settings.deviceId || deviceId || '';
    await refreshCameraDevices();
    send({
      type: 'camera_status', status: 'live', message: 'Browser camera live',
      width: settings.width || els.cameraVideo.videoWidth || 0,
      height: settings.height || els.cameraVideo.videoHeight || 0,
    });
    toast('Camera live — frames stay on this machine.', 'success', 2600);
  } catch (error) {
    const message = cameraErrorMessage(error);
    state.cameraStatus = 'error';
    state.cameraError = message;
    updateCameraPill();
    updateStartPanel();
    send({ type: 'camera_status', status: 'error', message });
    toast(message, 'error', 5000);
  }
}

export function cameraErrorMessage(error) {
  switch (error?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Camera permission was blocked. Allow it in the address bar, then retry.';
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No usable camera was found. Connect a webcam or use the simulated feed.';
    case 'NotReadableError':
      return 'The camera is busy in another application. Close it and retry.';
    case 'AbortError':
      return 'The camera stopped before it could start. Retry or use the simulated feed.';
    default:
      return `Camera could not start${error?.message ? `: ${error.message}` : '.'}`;
  }
}

export async function stopCamera(notify = true) {
  stopCaptureLoop();
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
    state.cameraStream = null;
  }
  if (els.cameraVideo.srcObject) els.cameraVideo.srcObject = null;
  state.cameraStatus = 'off';
  updateCameraPill();
  if (notify) send({ type: 'camera_status', status: 'stopped', message: 'Camera stopped' });
}

export function startCaptureLoop() {
  stopCaptureLoop();
  if (!state.cameraStream) return;
  state.captureTimer = setInterval(captureFrame, 85);
}

export function stopCaptureLoop() {
  if (state.captureTimer) clearInterval(state.captureTimer);
  state.captureTimer = null;
}

export function captureFrame() {
  const video = els.cameraVideo;
  if (!state.cameraStream || state.demo || document.hidden) return;
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  if (state.ws.bufferedAmount > 1_400_000) return;
  if (!video.videoWidth || !video.videoHeight || video.readyState < 2) return;
  const width = Math.min(720, video.videoWidth);
  const height = Math.max(2, Math.round(video.videoHeight * (width / video.videoWidth)));
  const canvas = els.captureCanvas;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = captureCtx;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, width, height);
  if (state.config.mirror_camera) {
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
  }
  ctx.drawImage(video, 0, 0, width, height);
  const data = canvas.toDataURL('image/jpeg', 0.64);
  if (data.length > 3_200_000) return;
  send({ type: 'frame', image: data });
}

export async function refreshCameraDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter((device) => device.kind === 'videoinput');
    const current = els.cameraDevice.value;
    els.cameraDevice.innerHTML = '<option value="">Default camera</option>';
    cameras.forEach((camera, index) => {
      const option = document.createElement('option');
      option.value = camera.deviceId;
      option.textContent = camera.label || `Camera ${index + 1}`;
      els.cameraDevice.appendChild(option);
    });
    const selected = state.cameraDeviceId || current;
    if (selected && cameras.some((camera) => camera.deviceId === selected)) {
      els.cameraDevice.value = selected;
    }
  } catch (_) { /* labels require permission; not fatal */ }
}

export function updateCameraPill() {
  let text = 'CAMERA OFF';
  let tone = 'muted';
  if (state.demo) { text = 'SIMULATED'; tone = 'amber'; }
  else if (state.cameraStatus === 'live') { text = 'CAMERA LIVE'; tone = 'mint'; }
  else if (state.cameraStatus === 'error') { text = 'CAMERA ERROR'; tone = 'danger'; }
  setPill(els.cameraPill, text, tone);
  setText(els.cameraPillText, text);
  setText(els.demoChip, state.demo ? 'SIMULATED' : '');
  els.demoChip.hidden = !state.demo;
}

/* ------------------------------------------------------------------ demo */
export function startDemo(seek = 0) {
  state.manualOnly = false;
  state.startPanelDismissed = false;
  state.wantDemo = true;
  state.demoSeek = Math.max(0, Math.min(20, Number(seek) || 0));
  state.demo = true;
  state.demoImage = null;
  state.demoSeq = 0;
  state.demoSeqApplied = 0;
  stopCamera(false);
  hideStartPanel();
  updateCameraPill();
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    send({ type: 'demo', enabled: true, seek: state.demoSeek });
    toast('Simulated feed running — the real gesture core is in control.', 'warning', 3000);
  }
}

export function stopDemo(notify = true) {
  state.wantDemo = false;
  state.demo = false;
  state.demoImage = null;
  state.demoSeqApplied = 0;
  if (notify) send({ type: 'demo', enabled: false });
  updateCameraPill();
  updateStartPanel();
}

/* ------------------------------------------------------------------ start panel */
export function updateStartPanel() {
  if (state.demo || state.cameraStream) { hideStartPanel(); return; }
  if (state.manualOnly) { hideStartPanel(); return; }
  if (!state.connected) {
    els.startPanelTitle.textContent = 'Connecting to the local service';
    els.startPanelBody.textContent = 'The browser UI is ready. Waiting for the Python core to accept the local WebSocket connection.';
    els.startPanel.hidden = false;
    return;
  }
  if (state.cameraStatus === 'error') {
    els.startPanelTitle.textContent = 'Camera unavailable';
    els.startPanelBody.textContent = state.cameraError || 'Check browser camera permissions, or continue with the simulated feed.';
  } else {
    els.startPanelTitle.textContent = 'Bring your own camera';
    els.startPanelBody.textContent = 'AirCanvas uses your webcam locally. The browser will ask for permission; frames are sent only to the Python service on this machine.';
  }
  els.startPanel.hidden = false;
}
export function hideStartPanel() { els.startPanel.hidden = true; }


