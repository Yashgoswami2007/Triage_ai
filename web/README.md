# Triage AI WebUI (Next.js)

## Configure
Copy env:
- `web/.env.example` -> `web/.env.local`

Set:
- `NEXT_PUBLIC_TRIAGE_API_URL` (used by the browser)

## Run locally
```bash
cd web
npm install
npm run dev
```

## Expected backend contract
Web calls:
- `POST ${TRIAGE_API_URL}/triage`

Request body:
- `{ "symptoms": "...", "language": "Hindi" }` (language optional)

Response:
- `{ severity, advice: { what_to_do_now, self_care_steps, monitor_for, seek_care_if, disclaimer }, reasoning }`

