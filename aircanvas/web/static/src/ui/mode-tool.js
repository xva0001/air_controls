'use strict';

import { state, activeTool } from '../core/state.js';
import { els, setText, setPill } from '../core/ui.js';
import { send } from '../core/bridge.js';
import { updateStartPanel } from '../features/camera.js';

/** Mode/tool presentation and toolbar state. */
export function setButtons() {
  document.querySelectorAll('.mode-tab').forEach((btn) => {
    const active = btn.dataset.mode === state.config.mode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
}

export function updateModeUI(mode, options = {}) {
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
  els.trackingSection.hidden = screenMode;
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
  updateToolUI(activeTool(), { send: false });
}

export function updateToolUI(tool, options = {}) {
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

export function setMode(mode, options = {}) {
  if (!['screen', 'mirror'].includes(mode)) return;
  state.config.mode = mode;
  updateModeUI(mode, options);
  updateToolUI(activeTool(), { send: false });
  if (options.send !== false) send({ type: 'mode', value: mode });
  updateStartPanel();
}

export function setTool(tool, options = {}) {
  const screen = state.config.mode === 'screen';
  if (screen && ['draw', 'navigate', 'mouse'].includes(tool)) state.config.tool = tool;
  if (!screen && ['annotate', 'track'].includes(tool)) state.config.mirror_tool = tool;
  updateToolUI(tool, { send: options.send !== false });
}

export function updateSmartPill() {
  const on = !!state.config.auto_shapes;
  setPill(els.smartPill, on ? 'SMART SHAPES ON' : 'SMART SHAPES OFF', on ? 'mint' : 'muted');
}
