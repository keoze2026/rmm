/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#F7F9FC',        // app background (light gray-blue canvas)
        surface: '#FFFFFF',    // cards
        raised: '#FFFFFF',     // raised cards / dialogs
        sidebar: '#FFFFFF',    // sidebar surface
        line: '#E6EAF0',       // subtle borders
        edge: '#D4DAE3',       // stronger borders
        fg: '#1E2A38',         // primary text (dark slate)
        dim: '#8A94A6',        // secondary text
        faint: '#A7B0BF',      // faint / placeholder
        signal: '#2F6FE4',     // primary blue
        signalHover: '#3B7DDB',
        accent: '#8CB6F2',     // light accent blue
        accentSoft: '#B9D4F7',
        online: '#3FBF7F',     // success green
        offline: '#C2C9D4',    // offline gray
        warn: '#F5C451',       // pending / warning yellow
        success: '#3FBF7F',
        danger: '#EF6B6B'      // rejected / declined coral
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace']
      },
      boxShadow: {
        card: '0 1px 3px rgba(30,42,56,0.06), 0 1px 2px rgba(30,42,56,0.04)',
        cardHover: '0 4px 12px rgba(30,42,56,0.10)',
        glow: '0 0 0 1px rgba(47,111,228,0.20), 0 0 18px -4px rgba(47,111,228,0.35)'
      }
    }
  },
  plugins: []
}