'use strict';

import { els, handCtx } from '../core/ui.js';
import { HAND_CONNECTIONS } from '../core/constants.js';
import { roundedRect } from '../core/utils.js';

/** Inspector hand preview; separate from the main stage canvas. */
/* ------------------------------------------------------------------ hand preview */
export function drawHandPreview(snapshot) {
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
