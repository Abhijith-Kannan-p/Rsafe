import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The screenshot script points the proxy at its own throwaway backend; normal dev uses 8765.
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};
const API = env.RSAFE_API_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Pin IPv4: on Windows "localhost" can bind to ::1 only, which breaks 127.0.0.1 clients.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": API,
    },
  },
});
