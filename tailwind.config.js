/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto",
          "Helvetica Neue", "Arial", "sans-serif",
        ],
      },
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
      boxShadow: {
        soft: "0 1px 2px 0 rgb(16 24 32 / 0.04), 0 1px 3px 0 rgb(16 24 32 / 0.06)",
        card: "0 1px 2px 0 rgb(16 24 32 / 0.04), 0 8px 24px -8px rgb(16 24 32 / 0.10)",
        popover: "0 12px 32px -8px rgb(16 24 32 / 0.18)",
      },
      borderRadius: {
        xl: "0.85rem",
        "2xl": "1.1rem",
      },
    },
  },
  plugins: [],
};
