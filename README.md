# Campaign Builder — Web App

FastAPI web app that converts 4 agency Excel inputs (Media Brief, Media Plan, Audience Matrix, Trafficking Sheet) into platform-specific bulk upload files for **TTD**, **DV360**, and **Amazon DSP**.

---

## Platform Support

| Platform | Status | Output |
|---|---|---|
| **The Trade Desk (TTD)** | ✅ Full | Excel bulk upload sheet (6 tabs) |
| **DV360** | ✅ Full | SDF v9.2 Insertion Orders CSV |
| **Amazon DSP** | ✅ Full | Multi-tab Excel bulksheet |

---

## File & Folder Map

```
ttd-campaign-builder/
│
│  ── ENTRY POINT ──────────────────────────────────────────────────────────
├── app.py                        [TTD + DV360]   FastAPI web server
│                                                 Routes: /generate (TTD),
│                                                 /generate/dv360, /export,
│                                                 /export/dv360, /filter, /knowledge
│
│  ── MAPPERS (rule-based, no AI required) ──────────────────────────────────
├── mapper.py                     [TTD ONLY]      Parses all 4 inputs → TTD bulk
│                                                 upload format. Campaign Sets,
│                                                 Campaigns, Ad Groups, Budget Flights.
│
├── dv360_mapper.py               [DV360 ONLY]    Parses all 4 inputs → DV360 SDF v9.2
│                                                 Insertion Orders CSV.
│
├── amazon_mapper.py              [AMAZON DSP]    Parses all 4 inputs → Amazon DSP
│                                                 bulksheet (Orders + 5 line-item
│                                                 tabs + Creative Associations).
│
│  ── DEFAULTS / CONFIG ──────────────────────────────────────────────────────
├── defaults.json                 [TTD ONLY]      Business defaults by channel + LOB
│                                                 (Goal Type, Base Bid, Pacing, etc.)
│
├── platform_defaults.json        [TTD ONLY]      TTD technical field defaults
│                                                 (applied as base layer to all rows)
│
├── amazon_defaults.json          [AMAZON DSP]    Amazon business defaults by channel + LOB
│                                                 (Goal KPI, Supply Source, Bid amounts)
│
├── amazon_platform_defaults.json [AMAZON DSP]    Amazon technical field defaults
│                                                 (applied as base layer to all rows)
│
│  ── REFERENCE ──────────────────────────────────────────────────────────────
├── MAPPING_REFERENCE.md          [TTD ONLY]      Human-readable field mapping guide.
│                                                 Served at /mapping in the web app.
│
├── requirements.txt              [ALL PLATFORMS] Python dependencies
│
│  ── UI TEMPLATES ──────────────────────────────────────────────────────────
├── templates/
│   ├── index.html                [TTD + DV360]   Main upload UI — file inputs,
│   │                                             generate + export buttons
│   ├── filter.html               [TTD ONLY]      Input filter UI — strips non-TTD
│   │                                             rows before processing
│   └── knowledge.html            [TTD ONLY]      Knowledge base viewer — shows
│                                                 loaded defaults and feedback rules
│
│  ── TTD INPUT FILTER ───────────────────────────────────────────────────────
└── ttd_filter/
    ├── __init__.py               [TTD ONLY]      Package init
    └── filter.py                 [TTD ONLY]      Strips non-TTD rows from all 4 input
                                                  Excel files before mapping. Outputs
                                                  both cleaned Excel + filtered JSON.
```

---

## How It Works

```
User uploads 4 Excel files
        │
        ▼
[Optional] TTD Filter (/filter)
  → Strips rows where DSP ≠ TTD
  → Downloads cleaned Excel files
        │
        ▼
Generate endpoint (/generate or /generate/dv360)
  → Reads Excel → dict via openpyxl
  → Runs platform mapper (TTD: Claude AI + rule-based; DV360: rule-based)
  → Returns JSON preview of bulk upload data
        │
        ▼
User reviews, optionally revises (/revise)
  → Claude re-maps with correction
  → Correction saved as a feedback rule for future campaigns
        │
        ▼
Export (/export or /export/dv360)
  → Writes mapped data into the TTD Excel template or DV360 CSV
  → Browser downloads the file
```

---

## Defaults Priority (TTD)

Applied most-specific-wins:

1. `platform_defaults.json` — TTD technical fields (base layer)
2. `global` in `defaults.json` — applies to everything
3. `by_channel` — applies when channel is known (CTV, OLV, Display, etc.)
4. `by_lob` — applies when Line of Business is known
5. `by_lob_and_channel` — most specific, overrides all others

---

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload
# Open http://localhost:8000
```

---

## Related Repo

`agentic-campaign-builder/` — future-state multi-agent version of this tool that calls DSP APIs directly instead of producing bulk upload files.
