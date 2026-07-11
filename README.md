# 🧭 PathFinder — Agentic Career Counselling Companion

An AI-powered career counselling web app built with **Python Flask** and **IBM Watsonx.ai (Granite models)**.  
It features a RAG pipeline grounded in real labor market data, a streaming chat interface, skill-gap analysis, and a personalised 6-month roadmap generator.

---

## ✨ Features

| Feature | Details |
|---|---|
| 💬 **Agentic Chat** | Streaming SSE chat powered by IBM Granite models via Watsonx.ai |
| 🔍 **RAG Pipeline** | TF-IDF retrieval over 12 roles, trending skills, industry outlook data |
| 📊 **Dashboard** | Trending skills, industry hiring index, and role cards |
| 🔬 **Skill-Gap Analyser** | Match score, missing skills, recommended certs, and entry paths |
| 🗺️ **Roadmap Planner** | AI-generated 6-month career roadmap tailored to your profile |
| ⚙️ **AGENT_INSTRUCTIONS** | Fully customisable tone, style, and safety rules in one config file |
| 🌙 **Dark Mode** | Bootstrap 5 dark theme, fully responsive for mobile |
| 🔒 **Secure Credentials** | All secrets via `.env` — never hardcoded |

---

## 🗂 Project Structure

```
PathFinder-Career-Agent/
├── run.py                     ← App entry point (development)
├── wsgi.py                    ← WSGI entry (production)
├── Procfile                   ← Heroku/Render/Railway deployment
├── requirements.txt
├── .env.example               ← Copy to .env and fill in secrets
│
├── config/
│   └── agent_instructions.py  ← ⚙️ Customise tone, style, safety rules here
│
├── data/
│   └── labor_market.json      ← RAG corpus (roles, skills, outlook)
│
└── app/
    ├── __init__.py            ← Flask application factory
    ├── watsonx_client.py      ← IBM Watsonx.ai / Granite integration
    ├── rag_engine.py          ← TF-IDF RAG pipeline
    ├── routes/
    │   ├── chat.py            ← POST /api/chat, SSE /api/chat/stream
    │   ├── dashboard.py       ← GET /api/dashboard/*, POST /api/dashboard/skill-gap
    │   └── api.py             ← GET / (serves HTML), GET /api/info
    ├── templates/
    │   └── index.html         ← Single-page app (Bootstrap 5 dark)
    └── static/
        ├── css/style.css      ← Dark-mode custom styles
        └── js/app.js          ← Chat SSE, dashboard, skill-gap, roadmap JS
```

---

## 🚀 Quick Start (Local Development)

### 1. Clone & set up Python environment

```bash
git clone <your-repo-url>
cd PathFinder-Career-Agent

# Create a virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate.bat       # Windows CMD
# venv\Scripts\Activate.ps1       # Windows PowerShell
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```ini
IBM_API_KEY=your_ibm_cloud_api_key_here
IBM_PROJECT_ID=your_watsonx_project_id_here
IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com
GRANITE_CHAT_MODEL=ibm/granite-3-3-8b-instruct
FLASK_SECRET_KEY=change-me-to-a-long-random-string
```

> **Demo mode:** If you leave `IBM_API_KEY` empty, the app runs in demo mode with sample responses — great for testing the UI without credentials.

### 4. Run the development server

```bash
python run.py
```

Open **http://localhost:5000** in your browser.

---

## 🔑 Getting IBM Watsonx.ai Credentials

1. Sign up at [https://cloud.ibm.com](https://cloud.ibm.com)
2. Create an **IBM Cloud API Key**: [Manage → Access (IAM) → API keys](https://cloud.ibm.com/iam/apikeys)
3. Go to [Watsonx.ai](https://dataplatform.cloud.ibm.com/) → Create a new **Project**
4. Copy the **Project ID** from the project settings
5. Set `IBM_WATSONX_URL` to the region closest to you:
   - US South: `https://us-south.ml.cloud.ibm.com`
   - EU Frankfurt: `https://eu-de.ml.cloud.ibm.com`
   - Tokyo: `https://jp-tok.ml.cloud.ibm.com`

---

## ⚙️ Customising the AI Agent

Edit **`config/agent_instructions.py`** to change:

| Setting | What it controls |
|---|---|
| `AGENT_NAME` | The agent's display name |
| `AGENT_PERSONA` | Core personality description |
| `COUNSELLING_STYLE` | `"encouraging"` / `"direct"` / `"socratic"` / `"formal"` |
| `RESPONSE_FORMAT_INSTRUCTIONS` | How the AI structures its output |
| `SAFETY_RULES` | Hard rules the AI must never break |
| `ALLOWED_TOPICS` | List of permitted counselling topics |
| `RAG_GROUNDING_INSTRUCTION` | How the AI uses retrieved labor market data |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve the web app |
| `GET` | `/health` | App health + demo mode status |
| `GET` | `/api/info` | App version, model, demo mode |
| `POST` | `/api/chat` | Full chat completion (JSON response) |
| `POST` | `/api/chat/stream` | Streaming chat (SSE) |
| `GET` | `/api/chat/session` | Get conversation history |
| `DELETE` | `/api/chat/session` | Clear conversation history |
| `GET` | `/api/dashboard/overview` | All dashboard data |
| `POST` | `/api/dashboard/skill-gap` | Single-role skill gap analysis |
| `POST` | `/api/dashboard/skill-gap/multi` | All-roles skill gap comparison |
| `GET` | `/api/dashboard/roles` | All career roles |
| `GET` | `/api/dashboard/trending` | Trending skills 2025 |
| `GET` | `/api/dashboard/outlook` | Industry hiring outlook |
| `POST` | `/api/dashboard/roadmap` | Generate 6-month roadmap |

### Example: Chat request
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I studied Mathematics and I am interested in AI. What career paths should I explore?",
    "profile": {
      "education": "Mathematics",
      "skills": ["Python", "Statistics", "Linear Algebra"],
      "interests": "Machine Learning, AI"
    }
  }'
```

### Example: Skill Gap Analysis
```bash
curl -X POST http://localhost:5000/api/dashboard/skill-gap \
  -H "Content-Type: application/json" \
  -d '{"skills": ["Python", "SQL", "Statistics"], "role_id": "data_scientist"}'
```

---

## 🌐 Deployment

### Option A — Render (Recommended, free tier available)

1. Push your code to GitHub (without `.env` — it's in `.gitignore`)
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4`
6. Add all `.env` variables in the **Environment** tab
7. Deploy

### Option B — Heroku

```bash
heroku create pathfinder-career-agent
heroku config:set IBM_API_KEY=... IBM_PROJECT_ID=... FLASK_SECRET_KEY=...
git push heroku main
```

### Option C — Docker

```bash
# Build
docker build -t pathfinder .

# Run
docker run -p 5000:5000 \
  -e IBM_API_KEY=your_key \
  -e IBM_PROJECT_ID=your_project \
  -e FLASK_SECRET_KEY=some-secret \
  pathfinder
```

### Option D — IBM Code Engine

```bash
ibmcloud ce application create \
  --name pathfinder \
  --image icr.io/<namespace>/pathfinder:latest \
  --env IBM_API_KEY=<key> \
  --env IBM_PROJECT_ID=<project-id> \
  --port 5000
```

---

## 🐳 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120"]
```

---

## 🔒 Security Notes

- **Never commit `.env`** — it's listed in `.gitignore`
- The `FLASK_SECRET_KEY` must be a long, random string in production
- The `SAFETY_RULES` in `config/agent_instructions.py` are injected into every system prompt
- API keys are read from environment variables — never hardcoded

---

## 📦 Extending the RAG Corpus

To add more roles or update market data, edit **`data/labor_market.json`**.  
The RAG engine automatically re-indexes on next startup. No code changes required.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | IBM Granite 3.3 8B Instruct via Watsonx.ai |
| **Backend** | Python 3.11 · Flask 3.0 |
| **RAG** | Custom TF-IDF retriever (zero external vector DB dependency) |
| **Frontend** | Bootstrap 5 dark · Vanilla JS · SSE streaming |
| **Deployment** | Gunicorn · Render / Heroku / IBM Code Engine |

---

*Made with ❤️ using IBM Watsonx.ai and Granite*
