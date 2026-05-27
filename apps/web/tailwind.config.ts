import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["'Newsreader'", "Georgia", "serif"],
      },
      colors: {
        ink: {
          50: "#f6f5f1",
          100: "#ecebe3",
          200: "#d6d3c2",
          400: "#8a8470",
          600: "#4b4636",
          900: "#1a1814",
        },
        accent: {
          DEFAULT: "#c2410c",
          soft: "#fed7aa",
          deep: "#9a3412",
        },
        paper: "#fbfaf6",
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,24,20,0.04), 0 0 0 1px rgba(26,24,20,0.06)",
        sticky: "0 4px 16px -8px rgba(154,52,18,0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
