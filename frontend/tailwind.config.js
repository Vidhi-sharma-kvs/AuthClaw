/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: "#08152B",
        cardBg: "rgba(11, 31, 63, 0.4)",
        borderBg: "rgba(255, 255, 255, 0.05)",
        navy: {
          950: "#08152B",
          900: "#0B1F3F",
          800: "#12294B",
          700: "#1B3663",
        },
        brandViolet: {
          DEFAULT: "#6D28D9",
          500: "#7C3AED",
          300: "#A78BFA",
          50: "#F1ECFE",
        },
        brandGold: {
          DEFAULT: "#E9A93C",
          600: "#C9862A",
          50: "#FBF1DE",
        }
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        display: ["Space Grotesk", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
