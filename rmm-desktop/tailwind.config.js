/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0B0F14',
        surface: '#10161F',
        raised: '#141C27',
        line: '#1E2A38',
        edge: '#27374A',
        fg: '#E6EDF3',
        dim: '#8B97A6',
        faint: '#5B6675',
        signal: '#35C2D8',
        online: '#34D399',
        offline: '#4B5563',
        warn: '#F5B544'
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace']
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(53,194,216,0.25), 0 0 18px -4px rgba(53,194,216,0.45)'
      }
    }
  },
  plugins: []
}
