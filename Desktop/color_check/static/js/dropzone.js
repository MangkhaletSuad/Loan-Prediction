// Image file selection: type/size checks (the server re-validates the content).
import { el, icon, toast } from './ui.js';

export const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp'];
export const MAX_FILE_MB = 20;

/** Returns [validFiles, rejectedMessages]. */
export function filterImageFiles(list) {
  const ok = [];
  const bad = [];
  Array.from(list).forEach((f) => {
    if (!ACCEPTED_TYPES.includes(f.type)) bad.push(`${f.name}: unsupported type`);
    else if (f.size > MAX_FILE_MB * 1024 * 1024) bad.push(`${f.name}: larger than ${MAX_FILE_MB} MB`);
    else ok.push(f);
  });
  return [ok, bad];
}

/** Keep only valid files, toasting the rejected ones. */
export function acceptFiles(list) {
  const [ok, bad] = filterImageFiles(list);
  if (bad.length) toast(`Skipped: ${bad.join('; ')}`, 'error');
  return ok;
}

/** Drag & drop area with previews. onChange(files) on every change. Returns {getFiles()}. */
export function mountDropzone(container, { onChange } = {}) {
  let files = [];
  let urls = [];
  const input = el('input', { type: 'file', accept: ACCEPTED_TYPES.join(','), multiple: true, hidden: true });
  const zone = el('div', { class: 'dropzone', role: 'button', tabindex: '0' },
    icon('upload', 28),
    el('strong', {}, 'Click to choose or drag images here'),
    el('span', { class: 'muted small' }, `PNG, JPG, WEBP, GIF or BMP · up to ${MAX_FILE_MB} MB each · multiple allowed`),
    input);
  const grid = el('div', { class: 'preview-grid' });
  container.replaceChildren(zone, grid);

  const render = () => {
    urls.forEach((u) => URL.revokeObjectURL(u));
    urls = files.map((f) => URL.createObjectURL(f));
    grid.hidden = !files.length;
    grid.replaceChildren(...files.map((f, i) => el('div', { class: 'preview' },
      el('img', { src: urls[i], alt: f.name }),
      el('button', {
        type: 'button', class: 'preview-remove', 'aria-label': `Remove ${f.name}`,
        onclick: (e) => { e.stopPropagation(); files = files.filter((_, j) => j !== i); render(); },
      }, icon('close', 14)),
      el('span', { class: 'preview-name' }, f.name))));
    onChange?.(files);
  };
  const add = (list) => {
    const ok = acceptFiles(list);
    if (ok.length) { files = [...files, ...ok]; render(); }
  };

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && input.click());
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
  zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('drag'); add(e.dataTransfer.files); });
  input.addEventListener('change', () => { add(input.files); input.value = ''; });
  grid.hidden = true;

  return { getFiles: () => files };
}
