import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrandProvider, ThemeProvider } from "@rajesh-hub/ui"
import App from "./App"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark">
      <BrandProvider value={{ companyName: "Trading Console", companyLogo: null }}>
        <App />
      </BrandProvider>
    </ThemeProvider>
  </StrictMode>,
)
