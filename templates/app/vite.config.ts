import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // packages/ui has no tsconfig of its own; without this its files fall back to
  // classic JSX (React.createElement) and the page renders blank.
  esbuild: { jsx: "automatic" },
})
