/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // Palette ASSIF — rosso primario #FD0000, secondario #C6343B
        brand: {
          50:  '#fff5f5',
          100: '#ffe3e3',
          200: '#ffc2c2',
          300: '#ff9090',
          500: '#FD0000',   // rosso primario ASSIF
          600: '#e00000',
          700: '#C6343B',   // rosso secondario ASSIF
          800: '#222222',   // quasi nero
          900: '#000000',   // nero (footer, header scuro)
        },
      },
      fontFamily: {
        sans: ['"Fira Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
