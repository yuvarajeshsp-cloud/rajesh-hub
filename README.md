# Rajesh Hub

Shared designs, components and features for every app, website and trading bot, so nothing gets built twice.

Built from: Embroidery-Shop-Manager, paavai-embroidery-web, Microgreentracker, MT--breakoutbot, SidewayBreakoutBot, RangeBreakeoutBot, HFT-Bot. The full list of 70 reusable parts, including the ones not moved here yet, is in [CATALOGUE.md](CATALOGUE.md).

## What's inside

| Package | Use it for | Came from |
|---|---|---|
| `@rajesh-hub/tokens` | Brand colours, radius, dark mode (`app.css`, Tailwind 4), website type and layout (`web.css`), mobile WebView fixes (`mobile.css`) | Shop Manager, Paavai web, Microgreen |
| `@rajesh-hub/ui` | 47 shadcn/ui components, theme + mode toggle, date range and multi-select filters, Excel export dialog, `BrandProvider` | Shop Manager |
| `@rajesh-hub/print` | Thermal receipts over USB / Web Bluetooth / native BLE (58 and 80 mm, ₹ and Tamil), receipt layout, Excel export | Shop Manager |
| `@rajesh-hub/native` | Face ID / fingerprint unlock, keychain credentials, durable Supabase session on phones, save or share any file | Shop Manager, Microgreen |
| `@rajesh-hub/offline-store` | Crash-safe on-device data, daily snapshots, photos with thumbnails, zip backup and restore, React hooks | Microgreen |
| `@rajesh-hub/supabase-kit` | Supabase client (passkeys), audit log, edge-function error messages, feature flags; edge functions for staff invites, phone OTP, account deletion; keep-awake job | Shop Manager |
| `@rajesh-hub/web-growth` | Astro: cookie consent, Meta Pixel + Conversions API, ad attribution, ♡ shortlist, item stats, WhatsApp button, Instagram feed, image CDN | Paavai web |
| `trading/` | MQL5 `RiskManager`, `TradeUtils`, `Dashboard` includes; TradingView → MT5 webhook bridge (Python + Mac app); signal receiver EA | Breakout bots |

| Template | Starts |
|---|---|
| `templates/app` | Vite + React + Tailwind 4 + Capacitor app with the hub wired in |
| `templates/site` | Astro site with brand styles, WhatsApp button, consent, tracking, shortlist and Netlify functions |

## Start a new project

```bash
git clone https://github.com/yuvarajeshsp-cloud/rajesh-hub.git
cd rajesh-hub && npm install
cp -r templates/app apps/my-new-app    # or templates/site
```

The simplest setup is to keep each new project inside the hub, in `apps/`, so it shares the npm workspace and always gets the latest packages:

```bash
cp -r templates/app apps/thulir-v2
npm install
```

A project that must stay in its own repo can point at a local checkout instead:

```bash
npm install ../rajesh-hub/packages/ui ../rajesh-hub/packages/tokens
```

## Using each package

**Tokens** (app `src/index.css`):
```css
@import "tailwindcss";
@import "tw-animate-css";
@import "@rajesh-hub/tokens/app.css";
@import "@rajesh-hub/tokens/mobile.css";
@source "../node_modules/@rajesh-hub/ui/src";
```

**UI**:
```tsx
import { BrandProvider, ThemeProvider, Button, Dialog, DateRangeFilter } from "@rajesh-hub/ui"

<ThemeProvider defaultTheme="system">
  <BrandProvider value={{ companyName: "Thulir Microgreens", companyLogo: logoUrl }}>
    <App />
  </BrandProvider>
</ThemeProvider>
```
On phones, `Dialog` opens as a full page with the brand header, edge-swipe back and Android back-button support.

**Print**:
```ts
import { printReceipt, headerBlocks, pairPrinter, setPaperWidth } from "@rajesh-hub/print"

await printReceipt([
  ...headerBlocks({ name: "Paavai Embroidery", lines: ["Chennai", "Ph: 98765 43210"] }),
  { t: "divider" },
  { t: "row", left: "Blouse work", right: "₹1,200.00" },
  { t: "row", left: "TOTAL", right: "₹1,200.00", size: "big", bold: true },
])
```
Call it from a button tap: the first print asks the user to pick a printer, then it is remembered on that device.

**Offline store**:
```ts
import { configureStorage, createStore, createSnapshots, createBackup, useStore, useDailySnapshot } from "@rajesh-hub/offline-store"

configureStorage({ root: "thulir" })
export const store = createStore<AppData>({ schemaVersion: 1, defaults: () => ({ items: [] }), normalize })
export const snapshots = createSnapshots<AppData>({ normalize })
export const backup = createBackup<AppData>({
  format: "thulir-backup", schemaVersion: 1, appName: "Thulir", filePrefix: "thulir-backup",
  photoNames: (d) => d.items.flatMap((i) => i.photos), normalize,
})

const { data, update } = useStore(store)
useDailySnapshot(snapshots, data)
```

**Native**:
```ts
import { authenticateWithBiometry, saveFile, capacitorSupabaseStorage } from "@rajesh-hub/native"
import { createHubClient } from "@rajesh-hub/supabase-kit"

export const supabase = createHubClient(url, anonKey, { storage: capacitorSupabaseStorage })
await saveFile("report.csv", csvText, "text/csv")   // download on web, share sheet on phones
```

**Supabase kit edge functions**: copy `packages/supabase-kit/functions/<name>` into the project's `supabase/functions/`. They expect a `user_profiles` table with `id`, `role`, `is_active`, `organization_id` and `phone`; `delete-account` also calls a `purge_account` SQL function and the OTP functions need `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_VERIFY_SERVICE_SID`. The matching SQL is in Embroidery-Shop-Manager `supabase/migrations`.

**Audit log** needs:
```sql
create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  user_id uuid, user_name text, table_name text, record_id text, action text,
  previous_values jsonb, new_values jsonb, reason text
);
```

**Web growth** (Astro): see `templates/site/src/layouts/Base.astro`. Environment variables are listed in `templates/site/.env.example`; `PUBLIC_SITE_KEY` keeps each site's consent, shortlist and stats separate in the browser.

**Trading**: copy `packages/trading/mql5/Include/RajeshHub` into `MQL5/Include/`, then:
```mql5
#define DASHBOARD_TITLE "My EA"
#define DASHBOARD_PREFIX "MYEA_"
#include <RajeshHub/RiskManager.mqh>
#include <RajeshHub/Dashboard.mqh>
```

## Checking changes

```bash
npm install
npm run typecheck        # every package
cd templates/app && npx vite build
cd templates/site && npx astro build
```

## Adding something new to the hub

1. Build it in a project first.
2. Once a second project needs it, move it into the right package and remove app-specific names (pass them in as options).
3. Add or update its row in `CATALOGUE.md` and the package table above.
4. Run the checks.
