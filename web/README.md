# NYC Block Pulse Web

Next.js frontend for the map-first block intelligence UI.

## Local Development

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI backend URL. It defaults to
`http://localhost:8000` in the fetch wrappers for local development.

## Scripts

- `npm run dev`
- `npm run build`
- `npm run start`
