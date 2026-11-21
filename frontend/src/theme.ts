import type { ThemeTokens } from '@venturet/theme';

/**
 * Chop Shop base tokens. Safety orange is reserved for value bars and the
 * primary action; everything else stays in steel and navy ink.
 */
export const baseTheme: Partial<ThemeTokens> = {
  colorPrimary: '#F26B1D',
  colorSecondary: '#1F8A5B',
  borderRadius: 6,
  fontSize: 15,
  shadow: 'none',
  density: 'comfortable',
  mode: 'light',
};

export const FONT_BODY = "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
export const FONT_DISPLAY = "'IBM Plex Sans Condensed', 'IBM Plex Sans', sans-serif";
