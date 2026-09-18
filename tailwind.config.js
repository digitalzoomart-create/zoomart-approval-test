/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#e6faf1",
          100: "#c0f2dd",
          200: "#8de6c3",
          300: "#4ad89f",
          400: "#00c684",
          500: "#00b274",
          600: "#00b274",
          700: "#009262",
          800: "#00734d",
          900: "#075c40",
        },
        "brand-blue": {
          500: "#2b8ec8",
          600: "#2b8ec8",
        },
        "brand-orange": "#ef4123",
        ink: "#101820",
      },
    },
  },
  plugins: [],
};
