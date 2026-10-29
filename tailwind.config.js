/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./**/templates/**/*.html"],
  safelist: [
    "badge", "badge-gray", "badge-yellow", "badge-green", "badge-red",
    "badge-orange", "badge-blue", "input", "is-active", "nav-open",
    "h-4", "w-4", "rounded", "border-gray-300", "text-brand-600", "focus:ring-brand-500",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Noto Sans Georgian", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Arial", "sans-serif"],
        display: ["FiraGO", "Noto Sans Georgian", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eaf8ef", 100: "#c5f0dc", 200: "#8de6c3", 300: "#4ad89f",
          400: "#00c684", 500: "#00b274", 600: "#00b274", 700: "#008659",
          800: "#12613f", 900: "#123c2b", 950: "#102c22",
        },
        "brand-blue": { 500: "#2b8ec8", 600: "#267bad" },
        "brand-orange": "#ef4123",
        ink: "#101820",
        gray: {
          50: "#f7faf5", 100: "#eaf1e4", 200: "#dce7d5", 300: "#b9cdb0",
          400: "#6e8171", 500: "#5a7360", 600: "#47634e", 700: "#304e3a",
          800: "#203a2a", 900: "#162d20", 950: "#10251a",
        },
      },
      boxShadow: {
        soft: "0 4px 15px rgb(28 64 34 / 0.04)",
        card: "0 9px 24px rgb(24 63 31 / 0.09)",
        popover: "0 18px 40px rgb(10 39 25 / 0.18)",
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem" },
    },
  },
  plugins: [],
};
