import { api } from './api.js';
import { confirmDialog, reloadWith, toast } from './ui.js';

/** Read the color dict embedded in a table row (data-color). */
export const rowColor = (row) => JSON.parse(row.dataset.color);

/**
 * Wire Edit / Delete buttons of _color_table.html rows inside root.
 * onEdit(color) is called with the row's color dict.
 */
export function bindColorActions(root, { onEdit } = {}) {
  root.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-edit-color, .js-delete-color');
    if (!btn) return;
    const color = rowColor(btn.closest('tr'));

    if (btn.classList.contains('js-edit-color')) {
      onEdit?.(color);
      return;
    }
    const ok = await confirmDialog({
      title: 'Delete color?',
      message: `Delete “${color.color_name}” (${color.rgb}) from ${color.house_name}? This cannot be undone.`,
    });
    if (!ok) return;
    try {
      await api.del(`/api/colors/${color.id}`);
      reloadWith('Color deleted.');
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}
