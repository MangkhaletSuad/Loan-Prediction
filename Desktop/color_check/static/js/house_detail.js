import { api } from './api.js';
import { bindColorActions } from './color_actions.js';
import { openColorForm } from './color_form.js';
import { acceptFiles } from './dropzone.js';
import { mountPicker } from './picker.js';
import { confirmDialog, el, goTo, openModal, reloadWith, showFieldErrors, toast } from './ui.js';

const house = JSON.parse(document.getElementById('house-data').textContent);
const pickerEl = document.querySelector('.js-picker');
const imageName = document.querySelector('.js-image-name');
const fileInput = document.querySelector('.js-file-input');

// ---- Active image (kept in ?image=<id> so reloads return to it) ------------ //
const params = new URLSearchParams(window.location.search);
let imageId = Number(params.get('image')) || null;
if (!house.images.some((i) => i.id === imageId)) imageId = house.images[0]?.id ?? null;
let picker = null;

function urlWith(changes) {
  const p = new URLSearchParams(window.location.search);
  Object.entries(changes).forEach(([k, v]) => (v == null ? p.delete(k) : p.set(k, v)));
  const s = p.toString();
  return `${window.location.pathname}${s ? `?${s}` : ''}`;
}

function showImage(id) {
  const img = house.images.find((i) => i.id === id);
  if (!img || !pickerEl) return;
  imageId = id;
  history.replaceState(null, '', urlWith({ image: id }));
  document.querySelectorAll('.thumb-item').forEach((t) => t.classList.toggle('active', Number(t.dataset.imageId) === id));
  imageName.textContent = img.original_name || '';
  picker?.destroy();
  picker = mountPicker(pickerEl, img.url, onPick, house.house_name);
}

async function afterSave(saved) {
  if (!saved) return;
  const other = String(saved.house_id) !== String(house.id);
  reloadWith(other ? `Saved to “${saved.house_name}”.` : 'Color saved.');
}

async function onPick(p) {
  afterSave(await openColorForm({ preset: { r: p.r, g: p.g, b: p.b, house_id: house.id, image_id: imageId } }));
}

const editColor = async (color) => {
  const saved = await openColorForm({ color });
  if (saved) reloadWith(String(saved.house_id) !== String(house.id) ? `Moved to “${saved.house_name}”.` : 'Color updated.');
};

if (imageId) showImage(imageId);

document.querySelectorAll('.js-thumb').forEach((btn) => btn.addEventListener('click', () => {
  showImage(Number(btn.closest('.thumb-item').dataset.imageId));
}));

// ---- Colors ---------------------------------------------------------------- //
document.querySelector('.js-add-color').addEventListener('click', async () => {
  afterSave(await openColorForm({ preset: { house_id: house.id, image_id: imageId } }));
});

document.querySelectorAll('.js-edit-tile').forEach((btn) => btn.addEventListener('click', () => {
  editColor(house.colors.find((c) => c.id === Number(btn.dataset.colorRef)));
}));

const table = document.querySelector('.js-color-table');
if (table) {
  bindColorActions(table, { onEdit: editColor });
  table.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-show-image');
    if (!btn) return;
    showImage(Number(btn.dataset.imageId));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

// ---- Images ---------------------------------------------------------------- //
document.querySelectorAll('.js-upload').forEach((btn) => btn.addEventListener('click', () => fileInput.click()));

fileInput.addEventListener('change', async () => {
  const files = acceptFiles(fileInput.files);
  fileInput.value = '';
  if (!files.length) return;
  const labels = document.querySelectorAll('.js-upload-label');
  labels.forEach((l) => { l.textContent = 'Uploading…'; });
  document.querySelectorAll('.js-upload').forEach((b) => { b.disabled = true; });
  const form = new FormData();
  files.forEach((f) => form.append('images', f));
  try {
    const created = await api.upload(`/api/houses/${house.id}/images`, form);
    goTo(urlWith({ image: created[0].id }), `${created.length} image(s) uploaded.`);
  } catch (err) {
    toast(err.fields?.images || err.message, 'error');
    labels.forEach((l) => { l.textContent = 'Upload images'; });
    document.querySelectorAll('.js-upload').forEach((b) => { b.disabled = false; });
  }
});

document.querySelectorAll('.js-delete-image').forEach((btn) => btn.addEventListener('click', async () => {
  const id = Number(btn.closest('.thumb-item').dataset.imageId);
  const linked = house.colors.filter((c) => c.image_id === id).length;
  const ok = await confirmDialog({
    title: 'Delete image?',
    message: linked
      ? `This image is referenced by ${linked} color record(s). The colors are kept, but their image reference will be cleared.`
      : 'The image file will be permanently removed.',
    confirmText: 'Delete image',
  });
  if (!ok) return;
  try {
    await api.del(`/api/images/${id}`);
    goTo(urlWith({ image: null }), 'Image deleted.');
  } catch (err) {
    toast(err.message, 'error');
  }
}));

// ---- House ----------------------------------------------------------------- //
document.querySelector('.js-delete-house').addEventListener('click', async () => {
  const ok = await confirmDialog({
    title: 'Delete house?',
    message: `Delete “${house.house_name}” with its ${house.image_count} image(s) and ${house.color_count} color record(s)? This cannot be undone.`,
    confirmText: 'Delete house',
  });
  if (!ok) return;
  try {
    await api.del(`/api/houses/${house.id}`);
    goTo('/', 'House deleted.');
  } catch (err) {
    toast(err.message, 'error');
  }
});

document.querySelector('.js-rename').addEventListener('click', () => {
  const input = el('input', { id: 'rename', name: 'house_name', class: 'input', maxlength: 150, value: house.house_name });
  const form = el('form', { id: 'rename-form', novalidate: true },
    el('div', { class: 'field' }, el('label', { for: 'rename' }, 'House name'), input));
  const cancel = el('button', { type: 'button', class: 'btn' }, 'Cancel');
  const save = el('button', { type: 'submit', form: 'rename-form', class: 'btn btn-primary' }, 'Save');
  const m = openModal({ title: 'Rename house', size: 'sm', body: form, footer: [cancel, save] });
  cancel.addEventListener('click', m.close);
  input.focus();
  input.select();
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return showFieldErrors(form, { house_name: 'House name is required.' });
    save.disabled = true;
    try {
      await api.put(`/api/houses/${house.id}`, { house_name: name });
      reloadWith('House renamed.');
    } catch (err) {
      showFieldErrors(form, err.fields && Object.keys(err.fields).length ? err.fields : { house_name: err.message });
      save.disabled = false;
    }
  });
});
