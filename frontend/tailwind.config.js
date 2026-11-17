// lectern's design tokens. Colours live in src/index.css as "r g b" channels so opacity modifiers work.
import typography from '@tailwindcss/typography';

const rgb = (name) => `rgb(var(--${name}) / <alpha-value>)`;
const status = (name, ink) => ({
  DEFAULT: rgb(name),
  soft: rgb(`${name}-soft`),
  line: rgb(`${name}-line`),
  ...(ink ? { ink: rgb(`${name}-ink`) } : {}),
});
const tag = (name) => ({ bg: rgb(`tag-${name}-bg`), fg: rgb(`tag-${name}-fg`), line: rgb(`tag-${name}-line`) });

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    screens: { sm: '576px', md: '768px', nav: '800px', lg: '992px', xl: '1200px', '2xl': '1600px' },
    extend: {
      colors: {
        brand: { DEFAULT: rgb('brand'), strong: rgb('brand-strong'), hover: rgb('brand-hover'), soft: rgb('brand-soft') },
        ink: {
          DEFAULT: '#262626',
          strong: 'rgba(0,0,0,.88)',
          soft: '#595959',
          muted: '#8C8C8C',
          faint: 'rgba(0,0,0,.45)',
        },
        line: { DEFAULT: '#D9D9D9', soft: '#F0F0F0' },
        surface: { DEFAULT: '#FFFFFF', muted: '#FAFAFA', sunken: '#F5F5F5', selected: '#F5F5FA', hover: '#F3F2F2' },
        success: status('success'),
        warning: status('warning', true),
        info: status('info'),
        danger: status('danger', true),
        tag: { pink: tag('pink'), cyan: tag('cyan'), orange: tag('orange'), teal: tag('teal'), neutral: tag('neutral') },
      },
      fontFamily: {
        display: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        xs: ['.75rem', '1.25rem'],
        sm: ['.875rem', '1.375rem'],
        base: ['1rem', '1.5rem'],
        lg: ['1.125rem', '1.5rem'],
        xl: ['1.25rem', '1.75rem'],
        '2xl': ['1.5rem', '2rem'],
        '3xl': ['2.25rem', '3.375rem'],
      },
      borderRadius: { sm: '2px', DEFAULT: '4px', md: '6px', lg: '8px' },
      boxShadow: { panel: '0 0 10px rgba(0,0,0,.1)', card: '0 2px 10px rgba(0,0,0,.1)' },
      spacing: { sider: '178px', 'sider-collapsed': '80px', drawer: '250px', topbar: '64px' },
      maxWidth: { content: '1600px' },
    },
  },
  plugins: [typography],
};
