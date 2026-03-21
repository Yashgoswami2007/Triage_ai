# Triage AI Deployment Notes

## Backend (FastAPI -> Cloud Run)

### Prerequisites
1. Install and authenticate Google Cloud SDK (`gcloud`).
2. Enable required services:
   - `run.googleapis.com`
   - `cloudbuild.googleapis.com`

### Deploy
1. Set your API key:
   - `GEMINI_API_KEY` (Gemini API key)
2. Deploy:
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

gcloud run deploy triage-ai \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 30 \
  --set-env-vars "GEMINI_API_KEY=YOUR_GEMINI_API_KEY,ALLOWED_ORIGINS=*"
```

Cloud Run will output a service URL, e.g. `https://triage-ai-xxxx-el.a.run.app`.

### CORS
The backend uses `ALLOWED_ORIGINS` (comma-separated). Set it to your WebUI domain for production.

## WebUI (Next.js -> Cloud Run)

### Build-time env for Next.js
Because the browser calls the API, Next.js must be built with the API base URL.
Set `NEXT_PUBLIC_TRIAGE_API_URL` so it is available during `npm run build`.

### Deploy (via `web/Dockerfile`)
```bash
gcloud run deploy triage-webui \
  --source web \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 30 \
  --set-env-vars "PORT=8080" \
  --set-build-env-vars "NEXT_PUBLIC_TRIAGE_API_URL=https://YOUR_BACKEND_URL"
```

After deploy, you can open the WebUI URL in a browser.

## Android App (Expo -> Android build)

### Configure
1. Copy `mobile/.env.example` to `mobile/.env`.
2. Set:
   - `TRIAGE_API_URL=https://YOUR_BACKEND_URL`

### Build
Recommended: Expo EAS build.
```bash
npm install -g eas-cli

cd mobile
eas build -p android
```

If you prefer a local dev build:
```bash
cd mobile
npm install
npm start
```

