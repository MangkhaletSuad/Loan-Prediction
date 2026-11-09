// Shared UI helpers: DOM builder, icons, toasts, modal, confirm dialog, page behaviors.
// User text is only ever inserted with textContent (never innerHTML).

const SVG_NS = 'http://www.w3.org/2000/svg';

/** el('div', {class: 'x', onclick: fn, dataset: {id: 1}}, 'text', childNode, ...) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (k === 'style' && typeof v === 'object') Object.assign(node.style, v);
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, '');
    else node.setAttribute(k, String(v));
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const c of children.flat()) {
    if (c === undefined || c === null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

/** Icon from the sprite in base.html. */
export function icon(name, size = 18) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'currentColor');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

// ---- Toasts -------------------------------------------------------------- //
const FLASH_KEY = 'hc.flash';

export function toast(message, type = 'success') {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const t = el('div', { class: `toast toast-${type}` }, icon(type === 'error' ? 'alert' : 'check', 16), el('span', {}, message));
  root.append(t);
  setTimeout(() => t.remove(), type === 'error' ? 6000 : 3500);
}

/** Show a toast on the next page load (after a redirect or reload). */
export function flash(message, type = 'success') {
  try {
    sessionStorage.setItem(FLASH_KEY, JSON.stringify({ message, type }));
  } catch {
    /* storage unavailable: the message is skipped */
  }
}

export function reloadWith(message, type) {
  if (message) flash(message, type);
  window.location.reload();
}

export function goTo(url, message, type) {
  if (message) flash(message, type);
  window.location.assign(url);
}

function showFlash() {
  try {
    const raw = sessionStorage.getItem(FLASH_KEY);
    if (!raw) return;
    sessionStorage.removeItem(FLASH_KEY);
    const { message, type } = JSON.parse(raw);
    toast(message, type);
  } catch {
    /* ignore */
  }
}

// ---- Modal ----------------------------------------------------------------- //
/** Open a modal. Returns {close, body, footer, root}. onClose runs once when closed. */
export function openModal({ title, body, footer, size = 'md', onClose }) {
  let closed = false;
  const prevOverflow = document.body.style.overflow;
  const close = () => {
    if (closed) return;
    closed = true;
    document.removeEventListener('keydown', onKey);
    document.body.style.overflow = prevOverflow;
    backdrop.remove();
    onClose?.();
  };
  const onKey = (e) => e.key === 'Escape' && close();

  const bodyEl = el('div', { class: 'modal-body' }, body);
  const footerEl = footer ? el('div', { class: 'modal-footer' }, footer) : null;
  const modal = el('div', { class: `modal modal-${size}`, role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
    el('div', { class: 'modal-header' },
      el('h2', {}, title),
      el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Close', onclick: close }, icon('close'))),
    bodyEl, footerEl);
  const backdrop = el('div', { class: 'modal-backdrop', onmousedown: (e) => e.target === backdrop && close() }, modal);

  document.addEventListener('keydown', onKey);
  document.body.style.overflow = 'hidden';
  document.body.append(backdrop);
  return { close, body: bodyEl, footer: footerEl, root: modal };
}

/** Promise-based confirm (no window.confirm). Resolves true/false. */
export function confirmDialog({ title = 'Are you sure?', message, confirmText = 'Delete', danger = true } = {}) {
  return new Promise((resolve) => {
    let result = false;
    const ok = el('button', { class: `btn ${danger ? 'btn-danger' : 'btn-primary'}`, type: 'button' }, confirmText);
    const cancel = el('button', { class: 'btn', type: 'button' }, 'Cancel');
    const m = openModal({
      title, size: 'sm',
      body: el('p', { class: 'confirm-text' }, message),
      footer: [cancel, ok],
      onClose: () => resolve(result),
    });
    ok.addEventListener('click', () => { result = true; m.close(); });
    cancel.addEventListener('click', () => m.close());
    ok.focus();
  });
}

/** Map ApiError.fields onto inputs: sets .is-invalid and a .field-error under the field. */
export function showFieldErrors(form, fields = {}, map = {}) {
  form.querySelectorAll('.field-error.js-server').forEach((n) => n.remove());
  form.querySelectorAll('.is-invalid').forEach((n) => n.classList.remove('is-invalid'));
  for (const [field, msg] of Object.entries(fields)) {
    const input = form.querySelector(map[field] || `[name="${field}"]`);
    const holder = input?.closest('.field');
    if (input) input.classList.add('is-invalid');
    if (holder) holder.append(el('div', { class: 'field-error js-server' }, msg));
  }
}

export function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

// ---- Page-wide behaviors ------------------------------------------------- //
function swapToPlaceholder(img) {
  const ph = el('div', { class: `img-placeholder ${img.className.replace('js-safe-img', '')}`, role: 'img', 'aria-label': img.alt || 'Image missing' },
    icon('image', 28), el('span', {}, 'Image missing'));
  img.replaceWith(ph);
}

function init() {
  showFlash();

  // Images whose file is missing show a placeholder instead of a broken icon.
  document.addEventListener('error', (e) => {
    if (e.target instanceof HTMLImageElement && e.target.classList.contains('js-safe-img')) swapToPlaceholder(e.target);
  }, true);
  document.querySelectorAll('img.js-safe-img').forEach((img) => {
    if (img.complete && img.naturalWidth === 0) swapToPlaceholder(img);
  });

  // Local date/time display.
  document.querySelectorAll('time.js-local-time').forEach((t) => {
    if (t.dateTime) t.textContent = formatDate(t.dateTime);
  });

  // Mobile sidebar.
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const setNav = (open) => { sidebar?.classList.toggle('open', open); if (backdrop) backdrop.hidden = !open; };
  document.querySelectorAll('.js-nav-open').forEach((b) => b.addEventListener('click', () => setNav(true)));
  document.querySelectorAll('.js-nav-close').forEach((b) => b.addEventListener('click', () => setNav(false)));

  // Clickable table rows.
  document.addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-href]');
    if (row && !e.target.closest('a, button, input, select, label')) window.location.assign(row.dataset.href);
  });

  // Filter forms: selects submit immediately, search submits after typing stops.
  document.querySelectorAll('form.js-autosubmit').forEach((form) => {
    form.querySelectorAll('select').forEach((s) => s.addEventListener('change', () => {
      const page = form.querySelector('[name="page"]');
      if (page) page.remove();
      form.requestSubmit();
    }));
    const search = form.querySelector('input[type="search"]');
    if (search) {
      let timer;
      search.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => form.requestSubmit(), 500);
      });
      // Keep the caret at the end after the reload triggered by typing.
      let refocus = false;
      try {
        refocus = sessionStorage.getItem('hc.searchFocus') === '1';
        sessionStorage.removeItem('hc.searchFocus');
      } catch { /* ignore */ }
      if (refocus) {
        search.focus();
        search.setSelectionRange(search.value.length, search.value.length);
      }
      form.addEventListener('submit', () => {
        try { sessionStorage.setItem('hc.searchFocus', document.activeElement === search ? '1' : '0'); } catch { /* ignore */ }
      });
    }
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
