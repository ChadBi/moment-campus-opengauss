export interface CategoryVisual {
  text: string;
  background: string;
  border: string;
  marker: string;
}

const NEUTRAL_VISUAL: CategoryVisual = {
  text: '#5f7074',
  background: '#edf1f2',
  border: '#d8e1e3',
  marker: '#6a7d81',
};

const CATEGORY_VISUALS: CategoryVisual[] = [
  { text: '#8f432f', background: '#f9ede7', border: '#efc9bb', marker: '#d86849' },
  { text: '#5e477d', background: '#f2ebf6', border: '#d9cae5', marker: '#8063a4' },
  { text: '#315f67', background: '#e7f0f1', border: '#bfd6d9', marker: '#497d86' },
  { text: '#385b88', background: '#ebf0f7', border: '#c7d4e6', marker: '#5878a6' },
  { text: '#8a6023', background: '#f8efe0', border: '#ead2a9', marker: '#c58b32' },
  { text: '#426f48', background: '#ebf2ed', border: '#c6d9c9', marker: '#639b69' },
  { text: '#8a4f42', background: '#f6ece9', border: '#e4c8c1', marker: '#b96956' },
  { text: '#3e6c5c', background: '#e9f1ed', border: '#c3d8ce', marker: '#5d8b78' },
  { text: '#756020', background: '#f6f1df', border: '#e4d7a8', marker: '#aa8c35' },
  { text: '#445f72', background: '#eaf0f3', border: '#c5d4dc', marker: '#607f92' },
];

const hashCategoryCode = (code: string): number => {
  let hash = 2166136261;
  for (let index = 0; index < code.length; index += 1) {
    hash ^= code.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

export const getCategoryVisual = (code?: string | null): CategoryVisual => {
  const normalized = code?.trim().toLowerCase();
  if (!normalized) return NEUTRAL_VISUAL;
  return CATEGORY_VISUALS[hashCategoryCode(normalized) % CATEGORY_VISUALS.length];
};
