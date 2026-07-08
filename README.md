<div align="center">

# 🩺 AI Business Doctor

### Your business has a pulse. We help you read it.

An AI-powered diagnostic platform that turns raw sales and inventory data into a health score, ranked action plan, and plain-language advice — the way a doctor turns symptoms into a diagnosis and a prescription.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%204%20Scout-F55036?style=flat-square)](https://groq.com/)
[![Deployed](https://img.shields.io/badge/Backend-Render-46E3B7?style=flat-square&logo=render&logoColor=white)](https://ai-business-doctor.onrender.com)
[![Deployed](https://img.shields.io/badge/Frontend-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)](https://ai-business-doctor.vercel.app/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](#license)

[Live Demo](https://ai-business-doctor.vercel.app/) · [API](https://ai-business-doctor.onrender.com) · [Video Walkthrough](https://youtu.be/imnm1sa_aGk) · [Pitch Deck](https://gamma.app/docs/AI-Business-Doctor-zukj75z416shptp) · [Report a Bug](../../issues)

</div>

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Preview](#preview)
- [Live Demo](#live-demo)
- [Features](#features)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [AI Workflow](#ai-workflow)
- [Performance & Reliability](#performance--reliability)
- [Deployment](#deployment)
- [Testing](#testing)
- [Challenges Faced](#challenges-faced)
- [Future Improvements](#future-improvements)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)
- [Acknowledgements](#acknowledgements)

---

## Why This Exists

Small business owners generate sales and inventory data every single day — but almost none of it gets read. Point-of-sale tools record transactions without interpreting them. Enterprise BI platforms interpret data but demand analyst-level skills and budgets neither is built for a shopkeeper. The result: decisions made on gut feeling instead of evidence.

**AI Business Doctor** closes that gap. It reads a business's "vitals," diagnoses what's actually happening, and prescribes ranked, specific actions — in plain language, on a budget any small business can afford.

---

## Preview

> 🖼️ *Replace the placeholders below with real screenshots/GIFs from your deployment.*

| Dashboard | Consult the Doctor |
|---|---|
| `![Dashboard Screenshot](docs/screenshots/dashboard.png)` | `![Chat Screenshot](docs/screenshots/consult.png)` |

| Board Meeting Mode | Architecture Diagram |
|---|---|
| `![Board Meeting Screenshot](docs/screenshots/board-meeting.png)` | `![Architecture Diagram](docs/screenshots/architecture.png)` |

`![Demo GIF](docs/screenshots/demo.gif)`

---

## Live Demo

| Resource | Link |
|---|---|
| 🌐 Live Website | [ai-business-doctor.vercel.app](https://ai-business-doctor.vercel.app/) |
| ⚙️ Backend API | [ai-business-doctor.onrender.com](https://ai-business-doctor.onrender.com) |
| 🎥 Video Demo | [YouTube Walkthrough](https://youtu.be/imnm1sa_aGk) |
| 📊 Pitch Deck | [Gamma Presentation](https://gamma.app/docs/AI-Business-Doctor-zukj75z416shptp) |

> **Note:** The backend runs on Render's free tier and spins down after inactivity. The first request after idle time may take up to ~50 seconds to respond while the instance wakes up.

---

## Features

### Core Diagnostics
- 🩺 **Business Health Score (0–100)** — fully transparent, point-by-point explainable, never a black box
- 📈 **Profit Driver Analysis** — compares recent vs. prior performance to surface exactly what's dragging profit down
- 🛑 **Stop-Selling Detection** — flags low-velocity, low-margin products quietly tying up capital
- 📦 **Smart Reorder Alerts** — flags anything within 7 days of stockout, with a recommended reorder quantity
- ⚡ **Anomaly Detection** — catches demand spikes, overstock, and critical (≤3 day) stockouts proactively
- 🎯 **Priority Actions** — merges every issue type into one list, ranked purely by real rupee impact

### AI Features
- 💬 **Consult the Doctor** — natural-language Q&A with session-based follow-up memory
- 🎤 **Board Meeting Mode** — one-click AI-generated executive summary, with a deterministic fallback if the LLM call fails
- 🧠 **Hybrid Intent Routing** — instant deterministic answers for common questions, LLM fallback for everything else, always grounded in real computed data

### Reporting
- 📄 **PDF Export** — downloadable, formatted diagnostic report for sharing with partners or suppliers

### Developer Experience
- 🚀 Fast local setup with Vite hot-reload
- 🧩 Clean separation between deterministic analysis (pandas/NumPy) and the AI reasoning layer
- 🔐 Environment-variable-driven config for zero-code-change deployment

---

## Problem Statement

Millions of small business owners operate without real visibility into their own numbers. Sales and inventory data is generated constantly, but the tools available to interpret it fail at both ends of the market:

- **Basic POS/inventory tools** record transactions but offer zero interpretation
- **Enterprise BI platforms** (Power BI, Tableau) are powerful but assume analyst-level skill
- **ERP systems** are capable but priced far outside small-business reach

The result is real financial damage that compounds silently: capital trapped in dead stock, stockouts on fast-moving items, and profit erosion with no clear explanation — because nothing affordable tells the owner both *what's wrong* and *what to do about it*.

---

## Solution

AI Business Doctor applies a medical metaphor end-to-end: **vitals → diagnosis → prescription → consultation.**

1. **Vitals** — a transparent Health Score summarizes overall business condition at a glance
2. **Diagnosis** — deterministic analysis (pandas/NumPy) identifies profit drivers, dead stock, reorder risk, and anomalies
3. **Prescription** — every issue is converted into a common currency (rupee impact) and ranked into one prioritized action list
4. **Consultation** — a conversational interface lets owners ask questions in plain English and get grounded, data-backed answers

The core financial logic is deliberately deterministic and explainable — no black-box ML for numbers that drive real decisions. The AI/LLM layer (Groq) is used only where it belongs: natural language reasoning, conversation, and narrative generation.

---

## Tech Stack

| Category | Technology |
|---|---|
| **Frontend** | React 19, Vite, Axios, Recharts |
| **Backend** | Python, FastAPI, Uvicorn |
| **Data Analysis** | pandas, NumPy |
| **AI / LLM** | Groq API — `meta-llama/llama-4-scout-17b-16e-instruct` |
| **PDF Generation** | ReportLab |
| **Styling** | Custom CSS |
| **Deployment (Backend)** | Render |
| **Deployment (Frontend)** | Vercel |
| **Version Control** | Git & GitHub |

---

## Architecture

```
Client (Browser)
       ↓
Frontend — React + Vite (Vercel)
       ↓  HTTPS/JSON
Backend API — FastAPI (Render)
       ↓
Analysis Engine (pandas + NumPy)  ──────►  Deterministic diagnostics
       │                                    (health score, priority actions,
       │                                     reorder, anomalies)
       ↓
Groq LLM (Llama 4 Scout)  ──────────────►  Natural language layer
       │                                    (Q&A, executive summaries)
       ↓
Structured JSON Response
       ↓
Client renders dashboard / chat / PDF export
```

**Design principle:** the numbers are computed once, deterministically, and both the dashboard and the LLM narrative layer draw from that same source of truth — so the AI never "makes up" a number the dashboard doesn't already show.

---

## Folder Structure

```
ai-business-doctor/
├── backend/
│   ├── main.py               # FastAPI app, routes, Pydantic response schemas
│   ├── analysis_engine.py    # Core diagnostic logic: profit analysis, reorder,
│   │                         #   anomalies, health score, LLM Q&A routing
│   ├── pdf_report.py         # ReportLab-based PDF report generation
│   ├── create_dataset.py     # Generates the synthetic demo dataset
│   ├── sales_data.csv        # Sales dataset used by the analysis engine
│   ├── inventory_data.csv    # Inventory dataset used by the analysis engine
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main dashboard: health score, priority actions,
│   │   │                     #   anomaly alerts, chat, board meeting modal
│   │   ├── App.css           # Application styling
│   │   ├── config.js         # Environment-driven API base URL
│   │   ├── main.jsx          # React entry point
│   │   ├── index.css         # Global styles
│   │   └── assets/           # Images and static assets
│   ├── public/                # Static public files (favicon, icons)
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── .gitignore
```

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com/)

### 1. Clone the repository

```bash
git clone https://github.com/bonamukkala-bot/ai-business-doctor.git
cd ai-business-doctor
```

### 2. Backend setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:

```env
GROQ_API_KEY=your_groq_api_key_here
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Generate the demo dataset (if not already present):

```bash
python create_dataset.py
```

Run the backend:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 3. Frontend setup

```bash
cd ../frontend
npm install
```

Create a `.env` file inside `frontend/` for local development (optional — defaults to `127.0.0.1:8000` if omitted):

```env
VITE_API_URL=http://127.0.0.1:8000
```

Run the frontend:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### 4. Production build

```bash
npm run build
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|---|---|---|
| `GROQ_API_KEY` | API key for Groq's LLM used in Q&A and executive summaries | ✅ Yes |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | ⚠️ Recommended (defaults to localhost) |

### Frontend (`frontend/.env`)

| Variable | Description | Required |
|---|---|---|
| `VITE_API_URL` | Base URL of the backend API | ⚠️ Recommended (defaults to `127.0.0.1:8000`) |

> **Note:** If `GROQ_API_KEY` is missing or a Groq request fails, the app does **not** crash — it gracefully falls back to deterministic templated responses for both the executive summary and Q&A.

---

## Usage

1. Open the app — the dashboard automatically runs a diagnostic scan on load
2. Review the **Business Health Score** and its breakdown at the top
3. Check **Priority Actions** for the highest-impact issues to address first
4. Scroll to **Anomaly Alerts** for anything unusual (spikes, overstock, critical stockouts)
5. Use **Consult the Doctor** to ask questions like:
   - *"Why are profits down?"*
   - *"What should I stop selling?"*
   - *"What should I reorder?"*
6. Click **🎤 Board Meeting Mode** for an instant AI-generated executive summary
7. Click **⬇ Download Report** to export the full diagnosis as a PDF

---

## API Endpoints

| Method | Route | Purpose | Auth |
|---|---|---|---|
| `GET` | `/` | Health check | None |
| `GET` | `/insights` | Full diagnostic bundle — profit analysis, stop-selling, reorder, priority actions, anomalies, health score, executive summary | None |
| `GET` | `/executive-summary` | Standalone AI-generated board-meeting summary | None |
| `GET` | `/export-report` | Streams a generated PDF diagnostic report | None |
| `POST` | `/ask` | Accepts `{ question, session_id }`, returns a grounded natural-language answer | None |

> **Note:** This project currently has no authentication layer — see [Future Improvements](#future-improvements).

---

## AI Workflow

```
User Question
     ↓
Keyword Intent Router (fast, deterministic, offline)
     ↓
     ├── Matched intent  →  Computed answer from analysis_engine.py  →  Response
     │
     └── No match
             ↓
        Prompt built from live business data + recent session history
             ↓
        Groq LLM (Llama 4 Scout)
             ↓
        Post-processed, grounded natural-language answer
             ↓
        Response (or deterministic fallback if the LLM call fails)
```

This hybrid approach keeps common questions instant and free, while still handling open-ended questions intelligently — without ever letting the AI improvise numbers that contradict the dashboard.

---

## Screenshots

> 🖼️ *Add captioned screenshots here once available.*

**Dashboard — Health Score & Vitals**
`![Dashboard](docs/screenshots/dashboard.png)`

**Priority Actions Panel**
`![Priority Actions](docs/screenshots/priority-actions.png)`

**Consult the Doctor — Live Q&A**
`![Consult the Doctor](docs/screenshots/consult.png)`

**Board Meeting Mode**
`![Board Meeting Mode](docs/screenshots/board-meeting.png)`

---

## Performance & Reliability

- Core diagnostic analysis (health score, priority actions, reorder, anomalies) runs entirely on deterministic pandas/NumPy logic — no network dependency, near-instant response
- Executive summary and open-ended Q&A include a deterministic fallback path, so the app never shows a blank error if the Groq API is slow or unavailable
- Session-based conversation history is capped (last 6 exchanges) to keep follow-up context relevant without unbounded memory growth

> **Note:** Render's free-tier backend spins down after inactivity, adding a one-time cold-start delay (~50s) to the first request.

---

## Security

> This is a demo/portfolio project and does not currently implement authentication or authorization. See [Future Improvements](#future-improvements).

- CORS is restricted via the `ALLOWED_ORIGINS` environment variable rather than a wildcard
- Input validation is enforced via Pydantic models on all request/response schemas
- No sensitive data (API keys, credentials) is committed to the repository — all secrets are environment-variable-driven

---

## Deployment

| Layer | Platform | Notes |
|---|---|---|
| **Frontend** | [Vercel](https://vercel.com) | Auto-deploys from the `main` branch; `VITE_API_URL` set to the live Render backend URL |
| **Backend** | [Render](https://render.com) | Web Service, Python 3, root directory `backend`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Environment Variables** | Set directly in each platform's dashboard | `GROQ_API_KEY` and `ALLOWED_ORIGINS` on Render; `VITE_API_URL` on Vercel |

**Live URLs:**
- Frontend: [ai-business-doctor.vercel.app](https://ai-business-doctor.vercel.app/)
- Backend: [ai-business-doctor.onrender.com](https://ai-business-doctor.onrender.com)

---

## Testing

- ✅ Manual end-to-end testing across all endpoints (`/insights`, `/executive-summary`, `/ask`, `/export-report`)
- ✅ Verified LLM fallback behavior by testing with and without a valid `GROQ_API_KEY`
- ✅ Verified session-based follow-up context in the Q&A chat
- 🔜 Automated unit tests for `analysis_engine.py` functions (planned — see roadmap)
- 🔜 Integration tests for API endpoints using `pytest` + `httpx`

---

## Challenges Faced

| Challenge | Solution |
|---|---|
| LLM calls can fail, time out, or be rate-limited mid-demo | Built deterministic fallback templates for both the executive summary and Q&A, so the app never shows a blank error |
| Comparing fundamentally different problem types (profit loss, dead stock, stockout risk) on one list | Converted every issue into a common unit — real rupee impact — and ranked them together |
| Making an AI-driven health score feel trustworthy rather than a black box | Built a fully transparent, point-by-point deduction system where every score change traces to a specific, stated reason |
| CORS misconfiguration blocking the deployed frontend from reaching the deployed backend | Replaced wildcard origins with an environment-variable-driven `ALLOWED_ORIGINS` list, safe for both local dev and production |

---

## Future Improvements

- [ ] Authentication & multi-tenant support (multiple businesses per account)
- [ ] Automated data sync from POS/billing systems (remove manual CSV dependency)
- [ ] Predictive, SKU-level demand forecasting
- [ ] WhatsApp/voice-based "Consult the Doctor" interface
- [ ] Regional language support
- [ ] Dockerized deployment
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Automated test suite (pytest + Vitest)
- [ ] Monitoring & analytics dashboard for usage insights

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

Please open an issue first for major changes to discuss what you'd like to modify.

---

## License

This project is licensed under the **MIT License**.

> ⚠️ No `LICENSE` file currently exists in this repository. Add one (e.g. via GitHub's "Add file → Create new file → LICENSE" and selecting the MIT template) to make this official.

---

## Author

**Charan Bonamukkala**

- 💻 GitHub: [@bonamukkala-bot](https://github.com/bonamukkala-bot)
- 🔗 LinkedIn: [bonamukkala-charan](https://linkedin.com/in/bonamukkala-charan)
- 📧 Email: bonamukkalacharan@gmail.com

---

## Acknowledgements

- [Groq](https://groq.com/) for fast LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) for the frontend tooling
- [ReportLab](https://www.reportlab.com/) for PDF generation
- [Render](https://render.com/) and [Vercel](https://vercel.com/) for hosting

---

<div align="center">

**Every business deserves a doctor.**

⭐ Star this repo if you find it useful!

</div>
