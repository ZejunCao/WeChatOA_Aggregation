# WeChatOA_Aggregation

**Language:** [**简体中文**](README.md) · [English](README.en.md) (this page)

**Local workspace for WeChat Official Account articles** — subscribe and crawl in bulk; the feed shows **cover, title, and summaries** (digest and/or optional LLM); **full articles open on WeChat** in the browser; optional LLM tagging and summaries.

![Feed preview](figures/blog_preview.png)

---

## Problem this solves

Content from many WeChat Official Accounts is scattered; switching in the browser is tedious. If you want **local archiving, filtering, read/bookmark state, and optional LLM tags or summaries**, you need a small self-hosted stack.  
This repo ships a **FastAPI backend + Vue frontend**, stores everything under local `data/`, and needs no separate database—suitable for individuals or small teams.

---

## What you can do with it

Capabilities in table form—**what you get**, not file paths. For where data lands on disk, see [Data & storage](#data--storage).

| Capability | Description |
|------------|-------------|
| **Accounts & subscriptions** | Search, add, or remove accounts; **hide** one from the feed but keep the subscription—split work vs. personal reading. |
| **Credentials & QR login** | Config **QR login** stores the session locally; banner on expiry—scan again so crawls don’t fail mid-run. |
| **Crawl & sync** | One-click batch crawl with incremental dedup; UI shows progress; bad credentials stop the job with a reason. |
| **Covers, titles & snippets** | Feed shows cover, title, summary, tags; **open the link** for full text. Covers cached locally; body text is for backend stats & LLM. |
| **Reading, filters & layout** | Card/row layouts, date groups, filters (keyword, account, date, tags, sort); Feed themes; light/dark/system. |
| **Read, bookmark & delete** | Open link → **read**; filter unread/bookmarked; **delete** drops the item and skips it on later crawls. |
| **LLM (optional)** | Chat Completions–compatible API: crawl-time summary & tags; tune concurrency. Off = no AI snippets/tags only. |
| **Near-duplicates** | **MinHash + LSH** for near-duplicate posts; details in `README.legacy.md`. |
| **Logs** | Crawl, account, and cache events in an operation log; browse by time in the UI for debugging. |

---

## End-to-end workflow

1. **Environment**: Install Python and frontend deps (tables and commands below).
2. **Credentials**: Start the app → Config → QR login until the UI shows a healthy session.
3. **Subscriptions**: Add accounts; hide some from the feed if needed.
4. **Crawl**: One-click crawl → article lists, covers, and optional backend body cache update per your settings; progress and errors are visible in the UI.
5. **Optional LLM**: Enable crawl-time summary/tagging and set concurrency and task profile in Config.
6. **Daily use**: Filter in the feed, mark read/bookmark, open original links.

```text
Browser (Vue)  ←→  FastAPI backend  ←→  Local archive (lists, body text, covers, …)
                      ↓
              WeChat MP APIs · body fetch · optional LLM
```

---

## Tech stack

| Layer | Stack |
|-------|--------|
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS v4, Pinia, Vue Router, lucide-vue-next, … |
| Backend | FastAPI, Uvicorn, Requests, Pillow, DrissionPage, datasketch, … (see `pyproject.toml`) |
| Data | Local JSON / JSONL, static cover files—no database server |

---

## Requirements

| Tool | Version | Role |
|------|---------|------|
| **Python** | ≥ 3.11 | Backend & scripts |
| **uv** | Latest stable | Recommended for Python deps |
| **Node.js** | LTS (with npm) | Frontend dev & build |

---

## Quick start

### 1. Install dependencies

```bash
# After cloning, from the repo root
cd WeChatOA_Aggregation

uv sync
cd frontend && npm install && cd ..
```

### 2. One-command dev start

```bash
./start_all.sh
```

| Service | URL |
|---------|-----|
| Backend API | <http://127.0.0.1:8000> |
| Frontend dev | <http://127.0.0.1:5173> |

`Ctrl+C` stops both child processes.

### 3. Run backend and frontend separately (optional)

```bash
# Terminal 1
uv run uvicorn api:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

---

## Configuration

### WeChat Official Account session

| Step | Action |
|------|--------|
| 1 | Open the frontend → **Config** |
| 2 | **QR login** and complete the MP login flow |
| 3 | Token / cookie are written to `data/id_info.json` (advanced users may edit manually at their own risk) |

When the session expires, the banner on Config prompts you; scan again to refresh.

### LLM (optional)

| Item | Description |
|------|-------------|
| **Config file** | `data/llm_config.json`, edited via the **Model config** UI: multiple profiles, task binding, crawl-time summary/tag toggles, multithread preset, etc. |
| **Code** | `src/llm/` (`llm_config.py`, `article_tagging.py`, `model_client.py`, …); crawl integration in `api.py`. |

Legacy env-only setup (`QWEN35_27B_*`, …) is documented in **`README.legacy.md`** (section 4 table). The legacy file is mostly Chinese.

---

## Data & storage

| Path | Purpose |
|------|---------|
| `data/id_info.json` | WeChat session |
| `data/name2fakeid.json` | Subscribed accounts |
| `data/message_info.json` | Main article records (metadata, tags, summaries, …) |
| `data/message_detail_text.json` | Cached article body |
| `data/covers/` | Cover images |
| `data/deleted_article_ids.json` | Deletion blacklist |
| `data/operation_logs.jsonl` | Operation log |
| `data/llm_config.json` | LLM & task settings |

**Security:** These files often contain secrets—do not commit them to public repos; use `.gitignore` and team policy.

---

## Repository layout

```text
WeChatOA_Aggregation/
├── api.py                 # FastAPI: accounts, crawl, cache, auth, logs, LLM config APIs, …
├── start_all.sh           # Dev: start backend + frontend
├── pyproject.toml         # Python dependencies
├── data/                  # Runtime data (usually not in VCS)
├── src/
│   ├── crawler/           # WeChat HTTP / crawl
│   ├── llm/               # Config, tagging/summary, model client
│   └── utils/             # Data manager, helpers
├── frontend/              # Vue 3 app
├── scripts/               # Cron / ops examples
├── figures/               # README assets
├── README.md              # Chinese README
└── README.legacy.md       # Full historical doc (Chinese: TODO, MinHash experiments, long tree)
```

---

## Production build

```bash
cd frontend
npm run build
```

Output: `frontend/dist/`. You still need to wire **API + static hosting** (same origin or reverse proxy), **CORS**, and **persistent `data/`**—this repo does not prescribe one hosting pattern.

---

## Further reading & roadmap

- **`README.legacy.md`**: Original long-form README (mostly **Chinese**): feature tables, full `data/` tree, **TODO roadmap**, **MinHash experiment table**, more links.  
- Section structure here follows common open-source README patterns (e.g. [MiroFish](https://github.com/666ghj/MiroFish): overview → workflow → env table → quick start); content matches this repo only.

---

## Acknowledgements & references

- [wechat-article-exporter](https://github.com/jooooock/wechat-article-exporter)
- [WeChat_Article](https://github.com/1061700625/WeChat_Article)
