// Create / edit a color record in a modal.
import { api } from './api.js';
import { clampChannel, formatRgb, fromHex, isLight, toHex } from './color.js';
import { mountManufacturerSelect } from './manufacturer_select.js';
import { el, openModal, showFieldErrors, toast } from './ui.js';

const NEW_HOUSE = '__new__';

/**
 * Open the color form.
 *   color:  existing record (Color.to_dict()) to edit
 *   preset: {r, g, b, house_id, image_id} for a new record (e.g. from the picker)
 * Resolves with the saved color, or null when cancelled.
 */
export function openColorForm({ color = null, preset = {} } = {}) {
  return new Promise((resolve) => {
    const src = color || preset;
    const state = {
      r: src.r ?? 255, g: src.g ?? 255, b: src.b ?? 255,
      house_id: src.house_id ? String(src.house_id) : '',
      image_id: src.image_id ? String(src.image_id) : '',
    };
    let houses = [];
    let saved = null;

    // ---- fields ---------------------------------------------------------- //
    const field = (labelText, control, { req = true, forId } = {}) => el('div', { class: 'field' },
      el('label', { for: forId }, labelText, req ? ' ' : '', req ? el('span', { class: 'req' }, '*') : ''), control);

    const nameInput = el('input', { id: 'cf-name', name: 'color_name', class: 'input', maxlength: 100, placeholder: 'e.g. Warm White, Cream Beige, Ocean Blue', value: color?.color_name || '' });
    const mfrInput = el('input', { id: 'cf-mfr', name: 'manufacturing', class: 'input', placeholder: 'Search or type a manufacturer (TOA, DELUX…)', value: color?.manufacturing || '' });
    const modelInput = el('input', { id: 'cf-model', name: 'model', class: 'input', maxlength: 150, placeholder: 'e.g. TOA 4 SEASONS, DELUX EASYCLEAN', autocapitalize: 'characters', value: (color?.model || '').toUpperCase() });
    const houseSelect = el('select', { id: 'cf-house', name: 'house_id', class: 'select' }, el('option', { value: '' }, 'Loading houses…'));
    const newHouseInput = el('input', { name: 'house_name', class: 'input mt-8', maxlength: 150, placeholder: 'New house name', hidden: true });
    const imageSelect = el('select', { id: 'cf-image', name: 'image_id', class: 'select', disabled: true });

    // Model: force uppercase while keeping the caret where the user is typing.
    modelInput.addEventListener('input', () => {
      const { selectionStart, selectionEnd } = modelInput;
      const upper = modelInput.value.toUpperCase();
      if (upper !== modelInput.value) {
        modelInput.value = upper;
        modelInput.setSelectionRange(selectionStart, selectionEnd);
      }
    });

    // RGB editor
    const bigSwatch = el('div', { class: 'big-swatch' }, el('span', { class: 'mono' }));
    const rgbText = el('div', { class: 'mono strong' });
    const hexText = el('div', { class: 'mono strong' });
    const hexInput = el('input', { id: 'cf-hex', name: 'hex', class: 'input mono', maxlength: 7 });
    const nativeColor = el('input', { type: 'color', class: 'native-color', 'aria-label': 'Color picker' });
    const channels = {};
    const rgbRows = [['r', 'Red'], ['g', 'Green'], ['b', 'Blue']].map(([ch, label]) => {
      const range = el('input', { type: 'range', min: 0, max: 255, 'aria-label': `${label} slider` });
      const num = el('input', { id: `cf-${ch}`, type: 'number', min: 0, max: 255, class: 'input input-num' });
      channels[ch] = { range, num };
      const onInput = (e) => setChannel(ch, e.target.value);
      range.addEventListener('input', onInput);
      num.addEventListener('input', onInput);
      return el('div', { class: `rgb-row rgb-${ch}` }, el('label', { for: `cf-${ch}` }, ch.toUpperCase()), range, num);
    });

    const channelsOk = () => ['r', 'g', 'b'].every((k) => state[k] !== '' && state[k] >= 0 && state[k] <= 255);

    function paint({ skipHexInput = false, skip = null } = {}) {
      const ok = channelsOk();
      const hex = ok ? toHex(state.r, state.g, state.b) : '#FFFFFF';
      bigSwatch.style.background = hex;
      bigSwatch.style.color = isLight(state.r || 0, state.g || 0, state.b || 0) ? '#111827' : '#fff';
      bigSwatch.firstChild.textContent = hex;
      rgbText.textContent = ok ? formatRgb(state.r, state.g, state.b) : '—';
      hexText.textContent = hex;
      nativeColor.value = hex.toLowerCase();
      if (!skipHexInput && ok) hexInput.value = hex;
      for (const ch of ['r', 'g', 'b']) {
        channels[ch].range.value = state[ch] === '' ? 0 : state[ch];
        if (skip !== channels[ch].num) channels[ch].num.value = state[ch];
      }
    }

    function setChannel(ch, value) {
      state[ch] = value === '' ? '' : clampChannel(value);
      paint({ skip: value === '' ? channels[ch].num : null });
    }

    function setHex(value) {
      const rgb = fromHex(value);
      if (rgb) {
        Object.assign(state, rgb);
        hexInput.value = value.toUpperCase();
      }
      paint({ skipHexInput: true });
    }
    hexInput.addEventListener('input', () => setHex(hexInput.value));
    nativeColor.addEventListener('input', () => { setHex(nativeColor.value); hexInput.value = nativeColor.value.toUpperCase(); });

    // Houses & images
    function renderImages() {
      const house = houses.find((h) => String(h.id) === houseSelect.value);
      const imgs = house?.images || [];
      imageSelect.replaceChildren(
        el('option', { value: '' }, imgs.length ? 'None' : 'No images for this house'),
        ...imgs.map((img, i) => el('option', { value: img.id }, `#${i + 1} ${img.original_name || img.image_path}`)));
      imageSelect.disabled = !imgs.length;
      imageSelect.value = imgs.some((i) => String(i.id) === state.image_id) ? state.image_id : '';
    }
    houseSelect.addEventListener('change', () => {
      state.image_id = '';
      newHouseInput.hidden = houseSelect.value !== NEW_HOUSE;
      if (!newHouseInput.hidden) newHouseInput.focus();
      renderImages();
    });
    imageSelect.addEventListener('change', () => { state.image_id = imageSelect.value; });

    // ---- layout ---------------------------------------------------------- //
    const form = el('form', { id: 'color-form', class: 'color-form', novalidate: true },
      el('div', { class: 'color-form-preview' }, bigSwatch,
        el('div', { class: 'color-values' },
          el('div', {}, el('span', { class: 'muted small' }, 'RGB'), rgbText),
          el('div', {}, el('span', { class: 'muted small' }, 'HEX'), hexText))),
      el('div', { class: 'color-form-fields' },
        field('Color name', nameInput, { forId: 'cf-name' }),
        el('fieldset', { class: 'field' },
          el('legend', {}, 'RGB ', el('span', { class: 'req' }, '*')),
          el('div', { class: 'rgb-editor' }, rgbRows),
          el('div', { class: 'hex-row' }, nativeColor, el('label', { for: 'cf-hex', class: 'muted small' }, 'HEX'), hexInput),
          el('input', { type: 'hidden', name: 'rgb' })),
        el('div', { class: 'field-grid' },
          field('Manufacturing', mfrInput, { forId: 'cf-mfr' }),
          field('Model', modelInput, { forId: 'cf-model' })),
        el('div', { class: 'field-grid' },
          el('div', { class: 'field' }, el('label', { for: 'cf-house' }, 'House name ', el('span', { class: 'req' }, '*')), houseSelect, newHouseInput),
          field('Image reference', imageSelect, { req: false, forId: 'cf-image' }))));

    const cancelBtn = el('button', { type: 'button', class: 'btn' }, 'Cancel');
    const saveBtn = el('button', { type: 'submit', form: 'color-form', class: 'btn btn-primary' }, color ? 'Save changes' : 'Save color');
    const modal = openModal({
      title: color ? 'Edit color' : 'Add color', size: 'lg', body: form, footer: [cancelBtn, saveBtn],
      onClose: () => resolve(saved),
    });
    cancelBtn.addEventListener('click', modal.close);
    paint();
    nameInput.focus();

    // Error map: server field names → inputs
    const errorMap = { rgb: '[name="hex"]', hex: '[name="hex"]', house_id: '[name="house_id"]', house_name: '[name="house_id"]', image_id: '[name="image_id"]' };

    // ---- load houses + manufacturers ------------------------------------- //
    Promise.all([api.get('/api/houses'), api.get('/api/manufacturers')])
      .then(([h, m]) => {
        houses = h;
        mountManufacturerSelect(mfrInput, m.map((x) => x.name));
        houseSelect.replaceChildren(
          el('option', { value: '' }, 'Select a house…'),
          ...houses.map((x) => el('option', { value: x.id }, x.house_name)),
          el('option', { value: NEW_HOUSE }, '+ Create new house'));
        houseSelect.value = state.house_id || (houses.length ? '' : NEW_HOUSE);
        newHouseInput.hidden = houseSelect.value !== NEW_HOUSE;
        renderImages();
      })
      .catch((e) => {
        toast(e.message, 'error');
        houseSelect.replaceChildren(el('option', { value: NEW_HOUSE }, '+ Create new house'));
        newHouseInput.hidden = false;
      });

    // ---- submit ----------------------------------------------------------- //
    function validate() {
      const e = {};
      const name = nameInput.value.trim();
      if (!name) e.color_name = 'Color name is required.';
      else if (name.length > 100) e.color_name = 'Max 100 characters.';
      if (!channelsOk()) e.rgb = 'Each RGB channel must be a number between 0 and 255.';
      if (!mfrInput.value.trim()) e.manufacturing = 'Manufacturing is required.';
      const model = modelInput.value.trim();
      if (!model) e.model = 'Model is required.';
      else if (model.length > 150) e.model = 'Max 150 characters.';
      if (houseSelect.value === NEW_HOUSE) {
        if (!newHouseInput.value.trim()) e.house_name = 'House name is required.';
      } else if (!houseSelect.value) {
        e.house_name = 'Select a house or create a new one.';
      }
      return e;
    }

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errs = validate();
      showFieldErrors(form, errs, errorMap);
      if (Object.keys(errs).length) return;

      const isNew = houseSelect.value === NEW_HOUSE;
      const payload = {
        color_name: nameInput.value.trim(),
        r: state.r, g: state.g, b: state.b,
        manufacturing: mfrInput.value.trim(),
        model: modelInput.value.trim().toUpperCase(),
        image_id: isNew ? null : imageSelect.value || null,
      };
      if (isNew) payload.house_name = newHouseInput.value.trim();
      else payload.house_id = Number(houseSelect.value);

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving…';
      try {
        saved = color ? await api.put(`/api/colors/${color.id}`, payload) : await api.post('/api/colors', payload);
        modal.close();
      } catch (err) {
        showFieldErrors(form, err.fields, errorMap);
        toast(err.message, 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = color ? 'Save changes' : 'Save color';
      }
    });
  });
}
