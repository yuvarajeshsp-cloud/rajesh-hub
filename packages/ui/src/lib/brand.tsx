import * as React from "react"

// The business name and logo shown in full-page dialogs and app chrome.
// In Shop Manager this came from the shop's business profile; here each app
// passes its own values once, at the root:
//
//   <BrandProvider value={{ companyName: "Thulir Microgreens", companyLogo: logoUrl }}>
//     <App />
//   </BrandProvider>

export interface Brand {
  companyName: string
  companyLogo: string | null
}

const BrandContext = React.createContext<Brand>({ companyName: "", companyLogo: null })

export function BrandProvider({ value, children }: { value: Brand; children: React.ReactNode }) {
  return <BrandContext.Provider value={value}>{children}</BrandContext.Provider>
}

export function useBrand(): Brand {
  return React.useContext(BrandContext)
}
