# Google AI (Gemini) Setup Guide

Use this guide to configure Google Gemini for OCR→JSON in the Onboarding Automation app.

## 1) Get API Key
- Visit: https://makersuite.google.com/app/apikey
- Create an API key
- Keep it safe and do not commit it

## 2) Configure `.env`
Create or update a `.env` file in the project root:
```bash
GOOGLE_AI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-pro
DEBUG=True
```
> The app defaults to `gemini-2.5-pro`. You can change it to another available model if needed.

## 3) Install & Run
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## 4) Verify
- Go to `http://127.0.0.1:8000/gemini-info/`
  - Should say configured
- Upload a document at `/upload/`
- Open the document detail page
  - The OCR JSON panel should render valid JSON with a Copy button

## Notes & Limits
- Ensure Poppler is installed for PDF processing
- Respect Google AI rate limits and quotas; see https://ai.google.dev/pricing
- OCR JSON is the source of truth in this app; we do not run regex field extraction

## Troubleshooting
- “API key not configured”: Check `.env` and restart the server
- “Expecting value …” (JSON error): The app now parses Gemini output robustly and will wrap non-JSON as `{ "text": "..." }` to keep it valid
- Timeouts (504): Retry; the app uses fallback prompts when possible
- PDFs: Convert per-page; merged JSON is generated in the backend

That’s it—your app is ready to extract clean JSON using Gemini. 