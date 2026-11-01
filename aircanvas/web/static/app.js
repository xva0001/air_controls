'use strict';

/* AirCanvas web client.
 * The browser is deliberately a renderer + camera transport. Gesture
 * recognition, mapping, drawing, shape correction and tracking all run in the
 * shared Python core over the local WebSocket.
 *
 * Structure mirrors a small Vue-style app without a build step:
 *   core/       constants, state, DOM helpers, utilities
 *   render/     canvas stage + hand preview
 *   features/   camera / config / snapshot controllers
 *   app.js      orchestration and bindings (this file)
 */

import { DEFAULT_CONFIG } from './src/core/constants.js';
import { activeTool, state } from './src/core/state.js';
import {
  els,
  stageCtx,
  stageMetrics,
  cacheElements,
  setText,
  toast,
  setSwitch,
} from './src/core/ui.js';
import { send } from './src/core/bridge.js';
import { activeRect, exportPng, renderLoop, renderStage, syncCanvasSize } from './src/render/stage.js';
import { applySnapshot } from './src/features/snapshot.js';
import {
  enableCamera,
  hideStartPanel,
  startCaptureLoop,
  startDemo,
  stopCaptureLoop,
  stopDemo,
  updateCameraPill,
  updateStartPanel,
} from './src/features/camera.js';
import {
  applyServerModeTool,
  hydrateConfig,
  normalizeConfig,
  patchConfig,
  setupMappingOptions,
} from './src/features/config.js';
import {
  setMode,
  setTool,
  updateModeUI,
  updateToolUI,
  updateSmartPill,
} from './src/ui/mode-tool.js';

function init() {
  cacheElements();
  setupMappingOptions();
  bindUI();
  hydrateConfig(DEFAULT_CONFIG);
  parseUrlOptions();
  updateModeUI(state.config.mode, { send: false });
  updateToolUI(activeTool(), { send: false });
  connect();
  requestAnimationFrame(renderLoop);
  setInterval(updateFpsPill, 1000);
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1120) closeDrawers();
    syncCanvasSize();
  });
  const observer = new ResizeObserver(syncCanvasSize);
  observer.observe(els.stageShell);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopCaptureLoop();
    } else if (state.cameraStream) {
      startCaptureLoop();
    }
  });
  window.addEventListener('beforeunload', cleanup);
}

document.addEventListener('DOMContentLoaded', init);

function parseUrlOptions() {
  const params = new URLSearchParams(location.search);
  const intro = params.get('intro');
  let welcomed = false;
  try { welcomed = localStorage.getItem('aircanvas_welcomed') === '1'; } catch (_) { /* private mode */ }
  state.skipIntro = intro === '0' || welcomed;
  state.autoDemo = params.get('demo') === '1';
  state.autoDemoSeek = Math.max(0, Math.min(20, parseFloat(params.get('seek') || '0') || 0));
  state.urlMode = ['screen', 'mirror'].includes(params.get('mode')) ? params.get('mode') : null;
  state.urlTool = params.get('tool');
  if (state.urlMode) state.config.mode = state.urlMode;
  if (state.urlTool) {
    if (state.config.mode === 'screen' && ['draw', 'navigate', 'mouse'].includes(state.urlTool)) state.config.tool = state.urlTool;
    if (state.config.mode === 'mirror' && ['annotate', 'track'].includes(state.urlTool)) state.config.mirror_tool = state.urlTool;
  }
  if (state.autoDemo) state.skipIntro = true;
}

/* ------------------------------------------------------------------ WebSocket */
function connect() {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${scheme}://${location.host}/ws`);
  state.ws = socket;
  socket.addEventListener('open', () => {
    state.connected = true;
    state.reconnectDelay = 900;
    els.connectionStatus.classList.add('connected');
    setText(els.connectionStatus.querySelector('span:last-child'), 'LOCAL');
    setText(els.serviceState, 'connected');
    send({ type: 'hello', config: state.config });
    if (state.wantDemo) {
      setTimeout(() => {
        if (state.wantDemo) send({ type: 'demo', enabled: true, seek: state.demoSeek });
      }, 180);
    }
  });
  socket.addEventListener('message', (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch (_) { return; }
    handleMessage(message);
  });
  socket.addEventListener('close', () => {
    state.connected = false;
    els.connectionStatus.classList.remove('connected');
    setText(els.connectionStatus.querySelector('span:last-child'), 'OFFLINE');
    setText(els.serviceState, 'connecting…');
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(connect, state.reconnectDelay);
    state.reconnectDelay = Math.min(5000, state.reconnectDelay * 1.5);
  });
  socket.addEventListener('error', () => {
    try { socket.close(); } catch (_) {}
  });
}

function handleMessage(message) {
  switch (message.type) {
    case 'ready':
      state.features = message.features || {};
      break;
    case 'configured':
      state.configured = true;
      state.features = message.features || state.features;
      state.config = normalizeConfig(message.config || state.config);
      hydrateConfig(state.config);
      if (state.autoDemo && !state.autoDemoLaunched) {
        state.autoDemoLaunched = true;
        startDemo(state.autoDemoSeek);
      } else if (!state.skipIntro && !state.autoDemo && !state.introShown) {
        state.introShown = true;
        openModal(els.welcomeDialog);
      }
      updateStartPanel();
      break;
    case 'state':
      handleSnapshot(message);
      break;
    case 'error':
      toast(message.message || 'The local service reported an error.', 'error', 4200);
      break;
    case 'pong':
      break;
    default:
      break;
  }
}

function handleSnapshot(message) {
  if (message.seq && message.seq < state.lastSeq) return;
  state.lastSeq = message.seq || state.lastSeq;
  state.snapshot = message.state;
  if (message.frame) {
    if (state.snapshot?.camera?.source === 'demo' || state.snapshot?.camera?.status === 'demo') state.demo = true;
    loadDemoFrame(message.frame, message.seq);
  }
  if (state.snapshot) {
    state.config = normalizeConfig(state.snapshot.config || state.config);
    applyServerModeTool();
    applySnapshot(state.snapshot);
  }
}

function loadDemoFrame(data, seq) {
  const img = new Image();
  state.demoSeq = Math.max(state.demoSeq, seq || 0);
  img.onload = () => {
    if ((seq || 0) >= (state.demoSeqApplied || 0)) {
      state.demoImage = img;
      state.demoSeqApplied = seq || 0;
      state.demo = true;
      setText(els.demoChip, 'SIMULATED');
      els.demoChip.hidden = false;
      updateCameraPill();
    }
  };
  img.src = data;
}

/* ------------------------------------------------------------------ bind UI */
function bindUI() {
  document.querySelectorAll('.mode-tab').forEach((btn) => {
    btn.addEventListener('click', () => setMode(btn.dataset.mode));
  });
  els.toolList.querySelectorAll('.tool-btn').forEach((btn) => {
    btn.addEventListener('click', () => setTool(btn.dataset.tool));
  });

  document.querySelectorAll('.swatch').forEach((swatch) => {
    swatch.addEventListener('click', () => {
      const color = swatch.dataset.color;
      state.config.brush_color = color;
      document.querySelectorAll('.swatch').forEach((s) => s.classList.toggle('active', s === swatch));
      setText(els.brushColorLabel, color.toUpperCase());
      patchConfig({ brush_color: color }, 0);
      closeDrawersIfMobile();
    });
  });
  els.brushWidth.addEventListener('input', () => {
    const value = Number(els.brushWidth.value);
    els.brushWidthValue.textContent = `${value} px`;
    state.config.brush_width = value;
    patchConfig({ brush_width: value }, 90);
  });
  els.smartShapes.addEventListener('click', () => {
    const on = !els.smartShapes.classList.contains('on');
    setSwitch(els.smartShapes, on);
    state.config.auto_shapes = on;
    updateSmartPill();
    patchConfig({ auto_shapes: on }, 0);
    toast(on ? 'Smart shape correction enabled' : 'Freehand drawing — correction off', on ? 'success' : 'info', 1700);
  });
  els.securityLink.addEventListener('click', (event) => { event.preventDefault(); openModal(els.securityDialog); });

  document.querySelectorAll('.quick-btn').forEach((btn) => {
    btn.addEventListener('click', () => handleQuickAction(btn.dataset.action));
  });
  els.startCameraBtn.addEventListener('click', () => enableCamera());
  els.startDemoBtn.addEventListener('click', () => startDemo(0));
  els.startMouseBtn.addEventListener('click', () => {
    state.manualOnly = true;
    hideStartPanel();
    toast('Mouse drawing ready. Enable a camera anytime from the camera status pill.', 'info', 3200);
    els.stageCanvas.focus();
  });
  els.cameraPill.addEventListener('click', () => {
    if (state.demo) { toast('Simulated feed is active. Choose Enable camera to switch.', 'info'); return; }
    state.manualOnly = false;
    updateStartPanel();
    els.startPanel.hidden = false;
    els.startPanelTitle.focus?.();
  });
  els.helpBtn.addEventListener('click', () => openModal(els.helpDialog));
  els.closeHelp.addEventListener('click', () => closeModal(els.helpDialog));
  els.helpDone.addEventListener('click', () => closeModal(els.helpDialog));
  els.closeSecurity.addEventListener('click', () => closeModal(els.securityDialog));
  els.securityDone.addEventListener('click', () => closeModal(els.securityDialog));
  els.closeWelcome.addEventListener('click', () => closeWelcome());
  els.welcomeCamera.addEventListener('click', () => { closeWelcome(true); enableCamera(); });
  els.welcomeDemo.addEventListener('click', () => { closeWelcome(true); startDemo(0); });
  els.welcomeMouse.addEventListener('click', () => {
    closeWelcome(true);
    state.manualOnly = true;
    hideStartPanel();
    toast('Mouse drawing ready. Use the canvas directly, or enable a camera anytime.', 'info', 3600);
    els.stageCanvas.focus();
  });

  els.mapDraw.addEventListener('change', () => {});
  els.pinchSensitivity.addEventListener('input', () => {
    const v = Number(els.pinchSensitivity.value);
    els.pinchSensitivityValue.textContent = `${v}%`;
    patchConfig({ gesture: { pinch_sensitivity: v / 100 } }, 90);
  });
  els.cursorSmoothing.addEventListener('input', () => {
    const v = Number(els.cursorSmoothing.value);
    els.cursorSmoothingValue.textContent = `${v}%`;
    patchConfig({ gesture: { cursor_smoothing: v / 100 } }, 90);
  });
  els.navHold.addEventListener('input', () => {
    const v = Number(els.navHold.value);
    els.navHoldValue.textContent = `${v} ms`;
    patchConfig({ gesture: { nav_hold_ms: v } }, 90);
  });
  els.poseStability.addEventListener('input', () => {
    const v = Number(els.poseStability.value);
    els.poseStabilityValue.textContent = `${v} frames`;
    patchConfig({ gesture: { stability_frames: v } }, 90);
  });
  els.mirrorCamera.addEventListener('click', () => {
    const on = !els.mirrorCamera.classList.contains('on');
    setSwitch(els.mirrorCamera, on);
    state.config.mirror_camera = on;
    patchConfig({ mirror_camera: on }, 0);
  });
  els.showLandmarks.addEventListener('click', () => {
    const on = !els.showLandmarks.classList.contains('on');
    setSwitch(els.showLandmarks, on);
    state.config.show_landmarks = on;
    patchConfig({ show_landmarks: on }, 0);
  });
  els.leftHanded.addEventListener('click', () => {
    const on = !els.leftHanded.classList.contains('on');
    setSwitch(els.leftHanded, on);
    state.leftHanded = on;
    state.config.gesture.left_handed = on;
    document.body.classList.toggle('left-handed', on);
    patchConfig({ gesture: { left_handed: on } }, 0);
  });
  els.dominantHand.addEventListener('change', () => {
    patchConfig({ gesture: { dominant_hand: els.dominantHand.value } }, 0);
  });
  els.handModel.addEventListener('change', () => {
    const backend = els.handModel.value;
    const allowed = { mediapipe: ['.task'], rtmpose: ['.onnx', '.zip', '.tflite'], yolo_pose: ['.pt'] }[backend] || [];
    let path = state.config.hand_model_path || '';
    if (path && !allowed.some((ext) => path.toLowerCase().endsWith(ext))) path = '';
    state.config.hand_model_path = path;
    els.handModelPath.value = path;
    patchConfig({ hand_backend: backend, hand_model_path: path }, 0);
  });
  els.handModelPath.addEventListener('change', () => {
    patchConfig({ hand_model_path: els.handModelPath.value.trim() }, 0);
  });
  els.handModelPath.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') els.handModelPath.blur();
  });
  els.cameraDevice.addEventListener('change', () => {
    state.cameraDeviceId = els.cameraDevice.value;
    if (state.cameraStream) enableCamera(state.cameraDeviceId);
  });
  els.clearTracks.addEventListener('click', () => send({ type: 'action', name: 'clear_tracks' }));
  els.toolsToggle.addEventListener('click', () => toggleDrawer('tools'));
  els.controlsToggle.addEventListener('click', () => toggleDrawer('inspector'));
  els.closeTools.addEventListener('click', closeDrawers);
  els.closeInspector.addEventListener('click', closeDrawers);
  els.drawerBackdrop.addEventListener('click', closeDrawers);

  els.stageCanvas.addEventListener('pointerdown', onPointerDown);
  els.stageCanvas.addEventListener('pointermove', onPointerMove);
  els.stageCanvas.addEventListener('pointerup', onPointerUp);
  els.stageCanvas.addEventListener('pointercancel', onPointerUp);
  els.stageCanvas.addEventListener('pointerleave', (event) => {
    if (event.buttons === 0) state.trail = [];
  });

  window.addEventListener('keydown', onKeyDown);
  document.querySelectorAll('dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) closeModal(dialog);
    });
  });
}

function handleQuickAction(action) {
  if (action === 'undo') send({ type: 'action', name: 'undo' });
  else if (action === 'redo') send({ type: 'action', name: 'redo' });
  else if (action === 'clear') {
    send({ type: 'action', name: 'clear' });
    toast('Canvas cleared — Ctrl+Z restores it.', 'info', 2400);
  } else if (action === 'export') {
    exportPng();
  }
}

/* ------------------------------------------------------------------ keyboard & drawers */
function onKeyDown(event) {
  const tag = event.target?.tagName;
  if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(tag) && !event.ctrlKey && event.key !== 'Escape') {
    // Keep typing/navigation inside form controls, except global mode keys.
    if (tag !== 'BUTTON') return;
  }
  const key = event.key.toLowerCase();
  if (event.ctrlKey || event.metaKey) {
    if (key === 'z') {
      event.preventDefault();
      send({ type: 'action', name: event.shiftKey ? 'redo' : 'undo' });
    } else if (key === 'y') {
      event.preventDefault();
      send({ type: 'action', name: 'redo' });
    } else if (key === 's') {
      event.preventDefault();
      exportPng();
    }
    return;
  }
  if (event.altKey) return;
  if (key === '1') { event.preventDefault(); setMode('screen'); }
  else if (key === '2') { event.preventDefault(); setMode('mirror'); }
  else if (key === 'd' && state.config.mode === 'screen') setTool('draw');
  else if (key === 'n' && state.config.mode === 'screen') setTool('navigate');
  else if (key === 'm' && state.config.mode === 'screen') setTool('mouse');
  else if (key === 'a' && state.config.mode === 'mirror') setTool('annotate');
  else if (key === 't' && state.config.mode === 'mirror') setTool('track');
  else if (key === 'delete' || key === 'backspace') {
    if (tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'TEXTAREA') {
      event.preventDefault();
      send({ type: 'action', name: 'clear' });
      toast('Canvas cleared — Ctrl+Z restores it.', 'info', 2200);
    }
  } else if (key === 'f1') {
    event.preventDefault();
    openModal(els.helpDialog);
  } else if (key === 'escape') {
    closeModal(els.helpDialog);
    closeModal(els.securityDialog);
    closeDrawers();
    if (state.startPanel && !els.startPanel.hidden && state.cameraStatus !== 'error') hideStartPanel();
  }
}

function toggleDrawer(name) {
  closeDrawers(name);
  document.body.classList.toggle(name === 'tools' ? 'tools-open' : 'inspector-open');
  const open = document.body.classList.contains(name === 'tools' ? 'tools-open' : 'inspector-open');
  els.drawerBackdrop.hidden = !open;
}

function closeDrawers(keep) {
  if (keep !== 'tools') document.body.classList.remove('tools-open');
  if (keep !== 'inspector') document.body.classList.remove('inspector-open');
  els.drawerBackdrop.hidden = true;
}
function closeDrawersIfMobile() { if (window.innerWidth <= 820) closeDrawers(); }

/* ------------------------------------------------------------------ dialogs */
function openModal(dialog) {
  if (!dialog) return;
  try { dialog.showModal(); } catch (_) { dialog.setAttribute('open', ''); }
}
function closeModal(dialog) {
  if (!dialog) return;
  try { dialog.close(); } catch (_) { dialog.removeAttribute('open'); }
}
function closeWelcome(skipPanel = false) {
  closeModal(els.welcomeDialog);
  try { localStorage.setItem('aircanvas_welcomed', '1'); } catch (_) {}
  if (!skipPanel) {
    state.manualOnly = false;
    updateStartPanel();
  }
}

/* ------------------------------------------------------------------ snapshot -> UI */
/* ------------------------------------------------------------------ drawing input */
function onPointerDown(event) {
  if (event.button !== 0) return;
  if (!isManualDrawingAllowed()) return;
  const point = pointFromCanvas(event);
  if (!point) return;
  event.preventDefault();
  els.stageCanvas.setPointerCapture(event.pointerId);
  state.manualDrawing = { pointerId: event.pointerId, last: point, lastSent: performance.now() };
  send({ type: 'pointer', phase: 'start', x: point.x, y: point.y });
}

function onPointerMove(event) {
  if (!state.manualDrawing || event.pointerId !== state.manualDrawing.pointerId) return;
  const point = pointFromCanvas(event);
  if (!point) return;
  const now = performance.now();
  if (now - state.manualDrawing.lastSent < 24) return;
  state.manualDrawing.lastSent = now;
  state.manualDrawing.last = point;
  send({ type: 'pointer', phase: 'move', x: point.x, y: point.y });
}

function onPointerUp(event) {
  if (!state.manualDrawing || (event.pointerId !== undefined && event.pointerId !== state.manualDrawing.pointerId)) return;
  state.manualDrawing = null;
  send({ type: 'pointer', phase: 'end' });
}

function isManualDrawingAllowed() {
  if (state.config.mode === 'screen') return state.config.tool === 'draw';
  return state.config.mirror_tool === 'annotate';
}

function pointFromCanvas(event) {
  const rect = els.stageCanvas.getBoundingClientRect();
  const active = activeRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  if (x < active.x || x > active.x + active.w || y < active.y || y > active.y + active.h) return null;
  return {
    x: Math.max(0, Math.min(1, (x - active.x) / active.w)),
    y: Math.max(0, Math.min(1, (y - active.y) / active.h)),
  };
}

function updateFpsPill() {
  // Camera FPS is not a reliable browser metric; the Python recognition rate is
  // shown in the inspector and footer. This keeps the top-bar rate current.
  if (state.snapshot?.stats) {
    setText(els.metricFps, Number(state.snapshot.stats.fps || 0).toFixed(1));
  }
}

function cleanup() {
  stopCaptureLoop();
  if (state.cameraStream) state.cameraStream.getTracks().forEach((track) => track.stop());
  if (state.ws) { try { state.ws.close(); } catch (_) {} }
}

/* Public, documented test/demo hook used by the screenshot and evaluation scripts. */
window.AirCanvas = {
  setMode: (mode) => setMode(mode),
  setTool: (tool) => setTool(tool),
  startDemo: (options = {}) => {
    if (options.mode) setMode(options.mode);
    if (options.tool) setTool(options.tool);
    startDemo(options.seek || 0);
  },
  stopDemo: () => stopDemo(true),
  enableCamera: () => enableCamera(),
  getState: () => state.snapshot,
  getConfig: () => state.config,
  getDebug: () => ({
    connected: state.connected, configured: state.configured,
    autoDemo: state.autoDemo, autoDemoLaunched: state.autoDemoLaunched,
    wantDemo: state.wantDemo, demo: state.demo, demoSeek: state.demoSeek,
    cameraStatus: state.cameraStatus, lastSeq: state.lastSeq,
    mode: state.config.mode, url: location.href,
  }),
  send: (payload) => send(payload),
  redraw: () => { if (stageCtx) renderStage(stageCtx, stageMetrics.w, stageMetrics.h, false); },
};