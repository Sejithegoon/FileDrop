// WiFiDrop colours: the same black-and-blue as the PC's web page, plus a light version.
import { useColorScheme } from 'react-native';

const dark = {
  bg: '#000000',
  surface: '#0a0d14',
  surface2: '#111725',
  border: '#1c2438',
  text: '#e8eefc',
  muted: '#8a96b0',
  accent: '#2f7bff',
  accentInk: '#ffffff',
  danger: '#f87171',
  ok: '#34d399',
  warn: '#fbbf24',
  folder: '#5c9bff',
  image: '#38bdf8',
  video: '#a78bfa',
  audio: '#34d399',
  doc: '#93c5fd',
  archive: '#fb923c',
};

const light: typeof dark = {
  bg: '#f4f6fb',
  surface: '#ffffff',
  surface2: '#eef2fa',
  border: '#dbe2f0',
  text: '#0b1220',
  muted: '#5b6782',
  accent: '#1f66e5',
  accentInk: '#ffffff',
  danger: '#dc2626',
  ok: '#059669',
  warn: '#b45309',
  folder: '#2f7bff',
  image: '#0284c7',
  video: '#7c3aed',
  audio: '#059669',
  doc: '#2563eb',
  archive: '#ea580c',
};

export type Colors = typeof dark;

export function useColors(): Colors {
  return useColorScheme() === 'light' ? light : dark;
}

export const radius = 14;
