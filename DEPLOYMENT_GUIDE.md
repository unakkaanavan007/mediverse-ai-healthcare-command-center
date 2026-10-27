# MEDIVERSE — Intelligent Healthcare. Connected Future.

College demonstration project. All included records and capacity figures are synthetic. This is not a clinical system. Do not enter real patient information or expose the demo to the public.

## Architecture

React + Vite client → Flask REST API → SQLAlchemy database (SQLite by default; PostgreSQL supported through DATABASE_URL). The API verifies JWTs and checks server-side roles. Gemini is called only by the backend if a key is configured. PDF files are processed in memory and not stored.

## Folder structure

```
mediverse/
  backend/
    app.py              Flask routes, models, seed data, AI integration
    requirements.txt    Python dependencies
    .env.example        Server configuration (copy to .env)
  frontend/
    src/main.jsx        React pages and UI logic
    src/style.css       Responsive dashboard styling
    index.html
    package.json
    postcss.config.js
    tailwind.config.js
  README.md
```

## Run in VS Code (Windows)

Install Python 3.10+ and Node.js 20 LTS or later. Extract the ZIP, open the `mediverse` folder in VS Code, then open two terminals.

**Terminal 1 — backend (PowerShell):**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe app.py` instead. The API runs at http://localhost:5000.

**Terminal 2 — frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Sign in with `admin@mediverse.demo` / `DemoAdmin123!`, or register a patient account. Database seed runs on first startup only. To reset the demo, stop the backend and delete `backend/instance/mediverse.db`.

Optional: place a Gemini API key in `backend/.env` as `GEMINI_API_KEY=...`; restart Flask. Without it, the assistant and report analyzer explicitly use demo mode. Never put the key in frontend code. If the service fails the application falls back to demo mode. Text and uploaded report contents are sent to Gemini when configured; only use synthetic data.

For PostgreSQL, create a database and set `DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/mediverse` in `.env` before starting the server. Create a unique random JWT secret in `.env`. SQLite is included for easy demonstration.

## API overview

- POST `/api/register`, `/api/login`; GET `/api/me`
- GET/POST `/api/patients` (create: admin/doctor)
- GET/POST `/api/doctors` (create: admin)
- GET/POST `/api/appointments`, PATCH `/api/appointments/<id>`
- POST `/api/assistant`, `/api/report` (multipart `file`)
- GET `/api/audit` (admin)

Authenticated routes require `Authorization: Bearer <token>`. Patient accounts see only their own patient and appointment records; demo admin and doctor accounts can view all demo records. Registration creates a patient role only. Chat history is stored in the browser only after opting in; turning that off removes saved history. Dashboard counts and appointment lists update after actions; illustrative activity chart and emergency capacity are labeled simulated. Downloadable appointment CSV is available on Analytics.

## Scope and known limitations

This is a functional demonstration, not a production or clinical deployment. PDF extraction supports text-based PDFs only; image OCR and scanned PDFs are not implemented. Gemini results are probabilistic and reference-range highlighting is only requested in the prompt, not independently validated. Patient medical histories, report storage, consultation records, doctor login/assignment, full notification delivery, real-time push, and live emergency integrations are not implemented. Filters apply to patient and doctor directories. The emergency request is explicitly simulated. Password reset, token revocation, account lockout, database migrations, production TLS, encryption at rest, full audit coverage, backups, and regulatory compliance are not implemented. The initial admin credential is public and unsuitable for deployment. Do not use real patient data.

## Deploy on Vercel

Deploy backend and frontend as two separate Vercel projects from the same Git repository. The project roots are `backend` and `frontend` respectively. Vercel requires persistent external PostgreSQL; local SQLite is not suitable. Use only synthetic data.

1. Import your repository to Vercel and choose `backend` as the root. Add a PostgreSQL integration and set `DATABASE_URL` to its pooled connection string, using the `postgresql+psycopg://` scheme. Set `JWT_SECRET_KEY` to a long random string and `DEMO_ADMIN_PASSWORD` to a strong unique password. Set `FRONTEND_ORIGIN` to your eventual frontend URL. Deploy and copy the backend URL.
2. Import the same repository as another Vercel project, selecting `frontend` as the root. Set `VITE_API_URL` to the backend URL followed by `/api`, for example `https://your-backend.vercel.app/api`. Deploy.
3. Set `FRONTEND_ORIGIN` in the backend project to the exact frontend URL (no trailing slash) and redeploy the backend. Open the frontend URL. Log in as `admin@mediverse.demo` using the password configured on first database initialization, or register a patient account. Changing DEMO_ADMIN_PASSWORD later does not change an existing admin account.

Vercel hosting is not verified in this package. The demo is not suitable for real patient data or public production use. AI and emergency limitations described above still apply.
