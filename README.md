# MedNova AI — runnable starter

An original multilingual medical-information platform starter. This repository provides a working FastAPI backend, SQLite persistence, basic account authentication, a provider-independent OpenAI-compatible chat adapter, live PubMed search via NCBI E-utilities, document upload/extraction, and a responsive web interface with six locale files and RTL support.

> **Clinical safety:** This is a software starter, not a medical device and not clinically validated. AI answers may be wrong and are not a diagnosis or treatment plan. Do not upload identifiable patient data to an unapproved environment. Professional access is not verified in this starter. Image diagnosis, medication interaction checking, validated calculators, production-grade storage/scanning, and mobile app packaging are not implemented.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

Without `AI_API_KEY`, chat returns an honest `503` error; it never invents a provider response. To enable chat, set `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` in `.env` for an OpenAI-compatible chat-completions endpoint. Keep secrets server-side.

PubMed search uses public NCBI E-utilities and needs internet access. Respect NCBI policies and rate limits. SQLite is for local development; use PostgreSQL, migrations, private object storage, managed secrets, HTTPS, monitoring, and a security review before production.

## Included endpoints

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/health`
- `POST /api/chat` (authenticated, persists conversations and messages)
- `GET /api/conversations`, `GET /api/conversations/{id}`, `DELETE /api/conversations/{id}`
- `GET /api/evidence/pubmed?q=...&page=1`
- `POST /api/documents` (authenticated, size/type checks, text extraction for TXT and text-based PDF)
- `GET /api/documents`

## Current implementation status

Working in this starter: registration/login, hashed passwords, bearer tokens, per-user conversation/document ownership, SQLite persistence, configurable AI provider adapter, live PubMed metadata/abstract retrieval, basic TXT/PDF extraction, six language dictionaries, RTL/LTR layout, responsive dashboard, Docker configuration, and basic tests.

Not yet production-ready: email verification/password reset, MFA, formal clinician credential verification, robust malware scanning/OCR, encrypted object storage, PostgreSQL/Alembic/Redis worker, streaming, full translation QA, medical safety evaluation, clinical calculators, validated image models, admin workflows, mobile release builds, and compliance review.
