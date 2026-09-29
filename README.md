# 🥨 Oktoberfest ("Wiesn") Insider & Decision Guide

An intelligent Bavarian companion powered by Google Cloud Agent Platform (ADK) that helps visitors make real-time decisions at Munich's Oktoberfest: whether to head to the festival grounds right now, which beer tent has open benches based on livecam occupancy and capacity, how to navigate the festival, and critically, **what NOT to do** to avoid fines or ejection.

---

## 🌟 What This Agent Does

- **Real-Time Headcount & Capacity Estimation**: Calculates live occupant counts, remaining unreserved benches, and door admission likelihood across major tents using festival geometry and livecam readings.
- **Definitive Go / No-Go Verdicts**: Evaluates live crowd conditions, group sizes, vibe preferences (party, traditional/locals, family), and reservation status to guide entrance strategy.
- **Interactive Tents & Grounds Map**: A dedicated, collapsible frontend sidebar featuring an authentic layout of Theresienwiese and instant hover cards for all major beer tents (capacities, breweries, Maß prices, and insider tips).
- **Webcam & Ground Vision**: Fetches and delivers livecam captures from key festival landmarks (Bavaria statue, St. Paul church, Löwenbräu tower, Paulaner, Armbrustschützen) stored in Google Cloud Storage.
- **Interactive Rich UI (A2UI)**: Returns structured visual cards (status badges, capacity breakdowns, photos) rendered directly inside the chat interface.
- **Cross-Session Long-Term Memory**: Remembers visitor dietary constraints, favorite tents, and past festival experiences across conversations.
- **Rules & Etiquette Guide**: Delivers vital safety advice (strict 3-liter bag limit, bench-only dancing rules, Maßkrug theft fines, and the 16:00–18:00 reservation changeover door lockouts).

---

## ☁️ Google Cloud Services & Tools Wired Up

Based directly on the code in `simple-agent/app/`:

| Capability / Service | Implementation in Code | Description |
|---|---|---|
| **Vertex AI Memory Bank** | `PreloadMemoryTool`, `generate_memories_callback` (`agent.py`) | Cross-session memory that persists user preferences, party sizes, and tent favorites. |
| **Google Cloud Firestore** | `firestore_backend.py` | Stores structured tent specifications (`oktoberfest_tents`) and crowd reports (`wiesn_crowd_reports`). |
| **Google Cloud Storage** | `screenshot_tool.py` | Public bucket storing and serving livecam captures and visual snapshot cards. |
| **A2UI (Basic Catalog v0.8)** | `a2ui_utils.py`, `a2ui_schema_manager` (`agent.py`) | Agent-to-User Interface protocol returning dynamic UI cards for chat clients. |
| **Google Maps Platform** | `maps_tools.py` | Geocoding API (`geocode_address`) and Places API New (`find_nearby_places`) for navigation. |
| **Livecam & Barometer Engine** | `oktoberfest_data.py` | Integrates with Wiesn.tv livecams and official Oktoberfest barometer metrics. |
| **Image Generation (Imagen)** | *Planned, not yet implemented* | Real-time crowd cameras and Cloud Storage are used; AI image generation is slated for future enhancements. |

---

## 🛠️ Project Structure

```
.
├── simple-agent/                # Core ADK Agent Engine project
│   ├── app/
│   │   ├── agent.py             # Agent definition, system instructions & tool registration
│   │   ├── a2ui_utils.py        # A2UI response formatting callback
│   │   ├── firestore_backend.py # Firestore client and collection operations
│   │   ├── maps_tools.py        # Google Maps Geocoding and Places tools
│   │   ├── oktoberfest_data.py  # Headcount algorithms, livecams & barometer
│   │   └── screenshot_tool.py   # Cloud Storage webcam capture and analysis
│   ├── agents-cli-manifest.yaml # Agent Platform deployment configuration
│   └── pyproject.toml           # Agent dependencies
├── frontend/                    # Web frontend & FastAPI A2A proxy
│   ├── main.py                  # Proxy connecting browser to Agent over A2A
│   ├── static/
│   │   └── index.html           # ChatGPT-style UI with foldable map sidebar & A2UI renderer
│   └── Dockerfile               # Container build for Cloud Run
├── scripts/
│   └── seed_firestore.py        # Database seed script for Oktoberfest tents
└── project_brief.md             # Project design and domain specification
```

---

## 🚀 Running Locally

### 1. Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud CLI (`gcloud`) authenticated to your GCP project:
  ```bash
  gcloud auth application-default login
  ```

### 2. Set Up the Agent
```bash
cd simple-agent
uv sync
```

Run the agent in development mode:
```bash
uv run agents-cli run
```

### 3. Run the Frontend
In a separate terminal:
```bash
cd frontend
uv sync
uv run python main.py
```

The frontend will be accessible locally on your configured port (default: port 8080 or port 80).

---

## 📄 License
Apache-2.0
