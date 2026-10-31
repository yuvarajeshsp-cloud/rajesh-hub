# Functionality catalogue

Every reusable part found across the 7 repos. **In hub** says where it lives now; blank means it is still only in its original repo (see *Source*) and is a candidate for the next extraction.

Readiness: **Ready** copy as-is · **Adapt** pull app-specific names into config · **Extract** refactor before reuse.

## Design system & UI

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-UI-01 | shadcn/ui component set | 47 primitives (dialog, sheet, drawer, table, form, calendar, chart, sidebar, OTP input…) on Radix + Tailwind 4. | App + web | Ready | ui | `Embroidery-Shop-Manager · src/components/ui` |
| HUB-UI-02 | Brand tokens (Paavai palette) | Navy, brand blue, teal, gold, periwinkle primary, oklch neutrals, radius scale and dark mode variables. | App + web | Adapt | tokens/app.css | `Shop-Manager · src/index.css + paavai-web · styles/global.css` |
| HUB-UI-03 | Website type & layout system | Playfair Display + Mukta Malar pairing with Tamil line-height rules, container, section and button styles. | Web | Ready | tokens/web.css | `paavai-embroidery-web · styles/global.css` |
| HUB-UI-04 | App shell & navigation | Desktop sidebar, mobile bottom nav, 'More' tab groups, page header and page stack. | App | Adapt | ui (BottomNav only) | `Shop-Manager · app-sidebar, bottom-nav, more-nav, page-stack` |
| HUB-UI-05 | Theme provider & mode toggle | Light, dark and system theme switch persisted per user. | App + web | Ready | ui | `Shop-Manager · theme-provider, mode-toggle` |
| HUB-UI-06 | Date range filter | Presets (today, this week, this month, custom) with a range picker and isWithinRange helper. | App + web | Ready | ui | `Shop-Manager · date-range-filter + lib/date-range` |
| HUB-UI-07 | Multi-select filter & status badges | Faceted filtering for lists and consistent coloured status chips. | App + web | Adapt | ui (filter only) | `Shop-Manager · multi-select-filter, status-badges` |
| HUB-UI-08 | Photo kit | Full-screen viewer, before/after compare, photo strip, gallery and thumbnail cache. | App | Ready | offline-store (photo storage; viewer UI not yet) | `Microgreentracker · components/photos + storage/photos` |
| HUB-UI-09 | Swipe pages & bottom sheets | Swipeable page container and action sheets tuned for one-hand phone use. | App | Adapt |  | `Microgreentracker · SwipePage, HarvestSheet, QuickActionModal` |
| HUB-UI-10 | Mobile hardening CSS | Safe-area padding, no input zoom, iOS date-input width fix, hidden scrollbars, no tap highlight. | App | Ready | tokens/mobile.css | `Microgreentracker · src/index.css` |
| HUB-UI-11 | Android back-button dialog stack | Back gesture closes the top full-screen dialog instead of leaving the page. | App | Ready | ui | `Shop-Manager · lib/dialog-stack` |
| HUB-UI-12 | Rack / shelf layout visualiser | Draws racks, shelves and slots with occupancy; usable for any physical inventory grid. | App | Adapt |  | `Microgreentracker · components/farm, utils/farmLayout` |

## Auth, users & tenancy

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-AUTH-01 | Supabase auth with passkeys | Email/password, passkey sign-in, invite and recovery links, set-password page. | App + web | Adapt | supabase-kit (client only) | `Shop-Manager · lib/supabase, lib/auth, pages/auth, capture-auth-redirect` |
| HUB-AUTH-02 | Biometric unlock | Face ID / fingerprint app lock with credentials in the OS keychain and resume handling. | App | Ready | native | `Shop-Manager · biometric-unlock, biometric-credentials, pages/biometric-lock` |
| HUB-AUTH-03 | Phone & email OTP verification | Send and verify OTP edge functions plus the verify-phone screen. | App + web | Adapt | supabase-kit/functions (phone OTP) | `Shop-Manager · functions/send-phone-otp, verify-phone-otp` |
| HUB-AUTH-04 | Roles & route permissions | Per-role page access with administrator override and assignable roles list. | App + web | Adapt |  | `Shop-Manager · lib/permissions` |
| HUB-AUTH-05 | Multi-tenant organisations + RLS | Org-scoped tables, self-serve signup, join protection, inactive-user enforcement in SQL. | App + web | Extract |  | `Shop-Manager · supabase/migrations (organizations, user_access_control…)` |
| HUB-AUTH-06 | Platform super-admin | Cross-organisation read access and admin console for you as the platform owner. | App + web | Adapt |  | `Shop-Manager · pages/platform-admin, lib/platform-admin` |
| HUB-AUTH-07 | Account deletion | In-app delete-account flow and edge function, required by Play Store and App Store. | App | Ready | supabase-kit/functions | `Shop-Manager · delete-account-card + functions/delete-account` |
| HUB-AUTH-08 | User invites | Admin creates or invites staff accounts from inside the app. | App + web | Ready | supabase-kit/functions | `Shop-Manager · functions/create-user, invite-user` |
| HUB-AUTH-09 | Durable mobile session storage | Keeps the Supabase session in Capacitor storage so phones stay signed in. | App | Ready | native | `Shop-Manager · lib/capacitor-storage` |

## Payments & access

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-PAY-01 | Razorpay subscriptions | Create subscription, verify payment, webhook, checkout loader and plan picker. | App + web | Adapt |  | `Shop-Manager · lib/subscription + functions/razorpay-*` |
| HUB-PAY-02 | Plan-based access gating | Access level read from the same SQL function RLS enforces; locked and deactivated screens. | App + web | Adapt |  | `Shop-Manager · useOrganizationAccess, pages/access-locked` |
| HUB-PAY-03 | Feature flags | Switch whole modules on or off for a release without touching other code. | App + web | Ready | supabase-kit | `Shop-Manager · lib/features` |

## Messaging

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-MSG-01 | WhatsApp Cloud API | Templates, allowed media types, order status messages, file sending, test message. | App + web | Adapt |  | `Shop-Manager · lib/whatsapp + functions/whatsapp-send` |
| HUB-MSG-02 | WhatsApp float button & click tracking | Floating chat button with per-design prefilled text and attributed click events. | Web | Ready | web-growth | `paavai-web · WhatsAppFloat.astro, scripts/tracking` |
| HUB-MSG-03 | Enquiry form | Netlify Forms enquiry reported to Meta as a Lead with shared event id. | Web | Ready | web-growth (Netlify function) | `paavai-web · EnquiryForm.astro, functions/enquiry` |

## Printing, PDFs & exports

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-DOC-01 | Thermal receipt printing | ESC/POS raster printing (₹ and Tamil print correctly) over USB, Web Bluetooth or native BLE, 58 mm and 80 mm. | App + web | Ready | print | `Shop-Manager · lib/printer/*` |
| HUB-DOC-02 | Receipt layout engine | Receipts described as blocks and drawn to canvas at printer dot width. | App + web | Adapt | print | `Shop-Manager · lib/printer/receipt` |
| HUB-DOC-03 | PDF invoices + native share | jsPDF invoice, print, download, upload, and OS share sheet on Android/iOS. | App + web | Adapt |  | `Shop-Manager · lib/pdf` |
| HUB-DOC-04 | Browser thermal print fallback | 80 mm invoice and order tag via hidden iframe and the system print dialog. | Web | Adapt |  | `Shop-Manager · lib/thermal-print` |
| HUB-DOC-05 | Excel export dialog | Pick fields and export any list to .xlsx. | App + web | Ready | print + ui | `Shop-Manager · lib/export, export-dialog` |
| HUB-DOC-06 | CSV & PDF reports | Per-batch PDF and all-records CSV; html2canvas report export. | App | Adapt |  | `Microgreentracker · utils/exportUtils, farm/ReportExport` |
| HUB-DOC-07 | File attachments | Upload, list, view and delete files on records via Supabase Storage. | App + web | Ready |  | `Shop-Manager · lib/attachments, attachment-section, attachment-viewer` |

## Data, offline & utilities

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-DATA-01 | Crash-safe offline storage | Alternating double-file writes with sequence numbers and schema versioning, on device or IndexedDB. | App | Ready | offline-store | `Microgreentracker · storage/appData, storage/fs` |
| HUB-DATA-02 | Backup & restore (.zip with photos) | Export everything plus photos into one zip, preview before restoring. | App | Ready | offline-store | `Microgreentracker · storage/backupFile (fflate)` |
| HUB-DATA-03 | Daily on-device snapshots | First open of each day takes a snapshot; list, restore, delete. | App | Ready | offline-store | `Microgreentracker · storage/snapshots, hooks/useBackup` |
| HUB-DATA-04 | Legacy data migration | Moves old localStorage / data-URL data into the new format once. | App | Adapt |  | `Microgreentracker · storage/legacy` |
| HUB-DATA-05 | Chunked saveFile | Saves large files on web and native without building one giant base64 string. | App | Ready | native | `Microgreentracker · utils/saveFile` |
| HUB-DATA-06 | Reminders engine | Generates reminders from records (watering, checks) with a notification panel. | App | Extract |  | `Microgreentracker · hooks/useReminders, NotificationPanel` |
| HUB-DATA-07 | Timezone-safe date utils | Local calendar dates that do not shift to the previous day in IST. | App + web | Ready |  | `Microgreentracker · utils/dateUtils` |
| HUB-DATA-08 | Money & numbering helpers | INR formatting, order totals and balances, sequential order / payment / customer codes. | App + web | Adapt |  | `Shop-Manager · lib/helpers` |
| HUB-DATA-09 | Audit log | Records who changed what for every important action. | App + web | Ready | supabase-kit | `Shop-Manager · lib/audit + audit table` |
| HUB-DATA-10 | Business profile & dynamic branding | Shop name and logo shared by sidebar, title and favicon from one cached source. | App + web | Ready |  | `Shop-Manager · lib/business-profile, lib/favicon` |
| HUB-DATA-11 | Shop-type vocabulary | One app serves several business types: wording, pricing mode and starter lists change per type. | App + web | Adapt |  | `Shop-Manager · lib/shop-type, migrations/shop_types` |
| HUB-DATA-12 | In-app help & FAQ | Structured help sections and FAQ groups rendered as pages. | App + web | Adapt |  | `Shop-Manager · lib/help-content, pages/help` |
| HUB-DATA-13 | Test data generator | Realistic sample records for demos and screenshots. | App | Adapt |  | `Microgreentracker · utils/generateTestData` |

## Website & growth

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-WEB-01 | Supabase as website CMS | Site content read once per build from Supabase, hidden items excluded. | Web | Adapt |  | `paavai-web · lib/content, supabase/*.sql` |
| HUB-WEB-02 | Website admin + Publish button | Edit catalogue, reviews, services and shop details; role-checked Netlify rebuild. | Web | Extract |  | `paavai-web · pages/admin, scripts/admin, functions/publish` |
| HUB-WEB-03 | Two-level catalogue & popularity | Categories, design pages, price buckets, 'new' tags, popularity from views, ♡ and enquiries. | Web | Adapt |  | `paavai-web · lib/designs, DesignBrowser, DesignCard` |
| HUB-WEB-04 | Shortlist (♡) | Visitors save items in the browser with a floating counter. | Web | Ready | web-growth | `paavai-web · scripts/shortlist, pages/shortlist` |
| HUB-WEB-05 | Anonymous item stats | Cookie-free counters for views, saves and enquiries per item. | Web | Ready | web-growth | `paavai-web · scripts/stats` |
| HUB-WEB-06 | Consent + Meta Pixel + Conversions API | Consent banner, ad attribution, Pixel with server-side duplicate events. | Web | Ready | web-growth | `paavai-web · ConsentBanner, scripts/tracking, functions/meta-event` |
| HUB-WEB-07 | Instagram feed | Latest posts pulled at build time, hidden when no token. | Web | Ready | web-growth | `paavai-web · lib/instagram, InstagramFeed` |
| HUB-WEB-08 | English + Tamil site | Mirrored /ta routes with a shared strings file. | Web | Adapt |  | `paavai-web · i18n/strings, pages/ta/*` |
| HUB-WEB-09 | SEO & product feed | Sitemap plus catalog.xml feed for Meta / Google shopping. | Web | Ready | templates/site (sitemap) | `paavai-web · astro sitemap, pages/catalog.xml` |
| HUB-WEB-10 | Image CDN resizing | Supabase photos served resized as WebP/AVIF through Netlify. | Web | Ready | web-growth | `paavai-web · lib/media, netlify.toml` |
| HUB-WEB-11 | Reviews & services blocks | Review cards and price list sections fed from the CMS. | Web | Ready |  | `paavai-web · Reviews, ServicesList, lib/services` |

## Build & infrastructure

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-OPS-01 | Capacitor app template | Android + iOS projects, icons/splash, app version injection. | App | Adapt | templates/app | `Shop-Manager & Microgreentracker · capacitor.config.ts` |
| HUB-OPS-02 | Supabase keep-awake | Scheduled Netlify function that stops free-tier Supabase pausing. | App + web | Ready | supabase-kit/netlify | `Shop-Manager · netlify/functions/keep-supabase-awake` |
| HUB-OPS-03 | Edge function error helper | Turns generic non-2xx errors into the real message from the function. | App + web | Ready | supabase-kit | `Shop-Manager · lib/edge-function-error` |
| HUB-OPS-04 | Playwright tests | Browser test setup for the app. | App | Adapt |  | `Microgreentracker · tests/` |

## Trading systems

| Code | Part | What it does | Runs on | Readiness | In hub | Source |
|---|---|---|---|---|---|---|
| HUB-TRD-01 | MQL5 risk manager | Lot sizing from risk percentage and stop distance. | Trading | Ready | trading | `MT--breakoutbot · Include/RiskManager.mqh` |
| HUB-TRD-02 | MQL5 trade utilities | Order placement, modification and position helpers. | Trading | Ready | trading | `MT--breakoutbot · Include/TradeUtils.mqh` |
| HUB-TRD-03 | On-chart dashboard panel | Status panel drawn on the MT5 chart. | Trading | Ready | trading | `MT--breakoutbot · Include/Dashboard.mqh` |
| HUB-TRD-04 | TradingView → MT5 signal bridge | Webhook receiver in Python plus a native Mac bridge app, feeding a signal EA. | Trading | Adapt | trading | `SidewayBreakoutBot · bridge/, mac/, mt5/` |
| HUB-TRD-05 | Tiered Pine indicator editions | Beta, Pro, Funded and Signal editions from one strategy core. | Trading | Extract |  | `SidewayBreakoutBot · pine/*` |
| HUB-TRD-06 | Range intelligence suite | Range detection and breakout context indicator. | Trading | Adapt |  | `RangeBreakeoutBot · range-intelligence-suite.pine` |
| HUB-TRD-07 | cTrader port | The sideways-breakout logic in C# for cTrader. | Trading | Adapt |  | `SidewayBreakoutBot · ctrader/` |
| HUB-TRD-08 | Fibonacci breakout EA | Large documented EA with Fibonacci breakout logic and full parameter guide. | Trading | Extract |  | `HFT-Bot · Experts/FibBreakoutEA.mq5 + docs` |
| HUB-TRD-09 | Ticket executor EA | Executes approved order tickets from Python: demo guard, broker-side loss re-check (OrderCalcProfit), on-screen Yes/No, one position per target, breakeven after TP1, flat-by close, results file. | Trading | Ready | trading | `rajesh-hub · packages/trading/mt5/TicketExecutorEA.mq5` |
| HUB-TRD-10 | Flat JSON reader for MQL5 | Read/write one flat JSON object and Common-Files text atomically; shared by the signal and ticket EAs. | Trading | Ready | trading | `rajesh-hub · Include/RajeshHub/FlatJson.mqh` |
| HUB-TRD-11 | Forex / CFD / futures skill pack | Six Claude skills: scanner (range break, sweep), economic calendar + blackout, entry/exit planner, Monte Carlo time machine, lot/contract sizing + risk gate, MT5 / NinjaTrader ATI / signals executor. Specs for FX, XAUUSD, CME, MCX, NSE. | Trading | Ready | apps | `rajesh-hub · apps/fx-futures-trader` |
| HUB-TRD-12 | Trading Console | Live web console for the trading skills: pipeline rail with running/done/blocked states, streamed backend activity (SSE), plan price ladder, replay odds, risk verdict, daily limit, scanner and news countdowns. Read-only. | Trading | Ready | apps | `rajesh-hub · apps/fx-console` |
