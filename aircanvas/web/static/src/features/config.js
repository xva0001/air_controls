'use strict';

import { DEFAULT_CONFIG, GESTURE_OPTIONS } from '../core/constants.js';
import { state, activeTool } from '../core/state.js';
import {
  els,
  setText,
  setSwitch,
  setSelect,
  setRange,
} from '../core/ui.js';
import { send } from '../core/bridge.js';
import { merge } from '../core/utils.js';
import { setButtons, updateModeUI, updateToolUI, updateSmartPill } from '../ui/mode-tool.js';

/** Config normalisation, server sync and DOM hydration. */
export function normalizeConfig(raw) {
  const config = merge(DEFAULT_CONFIG, raw || {});
  config.os_mouse = false;
  config.os_navigation = false;
  config.mode = config.mode === 'mirror' ? 'mirror' : 'screen';
  if (!['draw', 'navigate', 'mouse'].includes(config.tool)) config.tool = 'draw';
  if (!['annotate', 'track'].includes(config.mirror_tool)) config.mirror_tool = 'track';
  if (!['mediapipe', 'rtmpose', 'yolo_pose'].includes(config.hand_backend)) config.hand_backend = 'mediapipe';
  if (!['auto', 'cpu', 'cuda', 'mps'].includes(config.hand_device)) config.hand_device = 'auto';
  config.hand_model_path = String(config.hand_model_path || '').trim();
  return config;
}

export function applyServerModeTool() {
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

export function patchConfig(patch, delay = 60) {
  state.config = merge(state.config, patch);
  state.pendingConfig = merge(state.pendingConfig, patch);
  clearTimeout(state.configTimer);
  state.configTimer = setTimeout(flushConfig, delay);
}

export function flushConfig() {
  if (!state.pendingConfig || !Object.keys(state.pendingConfig).length) return;
  const patch = state.pendingConfig;
  state.pendingConfig = {};
  send({ type: 'config', patch });
}

export function hydrateConfig(config) {
  state.config = normalizeConfig(config);
  state.lastMode = state.config.mode;
  state.lastTool = activeTool();
  setButtons();
  els.brushWidth.value = String(Math.round(state.config.brush_width));
  els.brushWidthValue.textContent = `${Math.round(state.config.brush_width)} px`;
  setText(els.brushColorLabel, String(state.config.brush_color).toUpperCase());
  document.querySelectorAll('.swatch').forEach((swatch) => {
    swatch.classList.toggle('active', swatch.dataset.color.toLowerCase() === String(state.config.brush_color).toLowerCase());
  });
  setSwitch(els.smartShapes, !!state.config.auto_shapes);
  setSwitch(els.mirrorCamera, !!state.config.mirror_camera);
  setSwitch(els.showLandmarks, !!state.config.show_landmarks);
  setSwitch(els.leftHanded, !!state.config.gesture.left_handed);
  state.leftHanded = !!state.config.gesture.left_handed;
  document.body.classList.toggle('left-handed', state.leftHanded);
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
  setSelect(els.handModel, state.config.hand_backend);
  els.handModelPath.value = state.config.hand_model_path || '';
  updateModeUI(state.config.mode, { send: false });
  updateToolUI(activeTool(), { send: false });
  updateSmartPill();
}

export function setupMappingOptions() {
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
