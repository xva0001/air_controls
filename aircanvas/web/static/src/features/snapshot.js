'use strict';

import { GESTURE_LABELS } from '../core/constants.js';
import { state } from '../core/state.js';
import { els, setText, setPill, toast } from '../core/ui.js';
import { send } from '../core/bridge.js';
import { drawHandPreview } from '../render/hand-preview.js';
import { updateCameraPill, updateStartPanel } from './camera.js';
import { updateModeUI, updateSmartPill } from '../ui/mode-tool.js';

/** Snapshot -> presentation adapter (the browser's "view model"). */
export function applySnapshot(snapshot) {
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
  updateHandModelStatus(status);
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

export function statusTextForState(snapshot) {
  if (state.demo) return 'Simulated camera feed';
  if (state.cameraStatus === 'live') return 'Browser camera live';
  if (state.cameraStatus === 'error') return state.cameraError || 'Camera unavailable';
  return state.connected ? 'Ready' : 'Connecting to local service…';
}

export function updateHandModelStatus(status) {
  if (!els.handModelStatus) return;
  const selected = state.config.hand_backend;
  const entries = status.hand_backends || [];
  const info = entries.find((item) => item.key === selected) || status.hand_backend;
  if (!info) {
    setText(els.handModelStatus, 'Hand model status unavailable');
    els.handModelStatus.className = 'service-note hand-model-status';
    return;
  }
  const detail = info.available
    ? `● ${info.label} ready`
    : `○ ${info.label}: ${info.reason}${info.requires ? ` · ${info.requires}` : ''}`;
  setText(els.handModelStatus, detail);
  els.handModelStatus.className = `service-note hand-model-status ${info.available ? 'ready' : 'unavailable'}`;
  els.handModelStatus.title = info.note || '';
}

export function renderTrackList(tracks) {
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

export function collectEvents(snapshot) {
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


