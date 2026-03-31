import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      keyframes: {
        "blink-cursor": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "slide-up-fade": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(57,104,255,0.6)" },
          "50%": { boxShadow: "0 0 0 10px rgba(57,104,255,0)" },
        },
        "shimmer-right": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
        "brain-wave": {
          "0%, 100%": { transform: "scaleY(0.35)", opacity: "0.35" },
          "50%": { transform: "scaleY(1)", opacity: "1" },
        },
        "spin-slow": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "dot-flicker": {
          "0%, 80%, 100%": { opacity: "0", transform: "scale(0.8)" },
          "40%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "blink-cursor": "blink-cursor 1s step-end infinite",
        "slide-up-fade": "slide-up-fade 0.35s ease-out both",
        "pulse-glow": "pulse-glow 1.8s ease-in-out infinite",
        "shimmer-right": "shimmer-right 1.8s ease-in-out infinite",
        "brain-wave": "brain-wave 1s ease-in-out infinite",
        "spin-slow": "spin-slow 3s linear infinite",
        "fade-in": "fade-in 0.5s ease-out both",
        "dot-flicker": "dot-flicker 1.4s ease-in-out infinite",
      },
      colors: {
        tribultz: {
          50: "#eef5ff",
          100: "#dbe9ff",
          200: "#bdd6ff",
          300: "#90b8ff",
          400: "#5f90ff",
          500: "#3968ff",
          600: "#2c4fe6",
          700: "#233ec0",
          800: "#223799",
          900: "#233577",
        },
      },
    },
  },
  plugins: [],
};

export default config;
