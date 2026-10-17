import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `bun run dev` serves the UI with HMR and proxies the API to `spinagram serve --port 8765 --no-open`.
// `bun run build` writes the bundle that ships in the wheel.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  // the code editor (CodeMirror) is a lazy ~500 kB chunk loaded only when the code panel opens
  build: { outDir: "../src/spinagram/ui/static", emptyOutDir: true, chunkSizeWarningLimit: 600 },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: false } } },
});
