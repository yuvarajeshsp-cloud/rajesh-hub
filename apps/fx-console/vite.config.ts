import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// `npm run dev` proxies the API to the Python server (python3 server.py).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // packages/ui has no tsconfig of its own; without this its files fall back to
  // classic JSX (React.createElement) and the page renders blank.
  esbuild: { jsx: "automatic" },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: false } },
  },
})
