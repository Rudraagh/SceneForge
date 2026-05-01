/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      colors: {
        canvas: {
          DEFAULT: "#f4f3ef",
          muted: "#e8e6e1",
          subtle: "#ddd9d2",
        },
        ink: {
          DEFAULT: "#0c0c0c",
          soft: "#404040",
          faint: "#6b6b6b",
        },
        neon: {
          DEFAULT: "#e8ff3d",
          hover: "#daf22e",
          dim: "#c8e020",
        },
        forge: {
          950: "#0a0d12",
          900: "#0f141f",
          850: "#151c2a",
          800: "#1c2538",
          accent: "#5b8cff",
          mint: "#3ecf8e",
        },
      },
      keyframes: {
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        blobDrift: {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(4%, -3%) scale(1.08)" },
        },
        blobDriftSlow: {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(-3%, 4%) scale(1.06)" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeInDown: {
          "0%": { opacity: "0", transform: "translateY(-14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        floatSoft: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        gradientFlow: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        shimmerSweep: {
          "0%": { transform: "translateX(-130%) skewX(-10deg)" },
          "100%": { transform: "translateX(230%) skewX(-10deg)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.94)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        topoDrift: {
          "0%, 100%": { transform: "translate(0%, 0%)" },
          "50%": { transform: "translate(-1.8%, 1.2%)" },
        },
        conicSpin: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        videoBloom: {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.07)" },
        },
        ringPulse: {
          "0%, 100%": { opacity: "0.45" },
          "50%": { opacity: "0.9" },
        },
      },
      accentColor: {
        neon: "#e8ff3d",
      },
      animation: {
        slideUp: "slideUp 0.35s ease-out both",
        fadeIn: "fadeIn 0.35s ease-out both",
        fadeInUp: "fadeInUp 0.55s ease-out both",
        fadeInDown: "fadeInDown 0.45s ease-out both",
        scaleIn: "scaleIn 0.4s ease-out both",
        floatSoft: "floatSoft 5s ease-in-out infinite",
        gradientFlow: "gradientFlow 7s ease-in-out infinite",
        shimmerSweep: "shimmerSweep 3.4s ease-in-out infinite",
        blobDrift: "blobDrift 26s ease-in-out infinite",
        blobDriftSlow: "blobDriftSlow 38s ease-in-out infinite",
        topoDrift: "topoDrift 55s ease-in-out infinite",
        conicSpin: "conicSpin 100s linear infinite",
        videoBloom: "videoBloom 22s ease-in-out infinite",
        ringPulse: "ringPulse 12s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
