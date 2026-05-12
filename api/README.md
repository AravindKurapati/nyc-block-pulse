# NYC Block Pulse API

FastAPI backend for the v1 map frontend. It wraps the existing
`nyc_pulse` scoring and address normalization code without adding new
database tables or duplicating signal logic.

## Endpoints

- `GET /health`
- `GET /api/events?signal=quality_of_life&bbox=min_lon,min_lat,max_lon,max_lat`
- `POST /api/block`
- `GET /api/search?q=200 Atlantic Ave`

## Configuration

- `DATABASE_URL`: Supabase Postgres/PostGIS connection string.
- `NYC_GEOCLIENT_APP_KEY`: NYC Geoclient subscription key.
- `NYC_GEOCLIENT_APP_ID`: kept for compatibility with the CLI environment.
- `ALLOWED_ORIGINS`: comma-separated browser origins. Wildcards such as
  `https://*.vercel.app` are converted to a CORS origin regex.

## Local Run

```powershell
Push-Location api
pip install -r requirements.txt
Pop-Location
uvicorn api.main:app --reload
```

The API opens at `http://127.0.0.1:8000`.
