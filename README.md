# AimHigher AI Onboarding System

An autonomous multi-agent pipeline that discovers Web3 projects, qualifies them, and guides them to open campaign pools on AimHigher.

---

## Architecture

```
Data Sources (Twitter · Telegram · Reddit · Discord · Dexscreener · Moralis · Covalent)
                              ↓
                       Hunter Service
                   Score · dedup · filter 30k–3M cap
                              ↓
                        Orchestrator
              Route leads · track lifecycle · per-project memory
                    ↓         ↓         ↓         ↓
               Outreach  Qualification  Onboarding  Conversion
               DM·bot    Score·filter   RAG·Q&A     Nudge·track
                              ↓
              PostgreSQL · Redis · Pinecone
                              ↓
           Claude API · AimHigher Platform · Next.js Dashboard
```

**Lead lifecycle:** `discovered → contacted → qualified → onboarding → converted`

---

## Stack

| Layer        | Technology                                      |
|--------------|------------------------------------------------|
| Backend      | FastAPI (async), Python 3.12                   |
| Database     | PostgreSQL 16 + SQLAlchemy 2 (async)           |
| Queue        | Redis 7 (lists + sorted sets)                  |
| LLM          | Anthropic Claude (claude-sonnet-4-20250514)    |
| Embeddings   | OpenAI text-embedding-3-small                  |
| Vector DB    | Pinecone (serverless)                          |
| Onchain      | Dexscreener · Moralis · Covalent               |
| Social       | Twitter v2 · Telegram Bot · Discord.py · PRAW  |
| Frontend     | Next.js 14 · TypeScript · Tailwind · Recharts  |
| Deployment   | Docker Compose                                 |

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo>
cd aimhigher
cp .env.example .env
# Fill in all API keys in .env
```

### 2. Launch with Docker Compose

```bash
docker-compose up --build
```

Services:
- Backend API:  http://localhost:8000
- Frontend:     http://localhost:3000
- API docs:     http://localhost:8000/docs  (DEBUG=true only)

### 3. Run migrations (first run only)

Migrations run automatically on container start via the `command` in docker-compose.yml.
To run manually:

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Seed knowledge base

Upload AimHigher docs so the Onboarding Agent has context:

```bash
curl -X POST http://localhost:8000/api/v1/knowledge \
  -H "Content-Type: application/json" \
  -d '{"title": "AimHigher Product Docs", "source_url": "https://aimhigher.gitbook.io/product-docs/", "content": "<paste docs content here>"}'
```

Or use the dashboard Knowledge page to upload via UI.

---

## Services

### Hunter Service
Runs every 30 minutes (configurable via `HUNTER_INTERVAL_SECONDS`).

Sources:
- **Dexscreener** — scans new token pairs on Ethereum, BNB, Solana, Base for tokens in the 30k–3M market cap range
- **Moralis** — enriches market cap from circulating supply when Dexscreener data is incomplete
- **Covalent** — adds holder count and 7-day transaction activity
- **Twitter/X** — runs 5 discovery queries, detects pain signals via 12 regex patterns
- **Telegram** — monitors 10 watchlist groups, real-time via webhook
- **Reddit** — scans 14 subreddits (new/rising) for project and pain keywords
- **Discord** — reads up to 3 channels per joined guild over the past 24h

Scoring formula (0–100):
| Dimension         | Max pts | Logic                                    |
|-------------------|---------|------------------------------------------|
| Market cap        | 25      | Sweet spot 100k–800k; tapers to edges    |
| Pain signals      | 25      | 6 pts each, max 4; +1 specificity bonus  |
| Engagement rate   | 20      | Log scale; 1% → ~13pts, 10%+ → 20pts    |
| Activity recency  | 15      | Linear decay over 14 days                |
| Community size    | 15      | Log scale; 25k combined = max            |

HOT ≥ 75 · WARM ≥ 45 · COLD < 45

### Outreach Service
Consumes `queue:outreach_tasks`. Three task types:
- **initial_outreach** — personalized first message, channel-aware (Twitter/Telegram/Discord), pain-signal-led, no pitch in first message
- **reply** — full conversation history injected into Claude context, stage-aware escalation
- **followup** — 4 attempts at 2/4/7/14 day intervals, each with a different angle; lead marked DEAD after 4 failed attempts

Tone rules enforced in system prompt: no "circling back", no "I'd be happy to", max 5 sentences, never pitch in opener.

### Qualification Agent
Runs after 4+ conversation turns. Extracts via Claude JSON mode:
- Confirmed market cap, community size, platforms, decision-maker status
- Growth intent, pain confirmation, competitor mentioned, budget signal
- Objections detected (budget, competitor lock-in, trust, readiness)

Output: `qualification_score` (0–100), `category` (hot/warm/cold), `readiness_level` (high/medium/low).
Cold/low-readiness leads → DISQUALIFIED. All others → QUALIFIED + dispatch to onboarding queue.

### Onboarding Agent (RAG)
8-step pipeline:
0. Introduction — explain AimHigher, gauge interest
1. Fit assessment — confirm chain, market cap, community size
2. Campaign design — task types (follows, joins, on-chain interactions, content)
3. Budget discussion — pool sizing, pay-per-task framing
4. ROI demonstration — concrete metrics, handle "need proof"
5. Trust & mechanics — non-custodial, smart contract, task verification
6. Pool creation guide — step-by-step walkthrough
7. Converted — pool live confirmation

Each turn: Pinecone retrieval (top-4 chunks, score ≥ 0.28) → Claude with RAG context → step completion detection → advance step counter if complete.

### Conversion Engine
Proactive scan every 15 minutes. Nudge triggers:
- **inactivity**: no reply in 24h → re-engage with market hook
- **stuck_step**: same step for 72h+ → address what's blocking
- **urgency**: hot lead inactive 7+ days → limited slot / competitor signal
- **final_push**: inactive 14+ days → respectful close, door-closing message

Pool creation event → mark CONVERTED, broadcast WebSocket event to dashboard, update DailyMetrics.

### Orchestrator
Runs every 5 minutes:
- **Memory maintenance** — regenerates Claude summary for any lead with 10+ new conversation turns; injects into all future prompts
- **Anomaly detection** — flags leads stuck in CONTACTED (5d+), QUALIFIED (2d+), ONBOARDING (14d+) and queues nudges
- **Queue routing** — `route_lead()` maps stage → correct agent queue

---

## API Endpoints

### Leads
```
GET    /api/v1/leads                    List with filters (stage, priority, chain, score)
POST   /api/v1/leads                    Create lead
GET    /api/v1/leads/{id}               Get lead
PATCH  /api/v1/leads/{id}               Update lead
POST   /api/v1/leads/{id}/transition    Stage transition (with validation)
GET    /api/v1/leads/{id}/conversations Full conversation history
GET    /api/v1/leads/{id}/events        Audit trail
DELETE /api/v1/leads/{id}               Soft delete
```

### Outreach
```
POST /api/v1/outreach/send              Trigger outreach for a lead
POST /api/v1/outreach/reply             Ingest inbound reply (webhook)
POST /api/v1/outreach/followups         Schedule a follow-up
GET  /api/v1/outreach/followups/due     List due follow-ups
```

### Qualification
```
POST /api/v1/qualification/{id}/run           Queue qualification
POST /api/v1/qualification/{id}/qualify-now   Synchronous qualification (dashboard)
GET  /api/v1/qualification/{id}/result        Get qualification result
POST /api/v1/qualification/{id}/handle-objection  Generate objection response
```

### Onboarding
```
POST /api/v1/onboarding/chat            Process onboarding message
GET  /api/v1/onboarding/{id}/progress   Step progress view
POST /api/v1/onboarding/{id}/start      Start onboarding manually
POST /api/v1/onboarding/{id}/advance    Force-advance step (operator)
```

### Analytics & Agents
```
GET  /api/v1/analytics/dashboard        Stats: totals, funnel, rates
GET  /api/v1/agents/status              Agent on/off status
POST /api/v1/agents/toggle              Toggle agent
POST /api/v1/hunter/run                 Trigger hunter run
GET  /api/v1/hunter/queue-depth         Queue sizes
```

### Suggestions & Knowledge
```
POST /api/v1/suggestions                Get 3 AI reply options
POST /api/v1/suggestions/stream         Stream reply token-by-token
GET  /api/v1/knowledge                  List indexed docs
POST /api/v1/knowledge                  Upload doc (triggers indexing)
POST /api/v1/knowledge/search           Semantic search
```

### WebSocket
```
WS /ws    Real-time events: stage changes, conversions, nudges
```

---

## Dashboard Pages

| Page          | Route             | Description                                              |
|---------------|-------------------|----------------------------------------------------------|
| Dashboard     | /                 | Stats cards, funnel chart, priority breakdown, recent leads |
| Pipeline      | /pipeline         | Kanban board across 5 stages, filterable by chain/priority |
| Conversations | /conversations    | Slack-style chat, AI suggestions panel, lead quick-info  |
| Agents        | /agents           | Toggle agents, live queue depth monitor, trigger hunter  |
| Knowledge     | /knowledge        | Upload docs, semantic search, indexing status            |

---

## Environment Variables

See `.env.example` for full list. Required:

```
# Core
SECRET_KEY              32+ char random string
DATABASE_URL            postgresql://user:pass@host:5432/db
REDIS_URL               redis://:pass@host:6379/0

# AI
ANTHROPIC_API_KEY       sk-ant-...
OPENAI_API_KEY          sk-...       (embeddings only)
PINECONE_API_KEY
PINECONE_ENVIRONMENT

# Social
TWITTER_BEARER_TOKEN
TWITTER_API_KEY / SECRET / ACCESS_TOKEN / ACCESS_SECRET
TELEGRAM_BOT_TOKEN
DISCORD_BOT_TOKEN
REDDIT_CLIENT_ID / CLIENT_SECRET

# Onchain
MORALIS_API_KEY
COVALENT_API_KEY
```

---

## File Structure

```
aimhigher/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # leads, outreach, analytics, agents,
│   │   │                         # hunter, qualification, onboarding,
│   │   │                         # knowledge, suggestions
│   │   ├── agents/               # qualification, onboarding, conversion,
│   │   │                         # orchestrator (+ workers)
│   │   ├── core/                 # config, redis client
│   │   ├── db/                   # session, crud
│   │   ├── models/               # SQLAlchemy ORM (8 tables)
│   │   ├── schemas/              # Pydantic v2 schemas
│   │   ├── services/             # onchain, twitter, telegram, reddit,
│   │   │                         # discord, hunter, scorer, claude_client,
│   │   │                         # outreach_composer, outreach_worker,
│   │   │                         # vector_store
│   │   └── main.py               # FastAPI app + lifespan wiring
│   ├── alembic/                  # migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                  # Next.js App Router pages
│   │   │   ├── page.tsx          # Dashboard
│   │   │   ├── pipeline/         # Kanban
│   │   │   ├── conversations/    # Chat UI
│   │   │   ├── agents/           # Controls
│   │   │   └── knowledge/        # KB management
│   │   ├── components/           # Sidebar
│   │   └── lib/                  # api.ts, store.ts (Zustand)
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```
