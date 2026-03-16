/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0eaff',
          500: '#3b5fc0',
          600: '#2f4fa8',
          700: '#243d8a',
          900: '#162453',
        },
      },
    },
  },
  plugins: [],
}
