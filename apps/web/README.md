# KAI web

Next.js workspace for KAI. Setup, commands, and architecture live in the repository README and `docs/ARCHITECTURE.md`.

```bash
pnpm dev:web
```

The app expects the API at `NEXT_PUBLIC_KAI_API_URL` (default `http://localhost:8000`). Copy `.env.example` to `.env.local` to override it. Do not put secrets in this app.
