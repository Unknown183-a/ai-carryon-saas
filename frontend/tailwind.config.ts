import type { Config } from "tailwindcss";

// Design tokens — "broadcast ops desk" direction.
// ink/panel/line: the control-room shell. amber: the one "on-air" action
// color (primary buttons, active nav). signal: reserved ONLY for live/
// running pipeline state — never used decoratively, so when it shows up
// it always means something is actually happening right now.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0B0E14",
        panel: "#11151D",
        panel2: "#161B25",
        line: "#232A38",
        paper: "#EDEBE5",
        slate: "#8891A3",
        amber: "#FFB454",
        amberDim: "#3A2E1C",
        signal: "#4FD1C5",
        signalDim: "#123331",
        danger: "#F0665A",
        dangerDim: "#3A1E1B",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        pulseSignal: {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(79,209,197,0.5)" },
          "50%": { opacity: "0.7", boxShadow: "0 0 0 5px rgba(79,209,197,0)" },
        },
      },
      animation: {
        pulseSignal: "pulseSignal 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
