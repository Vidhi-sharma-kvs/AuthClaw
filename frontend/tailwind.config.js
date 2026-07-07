/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: "#FBFAF9",
        cardBg: "rgba(255, 255, 255, 0.85)",
        borderBg: "#E6E9F0",
        navy: {
          950: "#0E1726",
          900: "#475069",
          800: "#6B7488",
          700: "#7C3AED",
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
