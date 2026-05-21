# Dashboard UI Rebuild — Design Spec
**Date:** 2026-05-21  
**Branch:** rag_resolve  
**Working directory:** `/Users/siddesh.kale/Documents/DevForge/dashboard/`

---

## Problem

The dashboard has three compounding style conflicts:
1. `components.json` (shadcn `new-york`/`neutral` config) was created during onboarding and wires everything to a dark violet palette
2. `className="dark"` hardcoded on `<html>` forces permanent dark mode
3. Hardcoded Tailwind colors (`bg-zinc-*`, `bg-indigo-*`, `bg-purple-*`) throughout pages bypass the CSS variable system

## Approach: B — Surgical Cleanup + Full Restyle

- Delete `components.json` and remove `shadcn` from devDependencies
- Keep `@radix-ui` packages (pure behavior — no styles)
- Rewrite `globals.css` with Claude warm palette  
- Rebuild all UI components using CSS variables only — no cva, no shadcn tokens
- Update every page to use CSS variables only
- Fix root layout: remove `className="dark"`, set `defaultTheme="light"`

---

## Color Tokens

### Light Mode (default)
| Token | Value | Use |
|---|---|---|
| `--bg` | `247 246 241` (#F7F6F1) | Page background |
| `--surface` | `255 255 255` (#FFFFFF) | Cards, panels |
| `--surface-2` | `243 241 235` (#F3F1EB) | Inputs, hover |
| `--surface-3` | `236 234 226` (#ECEAE2) | Sidebar active, strong wash |
| `--border` | `228 225 215` (#E4E1D7) | Default borders |
| `--border-2` | `203 199 187` (#CBC7BB) | Stronger borders |
| `--text` | `26 24 21` (#1A1815) | Primary text |
| `--text-muted` | `112 108 98` (#706C62) | Secondary text |
| `--text-faint` | `165 160 153` (#A5A099) | Very muted |
| `--accent` | `217 119 87` (#D97757) | Claude coral — CTAs, active nav |
| `--accent-hover` | `201 100 68` (#C96444) | Darker coral on hover |
| `--accent-subtle` | `253 242 238` (#FDF2EE) | Coral tint background |
| `--accent-fg` | `255 255 255` | Text on coral |
| `--sidebar-bg` | `240 237 229` (#F0EDE5) | Sidebar background |
| `--success` | `45 134 83` (#2D8653) | Success green |
| `--success-bg` | `237 251 244` (#EDFBF4) | Success tint |
| `--warning` | `168 117 10` (#A8750A) | Warning amber |
| `--warning-bg` | `255 248 230` (#FFF8E6) | Warning tint |
| `--danger` | `204 60 53` (#CC3C35) | Error red |
| `--danger-bg` | `253 240 239` (#FDF0EF) | Error tint |

### Dark Mode
| Token | Value |
|---|---|
| `--bg` | `26 24 21` (#1A1815) |
| `--surface` | `33 31 27` (#211F1B) |
| `--surface-2` | `41 37 32` (#292520) |
| `--surface-3` | `51 46 40` (#332E28) |
| `--border` | `46 43 38` (#2E2B26) |
| `--border-2` | `61 57 51` (#3D3933) |
| `--text` | `232 229 220` (#E8E5DC) |
| `--text-muted` | `158 154 142` (#9E9A8E) |
| `--accent` | `217 119 87` (#D97757) — same coral |
| `--sidebar-bg` | `22 20 15` (#16140F) |

### Chart Colors
- `--chart-1`: `217 119 87` — coral
- `--chart-2`: `196 136 74` — amber  
- `--chart-3`: `94 143 112` — sage
- `--chart-4`: `107 143 173` — slate
- `--chart-5`: `155 122 173` — mauve

---

## Component Contracts

All components in `src/components/ui/` must:
- Use only CSS variables (e.g. `rgb(var(--accent))`) — never hardcoded colors
- Use `cn()` from `@/lib/utils` — never `cva`
- Keep exact same TypeScript export signatures as current files
- Radius: `6px` for inputs/buttons, `10px` for cards, `8px` for modals

### Button variants
- `default`: coral fill, white text, hover darkens
- `outline`: white bg, warm border, hover warm surface
- `ghost`: transparent, hover warm surface  
- `secondary`: surface-2 bg
- `destructive`: danger fill
- `link`: transparent, coral text, underline on hover

### Card
- White bg, warm border, `10px` radius, subtle shadow `0 1px 3px rgba(26,24,21,0.07)`

### Badge variants
- `default`: coral subtle bg + text
- `secondary`: surface-2 bg + muted text
- `success/warning/destructive`: status color tints
- `outline`: transparent + border

---

## Page Requirements

### Root layout (`src/app/layout.tsx`)
- Remove `className="dark"` from `<html>`
- ThemeProvider: `defaultTheme="light"`, keep `enableSystem={false}`

### Auth pages
- Full-screen `--bg` background, subtle dot-grid pattern, radial glow from top
- Centered white card, `10px` radius, warm border, soft shadow
- Logo at top, clean form with warm inputs
- Coral primary CTA, Google OAuth as outline secondary

### Dashboard sidebar
- `240px` wide, `--sidebar-bg` background
- Logo top with border separator
- Nav: icon + label, muted text default, active = coral left border `2px` + `--accent-subtle` bg + coral text
- User info at bottom, sign-out button

### All pages
- Replace ALL `bg-zinc-*`, `bg-indigo-*`, `bg-purple-*`, `text-green-*`, `text-red-*` with CSS variable equivalents
- Page header: `text-2xl font-bold text-[rgb(var(--text))]` + muted subtitle
- Stat cards: white, warm border, subtle shadow
- Code blocks: warm dark `#1A1815` bg, `#E8E5DC` text (intentional contrast)
- Tables: warm row dividers, hover `--surface-2`
- Empty states: centered icon in warm surface-3 box + description + CTA

---

## Tasks

### Task 1: Foundation Cleanup + Design System
- Delete `components.json`
- Remove `shadcn` from `package.json` devDependencies
- Remove `@import "tw-animate-css"` from globals.css
- Rewrite `globals.css` with full Claude token system (see Color Tokens above)
- Fix `src/app/layout.tsx`: remove `className="dark"`, change defaultTheme to `"light"`

### Task 2: Visual Primitive Components
Files: `button.tsx`, `card.tsx`, `input.tsx`, `badge.tsx`, `label.tsx`, `separator.tsx`, `skeleton.tsx`, `textarea.tsx`

### Task 3: Interactive Components  
Files: `dialog.tsx`, `alert-dialog.tsx`, `select.tsx`, `avatar.tsx`

### Task 4: Shared Components
Files: `src/components/logo.tsx`, `src/components/theme-toggle.tsx`

### Task 5: Auth Pages
Files: `(auth)/layout.tsx`, `(auth)/login/page.tsx`, `(auth)/register/page.tsx`

### Task 6: Dashboard Layout
File: `dashboard/layout.tsx`

### Task 7: Overview + Keys Pages
Files: `dashboard/page.tsx`, `dashboard/keys/page.tsx`

### Task 8: Usage Page
File: `dashboard/usage/page.tsx`

### Task 9: Playground Page
File: `dashboard/playground/page.tsx`

### Task 10: Settings + Docs Pages
Files: `dashboard/settings/page.tsx`, `dashboard/docs/page.tsx`

### Task 11: Admin + Remaining Pages
Files: `dashboard/admin/page.tsx`, `dashboard/admin/pricing/page.tsx`, `dashboard/admin/requests/page.tsx`, `dashboard/admin/users/page.tsx`, `dashboard/admin/users/[id]/page.tsx`, `src/app/page.tsx`
