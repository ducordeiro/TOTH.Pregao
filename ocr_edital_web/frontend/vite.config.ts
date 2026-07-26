import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../frontend_dist",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/pncp-search": "http://127.0.0.1:8765",
      "/identify-items": "http://127.0.0.1:8765",
      "/process": "http://127.0.0.1:8765",
      "/generate": "http://127.0.0.1:8765",
      "/download": "http://127.0.0.1:8765",
      "/template": "http://127.0.0.1:8765"
    }
  }
});
