# Rajesh Hub

This repo holds the shared designs and features for all of Rajesh's apps, websites and trading bots. Rajesh does not want any design or feature rebuilt when a version already exists.

## Rules for any project

- Before writing a component, screen, helper, edge function or EA routine, check `README.md` (packages) and `CATALOGUE.md` (every known part, including ones still in their original repo). If it exists, use or extend it.
- New apps start from `templates/app`; new websites from `templates/site`.
- Brand colours and fonts come only from `@rajesh-hub/tokens`. Don't hard-code colours in app code.
- If a part exists only in its original repo (blank *In hub* column), port it into the matching package, make app-specific names options, and update `CATALOGUE.md`.
- Keep every package free of business words (orders, batches, designs): those belong in the app.

## Stack

React 19, Vite 7, Tailwind 4, shadcn/ui (Radix), Capacitor 8 for Android/iOS, Supabase (auth, Postgres with RLS, edge functions), Netlify, Astro for websites, Razorpay, WhatsApp Cloud API, MQL5, Pine Script, cTrader C#.

## Checks before committing

`npm run typecheck`, then build the template that uses what you changed (`npx vite build` in `templates/app`, `npx astro build` in `templates/site`).
