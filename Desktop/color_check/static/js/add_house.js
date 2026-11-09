import { api } from './api.js';
import { mountDropzone } from './dropzone.js';
import { el, goTo, showFieldErrors, toast } from './ui.js';

const form = document.getElementById('add-house-form');
const nameInput = form.querySelector('[name="house_name"]');
const submit = form.querySelector('.js-submit');
let existing = [];
api.get('/api/houses').then((h) => { existing = h; }).catch(() => {});

const label = (n) => (n ? `Create house & upload ${n} image(s)` : 'Create house');
const dz = mountDropzone(form.querySelector('.js-dropzone'), { onChange: (files) => { submit.textContent = label(files.length); } });

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = nameInput.value.trim();
  const duplicate = existing.find((h) => h.house_name.toLowerCase() === name.toLowerCase());
  let error = '';
  if (!name) error = 'House name is required.';
  else if (name.length > 150) error = 'Max 150 characters.';
  else if (duplicate) error = 'A house with this name already exists.';
  if (error) {
    showFieldErrors(form, { house_name: error });
    if (duplicate) {
      form.querySelector('.field-error.js-server').append(' ',
        el('a', { href: `/houses/${duplicate.id}` }, `Open “${duplicate.house_name}” to add images or colors →`));
    }
    return;
  }

  const files = dz.getFiles();
  const data = new FormData();
  data.append('house_name', name);
  files.forEach((f) => data.append('images', f));
  submit.disabled = true;
  submit.textContent = 'Creating…';
  try {
    const house = await api.upload('/api/houses', data);
    goTo(`/houses/${house.id}`, `House “${house.house_name}” created.`);
  } catch (err) {
    showFieldErrors(form, err.fields, { images: '.js-dropzone .dropzone' });
    toast(err.message, 'error');
    submit.disabled = false;
    submit.textContent = label(files.length);
  }
});
