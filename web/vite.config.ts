import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    // Vitest stubs CSS imports to an empty module by default (CSS normally
    // can't affect a jsdom test outcome). tests/theme/tokens.test.tsx needs
    // the real contents of tokens.css (via a `?raw` import) so its contrast
    // checks measure what actually ships, not a copy that can drift.
    css: true,
  },
});
