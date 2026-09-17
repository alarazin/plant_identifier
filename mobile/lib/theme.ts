/** Shared beige, green and terracotta colors. */

export const colors = {
  bg: '#F5F0E6',
  /** Card background. */
  surface: '#FFFCF6',
  /** Recessed row, e.g. a history entry. */
  surfaceAlt: '#EFE8DA',
  border: '#E0D7C6',

  text: '#2B2721',
  textMuted: '#5C5449',
  textFaint: '#837A6B',

  accent: '#4F6F44',
  /** Decorative sage for empty-state and permission glyphs. Not for text. */
  accentDim: '#9DB790',

  // Colors for the three confidence levels.
  high: '#4F6F44',
  medium: '#9C6526',
  low: '#A0553B',

  warn: '#9C6526',
  danger: '#A0553B',

  /** Light text and dark overlays for controls over photos. */
  onImage: '#FBF8F2',
  onImageAccent: '#BBD3AD',
  scrim: 'rgba(38,33,26,0.55)',

  /** Photo overlay used during identification. */
  veil: 'rgba(245,240,230,0.55)',
} as const;

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 18,
  pill: 999,
} as const;

export const type = {
  display: { fontSize: 28, fontWeight: '700' as const, letterSpacing: -0.5 },
  title: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.3 },
  body: { fontSize: 15, fontWeight: '400' as const },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const },
  small: { fontSize: 13, fontWeight: '400' as const },
  caption: { fontSize: 11, fontWeight: '600' as const, letterSpacing: 0.6 },
  mono: { fontSize: 14, fontStyle: 'italic' as const },
} as const;

export const confidenceColor = (c: 'high' | 'medium' | 'low') =>
  c === 'high' ? colors.high : c === 'medium' ? colors.medium : colors.low;

/** Plain-language gloss. "high" alone reads as a probability; this doesn't. */
export const confidenceLabel = (c: 'high' | 'medium' | 'low') =>
  c === 'high' ? 'Confident' : c === 'medium' ? 'Fairly sure' : 'Uncertain';
