export const clampChannel = (v) => {
  const n = Math.round(Number(v));
  if (Number.isNaN(n)) return 0;
  return Math.min(255, Math.max(0, n));
};

export const toHex = (r, g, b) =>
  '#' + [r, g, b].map((v) => clampChannel(v).toString(16).padStart(2, '0')).join('').toUpperCase();

export const fromHex = (hex) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
};

export const formatRgb = (r, g, b) => `RGB(${r}, ${g}, ${b})`;

/** Perceived brightness — pick dark or light text over a swatch. */
export const isLight = (r, g, b) => 0.299 * r + 0.587 * g + 0.114 * b > 160;
