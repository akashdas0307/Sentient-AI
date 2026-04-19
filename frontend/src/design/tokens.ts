export const tokens = {
  colors: {
    bg: {
      0: 'var(--bg-0)',
      1: 'var(--bg-1)',
      2: 'var(--bg-2)',
      3: 'var(--bg-3)',
      4: 'var(--bg-4)',
      5: 'var(--bg-5)',
    },
    brand: {
      primary: 'var(--primary)',
      accent: 'var(--accent)',
      success: 'var(--success)',
      warning: 'var(--warning)',
      danger: 'var(--danger)',
    },
    text: {
      primary: 'var(--text-primary)',
      secondary: 'var(--text-secondary)',
      muted: 'var(--text-muted)',
      disabled: 'var(--text-disabled)',
    },
    border: {
      subtle: 'var(--border-subtle)',
      default: 'var(--border-default)',
      strong: 'var(--border-strong)',
    },
  },
} as const;
