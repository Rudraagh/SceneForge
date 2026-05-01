import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    global: "globalThis",
  },
  resolve: {
    alias: {
      // plotly.js uses require('buffer/'); map to the npm buffer polyfill for the browser
      "buffer/": "buffer",
      buffer: "buffer",
    },
  },
  optimizeDeps: {
    include: ["buffer", "plotly.js", "react-plotly.js"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },
    },
  },
});
