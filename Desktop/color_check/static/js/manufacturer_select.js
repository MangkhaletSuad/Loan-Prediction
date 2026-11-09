// Searchable combobox: pick an existing manufacturer or type a new one.
import { el } from './ui.js';

let uid = 0;

/** Enhance a text input. names: string[]. onChange(value) is optional. */
export function mountManufacturerSelect(input, names, onChange) {
  const listId = `combo-${++uid}`;
  const wrap = el('div', { class: 'combo' });
  input.replaceWith(wrap);
  wrap.append(input);
  Object.assign(input, { autocomplete: 'off' });
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-controls', listId);
  input.setAttribute('aria-expanded', 'false');

  let list = null;
  let items = [];
  let active = 0;

  const compute = () => {
    const value = input.value.trim();
    const q = value.toLowerCase();
    const matches = q ? names.filter((n) => n.toLowerCase().includes(q)) : names;
    items = matches.map((n) => ({ label: n, value: n }));
    if (q && !names.some((n) => n.toLowerCase() === q)) {
      items.push({ label: `Add “${value}” as new manufacturer`, value, isNew: true });
    }
  };

  const close = () => {
    list?.remove();
    list = null;
    input.setAttribute('aria-expanded', 'false');
  };

  const choose = (v) => {
    input.value = v;
    onChange?.(v);
    close();
  };

  const highlight = () => {
    list?.querySelectorAll('li').forEach((li, i) => {
      li.classList.toggle('active', i === active);
      li.setAttribute('aria-selected', String(i === active));
    });
  };

  const render = () => {
    compute();
    if (!items.length) return close();
    active = Math.min(active, items.length - 1);
    const ul = el('ul', { class: 'combo-list', id: listId, role: 'listbox' },
      items.map((it, i) => el('li', {
        role: 'option',
        'aria-selected': String(i === active),
        class: `${i === active ? 'active' : ''} ${it.isNew ? 'is-new' : ''}`,
        onmousedown: (e) => { e.preventDefault(); choose(it.value); },
        onmouseenter: () => { active = i; highlight(); },
      }, it.label)));
    if (list) list.replaceWith(ul);
    else wrap.append(ul);
    list = ul;
    input.setAttribute('aria-expanded', 'true');
  };

  input.addEventListener('input', () => { active = 0; onChange?.(input.value); render(); });
  input.addEventListener('focus', render);
  input.addEventListener('blur', close);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      active = list ? Math.min(active + 1, items.length - 1) : 0;
      render();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      active = Math.max(active - 1, 0);
      render();
    } else if (e.key === 'Enter' && list && items[active]) {
      e.preventDefault();
      choose(items[active].value);
    } else if (e.key === 'Escape' && list) {
      e.stopPropagation();
      close();
    }
  });
}
