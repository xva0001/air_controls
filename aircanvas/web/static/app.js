'use strict';

/* AirCanvas web client.
 * The browser is deliberately a renderer + camera transport. Gesture
 * recognition, mapping, drawing, shape correction and tracking all run in the
 * shared Python core over the local WebSocket. */

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

const GESTURE_LABELS = {
  none: 'No hand', point: 'Point', pinch: 'Pinch', peace: 'Two fingers',
  open_palm: 'Open palm', fist: 'Fist', three: 'Three fingers', unknown: 'Unknown',
};

const GESTURE_OPTIONS = [
  ['point', 'Point'], ['pinch', 'Pinch'], ['peace', 'Two fingers'],
  ['open_palm', 'Open palm'], ['three', 'Three fingers'], ['fist', 'Fist'],
];

const DEFAULT_CONFIG = {
  mode: 'screen', tool: 'draw', mirror_tool: 'track',
  auto_shapes: true, show_landmarks: true, mirror_camera: true,
  show_camera_pip: true, brush_color: '#ff6b57', brush_width: 5,
  gesture: {
    smoothing: 0.55, pinch_sensitivity: 1.0, stability_frames: 5,
    nav_sensitivity: 1.0, nav_hold_ms: 280, nav_cooldown_ms: 1000,
    right_click_hold_ms: 420, cursor_smoothing: 0.62,
    dominant_hand: 'auto', left_handed: false,
    draw_pose: 'point', click_pose: 'pinch', right_click_pose: 'peace',
    nav_pose: 'open_palm', page_pose: 'peace', show_gesture_trail: true,
    selection_hold_ms: 260,
  },
};

const state = {
  config: clone(DEFAULT_CONFIG),
  snapshot: null,
  connected: false,
  configured: false,
  lastSeq: 0,
  ws: null,
  reconnectTimer: null,
  reconnectDelay: 900,
  features: {},
  demo: false,
  demoImage: null,
  demoSeq: 0,
  wantDemo: false,
  demoSeek: 0,
  demoStarted: false,
  cameraStream: null,
  cameraStatus: 'off',
  cameraError: '',
  cameraDeviceId: '',
  captureTimer: null,
  manualOnly: false,
  startPanelDismissed: false,
  seenEventIds: new Set(),
  ripples: [],
  trail: [],
  lastPointer: null,
  lastTrackFingerprint: '',
  lastToast: '',
  toastTimer: null,
  pendingConfig: {},
  configTimer: null,
  frameInFlight: false,
  skipIntro: false,
  autoDemo: false,
  autoDemoSeek: 0,
  urlMode: null,
  urlTool: null,
  leftHanded: false,
};

const els = {};
let stageCtx = null;
let stageMetrics = { w: 0, h: 0, dpr: 1 };
let handCtx = null;
let captureCtx = null;

document.addEventListener('DOMContentLoaded', init);

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

function cacheElements() {
  const ids = [
    'stageCanvas', 'stageShell', 'handCanvas', 'cameraVideo', 'captureCanvas',
    'cameraPill', 'cameraPillText', 'gesturePill', 'gesturePillText',
    'connectionStatus', 'toolList', 'toolHint', 'brushSection', 'brushColorLabel',
    'brushWidth', 'brushWidthValue', 'smartShapes', 'surfaceSection',
    'stageEyebrow', 'stageTitle', 'stageDescription', 'smartPill', 'trackingPill',
    'stageModeChip', 'demoChip', 'trackChip', 'startPanel', 'startPanelTitle',
    'startPanelBody', 'startCameraBtn', 'startDemoBtn', 'startMouseBtn', 'toast', 'statusDot',
    'statusMessage', 'shortcutHint', 'stageStats', 'gestureName', 'confidencePill',
    'metricFps', 'metricLatency', 'metricPinch', 'trackingSection', 'trackList',
    'trackEmpty', 'clearTracks', 'mapDraw', 'mapClick', 'mapRight', 'mapNav',
    'mapPage', 'pinchSensitivity', 'pinchSensitivityValue', 'cursorSmoothing',
    'cursorSmoothingValue', 'navHold', 'navHoldValue', 'poseStability',
    'poseStabilityValue', 'mirrorCamera', 'showLandmarks', 'leftHanded',
    'dominantHand', 'cameraDevice', 'welcomeDialog', 'helpDialog', 'securityDialog',
    'securityLink', 'closeWelcome', 'welcomeCamera', 'welcomeDemo', 'welcomeMouse',
    'helpBtn', 'closeHelp', 'helpDone', 'closeSecurity', 'securityDone',
    'toolsToggle', 'controlsToggle', 'closeTools', 'closeInspector', 'leftPanel',
    'inspector', 'drawerBackdrop', 'serviceState', 'serviceUrl',
  ];
  for (const id of ids) els[id] = document.getElementById(id);
  stageCtx = els.stageCanvas.getContext('2d');
  handCtx = els.handCanvas.getContext('2d');
  captureCtx = els.captureCanvas.getContext('2d', { willReadFrequently: false });
  els.serviceUrl.textContent = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
}

/* ------------------------------------------------------------------ helpers */
function clone(value) { return JSON.parse(JSON.stringify(value)); }

function merge(base, patch) {
  const out = clone(base);
  if (!patch || typeof patch !== 'object') return out;
  for (const [key, value] of Object.entries(patch)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      out[key] = merge(out[key] || {}, value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

function normalizeConfig(raw) {
  const config = merge(DEFAULT_CONFIG, raw || {});
  config.os_mouse = false;
  config.os_navigation = false;
  config.mode = config.mode === 'mirror' ? 'mirror' : 'screen';
  if (!['draw', 'navigate', 'mouse'].includes(config.tool)) config.tool = 'draw';
  if (!['annotate', 'track'].includes(config.mirror_tool)) config.mirror_tool = 'track';
  return config;
}

function activeTool() {
  return state.config.mode === 'mirror' ? state.config.mirror_tool : state.config.tool;
}

function setText(el, text) {
  if (!el) return;
  const value = String(text ?? '');
  if (el.textContent !== value) el.textContent = value;
}

function send(payload) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    toast('Local service is not connected yet. Trying to reconnect…', 'warning');
    return false;
  }
  state.ws.send(JSON.stringify(payload));
  return true;
}

function toast(message, tone = 'info', ttl = 2800) {
  setText(els.toast, message);
  els.toast.dataset.tone = tone;
  els.toast.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { els.toast.hidden = true; }, ttl);
}

function setPill(el, text, tone) {
  if (!el) return;
  const label = el.querySelector('span:last-child');
  if (label) setText(label, text);
  el.dataset.tone = tone;
}

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

/* ------------------------------------------------------------------ server config */
function applyServerModeTool() {
  const config = state.config;
  if (config.mode !== state.lastMode) {
    state.lastMode = config.mode;
    updateModeUI(config.mode, { send: false });
  }
  if (activeTool() !== state.lastTool) {
    state.lastTool = activeTool();
    updateToolUI(state.lastTool, { send: false });
  }
}

function patchConfig(patch, delay = 60) {
  state.config = merge(state.config, patch);
  state.pendingConfig = merge(state.pendingConfig, patch);
  clearTimeout(state.configTimer);
  state.configTimer = setTimeout(flushConfig, delay);
}

function flushConfig() {
  if (!state.pendingConfig || !Object.keys(state.pendingConfig).length) return;
  const patch = state.pendingConfig;
  state.pendingConfig = {};
  send({ type: 'config', patch });
}

function hydrateConfig(config) {
  state.config = normalizeConfig(config);
  state.lastMode = state.config.mode;
  state.lastTool = activeTool();
  setButtons();
  // brush
  els.brushWidth.value = String(Math.round(state.config.brush_width));
  els.brushWidthValue.textContent = `${Math.round(state.config.brush_width)} px`;
  setText(els.brushColorLabel, String(state.config.brush_color).toUpperCase());
  document.querySelectorAll('.swatch').forEach((swatch) => {
    swatch.classList.toggle('active', swatch.dataset.color.toLowerCase() === String(state.config.brush_color).toLowerCase());
  });
  // toggles
  setSwitch(els.smartShapes, !!state.config.auto_shapes);
  setSwitch(els.mirrorCamera, !!state.config.mirror_camera);
  setSwitch(els.showLandmarks, !!state.config.show_landmarks);
  setSwitch(els.leftHanded, !!state.config.gesture.left_handed);
  state.leftHanded = !!state.config.gesture.left_handed;
  document.body.classList.toggle('left-handed', state.leftHanded);
  // mapping + tuning
  setSelect(els.mapDraw, state.config.gesture.draw_pose);
  setSelect(els.mapClick, state.config.gesture.click_pose);
  setSelect(els.mapRight, state.config.gesture.right_click_pose);
  setSelect(els.mapNav, state.config.gesture.nav_pose);
  setSelect(els.mapPage, state.config.gesture.page_pose);
  setRange(els.pinchSensitivity, els.pinchSensitivityValue, Math.round(state.config.gesture.pinch_sensitivity * 100), '%');
  setRange(els.cursorSmoothing, els.cursorSmoothingValue, Math.round(state.config.gesture.cursor_smoothing * 100), '%');
  setRange(els.navHold, els.navHoldValue, Math.round(state.config.gesture.nav_hold_ms), ' ms');
  setRange(els.poseStability, els.poseStabilityValue, Math.round(state.config.gesture.stability_frames), ' frames');
  setSelect(els.dominantHand, state.config.gesture.dominant_hand);
  updateModeUI(state.config.mode, { send: false });
  updateToolUI(activeTool(), { send: false });
  updateSmartPill();
}

function setButtons() {
  document.querySelectorAll('.mode-tab').forEach((btn) => {
    const active = btn.dataset.mode === state.config.mode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
}

function setSwitch(el, on) {
  if (!el) return;
  el.classList.toggle('on', !!on);
  el.setAttribute('aria-checked', on ? 'true' : 'false');
}

function setSelect(el, value) {
  if (!el) return;
  const idx = Array.from(el.options).findIndex((option) => option.value === value);
  if (idx >= 0) el.selectedIndex = idx;
}

function setRange(el, label, value, suffix) {
  if (!el) return;
  const clamped = Math.max(Number(el.min), Math.min(Number(el.max), value));
  el.value = String(clamped);
  if (label) label.textContent = `${clamped}${suffix}`;
}

function setupMappingOptions() {
  const map = {
    mapDraw: 'draw_pose', mapClick: 'click_pose', mapRight: 'right_click_pose',
    mapNav: 'nav_pose', mapPage: 'page_pose',
  };
  for (const id of Object.keys(map)) {
    const select = els[id];
    if (!select) continue;
    for (const [value, label] of GESTURE_OPTIONS) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    }
    select.addEventListener('change', () => {
      patchConfig({ gesture: { [map[id]]: select.value } }, 0);
    });
  }
}

/* ------------------------------------------------------------------ mode & tool */
function setMode(mode, options = {}) {
  if (!['screen', 'mirror'].includes(mode)) return;
  state.config.mode = mode;
  updateModeUI(mode, options);
  updateToolUI(activeTool(), { send: false });
  if (options.send !== false) send({ type: 'mode', value: mode });
  updateStartPanel();
}

function updateModeUI(mode, options = {}) {
  const screenMode = mode === 'screen';
  document.querySelectorAll('.mode-tab').forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  els.stageEyebrow.textContent = screenMode ? 'SCREEN MODE' : 'MIRROR MODE';
  els.stageTitle.textContent = screenMode ? 'Built-in canvas' : 'Mirror & track';
  els.stageDescription.textContent = screenMode
    ? 'Point to draw. Smart shapes can clean up circles.'
    : 'Annotate the live feed or circle an object to track it.';
  els.surfaceSection.hidden = !screenMode;
  els.trackingSection.hidden = !screenMode ? false : true;
  els.toolList.querySelectorAll('.tool-btn').forEach((btn) => {
    const key = btn.dataset.tool;
    const visible = screenMode ? ['draw', 'navigate', 'mouse'].includes(key) : ['annotate', 'track'].includes(key);
    btn.hidden = !visible;
  });
  els.shortcutHint.textContent = screenMode
    ? '1 / 2 mode · D draw · N navigate · M mouse · Ctrl+Z undo'
    : '1 / 2 mode · A annotate · T track · pinch a marker to remove';
  if (!screenMode) {
    els.surfaceSection.hidden = true;
  }
  const tool = activeTool();
  updateToolUI(tool, { send: false });
}

function updateToolUI(tool, options = {}) {
  document.querySelectorAll('.tool-btn').forEach((btn) => {
    const active = btn.dataset.tool === tool;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  const hints = {
    draw: 'Point and draw on the canvas.',
    navigate: 'Hold an open palm, then swipe with intent.',
    mouse: 'Pinch to click and drag. Two fingers for right-click.',
    annotate: 'Draw directly over the live feed.',
    track: 'Trace a loop around an object, then hold still.',
  };
  els.toolHint.textContent = hints[tool] || '';
  els.brushSection.hidden = state.config.mode === 'mirror' && tool === 'track';
  const titles = {
    draw: ['Built-in canvas', 'Point to draw. Smart shapes can clean up circles.'],
    navigate: ['Screen navigation', 'Hold an open palm, then swipe deliberately.'],
    mouse: ['Virtual mouse', 'Pinch clicks and drags. Two fingers right-click.'],
    annotate: ['Live feed annotator', 'Marks stay aligned with the camera frame.'],
    track: ['Object tracking', 'Trace a loop around an object, then hold still.'],
  };
  const title = titles[tool] || titles.draw;
  els.stageTitle.textContent = title[0];
  els.stageDescription.textContent = title[1];
  const modeLabel = state.config.mode === 'mirror' ? 'MIRROR' : 'SCREEN';
  setText(els.stageModeChip, `${modeLabel} / ${String(tool || '').toUpperCase()}`);
  if (options.send !== false) send({ type: 'tool', value: tool });
}

function setTool(tool, options = {}) {
  const screen = state.config.mode === 'screen';
  if (screen && ['draw', 'navigate', 'mouse'].includes(tool)) state.config.tool = tool;
  if (!screen && ['annotate', 'track'].includes(tool)) state.config.mirror_tool = tool;
  updateToolUI(tool, { send: options.send !== false });
}

function updateSmartPill() {
  const on = !!state.config.auto_shapes;
  setPill(els.smartPill, on ? 'SMART SHAPES ON' : 'SMART SHAPES OFF', on ? 'mint' : 'muted');
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

/* ------------------------------------------------------------------ camera */
function secureCameraContext() {
  if (!window.isSecureContext && !['localhost', '127.0.0.1', '::1'].includes(location.hostname)) {
    return 'Camera access requires a secure context. Open this app through localhost or HTTPS.';
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    return 'This browser does not expose the camera API. Try a current Chrome, Edge or Firefox build.';
  }
  return '';
}

async function enableCamera(deviceId = '') {
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

function cameraErrorMessage(error) {
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

async function stopCamera(notify = true) {
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

function startCaptureLoop() {
  stopCaptureLoop();
  if (!state.cameraStream) return;
  state.captureTimer = setInterval(captureFrame, 85);
}

function stopCaptureLoop() {
  if (state.captureTimer) clearInterval(state.captureTimer);
  state.captureTimer = null;
}

function captureFrame() {
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

async function refreshCameraDevices() {
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

function updateCameraPill() {
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
function startDemo(seek = 0) {
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

function stopDemo(notify = true) {
  state.wantDemo = false;
  state.demo = false;
  state.demoImage = null;
  state.demoSeqApplied = 0;
  if (notify) send({ type: 'demo', enabled: false });
  updateCameraPill();
  updateStartPanel();
}

/* ------------------------------------------------------------------ start panel */
function updateStartPanel() {
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
function hideStartPanel() { els.startPanel.hidden = true; }

/* ------------------------------------------------------------------ snapshot -> UI */
function applySnapshot(snapshot) {
  const hand = snapshot.hand || {};
  const gesture = snapshot.gesture || {};
  const visible = !!hand.visible;
  const stable = gesture.stable || 'none';
  const label = visible ? (gesture.label || GESTURE_LABELS[stable] || stable) : 'No hand';
  setText(els.gestureName, label);
  setText(els.gesturePillText, visible ? label.toUpperCase() : 'NO HAND');
  const confidence = Math.round((gesture.confidence || 0) * 100);
  setPill(els.confidencePill, visible ? `CONF ${confidence}%` : 'CONF —', visible ? (confidence >= 75 ? 'mint' : 'amber') : 'muted');
  setText(els.gesturePillText, visible ? label.toUpperCase() : 'NO HAND');
  els.gesturePill.dataset.tone = visible ? (confidence >= 75 ? 'mint' : 'amber') : 'muted';
  const stats = snapshot.stats || {};
  setText(els.metricFps, Number(stats.fps || 0).toFixed(1));
  const demoFeed = snapshot.camera?.status === 'demo' || state.demo;
  setText(els.metricLatency, demoFeed ? '—' : `${Number(stats.recognition_ms || 0).toFixed(1)} ms`);
  setText(els.metricPinch, visible ? Number(gesture.pinch_ratio || 0).toFixed(2) : '—');
  setText(els.stageStats, `${Number(stats.fps || 0).toFixed(1)} fps · ${demoFeed ? 'simulated' : `${Number(stats.recognition_ms || 0).toFixed(1)} ms`}`);
  const status = snapshot.status || {};
  setText(els.statusMessage, status.message || statusTextForState(snapshot));
  els.statusDot.style.background = visible ? 'var(--mint)' : 'var(--amber)';
  const drawing = snapshot.drawing || {};
  document.querySelector('[data-action="undo"]').disabled = !drawing.can_undo;
  document.querySelector('[data-action="redo"]').disabled = !drawing.can_redo;
  document.querySelector('[data-action="clear"]').disabled = !(drawing.strokes || []).length;
  setPill(els.trackingPill, snapshot.mode === 'mirror' && (snapshot.tracks || []).length ? 'TRACKING' : 'LIVE', snapshot.mode === 'mirror' && (snapshot.tracks || []).length ? 'mint' : 'coral');
  setText(els.trackChip, `${(snapshot.tracks || []).filter((track) => track.status === 'tracking' || track.status === 'occluded' || track.status === 'reacquiring').length} TRACKED`);
  els.trackChip.hidden = snapshot.mode !== 'mirror';
  if (snapshot.mode === 'mirror') {
    els.trackingSection.hidden = false;
  } else {
    els.trackingSection.hidden = true;
  }
  const camera = snapshot.camera || {};
  if (camera.status === 'demo') state.demo = true;
  if (camera.status === 'stopped' && state.demo && state.wantDemo === false) state.demo = false;
  updateCameraPill();
  updateSmartPill();
  const tracks = snapshot.tracks || [];
  const fingerprint = tracks.map((track) => `${track.id}:${track.status}:${track.label}`).join('|');
  if (fingerprint !== state.lastTrackFingerprint) {
    state.lastTrackFingerprint = fingerprint;
    renderTrackList(tracks);
  }
  const toastData = status.toast;
  if (toastData?.message && toastData.message !== state.lastToast) {
    state.lastToast = toastData.message;
    toast(toastData.message, toastData.tone || 'info', 2600);
  }
  collectEvents(snapshot);
  drawHandPreview(snapshot);
  updateStartPanel();
  if (snapshot.mode !== state.config.mode) {
    state.config.mode = snapshot.mode;
    updateModeUI(snapshot.mode, { send: false });
  }
}

function statusTextForState(snapshot) {
  if (state.demo) return 'Simulated camera feed';
  if (state.cameraStatus === 'live') return 'Browser camera live';
  if (state.cameraStatus === 'error') return state.cameraError || 'Camera unavailable';
  return state.connected ? 'Ready' : 'Connecting to local service…';
}

function renderTrackList(tracks) {
  els.trackList.innerHTML = '';
  if (!tracks.length) {
    els.trackEmpty.hidden = false;
    return;
  }
  els.trackEmpty.hidden = true;
  for (const track of tracks) {
    const row = document.createElement('div');
    row.className = 'track-row';
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = track.status === 'tracking' ? 'var(--mint)' : (track.status === 'occluded' || track.status === 'reacquiring') ? 'var(--amber)' : 'var(--danger)';
    const main = document.createElement('div');
    main.className = 'track-main';
    const name = document.createElement('strong');
    name.textContent = track.label || `Object ${track.id}`;
    const status = document.createElement('span');
    status.textContent = String(track.status || '').replaceAll('_', ' ').toUpperCase();
    status.style.color = dot.style.background;
    main.append(name, status);
    const remove = document.createElement('button');
    remove.className = 'icon-btn small';
    remove.setAttribute('aria-label', `Remove ${track.label || 'marker'}`);
    remove.title = 'Remove marker';
    remove.textContent = '×';
    remove.style.fontSize = '16px';
    remove.addEventListener('click', () => send({ type: 'action', name: 'remove_track', id: track.id }));
    row.append(dot, main, remove);
    els.trackList.appendChild(row);
  }
}

function collectEvents(snapshot) {
  for (const event of snapshot.events || []) {
    if (state.seenEventIds.has(event.id)) continue;
    state.seenEventIds.add(event.id);
    if (event.kind === 'click') {
      state.ripples.push({
        x: Number(event.data?.x ?? 0.5), y: Number(event.data?.y ?? 0.5),
        button: event.data?.button || 'left', at: performance.now(),
      });
    }
  }
  if (state.seenEventIds.size > 400) {
    const ids = Array.from(state.seenEventIds);
    state.seenEventIds = new Set(ids.slice(-200));
  }
  if (state.ripples.length > 20) state.ripples = state.ripples.slice(-20);
}

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

/* ------------------------------------------------------------------ rendering */
function syncCanvasSize() {
  const rect = els.stageShell.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  if (stageMetrics.w === rect.width && stageMetrics.h === rect.height && stageMetrics.dpr === dpr) return;
  stageMetrics = { w: rect.width, h: rect.height, dpr };
  els.stageCanvas.width = Math.round(rect.width * dpr);
  els.stageCanvas.height = Math.round(rect.height * dpr);
  stageCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function renderLoop() {
  requestAnimationFrame(renderLoop);
  if (!stageCtx) return;
  syncCanvasSize();
  renderStage(stageCtx, stageMetrics.w, stageMetrics.h, false);
}

function renderStage(ctx, width, height, exported) {
  if (!width || !height) return;
  const dpr = exported ? 1 : stageMetrics.dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const snapshot = state.snapshot;
  const mode = state.config.mode;
  if (mode === 'mirror') drawMirror(ctx, width, height, snapshot, exported);
  else drawScreen(ctx, width, height, snapshot, exported);
  drawRipples(ctx, width, height, mode);
}

function stageInset(width, height) { return Math.max(14, Math.min(22, width * 0.018)); }

function paperRect(width, height) {
  const inset = stageInset(width, height) + 8;
  return { x: inset, y: inset, w: width - inset * 2, h: height - inset * 2 };
}

function drawScreen(ctx, width, height, snapshot, exported) {
  roundedRect(ctx, 0, 0, width, height, 18);
  ctx.fillStyle = '#0c0b0a'; ctx.fill();
  const paper = paperRect(width, height);
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,.45)'; ctx.shadowBlur = 28; ctx.shadowOffsetY = 7;
  roundedRect(ctx, paper.x, paper.y, paper.w, paper.h, 10);
  const grad = ctx.createLinearGradient(paper.x, paper.y, paper.x + paper.w, paper.y + paper.h);
  grad.addColorStop(0, '#f4efe6'); grad.addColorStop(.6, '#f0ebe1'); grad.addColorStop(1, '#e7e0d4');
  ctx.fillStyle = grad; ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.strokeStyle = '#cec5b7'; ctx.lineWidth = 1; ctx.stroke();
  ctx.clip();
  drawDotGrid(ctx, paper);
  drawWatermark(ctx, paper, width);
  drawStrokes(ctx, paper, snapshot?.drawing);
  if (!exported) {
    drawCursor(ctx, paper, snapshot);
    drawNavHud(ctx, paper, snapshot);
    if (state.config.show_camera_pip) drawPip(ctx, paper, snapshot, width, height);
    if (!(snapshot?.drawing?.strokes || []).length) drawPaperHint(ctx, paper);
  }
  ctx.restore();
}

function drawMirror(ctx, width, height, snapshot, exported) {
  roundedRect(ctx, 0, 0, width, height, 18);
  ctx.fillStyle = '#0d0c0b'; ctx.fill();
  const area = { x: 12, y: 12, w: width - 24, h: height - 24 };
  const media = currentMedia();
  const size = mediaSize(media);
  if (media && size.w && size.h) {
    // Ambient blurred cover fills the letterbox and makes the stage feel alive.
    ctx.save();
    roundedRect(ctx, area.x, area.y, area.w, area.h, 14);
    ctx.clip();
    ctx.filter = 'blur(24px) saturate(0.8)';
    drawImageCover(ctx, media, size, area, false);
    ctx.filter = 'none';
    ctx.fillStyle = 'rgba(7,6,5,.68)';
    ctx.fillRect(area.x, area.y, area.w, area.h);
    ctx.restore();
  }
  const video = containRect(size.w || 16, size.h || 9, area);
  ctx.save();
  roundedRect(ctx, video.x, video.y, video.w, video.h, 11);
  ctx.clip();
  if (media && size.w && size.h) {
    drawImageContain(ctx, media, size, video, !state.demo && state.config.mirror_camera);
    const top = ctx.createLinearGradient(0, video.y, 0, video.y + 150);
    top.addColorStop(0, 'rgba(0,0,0,.5)'); top.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = top; ctx.fillRect(video.x, video.y, video.w, 150);
    const bottom = ctx.createLinearGradient(0, video.y + video.h - 180, 0, video.y + video.h);
    bottom.addColorStop(0, 'rgba(0,0,0,0)'); bottom.addColorStop(1, 'rgba(0,0,0,.55)');
    ctx.fillStyle = bottom; ctx.fillRect(video.x, video.y + video.h - 180, video.w, 180);
  } else {
    drawEmptyVideo(ctx, video);
  }
  drawStrokes(ctx, video, snapshot?.drawing, true);
  drawTracks(ctx, video, snapshot);
  drawSelection(ctx, video, snapshot);
  if (!exported && state.config.show_landmarks) drawHand(ctx, video, snapshot);
  if (!exported) {
    drawCursor(ctx, video, snapshot);
    drawMirrorHint(ctx, video, snapshot);
  }
  ctx.restore();
  roundedRect(ctx, video.x, video.y, video.w, video.h, 11);
  ctx.strokeStyle = '#3b342c'; ctx.lineWidth = 1; ctx.stroke();
  if (!exported) drawShotCorners(ctx, video);
}

function currentMedia() {
  if (state.demo) return state.demoImage;
  if (els.cameraVideo.readyState >= 2 && els.cameraVideo.videoWidth) return els.cameraVideo;
  return null;
}
function mediaSize(media) {
  if (!media) return { w: 0, h: 0 };
  if (media === els.cameraVideo) return { w: media.videoWidth, h: media.videoHeight };
  return { w: media.naturalWidth || media.width || 0, h: media.naturalHeight || media.height || 0 };
}

function drawImageContain(ctx, media, size, rect, mirror) {
  ctx.save();
  if (mirror) {
    ctx.translate(rect.x + rect.w, rect.y);
    ctx.scale(-1, 1);
    ctx.drawImage(media, 0, 0, rect.w, rect.h);
  } else {
    ctx.drawImage(media, rect.x, rect.y, rect.w, rect.h);
  }
  ctx.restore();
}
function drawImageCover(ctx, media, size, rect, mirror) {
  const targetAspect = rect.w / rect.h;
  const sourceAspect = size.w / size.h;
  let sx = 0, sy = 0, sw = size.w, sh = size.h;
  if (sourceAspect > targetAspect) {
    sw = size.h * targetAspect; sx = (size.w - sw) / 2;
  } else {
    sh = size.w / targetAspect; sy = (size.h - sh) / 2;
  }
  ctx.save();
  if (mirror) {
    ctx.translate(rect.x + rect.w, rect.y); ctx.scale(-1, 1);
    ctx.drawImage(media, sx, sy, sw, sh, 0, 0, rect.w, rect.h);
  } else {
    ctx.drawImage(media, sx, sy, sw, sh, rect.x, rect.y, rect.w, rect.h);
  }
  ctx.restore();
}
function containRect(sourceW, sourceH, area) {
  const scale = Math.min(area.w / sourceW, area.h / sourceH);
  const w = sourceW * scale, h = sourceH * scale;
  return { x: area.x + (area.w - w) / 2, y: area.y + (area.h - h) / 2, w, h };
}

function drawDotGrid(ctx, rect) {
  ctx.fillStyle = '#d8d0c3';
  for (let y = rect.y + 22; y < rect.y + rect.h - 10; y += 28) {
    for (let x = rect.x + 22; x < rect.x + rect.w - 10; x += 28) {
      ctx.beginPath(); ctx.arc(x, y, 1, 0, Math.PI * 2); ctx.fill();
    }
  }
}
function drawWatermark(ctx, rect, width) {
  ctx.save();
  ctx.font = `800 ${Math.max(28, Math.min(60, rect.w * 0.058))}px "Segoe UI", system-ui, sans-serif`;
  ctx.fillStyle = '#e2dacd';
  ctx.textBaseline = 'bottom';
  ctx.fillText('AIRCANVAS', rect.x + 34, rect.y + rect.h - 26);
  ctx.restore();
}
function drawPaperHint(ctx, rect) {
  ctx.save();
  ctx.fillStyle = '#8c8477';
  ctx.font = '500 13px "Segoe UI", system-ui, sans-serif';
  ctx.fillText('Point to draw in the air.', rect.x + 44, rect.y + 64);
  ctx.fillText('Use the mouse as an alternative.', rect.x + 44, rect.y + 84);
  ctx.fillStyle = '#a99f90'; ctx.font = '400 10px "Segoe UI", system-ui, sans-serif';
  ctx.fillText('Smart shapes corrects deliberate circles when enabled.', rect.x + 44, rect.y + 106);
  ctx.restore();
}

function drawPip(ctx, rect, snapshot, width, height) {
  const pipW = Math.min(282, Math.max(190, rect.w * 0.27));
  const pipH = pipW * 9 / 16;
  const pip = { x: rect.x + rect.w - pipW - 18, y: rect.y + rect.h - pipH - 18, w: pipW, h: pipH };
  ctx.save();
  roundedRect(ctx, pip.x, pip.y, pip.w, pip.h, 10);
  ctx.fillStyle = '#0e0d0c'; ctx.fill();
  ctx.clip();
  const media = currentMedia();
  const size = mediaSize(media);
  if (media && size.w && size.h) {
    drawImageCover(ctx, media, size, pip, !state.demo && state.config.mirror_camera);
  } else {
    ctx.fillStyle = '#171411'; ctx.fillRect(pip.x, pip.y, pip.w, pip.h);
    ctx.fillStyle = '#6d655b'; ctx.font = '600 9px "Segoe UI", system-ui'; ctx.textAlign = 'center';
    ctx.fillText('CAMERA OFF', pip.x + pip.w / 2, pip.y + pip.h / 2 + 4);
    ctx.textAlign = 'start';
  }
  if (state.config.show_landmarks && snapshot?.hand?.visible) drawHand(ctx, pip, snapshot, true);
  ctx.restore();
  roundedRect(ctx, pip.x, pip.y, pip.w, pip.h, 10);
  ctx.strokeStyle = '#4a4036'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = media ? '#74d7b6' : '#6d655b';
  ctx.beginPath(); ctx.arc(pip.x + 11, pip.y + 11, 2.6, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#f4efe5'; ctx.font = '700 8px "Segoe UI", system-ui'; ctx.fillText('REC', pip.x + 20, pip.y + 14);
}

function drawStrokes(ctx, rect, drawing, mirror = false) {
  if (!drawing) return;
  const strokes = [...(drawing.strokes || [])];
  if (drawing.current) strokes.push(drawing.current);
  for (let i = 0; i < strokes.length; i++) {
    const stroke = strokes[i];
    const pts = stroke.points || [];
    if (pts.length < 2) continue;
    let path;
    let circle = null;
    if (stroke.kind === 'circle') {
      const box = pointsBox(pts, rect);
      const radius = (box.w + box.h) / 4;
      circle = { x: box.x + box.w / 2, y: box.y + box.h / 2, r: radius };
      path = new Path2D();
      path.arc(circle.x, circle.y, radius, 0, Math.PI * 2);
    } else {
      path = strokePath(pts, rect);
      if (stroke.closed) path.closePath();
    }
    const width = Math.max(1.5, Number(stroke.width || 5) * Math.min(rect.w, rect.h) / 870 * 1.25);
    const color = stroke.color || '#f07157';
    const isCurrent = drawing.current && i === strokes.length - 1;
    ctx.save();
    ctx.globalAlpha = mirror ? 0.95 : 1;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = hexToRgba(color, isCurrent ? 0.25 : 0.16);
    ctx.lineWidth = width * 2.4;
    ctx.stroke(path);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke(path);
    ctx.restore();
  }
}

function strokePath(points, rect) {
  const mapped = points.map((p) => ({ x: rect.x + Number(p[0]) * rect.w, y: rect.y + Number(p[1]) * rect.h }));
  const path = new Path2D();
  path.moveTo(mapped[0].x, mapped[0].y);
  if (mapped.length === 2) { path.lineTo(mapped[1].x, mapped[1].y); return path; }
  for (let i = 1; i < mapped.length - 1; i++) {
    const mid = { x: (mapped[i].x + mapped[i + 1].x) / 2, y: (mapped[i].y + mapped[i + 1].y) / 2 };
    path.quadraticCurveTo(mapped[i].x, mapped[i].y, mid.x, mid.y);
  }
  path.lineTo(mapped[mapped.length - 1].x, mapped[mapped.length - 1].y);
  return path;
}

function pointsBox(points, rect) {
  const xs = points.map((p) => rect.x + Number(p[0]) * rect.w);
  const ys = points.map((p) => rect.y + Number(p[1]) * rect.h);
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(1, Math.max(...xs) - Math.min(...xs)), h: Math.max(1, Math.max(...ys) - Math.min(...ys)) };
}

function drawHand(ctx, rect, snapshot, compact = false) {
  const landmarks = snapshot?.hand?.landmarks || [];
  if (landmarks.length !== 21) return;
  const points = landmarks.map((p) => ({ x: rect.x + Number(p[0]) * rect.w, y: rect.y + Number(p[1]) * rect.h }));
  ctx.save();
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(10,9,8,.45)';
  ctx.lineWidth = compact ? 3.4 : 5.2;
  for (const [a, b] of HAND_CONNECTIONS) { ctx.beginPath(); ctx.moveTo(points[a].x, points[a].y); ctx.lineTo(points[b].x, points[b].y); ctx.stroke(); }
  ctx.strokeStyle = compact ? 'rgba(248,242,232,.64)' : 'rgba(248,242,232,.84)';
  ctx.lineWidth = compact ? 1.2 : 2;
  for (const [a, b] of HAND_CONNECTIONS) { ctx.beginPath(); ctx.moveTo(points[a].x, points[a].y); ctx.lineTo(points[b].x, points[b].y); ctx.stroke(); }
  points.forEach((point, index) => {
    if ([4, 8, 12, 16, 20].includes(index)) {
      ctx.fillStyle = index === 8 ? '#f07157' : '#f8f2e8';
      ctx.beginPath(); ctx.arc(point.x, point.y, compact ? 2 : 3.3, 0, Math.PI * 2); ctx.fill();
    } else if (!compact) {
      ctx.fillStyle = '#d6cec1'; ctx.beginPath(); ctx.arc(point.x, point.y, 1.7, 0, Math.PI * 2); ctx.fill();
    }
  });
  if (!compact) {
    const tip = points[8];
    ctx.strokeStyle = 'rgba(240,113,87,.35)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(tip.x, tip.y, 15 + Math.sin(performance.now() / 420) * 2, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = '#f07157'; ctx.lineWidth = 1.3;
    ctx.beginPath(); ctx.arc(tip.x, tip.y, 10, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore();
}

function drawCursor(ctx, rect, snapshot) {
  const pointer = snapshot?.pointer;
  if (!pointer?.visible) { state.trail = []; return; }
  const point = { x: rect.x + Number(pointer.x) * rect.w, y: rect.y + Number(pointer.y) * rect.h };
  if (!state.lastPointer || Math.hypot(state.lastPointer.x - point.x, state.lastPointer.y - point.y) > 1.2) {
    state.trail.push({ ...point, at: performance.now() });
    if (state.trail.length > 18) state.trail.shift();
    state.lastPointer = point;
  }
  const now = performance.now();
  for (let i = 1; i < state.trail.length; i++) {
    const age = now - state.trail[i].at;
    if (age > 380) continue;
    ctx.strokeStyle = `rgba(240,113,87,${0.22 * (1 - age / 380)})`;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(state.trail[i - 1].x, state.trail[i - 1].y); ctx.lineTo(state.trail[i].x, state.trail[i].y); ctx.stroke();
  }
  ctx.save();
  const kind = pointer.kind || 'crosshair';
  if (kind === 'mouse') {
    ctx.strokeStyle = '#f4efe5'; ctx.fillStyle = pointer.pressed ? '#f07157' : '#f7f2e8'; ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(point.x, point.y); ctx.lineTo(point.x, point.y + 22); ctx.lineTo(point.x + 6, point.y + 17);
    ctx.lineTo(point.x + 12, point.y + 27); ctx.lineTo(point.x + 16, point.y + 24); ctx.lineTo(point.x + 10, point.y + 15);
    ctx.lineTo(point.x + 18, point.y + 14); ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (kind === 'navigate') {
    const pulse = 1 + 0.16 * Math.sin(now / 240);
    ctx.strokeStyle = 'rgba(240,113,87,.7)'; ctx.lineWidth = 1.5; ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.arc(point.x, point.y, 22 * pulse, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]); ctx.strokeStyle = '#f07157'; ctx.lineWidth = 2;
    for (const [dx, dy] of [[0, -13], [0, 13], [-13, 0], [13, 0]]) {
      ctx.beginPath(); ctx.moveTo(point.x, point.y); ctx.lineTo(point.x + dx, point.y + dy); ctx.stroke();
    }
  } else {
    const glow = ctx.createRadialGradient(point.x, point.y, 2, point.x, point.y, 22);
    glow.addColorStop(0, `rgba(240,113,87,${pointer.pressed ? .32 : .12})`); glow.addColorStop(1, 'rgba(240,113,87,0)');
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(point.x, point.y, 22, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(244,239,229,.82)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(point.x, point.y, 10, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = '#f07157'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(point.x, point.y, 13, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = pointer.pressed ? '#f07157' : '#74d7b6';
    ctx.beginPath(); ctx.arc(point.x, point.y, 3.4, 0, Math.PI * 2); ctx.fill();
    if (kind === 'crosshair') {
      ctx.strokeStyle = 'rgba(244,239,229,.55)'; ctx.lineWidth = 1;
      for (const [x1, y1, x2, y2] of [[-17,0,-14,0],[14,0,17,0],[0,-17,0,-14],[0,14,0,17]]) {
        ctx.beginPath(); ctx.moveTo(point.x + x1, point.y + y1); ctx.lineTo(point.x + x2, point.y + y2); ctx.stroke();
      }
    }
  }
  ctx.restore();
}

function drawTracks(ctx, rect, snapshot) {
  for (const track of snapshot?.tracks || []) {
    const b = track.bbox || [0, 0, 0, 0];
    const box = { x: rect.x + b[0] * rect.w, y: rect.y + b[1] * rect.h, w: b[2] * rect.w, h: b[3] * rect.h };
    const tracking = track.status === 'tracking';
    const warn = ['occluded', 'reacquiring', 'lost'].includes(track.status);
    const color = tracking ? '#74d7b6' : warn ? '#f3c45d' : '#ed6a6a';
    ctx.save();
    ctx.strokeStyle = color; ctx.lineWidth = 2;
    if (!tracking) ctx.setLineDash([5, 4]);
    roundedRect(ctx, box.x - 4, box.y - 4, box.w + 8, box.h + 8, 12); ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 2.6; ctx.lineCap = 'round';
    const len = Math.min(20, box.w * .22, box.h * .22);
    for (const [cx, cy, dx, dy] of [[box.x - 4, box.y - 4, 1, 1], [box.x + box.w + 4, box.y - 4, -1, 1], [box.x - 4, box.y + box.h + 4, 1, -1], [box.x + box.w + 4, box.y + box.h + 4, -1, -1]]) {
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + len * dx, cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx, cy + len * dy); ctx.stroke();
    }
    if (tracking) {
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(box.x + box.w / 2, box.y + box.h / 2, 3 + Math.sin(performance.now() / 380), 0, Math.PI * 2); ctx.fill();
    }
    const subtitle = { tracking: 'TRACKING', occluded: 'OCCLUDED · SEARCHING', reacquiring: 'RE-ACQUIRING', lost: 'LOST', out_of_view: 'LEFT VIEW' }[track.status] || String(track.status).toUpperCase();
    ctx.font = '700 9px "Segoe UI", system-ui'; const tw = Math.max(ctx.measureText(track.label || 'Object').width, ctx.measureText(subtitle).width) + 20;
    const chip = { x: box.x - 4, y: box.y - 44, w: Math.max(118, Math.min(220, tw)), h: 36 };
    if (chip.y < rect.y + 8) chip.y = box.y - 4;
    if (chip.x + chip.w > rect.x + rect.w - 6) chip.x = box.x + box.w + 4 - chip.w;
    if (chip.x < rect.x + 6) chip.x = box.x - 4;
    roundedRect(ctx, chip.x, chip.y, chip.w, chip.h, 7);
    ctx.fillStyle = 'rgba(20,17,14,.93)'; ctx.fill(); ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#f4efe5'; ctx.font = '600 9px "Segoe UI", system-ui';
    ctx.fillText(track.label || 'Object', chip.x + 9, chip.y + 14);
    ctx.fillStyle = color; ctx.font = '700 7px "Segoe UI", system-ui';
    ctx.fillText(subtitle, chip.x + 9, chip.y + 27);
    ctx.restore();
  }
}

function drawSelection(ctx, rect, snapshot) {
  const selection = snapshot?.selection;
  const points = selection?.points || [];
  if (!points.length) return;
  const mapped = points.map((p) => ({ x: rect.x + Number(p[0]) * rect.w, y: rect.y + Number(p[1]) * rect.h }));
  ctx.save();
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(116,215,182,.18)'; ctx.lineWidth = 10;
  ctx.beginPath(); ctx.moveTo(mapped[0].x, mapped[0].y); mapped.slice(1).forEach((p) => ctx.lineTo(p.x, p.y)); ctx.stroke();
  ctx.strokeStyle = 'rgba(116,215,182,.9)'; ctx.lineWidth = 2; ctx.stroke();
  const end = mapped[mapped.length - 1];
  const progress = Number(selection.progress || 0);
  ctx.strokeStyle = 'rgba(116,215,182,.28)'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(end.x, end.y, 17, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = '#74d7b6'; ctx.lineWidth = 3; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.arc(end.x, end.y, 17, -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2); ctx.stroke();
  ctx.fillStyle = '#74d7b6'; ctx.beginPath(); ctx.arc(end.x, end.y, 4, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

function drawNavHud(ctx, rect, snapshot) {
  if (state.config.tool !== 'navigate') return;
  const nav = snapshot?.nav || {};
  const hint = nav.hint || 'Hold an open palm, then swipe';
  const progress = Number(nav.progress || 0);
  drawBottomPill(ctx, rect, hint, '#f07157');
  if (progress > .03) {
    const cx = rect.x + rect.w / 2, cy = rect.y + rect.h / 2 - 20;
    ctx.save();
    ctx.strokeStyle = `rgba(240,113,87,${.15 + .55 * Math.min(1, progress)})`; ctx.lineWidth = 1.4; ctx.setLineDash([3, 5]);
    ctx.beginPath(); ctx.arc(cx, cy, 46, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
    ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(cx, cy, 46, -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2); ctx.stroke();
    ctx.restore();
  }
}

function drawMirrorHint(ctx, rect, snapshot) {
  let text = '';
  if (state.config.mirror_tool === 'track') {
    if ((snapshot?.selection?.points || []).length) text = snapshot.selection.hint || 'Hold still to lock the selection';
    else if ((snapshot?.tracks || []).length) text = 'Pinch a marker to remove it · or use the tracking panel';
    else text = 'Trace a loop around any object to track it';
  } else {
    text = (snapshot?.drawing?.strokes || []).length
      ? 'Annotate the live feed · Smart shapes can correct circles'
      : 'Point to annotate the feed · your marks stay aligned to the video';
  }
  drawBottomPill(ctx, rect, text, state.config.mirror_tool === 'track' ? '#74d7b6' : '#f07157');
}

function drawBottomPill(ctx, rect, text, tone) {
  ctx.save();
  ctx.font = '500 10px "Segoe UI", system-ui';
  const w = Math.min(rect.w - 40, ctx.measureText(text).width + 44);
  const x = rect.x + (rect.w - w) / 2, y = rect.y + rect.h - 40;
  roundedRect(ctx, x, y, w, 27, 14);
  ctx.fillStyle = 'rgba(16,14,12,.9)'; ctx.fill(); ctx.strokeStyle = '#3b342c'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = tone; ctx.beginPath(); ctx.arc(x + 14, y + 13.5, 2.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#c9c1b5'; ctx.fillText(text, x + 24, y + 17);
  ctx.restore();
}

function drawStageChip(ctx, x, y, text, color, compact) {
  ctx.save();
  ctx.font = `700 ${compact ? 7 : 8}px "Segoe UI", system-ui`;
  const w = ctx.measureText(text).width + (compact ? 18 : 28);
  const h = compact ? 19 : 22;
  roundedRect(ctx, x, y, w, h, 5);
  ctx.fillStyle = 'rgba(16,14,12,.82)'; ctx.fill();
  ctx.strokeStyle = hexToRgba(color, .32); ctx.lineWidth = 1; ctx.stroke();
  if (!compact) { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x + 11, y + h / 2, 2.4, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = color; ctx.fillText(text, x + (compact ? 8 : 19), y + (compact ? 13 : 15));
  ctx.restore();
}

function drawEmptyVideo(ctx, rect) {
  roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 11);
  ctx.fillStyle = '#141210'; ctx.fill();
  ctx.strokeStyle = '#27221d'; ctx.lineWidth = 1; ctx.setLineDash([2, 8]);
  for (let x = rect.x + 20; x < rect.x + rect.w - 10; x += 34) { ctx.beginPath(); ctx.moveTo(x, rect.y + 12); ctx.lineTo(x, rect.y + rect.h - 12); ctx.stroke(); }
  for (let y = rect.y + 20; y < rect.y + rect.h - 10; y += 34) { ctx.beginPath(); ctx.moveTo(rect.x + 12, y); ctx.lineTo(rect.x + rect.w - 12, y); ctx.stroke(); }
  ctx.setLineDash([]);
  ctx.fillStyle = '#6d655b'; ctx.textAlign = 'center'; ctx.font = '600 13px "Segoe UI", system-ui';
  ctx.fillText('Camera feed offline', rect.x + rect.w / 2, rect.y + rect.h / 2);
  ctx.font = '400 10px "Segoe UI", system-ui';
  ctx.fillText('Enable the camera or try the simulated feed', rect.x + rect.w / 2, rect.y + rect.h / 2 + 20);
  ctx.textAlign = 'start';
}

function drawShotCorners(ctx, rect) {
  ctx.save();
  ctx.strokeStyle = 'rgba(239,231,219,.16)'; ctx.lineWidth = 1;
  const m = 8, len = 16;
  for (const [x, y, dx, dy] of [[rect.x + m, rect.y + m, 1, 1], [rect.x + rect.w - m, rect.y + m, -1, 1], [rect.x + m, rect.y + rect.h - m, 1, -1], [rect.x + rect.w - m, rect.y + rect.h - m, -1, -1]]) {
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + len * dx, y); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + len * dy); ctx.stroke();
  }
  ctx.restore();
}

function drawRipples(ctx, width, height, mode) {
  const now = performance.now();
  state.ripples = state.ripples.filter((ripple) => now - ripple.at < 680);
  if (!state.ripples.length) return;
  const rect = mode === 'mirror' ? activeRect() : paperRect(width, height);
  for (const ripple of state.ripples) {
    const age = (now - ripple.at) / 680;
    const x = rect.x + ripple.x * rect.w, y = rect.y + ripple.y * rect.h;
    const color = ripple.button === 'right' ? '#64a9e5' : '#f07157';
    ctx.save();
    ctx.strokeStyle = hexToRgba(color, .7 * (1 - age)); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(x, y, 10 + 34 * age, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = hexToRgba(color, .28 * (1 - age)); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(x, y, 17 + 34 * age, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }
}

function activeRect() {
  const width = stageMetrics.w, height = stageMetrics.h;
  if (state.config.mode === 'screen') return paperRect(width, height);
  const area = { x: 12, y: 12, w: width - 24, h: height - 24 };
  const media = currentMedia();
  const size = mediaSize(media);
  return containRect(size.w || 16, size.h || 9, area);
}

/* ------------------------------------------------------------------ hand preview */
function drawHandPreview(snapshot) {
  if (!handCtx) return;
  const canvas = els.handCanvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const targetW = Math.max(1, Math.round(rect.width * dpr));
  const targetH = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== targetW || canvas.height !== targetH) {
    canvas.width = targetW; canvas.height = targetH;
  }
  const ctx = handCtx;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = rect.width, h = rect.height;
  ctx.clearRect(0, 0, w, h);
  const grad = ctx.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, '#211e1a'); grad.addColorStop(1, '#171513');
  roundedRect(ctx, 0, 0, w, h, 8); ctx.fillStyle = grad; ctx.fill();
  ctx.strokeStyle = '#2b2722'; ctx.lineWidth = 1;
  for (let x = 12; x < w; x += 22) { ctx.beginPath(); ctx.moveTo(x, 1); ctx.lineTo(x, h - 1); ctx.stroke(); }
  for (let y = 12; y < h; y += 22) { ctx.beginPath(); ctx.moveTo(1, y); ctx.lineTo(w - 1, y); ctx.stroke(); }
  const landmarks = snapshot?.hand?.landmarks || [];
  const handVisible = !!snapshot?.hand?.visible;
  if (!handVisible || landmarks.length !== 21) {
    drawHandIconSkeleton(ctx, w, h);
    ctx.fillStyle = '#6d655b'; ctx.font = '500 10px "Segoe UI", system-ui'; ctx.textAlign = 'center';
    ctx.fillText('No hand in view', w / 2, h / 2 + 34);
    ctx.textAlign = 'start';
    drawPreviewCorners(ctx, w, h, '#3a342d');
    return;
  }
  const points = landmarks.map((p) => ({ x: p[0] * w, y: p[1] * h }));
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const span = Math.max(.08, Math.max(maxX - minX, maxY - minY));
  const scale = Math.min(w * .58, h * .72) / span;
  const cx = xs.reduce((a, b) => a + b, 0) / 21, cy = ys.reduce((a, b) => a + b, 0) / 21;
  const mapped = points.map((p) => ({ x: w / 2 + (p.x - cx) * scale, y: h / 2 + 2 + (p.y - cy) * scale }));
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(240,113,87,.14)'; ctx.lineWidth = 11;
  for (const [a, b] of HAND_CONNECTIONS) { ctx.beginPath(); ctx.moveTo(mapped[a].x, mapped[a].y); ctx.lineTo(mapped[b].x, mapped[b].y); ctx.stroke(); }
  ctx.strokeStyle = 'rgba(116,215,182,.84)'; ctx.lineWidth = 2;
  for (const [a, b] of HAND_CONNECTIONS) { ctx.beginPath(); ctx.moveTo(mapped[a].x, mapped[a].y); ctx.lineTo(mapped[b].x, mapped[b].y); ctx.stroke(); }
  mapped.forEach((point, index) => {
    ctx.fillStyle = [4, 8, 12, 16, 20].includes(index) ? (index === 8 ? '#f07157' : '#f4efe5') : '#d9d2c7';
    ctx.beginPath(); ctx.arc(point.x, point.y, index === 8 ? 3.8 : [4, 12, 16, 20].includes(index) ? 2.7 : 2.0, 0, Math.PI * 2); ctx.fill();
  });
  ctx.strokeStyle = '#f07157'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(mapped[8].x, mapped[8].y, 11, 0, Math.PI * 2); ctx.stroke();
  const confidence = Math.max(0, Math.min(1, Number(snapshot?.gesture?.confidence || 0)));
  ctx.fillStyle = '#2c2721'; roundedRect(ctx, 12, h - 10, w - 24, 3, 1.5); ctx.fill();
  ctx.fillStyle = confidence >= .75 ? '#74d7b6' : '#f3c45d';
  roundedRect(ctx, 12, h - 10, (w - 24) * confidence, 3, 1.5); ctx.fill();
  drawPreviewCorners(ctx, w, h, '#3a342d');
}

function drawHandIconSkeleton(ctx, w, h) {
  ctx.save();
  ctx.translate(w / 2, h / 2 - 10);
  ctx.strokeStyle = '#5b5349'; ctx.lineWidth = 1.4; ctx.lineCap = 'round';
  const pts = [[-7, 30], [-9, 0], [-4, -30], [4, -34], [10, -28], [12, 2], [16, -22], [18, 10], [22, -10], [24, 18], [27, 8], [28, 30], [8, 42]];
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.stroke();
  ctx.restore();
}
function drawPreviewCorners(ctx, w, h, color) {
  ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 1.2; const len = 9;
  for (const [x, y, dx, dy] of [[8, 8, 1, 1], [w - 8, 8, -1, 1], [8, h - 8, 1, -1], [w - 8, h - 8, -1, -1]]) {
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + len * dx, y); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + len * dy); ctx.stroke();
  }
  ctx.restore();
}

/* ------------------------------------------------------------------ export */
function exportPng() {
  const canvas = document.getElementById('exportCanvas');
  const width = 1920, height = 1080;
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d');
  renderStage(ctx, width, height, true);
  canvas.toBlob((blob) => {
    if (!blob) { toast('Export failed in this browser.', 'error'); return; }
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `aircanvas-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    toast('Artwork exported as PNG.', 'success', 2400);
  }, 'image/png');
}

/* ------------------------------------------------------------------ utilities */
function roundedRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}
function hexToRgba(hex, alpha) {
  const value = String(hex || '#f07157').replace('#', '');
  const normalized = value.length === 3 ? value.split('').map((c) => c + c).join('') : value;
  const int = parseInt(normalized, 16);
  if (Number.isNaN(int)) return `rgba(240,113,87,${alpha})`;
  return `rgba(${(int >> 16) & 255},${(int >> 8) & 255},${int & 255},${alpha})`;
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
