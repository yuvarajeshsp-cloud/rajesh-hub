---
name: rajesh-hub
description: Use when building or changing any of Rajesh's apps, websites or trading bots, so existing designs and features from the rajesh-hub repo are reused instead of rebuilt.
---

# Rajesh Hub

Rajesh keeps his shared designs and features in the GitHub repo `yuvarajeshsp-cloud/rajesh-hub`. He does not want anything rebuilt that already exists there or in one of his earlier projects.

## Before building anything

1. Get the hub: if it isn't in the session, attach `yuvarajeshsp-cloud/rajesh-hub` (or clone it) and read `README.md` and `CATALOGUE.md`.
2. Look up the feature in `CATALOGUE.md`. Each row says where it lives:
   - **In hub** filled: import it from that package.
   - **In hub** blank: the code exists in the repo named under *Source*. Port it into the matching package (make app-specific names options), update the catalogue row, then use it.
   - Not listed: build it in the project; if a second project will need it, put it in the hub instead.
3. New apps start from `templates/app` (Vite, React, Tailwind 4, Capacitor). New websites start from `templates/site` (Astro, Netlify). Put them in `apps/<name>` inside the hub unless Rajesh wants a separate repo.

## Package map

| Need | Package |
|---|---|
| Brand colours, fonts, dark mode, mobile CSS fixes | `@rajesh-hub/tokens` |
| Buttons, dialogs, sheets, forms, tables, charts, filters, theme toggle | `@rajesh-hub/ui` |
| Thermal receipts, Excel export | `@rajesh-hub/print` |
| Face ID / fingerprint, keychain, save/share files, phone sessions | `@rajesh-hub/native` |
| Offline data, snapshots, photos, zip backup | `@rajesh-hub/offline-store` |
| Supabase client, audit log, feature flags, invite / OTP / delete-account functions | `@rajesh-hub/supabase-kit` |
| Website consent, Meta Pixel + CAPI, WhatsApp button, shortlist, Instagram feed | `@rajesh-hub/web-growth` |
| MQL5 risk sizing, trade helpers, chart dashboard, TradingView → MT5 bridge | `packages/trading` |

Parts still only in their original repos include Razorpay subscriptions, WhatsApp Cloud API, PDF invoices, roles and multi-tenant orgs (Embroidery-Shop-Manager), the website CMS and catalogue (paavai-embroidery-web), reminders and rack layout (Microgreentracker), and the Pine indicator editions (SidewayBreakoutBot).

## Rules

- Colours and fonts only from `@rajesh-hub/tokens`; never hard-code a brand colour.
- Wrap each app in `ThemeProvider` and `BrandProvider` from `@rajesh-hub/ui`.
- Call `configureStorage({ root })` once at startup before using `@rajesh-hub/offline-store`.
- Keep business words (orders, batches, designs) out of hub packages.
- After changing the hub: `npm run typecheck`, then build the template that uses the change.
