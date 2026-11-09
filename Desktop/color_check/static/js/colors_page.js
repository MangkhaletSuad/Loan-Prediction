import { bindColorActions } from './color_actions.js';
import { openColorForm } from './color_form.js';
import { reloadWith } from './ui.js';

const table = document.querySelector('.js-color-table');
if (table) {
  bindColorActions(table, {
    onEdit: async (color) => {
      if (await openColorForm({ color })) reloadWith('Color updated.');
    },
  });
}

document.querySelector('.js-add-color').addEventListener('click', async () => {
  if (await openColorForm()) reloadWith('Color saved.');
});
