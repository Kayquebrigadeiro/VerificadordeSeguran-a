import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em produção o FastAPI serve dist/ na mesma origem (sem CORS).
// Em desenvolvimento, proxy /api -> backend em loopback.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8400", changeOrigin: false },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
