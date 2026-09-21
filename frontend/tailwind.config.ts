import type { Config } from 'tailwindcss';
import tailwindAnimate from 'tailwindcss-animate';

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        log: ['var(--font-log)'],
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'help-typing-dot': {
          '0%, 70%, 100%': {
            transform: 'translateY(0) scale(0.72)',
            backgroundColor: 'hsl(var(--muted-foreground) / 0.4)',
          },
          '35%': {
            transform: 'translateY(-5px) scale(1)',
            backgroundColor: 'hsl(var(--warning))',
          },
        },
        'help-typing-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.65' },
          '70%, 100%': { transform: 'scale(1.45)', opacity: '0' },
        },
        'help-typing-sweep': {
          '0%': { transform: 'translateX(-12px)', opacity: '0' },
          '35%': { opacity: '0.9' },
          '100%': { transform: 'translateX(46px)', opacity: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'help-typing-dot': 'help-typing-dot 1.15s ease-in-out infinite',
        'help-typing-ring': 'help-typing-ring 1.6s ease-out infinite',
        'help-typing-sweep': 'help-typing-sweep 1.15s ease-in-out infinite',
      },
    },
  },
  plugins: [tailwindAnimate],
} satisfies Config;
