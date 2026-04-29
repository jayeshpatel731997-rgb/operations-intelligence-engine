/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211b',
        muted: '#5c6b63',
        line: '#dce5df',
        panel: '#ffffff',
        plant: '#138060',
        amber: '#b76b16',
      },
      boxShadow: {
        panel: '0 18px 50px rgba(40, 61, 50, 0.08)',
      },
    },
  },
  plugins: [],
};
