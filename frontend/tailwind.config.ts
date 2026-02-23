import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
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
