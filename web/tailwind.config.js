/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // TensorBay brand — extracted from the Commission Plan deck slides
        space: {
          DEFAULT: '#0D0221', // deep-space purple — primary background
          900: '#0D0221',
          800: '#140630',
          700: '#1A0A3A',
          600: '#241043', // card/panel surface
          500: '#2E1557',
        },
        cyan: {
          DEFAULT: '#00D4FF', // primary accent
          glow: '#00D4FF',
        },
        grape: {
          DEFAULT: '#B165FB', // secondary accent (vivid purple)
          soft: '#B9A9D6', // muted lavender text
        },
        flamingo: {
          DEFAULT: '#FF6EC4', // tertiary accent / gradients
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(0,212,255,0.15), 0 8px 40px -12px rgba(177,101,251,0.35)',
        card: '0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 32px -16px rgba(0,0,0,0.7)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #B165FB 0%, #00D4FF 100%)',
        'brand-radial':
          'radial-gradient(1200px 600px at 80% -10%, rgba(177,101,251,0.18), transparent), radial-gradient(900px 500px at 10% 10%, rgba(0,212,255,0.10), transparent)',
      },
    },
  },
  plugins: [],
};
