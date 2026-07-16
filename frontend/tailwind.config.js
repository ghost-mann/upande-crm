import tailwindcssAnimate from 'tailwindcss-animate';

/** @type {import('tailwindcss').Config} */
// Scoped to this app's single CRM build.
// so no utility classes or preflight leak into portal/site/webshop/customer-panel.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        // Poppins everywhere (consistent with the other customer_portal sections).
        sans: ['Poppins', 'system-ui', 'sans-serif'],
        mono: ['Poppins', 'system-ui', 'sans-serif'],
        // Fraunces display serif for mail-client headings (UFD-modern reference).
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        hover: 'var(--shadow-hover)',
      },
      backgroundImage: {
        'grad-ink': 'var(--grad-ink)',
        'grad-gold': 'var(--grad-gold)',
      },
      colors: {
        // shadcn semantic tokens (HSL channels in CSS vars)
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        // CRM raw palette (exact hex via CSS vars) — UFD-modern ink + gold
        gold: { DEFAULT: 'var(--gold)', 2: 'var(--gold-2)', soft: 'var(--gold-soft)', text: 'var(--gold-text)' },
        hairline: 'var(--hairline)',
        canvas: 'var(--bg)',
        surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)', 3: 'var(--surface-3)' },
        ink: { DEFAULT: 'var(--text)', 2: 'var(--text-2)', 3: 'var(--text-3)', 4: 'var(--ink-4)', mute: 'var(--ink-mute)', faint: 'var(--ink-faint)' },
        bio: 'var(--bio)',
        line: { DEFAULT: 'var(--line)', 2: 'var(--line-2)' },
        good: { DEFAULT: 'var(--good)', soft: 'var(--good-soft)' },
        warn: { DEFAULT: 'var(--warn)', soft: 'var(--warn-soft)' },
        bad: { DEFAULT: 'var(--bad)', soft: 'var(--bad-soft)' },
        info: { DEFAULT: 'var(--info)', soft: 'var(--info-soft)' },
        hover: 'var(--hover)',
        selected: 'var(--selected)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 3px)',
      },
      keyframes: {
        'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
        'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [tailwindcssAnimate],
};
