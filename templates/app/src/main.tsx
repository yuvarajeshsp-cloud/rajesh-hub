import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrandProvider, ThemeProvider } from "@rajesh-hub/ui"
import { configureStorage } from "@rajesh-hub/offline-store"
import App from "./App"
import "./index.css"

// Every on-device file for this app lives under this folder name.
configureStorage({ root: "new-app" })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="system">
      <BrandProvider value={{ companyName: "New App", companyLogo: null }}>
        <App />
      </BrandProvider>
    </ThemeProvider>
  </StrictMode>,
)
