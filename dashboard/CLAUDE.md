# DevForge Dashboard

## Stack
- Next.js 14 (App Router)
- TypeScript
- shadcn/ui + Tailwind CSS v4
- NextAuth for authentication
- API proxy pattern — all backend calls go through `src/proxy.ts`

## Key conventions

### Never call the backend directly from components
All API calls go through the proxy routes in `src/app/api/proxy/`.
Do not call `http://localhost:8001` directly from any component or page.

### Auth pattern
- Session via NextAuth (`[...nextauth]/route.ts`)
- JWT token forwarded in proxy headers to backend
- Admin routes are under `/dashboard/admin/` — check `layout.tsx` for role guard

### File structure
```
src/app/
├── (auth)/          ← login, register pages (no sidebar)
├── dashboard/       ← main app (with sidebar layout)
│   ├── admin/       ← admin-only pages
│   ├── keys/        ← API key management
│   ├── usage/       ← usage analytics
│   └── settings/    ← user settings
└── api/proxy/       ← all backend API calls go here
```

### Component rules
- UI components from shadcn/ui only — do not add raw HTML equivalents
- Components in `src/components/ui/` are shadcn-generated. Only hand-edit them to replace hardcoded colours (e.g. `bg-white` → `bg-[rgb(var(--surface))]`) for dark mode compatibility. Never restructure their logic or markup.
- New shared components go in `src/components/` (not inside `ui/`)

### Dark mode — always use design tokens, never hardcode colours
All colours must reference CSS custom properties, not Tailwind palette values:

```tsx
// correct
className="bg-[rgb(var(--surface))] text-[rgb(var(--text-muted))]"

// wrong — breaks dark mode
className="bg-white text-gray-500"
```

The full token set is defined in `src/app/globals.css` under `:root` (light) and `.dark` (dark).
Key tokens: `--bg`, `--surface`, `--surface-2`, `--text`, `--text-muted`, `--border`, `--border-2`, `--accent`, `--accent-subtle`, `--success`, `--danger`, `--warning`, `--muted`.

### Tailwind v4 + shadcn compatibility
This project uses Tailwind v4 (`@import "tailwindcss"` + `@theme inline`).
shadcn components internally use standard class names like `bg-background`, `bg-card`, `bg-popover`, and `bg-muted` — these are **not** Tailwind v4 primitives.

They must be aliased in the `@theme inline` block in `src/app/globals.css`:

```css
@theme inline {
  /* … existing tokens … */

  /* Shadcn compatibility aliases */
  --color-background:       rgb(var(--bg));
  --color-foreground:       rgb(var(--text));
  --color-card:             rgb(var(--surface));
  --color-card-foreground:  rgb(var(--text));
  --color-popover:          rgb(var(--surface));
  --color-popover-foreground: rgb(var(--text));
  --color-muted:            rgb(var(--surface-2));
  --color-muted-foreground: rgb(var(--text-muted));
}
```

If a new shadcn component is added and appears unstyled in dark mode, check whether it uses an unmapped class name and add an alias here.

### Page heading standard
All dashboard pages use the same heading pattern:

```tsx
<h1 className="text-3xl font-bold tracking-tight">Page Title</h1>
<p className="text-[rgb(var(--text-muted))] mt-1">Short subtitle</p>
```

Do not use `text-2xl` or omit `tracking-tight` — it breaks visual consistency across the admin/usage/keys/settings pages.

### Data tables — grid column templates
Use CSS Grid with explicit column widths instead of `grid-cols-N`. Equal-fraction columns give variable-length content (tool names, emails) no room to truncate cleanly.

```tsx
// define once at the top of the file
const COL_TEMPLATE = "90px minmax(0,130px) minmax(0,1fr) 75px 65px";

// apply to header, skeleton rows, and body rows identically
<div className="grid gap-4" style={{ gridTemplateColumns: COL_TEMPLATE }}>
```

Rules:
- Fixed `px` for columns with predictable content (timestamps, numbers, badges)
- `minmax(0, Npx)` for columns that should cap and truncate
- `minmax(0, 1fr)` for the widest variable-length column (gets all remaining space)
- The `0` minimum is required — without it, CSS grid won't shrink the column below its content width, making `truncate` ineffective

### Running locally
```bash
cd dashboard
npm install
npm run dev        # starts on port 3000
```

Backend must be running on port 8001 for API calls to work.

## Backend API base URL
- Local: `http://localhost:8001`
- Set in: `.env.local` as `NEXT_PUBLIC_API_URL` or `BACKEND_URL`