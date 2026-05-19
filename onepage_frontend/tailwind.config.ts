import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#332b22",
        muted: "#84786b",
        paper: "#fffaf3",
        line: "#e8dac9",
        olive: "#686855",
        clay: "#9b7652",
        sky: "#9cc8dd"
      },
      boxShadow: {
        journal: "0 18px 50px rgba(82, 58, 35, 0.14)"
      },
      fontFamily: {
        song: ["Songti SC", "STSong", "serif"],
        kai: ["Kaiti SC", "STKaiti", "serif"]
      }
    }
  },
  plugins: []
};

export default config;
