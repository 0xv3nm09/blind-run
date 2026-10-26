import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// relative base so the built app works from ANY mount: FastAPI /app, GitHub
// Pages subpath (/blind-run/), or the repo root — no rebuild needed per host
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", assetsDir: "assets" },
});
