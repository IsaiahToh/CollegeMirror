/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      colors: {
        ink: {
          700: "#1A2238",
          800: "#101626",
          900: "#0A0E1A",
          950: "#06080F",
        },
        accent: {
          200: "#A5F0FF",
          300: "#7DE9FD",
          400: "#4ADCF5",
          500: "#22C8E6",
          600: "#0FA8C9",
          700: "#0B86A3",
        },
      },
      boxShadow: {
        glass: "0 8px 40px rgba(2, 6, 18, 0.45)",
        glow: "0 0 28px rgba(34, 200, 230, 0.35)",
        "glow-sm": "0 0 16px rgba(34, 200, 230, 0.22)",
      },
    },
  },
  plugins: [],
};
