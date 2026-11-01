'use strict';

import { state } from '../core/state.js';
import { els, stageCtx, stageMetrics, toast } from '../core/ui.js';
import { HAND_CONNECTIONS } from '../core/constants.js';
import { hexToRgba, roundedRect } from '../core/utils.js';

/** Canvas stage renderer. Pure drawing functions live here; no network state. */
/* ------------------------------------------------------------------ rendering */
export function syncCanvasSize() {
  const rect = els.stageShell.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  if (stageMetrics.w === rect.width && stageMetrics.h === rect.height && stageMetrics.dpr === dpr) return;
  stageMetrics.w = rect.width; stageMetrics.h = rect.height; stageMetrics.dpr = dpr;
  els.stageCanvas.width = Math.round(rect.width * dpr);
  els.stageCanvas.height = Math.round(rect.height * dpr);
  stageCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

export function renderLoop() {
  requestAnimationFrame(renderLoop);
  if (!stageCtx) return;
  syncCanvasSize();
  renderStage(stageCtx, stageMetrics.w, stageMetrics.h, false);
}

export function renderStage(ctx, width, height, exported) {
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

export function activeRect() {
  const width = stageMetrics.w, height = stageMetrics.h;
  if (state.config.mode === 'screen') return paperRect(width, height);
  const area = { x: 12, y: 12, w: width - 24, h: height - 24 };
  const media = currentMedia();
  const size = mediaSize(media);
  return containRect(size.w || 16, size.h || 9, area);
}
/* ------------------------------------------------------------------ export */
export function exportPng() {
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
