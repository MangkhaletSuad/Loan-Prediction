// Pixel-exact color picker: draws the image on a canvas at natural resolution and
// maps pointer coordinates back to source pixels. Images come from /uploads (same
// origin), so the canvas is never tainted and getImageData works.
import { formatRgb, toHex } from './color.js';
import { el, icon } from './ui.js';

const LOUPE_PIXELS = 11; // odd so there's a centre pixel
const LOUPE_SIZE = 132;

/** Mount a picker in container for imageUrl. onPick({x, y, r, g, b, hex}). Returns {destroy}. */
export function mountPicker(container, imageUrl, onPick, alt = '') {
  container.replaceChildren();
  const msg = el('div', { class: 'picker-msg' }, 'Loading image…');
  const canvas = el('canvas', { class: 'picker-canvas hidden', 'aria-label': alt ? `${alt} – click to pick a color` : 'Click to pick a color' });
  const loupe = el('canvas', { class: 'loupe', width: LOUPE_SIZE, height: LOUPE_SIZE });
  const readout = el('div');
  const panel = el('aside', { class: 'picker-panel' }, loupe, readout);
  container.append(el('div', { class: 'picker' }, el('div', { class: 'picker-stage' }, msg, canvas), panel));

  let ctx = null;
  let picked = null;
  let cancelled = false;

  const showHint = () => readout.replaceChildren(
    el('p', { class: 'muted small picker-hint' }, icon('picker', 14), ' Hover to preview, click anywhere on the image to pick the exact pixel color.'));
  const showReadout = (p, isHover) => readout.replaceChildren(
    el('div', { class: 'picker-readout' },
      el('span', { class: 'swatch', style: { background: p.hex, width: '36px', height: '36px' } }),
      el('div', {},
        el('div', { class: 'mono strong' }, formatRgb(p.r, p.g, p.b)),
        el('div', { class: 'mono muted' }, p.hex),
        el('div', { class: 'muted small' }, `x ${p.x}, y ${p.y}${isHover ? '' : ' · picked'}`))));
  showHint();

  const img = new Image();
  img.onload = () => {
    if (cancelled) return;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    msg.remove();
    canvas.classList.remove('hidden');
  };
  img.onerror = () => {
    if (cancelled) return;
    msg.className = 'picker-msg picker-error';
    msg.replaceChildren(icon('alert', 24), 'The image file is missing or cannot be loaded.');
  };
  img.src = imageUrl;

  function pixelAt(e) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.min(canvas.width - 1, Math.max(0, Math.floor(((e.clientX - rect.left) * canvas.width) / rect.width)));
    const y = Math.min(canvas.height - 1, Math.max(0, Math.floor(((e.clientY - rect.top) * canvas.height) / rect.height)));
    const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
    return { x, y, r, g, b, hex: toHex(r, g, b) };
  }

  function drawLoupe(x, y) {
    const lc = loupe.getContext('2d');
    const half = Math.floor(LOUPE_PIXELS / 2);
    const cell = LOUPE_SIZE / LOUPE_PIXELS;
    lc.imageSmoothingEnabled = false;
    lc.fillStyle = '#f3f4f6';
    lc.fillRect(0, 0, LOUPE_SIZE, LOUPE_SIZE);
    lc.drawImage(canvas, x - half, y - half, LOUPE_PIXELS, LOUPE_PIXELS, 0, 0, LOUPE_SIZE, LOUPE_SIZE);
    lc.strokeStyle = 'rgba(0,0,0,.12)';
    lc.lineWidth = 1;
    for (let i = 1; i < LOUPE_PIXELS; i++) {
      lc.beginPath();
      lc.moveTo(i * cell, 0);
      lc.lineTo(i * cell, LOUPE_SIZE);
      lc.moveTo(0, i * cell);
      lc.lineTo(LOUPE_SIZE, i * cell);
      lc.stroke();
    }
    lc.lineWidth = 2;
    lc.strokeStyle = '#fff';
    lc.strokeRect(half * cell, half * cell, cell, cell);
    lc.strokeStyle = '#111827';
    lc.strokeRect(half * cell - 2, half * cell - 2, cell + 4, cell + 4);
  }

  canvas.addEventListener('pointermove', (e) => {
    if (!ctx) return;
    const p = pixelAt(e);
    showReadout(p, true);
    drawLoupe(p.x, p.y);
  });
  canvas.addEventListener('pointerleave', () => {
    if (picked) {
      showReadout(picked, false);
      drawLoupe(picked.x, picked.y);
    } else showHint();
  });
  canvas.addEventListener('click', (e) => {
    if (!ctx) return;
    picked = pixelAt(e);
    showReadout(picked, false);
    drawLoupe(picked.x, picked.y);
    onPick?.(picked);
  });

  return { destroy: () => { cancelled = true; container.replaceChildren(); } };
}
