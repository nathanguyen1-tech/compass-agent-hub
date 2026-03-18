/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0d1117',
        surface:  '#161b22',
        surface2: '#1f2937',
        border:   '#30363d',
        cyan:     '#22d3ee',
        blue:     '#3b82f6',
        green:    '#10b981',
        yellow:   '#f59e0b',
        red:      '#ef4444',
        violet:   '#8b5cf6',
        gold:     '#f5a623',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'slide-in':   'slideIn .25s ease',
      },
      keyframes: {
        slideIn: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } }
      }
    }
  },
  plugins: []
}
