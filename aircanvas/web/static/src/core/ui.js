'use strict';

import { state } from './state.js';

/** Cached DOM references and tiny presentational primitives. */
export const els = {};
export let stageCtx = null;
export let handCtx = null;
export let captureCtx = null;
export const stageMetrics = { w: 0, h: 0, dpr: 1 };

export function cacheElements() {
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
    'dominantHand', 'cameraDevice', 'handModel', 'handModelPath', 'handModelStatus',
    'welcomeDialog', 'helpDialog', 'securityDialog',
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

export function setText(el, text) {
  if (!el) return;
  const value = String(text ?? '');
  if (el.textContent !== value) el.textContent = value;
}

export function toast(message, tone = 'info', ttl = 2800) {
  setText(els.toast, message);
  els.toast.dataset.tone = tone;
  els.toast.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { els.toast.hidden = true; }, ttl);
}

export function setPill(el, text, tone) {
  if (!el) return;
  const label = el.querySelector('span:last-child');
  if (label) setText(label, text);
  el.dataset.tone = tone;
}

export function setSwitch(el, on) {
  if (!el) return;
  el.classList.toggle('on', !!on);
  el.setAttribute('aria-checked', on ? 'true' : 'false');
}

export function setSelect(el, value) {
  if (!el) return;
  const idx = Array.from(el.options).findIndex((option) => option.value === value);
  if (idx >= 0) el.selectedIndex = idx;
}

export function setRange(el, label, value, suffix) {
  if (!el) return;
  const clamped = Math.max(Number(el.min), Math.min(Number(el.max), value));
  el.value = String(clamped);
  if (label) label.textContent = `${clamped}${suffix}`;
}
