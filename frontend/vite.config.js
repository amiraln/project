import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В разработке Vite проксирует запросы к Django — так cookie сессии и CSRF работают как на боевом сервере.
// Django на другом порту: DJANGO_URL=http://127.0.0.1:8001 npm run dev
const django = process.env.DJANGO_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": django,
      "/media": django,
      "/static": django,
      "/manage": django,
      "/payments": django,
    },
  },
});
