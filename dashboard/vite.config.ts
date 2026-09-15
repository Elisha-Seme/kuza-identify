import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base is read at runtime from VITE_API_BASE (see .env handling in
// App.tsx). In docker-compose the dev server proxies /api to the backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
