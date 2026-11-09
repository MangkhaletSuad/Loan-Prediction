import { api } from './api.js';
import { confirmDialog, reloadWith, showFieldErrors, toast } from './ui.js';

const form = document.getElementById('mfr-form');
const input = document.getElementById('mfr-name');
const existing = JSON.parse(document.getElementById('mfr-data').textContent).map((n) => n.toLowerCase());

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = input.value.trim();
  let error = '';
  if (!name) error = 'Manufacturer name is required.';
  else if (name.length > 100) error = 'Max 100 characters.';
  else if (existing.includes(name.toLowerCase())) error = 'This manufacturer already exists.';
  if (error) return showFieldErrors(form, { name: error });

  try {
    await api.post('/api/manufacturers', { name });
    reloadWith(`Added “${name}”.`);
  } catch (err) {
    showFieldErrors(form, err.fields && Object.keys(err.fields).length ? err.fields : { name: err.message });
  }
});

document.querySelectorAll('.js-delete-mfr').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const row = btn.closest('tr');
    const name = row.dataset.mfrName;
    const ok = await confirmDialog({ title: 'Delete manufacturer?', message: `Remove “${name}” from the manufacturer list?` });
    if (!ok) return;
    try {
      await api.del(`/api/manufacturers/${row.dataset.mfrId}`);
      reloadWith('Manufacturer deleted.');
    } catch (err) {
      toast(err.message, 'error');
    }
  });
});
