import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/examples": "http://localhost:8000",
      // /generate is both a backend API path (POST) and a SPA route (GET).
      // Let full-page HTML navigations fall through to index.html so
      // deep-linking and refreshing on /generate keep working in dev.
      "/generate": {
        target: "http://localhost:8000",
        bypass: (req) => {
          if (req.method === "GET" && req.headers.accept?.includes("text/html")) {
            return "/index.html";
          }
        },
      },
      "/jobs": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
