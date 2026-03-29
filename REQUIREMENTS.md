# CloudMcFly Virtual Company - Anforderungsprofil

## 1. Projektuebersicht

**Projekt:** CloudMcFly Agentic Company Architecture
**Auftraggeber:** Alex Ruetz (CEO CloudMcFly)
**Entwickler:** Claude Code (Senior Python Developer & AI Architect)
**Datum:** 2026-03-29
**Status:** Anforderungsphase

### Vision
CloudMcFly wird als virtuelles AI-Unternehmen aufgebaut. Ein Solo-Selbststaendiger
(Alex) fuehrt als CEO ein Team aus autonomen AI-Agents, die in einer
Unternehmenshierarchie organisiert sind. Die Agents arbeiten 24/7 auf einem
Hetzner Cloud VPS und kommunizieren mit dem CEO ueber Microsoft Teams.

---

## 2. Architektur - Die 4-Level-Hierarchie

```
+------------------------------------------------------------------+
|                    LEVEL 1: CEO (Human)                          |
|              Alex Ruetz via MS Teams                             |
|              contact@cloudmcfly.com                              |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                  LEVEL 2: CENTRAL ROUTER                         |
|    - Klassifiziert eingehende Anfragen                           |
|    - Stellt Rueckfragen an CEO bei unklaren Auftraegen           |
|    - Erstellt Aufgabenpakete                                     |
|    - Routet an 1..n Departments                                  |
|    - Wartet auf alle Departments bei Multi-Dept-Tasks             |
|    - Aggregiert finale Antwort fuer CEO                          |
+------------------------------------------------------------------+
          |          |          |          |          |          |
          v          v          v          v          v          v
+--------+ +--------+ +--------+ +--------+ +--------+ +--------+
|MARKET- | | SALES  | |CONSULT-| |DELIVER-| |AUTOMA- | |FINANCE |
|ING     | |        | |ING     | |Y       | |TION    | |& ADMIN |
|Head    | |Head    | |Head    | |Head    | |Head    | |Head    |
+--------+ +--------+ +--------+ +--------+ +--------+ +--------+
 |R|Y|G|B  |R|Y|G|B  |R|Y|G|B  |R|Y|G|B  |R|Y|G|B  |R|Y|G|B
```

### Level 1: CEO (Human-in-the-Loop)
- Einziger menschlicher Akteur
- Kommuniziert ausschliesslich ueber MS Teams
- Gibt strategische Richtung vor, trifft Entscheidungen, gibt Freigaben
- Beantwortet eskalierte Rueckfragen

### Level 2: Central Router
- KEIN Fach-Agent - reine Steuerungslogik
- Analysiert CEO-Input auf Vollstaendigkeit
- Stellt Rueckfragen an CEO bei fehlenden Informationen
- Klassifiziert: Task-Typ, Prioritaet, zustaendige(s) Department(s)
- Erstellt strukturierte Aufgabenpakete (JSON)
- **Multi-Department-Tasks: PARALLEL** - Alle betroffenen Departments
  erhalten ihre Aufgabenpakete gleichzeitig und arbeiten unabhaengig
- Wartet auf alle Departments (Fan-Out / Fan-In Pattern)
- Aggregiert und formatiert finale Antwort fuer CEO

### Level 3: Heads of Department (6 Stueck)
Jeder Head ist ein Mini-Orchestrator:
- Empfaengt Aufgabenpaket vom Router
- Darf Rueckfragen an Router stellen (Router beantwortet oder eskaliert an CEO)
- Uebersetzt Aufgabe in team-interne Prompts
- Koordiniert die 4 Farb-Agents
- Reviewt Ergebnisse, stellt ggf. Rueckfragen an Agents
- Max. 3 Iterationen, dann Entscheidung erzwingen oder eskalieren
- Liefert 1-2 finale Loesungsoptionen mit Pro/Contra/Kosten/Auswirkungen

**Departments:**
| # | Department        | Fokus                                           |
|---|-------------------|-------------------------------------------------|
| 1 | Marketing         | Content, LinkedIn, Positionierung, Kampagnen     |
| 2 | Sales             | Lead-Qualifizierung, Outreach, Angebote          |
| 3 | Consulting        | Konzepte, AI-Strategie, Kundenloesungen          |
| 4 | Delivery          | Projektsteuerung, Umsetzung, QA, Meilensteine   |
| 5 | Automation        | n8n, Integrationen, interne Tools, Agent-Building|
| 6 | Finance & Admin   | Rechnungen, Vertraege, Dokumente, Backoffice     |

### Level 4: 4 Farb-Agents pro Department (24 Stueck gesamt)
Basierend auf der DISC/Farbenlehre der Persoenlichkeiten:

| Farbe | Rolle            | Fokus                                    | Stil                          |
|-------|------------------|------------------------------------------|-------------------------------|
| Rot   | The Driver       | Execution, ROI, Meilensteine, Machbarkeit| Direkt, max. 3 Bulletpoints   |
| Gelb  | The Visionary    | Innovation, Skalierung, Out-of-the-Box   | Inspirierend, Wildcard-Ideen  |
| Gruen | The Harmonizer   | UX, Change Mgmt, Stabilitaet, Ethik      | Empathisch, nutzerorientiert  |
| Blau  | The Analyst      | Daten, Logik, Code-Qualitaet, Compliance | Faktenbasiert, kritisch       |

**Workflow innerhalb eines Departments:**
```
Aufgabe vom Router
       |
       v
  Head of Dept briefet Team
       |
       v
  Gelb: Ideation (kreative Ansaetze)
       |
       v
  Blau: Kritische Analyse (Machbarkeit, Risiken)
       |
       v
  Gruen: UX/Change-Management-Bewertung
       |
       v
  Rot: Execution-Plan (Meilensteine, Scope)
       |
       v
  Head: Review + ggf. Rueckfragen (max. 3 Iterationen)
       |
       v
  Head: 1-2 finale Optionen mit Pro/Contra
       |
       v
  Zurueck an Router
```

---

## 3. Tech-Stack

| Komponente         | Technologie                                    |
|--------------------|------------------------------------------------|
| Sprache            | Python 3.11+                                   |
| Agent-Framework    | LangGraph (State-Management, Zyklen, Routing)  |
| LLM-Anbindung      | LangChain + Anthropic Claude API               |
| API-Layer          | FastAPI (headless, kein Frontend)               |
| Datenbank          | SQLite (Dev) / PostgreSQL (Prod) fuer Task-State|
| CRM/Dashboard      | Airtable (bestehend, wird weiter genutzt)       |
| Dateisystem        | Docker Volume fuer Dokumente/Drafts             |
| Containerisierung  | Docker + docker-compose                         |
| Hosting            | Hetzner Cloud VPS (Ubuntu Linux)                |
| CEO-Kommunikation  | MS Teams via Microsoft Graph API                |
| Webhook-Bridge     | n8n (nur einfache Trigger, KEINE AI-Logik)      |
| LLM-Modell         | Claude API (primaer)                            |

---

## 4. Kommunikationsfluss

```
MS Teams (CEO)
     |
     v
n8n (Webhook Listener)  <-- Einfacher HTTP-Trigger
     |
     v
FastAPI: POST /api/v1/task  <-- Eingangs-Endpoint
     |
     v
LangGraph State Machine (Router -> Heads -> Agents)
     |
     v
FastAPI: Ergebnis als JSON
     |
     v
n8n (HTTP Request an MS Teams)  <-- Einfacher Rueckkanal
     |
     v
MS Teams (CEO erhaelt Antwort)
```

### Rueckfrage-Mechanismus
```
Agent/Head hat Rueckfrage
       |
       v
  Eskalation im Graph: Agent -> Head -> Router -> CEO
       |
       v
  FastAPI -> n8n -> MS Teams: "Rueckfrage: ..."
       |
       v
  CEO antwortet in MS Teams
       |
       v
  n8n -> FastAPI: POST /api/v1/task/{task_id}/reply
       |
       v
  LangGraph setzt Verarbeitung fort
```

---

## 5. Datenmodell (State)

```python
class TaskState(BaseModel):
    task_id: str                    # UUID
    source: str                     # "ceo", "router", "head_marketing", etc.
    original_request: str           # CEO's Originaltext
    task_type: str                  # "strategy", "content", "automation", etc.
    priority: str                   # "critical", "high", "normal", "low"
    departments: list[str]          # ["marketing", "consulting"]
    status: str                     # "pending", "routing", "in_progress",
                                    # "awaiting_reply", "completed", "escalated"

    # Router-Output
    sub_tasks: list[SubTask]        # Aufgabenpakete pro Department

    # Department-Outputs
    department_results: dict        # {"marketing": DeptResult, ...}

    # Rueckfragen
    questions: list[Question]       # Offene Rueckfragen

    # Finale Antwort
    final_response: str | None      # Aggregierte Antwort fuer CEO
    options: list[SolutionOption]   # 1-2 Loesungsoptionen mit Pro/Contra

    # Meta
    created_at: datetime
    updated_at: datetime
    iteration_count: int            # Max 3 pro Department
```

---

## 6. Projektstruktur (geplant)

```
cloudmcfly-company/
|-- main.py                    # FastAPI App + Endpoints
|-- config.py                  # Settings, API-Keys, Department-Config
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
|-- .env.example
|
|-- core/
|   |-- graph.py               # LangGraph State Machine (Hauptgraph)
|   |-- state.py               # Pydantic State-Modelle
|   |-- router.py              # Level 2: Central Router Logik
|   |-- department.py          # Level 3: Head of Department (generisch)
|   |-- agent.py               # Level 4: Farb-Agent (generisch)
|
|-- departments/
|   |-- marketing.py           # Dept-spezifische Prompts + Config
|   |-- sales.py
|   |-- consulting.py
|   |-- delivery.py
|   |-- automation.py
|   |-- finance.py
|
|-- personas/
|   |-- red.py                 # System-Prompts fuer roten Agent
|   |-- yellow.py
|   |-- green.py
|   |-- blue.py
|
|-- integrations/
|   |-- teams.py               # MS Teams / Graph API Client
|   |-- airtable.py            # Airtable CRM Client
|   |-- n8n_bridge.py          # n8n Webhook Handler
|
|-- db/
|   |-- models.py              # SQLAlchemy/DB Modelle
|   |-- repository.py          # CRUD Operationen
|
|-- data/                      # Docker Volume (persistent)
|   |-- ceo_desk/              # Fertige Reports fuer CEO
|   |-- router_inbox/          # Eingehende Task-Payloads
|   |-- departments/
|       |-- marketing/
|       |-- sales/
|       |-- consulting/
|       |-- delivery/
|       |-- automation/
|       |-- finance/
|
|-- tests/
|   |-- test_router.py
|   |-- test_departments.py
|   |-- test_agents.py
```

---

## 7. Integration bestehender Agents

Die zwei vorhandenen lokalen Agents werden integriert:

### cloudmcfly-agent (LinkedIn/CRM Agent)
- **Bestehende Module:** browser/linkedin.py, crm/airtable_client.py,
  brain/claude_client.py, core/orchestrator.py
- **Ziel-Department:** Marketing (LinkedIn-Posting) + Sales (Lead-Scoring, Outreach)
- **Migration:** Core-Logik wird als Skills in die neuen Farb-Agents eingebettet

### cloudmcfly-content-agent (Content Agent)
- **Bestehende Module:** core/researcher.py, core/writer.py,
  core/quality_checker.py, core/image_generator.py
- **Ziel-Department:** Marketing (Content-Erstellung)
- **Migration:** Researcher -> Gelber Agent, Writer -> Gruener Agent,
  Quality Checker -> Blauer Agent

---

## 8. API Endpoints (FastAPI)

| Method | Endpoint                        | Beschreibung                      |
|--------|---------------------------------|-----------------------------------|
| POST   | /api/v1/task                    | Neuen Task vom CEO/n8n einreichen |
| POST   | /api/v1/task/{id}/reply         | CEO-Antwort auf Rueckfrage        |
| GET    | /api/v1/task/{id}               | Task-Status abfragen              |
| GET    | /api/v1/tasks                   | Alle aktiven Tasks auflisten      |
| GET    | /api/v1/departments             | Department-Status                 |
| POST   | /api/v1/webhook/teams           | MS Teams Webhook Receiver         |
| GET    | /health                         | Health-Check                      |

---

## 9. Nicht-funktionale Anforderungen

- **Verfuegbarkeit:** 24/7 Betrieb auf Hetzner Cloud
- **Asynchronitaet:** Alle LLM-Calls muessen async sein (keine Blockierung von FastAPI)
- **Fehlertoleranz:** Graceful Handling bei LLM-API-Timeouts/Ausfaellen
- **Logging:** Strukturiertes Logging (JSON) fuer Debugging
- **Skalierbarkeit:** Neue Departments ohne Aenderung der Kernarchitektur hinzufuegbar
- **DSGVO:** Hetzner-Server in Deutschland, keine Daten an Dritte ausser Claude API
- **Wartbarkeit:** Einfache Ordnerstruktur, kein Visual-Spaghetti-Code (n8n nur als Bridge)

---

## 10. Hetzner Cloud Setup

**Empfohlener Server:** CX22 (2 vCPU, 4 GB RAM) oder CX32 (4 vCPU, 8 GB RAM)
**OS:** Ubuntu 24.04 LTS
**Kosten:** ca. 4-7 EUR/Monat
**Setup:** Docker + docker-compose, Persistent Volumes
**Netzwerk:** Firewall nur Port 443 (HTTPS) + SSH

Alex kuemmert sich parallel um das Hetzner Cloud Setup.

---

## 11. Entwicklungsreihenfolge (Phasen)

### Phase 1: Foundation
- [ ] Projektstruktur + Docker Setup
- [ ] State-Modelle (Pydantic)
- [ ] FastAPI Grundgeruest mit Health-Check
- [ ] LangGraph Grundstruktur (leerer Graph mit Nodes)

### Phase 2: Core Logic
- [ ] Router-Agent (Klassifikation, Routing, Rueckfrage-Logik)
- [ ] Head-of-Department Agent (generisch, konfigurierbar)
- [ ] 4 Farb-Agents (generische Persona-Engine)
- [ ] Conflict Resolution (max. 3 Iterationen)

### Phase 3: Departments
- [ ] Department-spezifische Prompts und Konfiguration
- [ ] Integration bestehender Agent-Logik (cloudmcfly-agent, content-agent)

### Phase 4: Integration
- [ ] MS Teams / Graph API Anbindung
- [ ] n8n Webhook Bridge
- [ ] Airtable CRM Sync
- [ ] Rueckfrage-Mechanismus (CEO -> Teams -> FastAPI -> Graph)

### Phase 5: Deployment
- [ ] Docker-Image optimieren
- [ ] Hetzner Cloud Deployment
- [ ] Monitoring + Logging
- [ ] End-to-End Test (CEO sendet Task via Teams, erhaelt Ergebnis)
