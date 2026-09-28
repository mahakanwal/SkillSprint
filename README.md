# SkillSprint AI

GenAI-powered employee onboarding intelligence platform — generates role-specific onboarding plans from your company's real documents, then independently verifies every claim with a Python validation pipeline before a human reviewer signs off.

Built for **NimbusRetail Pvt Ltd** (fictional company dataset) as part of the Aptech PowerPlay competition.

---

## Why this exists

Most "AI onboarding" tools just call an LLM and show you whatever it returns. SkillSprint AI doesn't stop there — every module, checklist item, task, and quiz question generated is checked against:

- **Coverage** — are all mandatory requirements for this role actually addressed?
- **Traceability** — does every generated item cite a real requirement and a real source document?
- **Consistency** — does the GenAI output actually match what the Requirement Matrix (ground truth) says?
- **Hallucination / Contradiction** — is any of it made up, or does it conflict with the source policy?

Flagged content goes to a **Reviewer Dashboard** where a human can approve, reject, or override — with a full audit trail.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| GenAI | Groq API (`openai/gpt-oss-120b`, with automatic fallback + retry) |
| Auth | JWT (python-jose), bcrypt password hashing |
| Frontend | React (Vite), Tailwind CSS, lucide-react |
| Document parsing | pdfplumber, python-docx |

---

## Project Structure

```
Skill-Sprint/
├── backend/
│   ├── main.py                    # FastAPI app, router registration, RBAC
│   ├── database/                  # SQLAlchemy models + connection
│   ├── routers/                   # API endpoints (auth, documents, roles,
│   │                               #   employees, requirements, onboarding,
│   │                               #   validation, review, reports)
│   ├── genai_pipeline/            # Groq client, retry/fallback, prompt
│   │                               #   templates, generator
│   ├── python_validation/         # Coverage / traceability / consistency /
│   │                               #   hallucination / contradiction / duplicate
│   │                               #   / sequence / role-relevance checkers
│   ├── document_processing/       # Extraction + chunking
│   ├── document_validation/       # File validation + version control
│   ├── security/                  # JWT auth, RBAC (role-based access)
│   └── services/                  # Orchestration layer (onboarding,
│                                   #   validation, review, reports, etc.)
├── frontend/
│   └── src/components/dashboard/  # One dashboard per role (see below)
└── sample_documents/              # NimbusRetail's 20-document dataset
```

---

## Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/skillsprint
SECRET_KEY=<any-long-random-string>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

GROQ_API_KEY=<your-groq-api-key>
GROQ_MODEL_PRIMARY=openai/gpt-oss-120b
GROQ_MODEL_FALLBACK=openai/gpt-oss-20b
```

Run the server:

```bash
uvicorn main:app --reload
```

API docs available at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`.

---

## Roles & Access

The platform has **5 roles**, each with its own dashboard and its own real, backend-enforced permissions (not just hidden UI):

| Role | Dashboard | Can do |
|---|---|---|
| **Admin** | Full admin dashboard | Everything — documents, roles, employees, requirements, onboarding, review, reports, staff account creation |
| **Training Manager** | Same as Admin, minus staff-account creation | Documents, roles, employees, requirements, onboarding, review, reports |
| **Reviewer** | Reviewer dashboard | Read/review generated plans, validation results; approve / reject / override with audit trail |
| **Manager** | Manager dashboard | Read-only view of their direct reports' onboarding progress |
| **Employee** | Employee dashboard | View + complete their own onboarding plan (checklist, tasks, quiz); edit their own profile |

---

## Login Credentials (test/demo accounts)

There is **no public sign-up**. Accounts are created one of two ways:

1. **First admin** — one-time bootstrap, only works before any user exists:
   `POST /auth/bootstrap-first-admin` with `{ "email": ..., "password": ... }`
2. **Everyone else** — created by an Admin:
   - Employees: auto-created from **Employee Manager** (a temporary password is generated and shown once)
   - Staff (Training Manager / Reviewer / Manager / another Admin): created via **Team Access** tab → `POST /auth/create-staff-login`

### Test accounts (already created on this project)

| Role | Email | Password |
|---|---|---|
| Admin | `admin@skillsprint.com` | `admin@skillsprint123!` |
| Training Manager | `fatima@skillsprint.com` | `I@ZKO0@nc4Bl` |
| Reviewer | `msami@skillsprint.com` | `kxZdaPR7&3X!` |
| Manager | `mirhafatima@skillsprint.com` | `AmP%e8Qt52w&` |
| Employee | `hammad@skillsprint.com` | `o7Bqjz!mcx6r` |

> ⚠️ These are real accounts on this project's database, for internal team/evaluator use only. Do not commit this table to a **public** repo — if this repo is public, move this section to a local-only file (e.g. `CREDENTIALS.md`, added to `.gitignore`) and reference it from here instead. Change all passwords before any production deployment.

**If the database is ever reset**, recreate them in this order:
1. Login page → "Brand-new install? Set up the first admin account" → use the Admin row above.
2. Log in as Admin → **Team Access** tab → recreate Training Manager, Reviewer, and Manager using the rows above (a *new* temporary password will be generated each time — update this table with whatever it gives you).
3. Log in as Admin/Training Manager → **Employees** tab → add the employee → note the new temporary password shown once → update this table.

---

## Dataset

`sample_documents/` contains NimbusRetail's full evaluation dataset:
- 20 active company documents (policies, SOPs, FAQs, compliance docs, process manuals)
- 10 policy-version-change pairs (old version marked `-OLD`, superseded)
- 10 deliberate conflict/ambiguity cases (documented in `CONFLICT_CASES.md`)
- 10 adversarial / prompt-injection test documents (`adversarial_cases/`)
- `requirement_matrix_full.csv` — 160 requirements across all 10 job roles, 130 mandatory

Upload documents via **Document Pipeline**, then bulk-import the requirement matrix via **Requirement Matrix → Upload CSV**.

---

## Core Pipeline (what actually happens on "Generate Plan")

1. Employee's role → pulls that role's rows from the **Requirement Matrix**
2. Pulls the real document chunks those requirements are sourced from
3. Sends both to Groq with a strict-JSON prompt (retried + falls back to a second model on failure)
4. Parses the response into modules / checklist / tasks / quiz
5. Runs the **Python validation pipeline** — coverage, traceability, consistency, hallucination, contradiction, duplicate, sequence, role-relevance checks
6. Computes a `verification_status` (Verified / Verified with Warning / Partially Verified / Incomplete / Unsupported / Contradictory / Manual Review Required)
7. Saves everything, including a per-requirement audit row, so a Reviewer can see exactly why each item passed or failed

---

## Requirements

| Tool | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 14+ |

## Team

| Name | Role |
|---|---|
| Maha Kanwal | Team Leader |
| Fatima Amir | Team Member |
| Mohib Raza | Team Member |
| Asharib | Team Member |

## AI Usage

See `AI_USAGE.md` for a full breakdown of what was AI-assisted vs. hand-written during development, per competition requirements.

## License

Submitted for the Aptech PowerPlay competition evaluation.