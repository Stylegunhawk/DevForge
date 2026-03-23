# DevForge Dashboard

## Stack
- Next.js 14 (App Router)
- TypeScript
- shadcn/ui + Tailwind CSS
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
- All components in `src/components/ui/` are shadcn-generated, do not hand-edit them
- New shared components go in `src/components/` (not inside `ui/`)

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