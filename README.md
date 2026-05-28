# Campaign Builder — Web App

FastAPI web app that converts 4 agency input files (Media Brief, Media Plan, Audience Matrix, Trafficking Sheet) into platform-specific bulk upload files for **The Trade Desk**, **DV360**, and **Amazon DSP**.

---

## What It Does

Upload your 4 standard Excel inputs → get back a ready-to-upload bulk sheet for each DSP.

| Platform | Output file | Route |
|---|---|---|
| The Trade Desk (TTD) | Excel bulk upload (6 tabs) | `/generate` + `/export` |
| Google DV360 | SDF v9.2 Insertion Orders CSV | `/generate/dv360` + `/export/dv360` |
| Amazon DSP | Excel bulksheet (6 tabs) | `/generate/amazon` + `/export/amazon` |

TTD mapping can run in two modes — AI (Claude, handles ambiguous inputs) or rule-based (faster, no API cost, fully auditable). DV360 and Amazon always use the rule-based mapper.

---

## File & Folder Map

```
ttd-campaign-builder/
│
│  ── WEB APP ────────────────────────────────────────────────────────────────
├── app.py                    FastAPI server. All routes live here.
│                             Imports mappers from campaign_builder/,
│                             reads templates from templates/.
│
│  ── MAPPER PACKAGE ─────────────────────────────────────────────────────────
├── campaign_builder/         pip-installable Python package.
│   │                         See campaign_builder/README.md for full detail.
│   │
│   ├── shared_utils.py       Shared parser functions used by all 3 mappers:
│   │                         parse_media_brief, parse_media_plan,
│   │                         parse_trafficking_sheet, extract_lob,
│   │                         build_campaign_name, normalise_channel,
│   │                         parse_flight_dates, apply_platform_defaults,
│   │                         get_default, excel_to_dict.
│   │
│   ├── ttd_mapper.py         [TTD ONLY]     Maps inputs → TTD bulk upload format.
│   ├── ttd_defaults.json     [TTD ONLY]     Business defaults by channel + LOB.
│   ├── ttd_platform_defaults.json           TTD technical field defaults.
│   │                         [TTD ONLY]     Applied as base layer to all rows.
│   │
│   ├── dv360_mapper.py       [DV360 ONLY]   Maps inputs → DV360 SDF v9.2
│   │                                        Insertion Orders CSV.
│   │
│   ├── amazon_mapper.py      [AMAZON DSP]   Maps inputs → Amazon DSP bulksheet.
│   ├── amazon_defaults.json  [AMAZON DSP]   Business defaults by media type + LOB.
│   └── amazon_platform_defaults.json        Amazon technical field defaults.
│                             [AMAZON DSP]   Applied as base layer to all rows.
│
│  ── INPUT FILTER ───────────────────────────────────────────────────────────
├── ttd_filter/
│   └── filter.py             [TTD ONLY]     Pre-processing step. Strips non-TTD
│                                            rows from all 4 input files before
│                                            mapping. Downloads cleaned Excel files.
│                                            Route: /filter
│
│  ── UI TEMPLATES ───────────────────────────────────────────────────────────
├── templates/
│   ├── index.html            Main upload UI — file inputs, platform tabs,
│   │                         generate + export buttons.
│   ├── filter.html           TTD input filter UI.
│   └── knowledge.html        Displays loaded defaults and saved feedback rules.
│                             Route: /knowledge
│
│  ── REFERENCE & CONFIG ─────────────────────────────────────────────────────
├── MAPPING_REFERENCE.md      [TTD ONLY]     Field-by-field mapping guide.
│                                            Rendered in the app at /mapping.
├── requirements.txt          Python dependencies.
└── pyproject.toml            Package config — makes campaign_builder/
                              pip-installable as campaign-builder.
```

---

## Routes

| Method | Route | Platform | What it does |
|---|---|---|---|
| GET | `/` | All | Main upload UI |
| POST | `/generate?mode=ai` | TTD | Map inputs → TTD data using Claude AI |
| POST | `/generate?mode=rules` | TTD | Map inputs → TTD data using rule-based mapper |
| POST | `/revise` | TTD | Re-run Claude with a correction; saves rule to feedback |
| POST | `/export` | TTD | Write TTD data into Excel bulk upload template |
| POST | `/generate/dv360` | DV360 | Map inputs → DV360 Insertion Orders |
| POST | `/export/dv360` | DV360 | Write DV360 data as SDF v9.2 CSV |
| POST | `/generate/amazon` | Amazon DSP | Map inputs → Amazon DSP bulksheet data |
| POST | `/export/amazon` | Amazon DSP | Write Amazon data as multi-tab Excel |
| GET | `/filter` | TTD | Input filter UI |
| POST | `/filter/run` | TTD | Strip non-TTD rows from input files |
| GET | `/knowledge` | TTD | View loaded defaults + saved feedback rules |
| GET | `/mapping` | TTD | Render MAPPING_REFERENCE.md in browser |

---

## How It Works

```
You upload 4 Excel files:
  Media Brief · Media Plan · Audience Matrix · Trafficking Sheet
          │
          ▼
  [Optional] /filter
  Strips rows where DSP ≠ TTD.
  Download the cleaned files before uploading to /generate.
          │
          ▼
  /generate  (or /generate/dv360 or /generate/amazon)
  Reads Excel → structured dict → runs the platform mapper.
  TTD: mode=ai uses Claude; mode=rules uses rule-based mapper.
  Returns a JSON preview of the mapped data.
          │
          ▼
  [TTD only] /revise
  You flag an issue in the preview → Claude re-maps with the correction.
  The correction is saved as a feedback rule and applied to future campaigns.
          │
          ▼
  /export  (or /export/dv360 or /export/amazon)
  Writes the mapped data into the correct file format.
  Browser downloads the file — ready to upload into the DSP.
```

---

## Defaults System (TTD + Amazon)

Defaults fill in fields that don't come from the source documents (bid amounts, goal types, pacing, etc.). They are applied in most-specific-wins order:

```
ttd_platform_defaults.json    ← base layer (TTD technical fields)
       ↓
global                        ← applies to everything
       ↓
by_channel                    ← applies when channel is known (CTV, OLV, Display…)
       ↓
by_lob                        ← applies when Line of Business is known
       ↓
by_lob_and_channel            ← most specific, overrides all others
```

Edit `campaign_builder/ttd_defaults.json` to change business defaults. Edit `campaign_builder/ttd_platform_defaults.json` to change TTD account-level technical fields. Amazon follows the same pattern with `amazon_defaults.json` and `amazon_platform_defaults.json`.

---

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload
# Open http://localhost:8000
```

Requires a TTD bulk upload template at `~/Downloads/TTD BULKSHEET.xlsx` for the `/export` route. The template must match the sheet names in `app.py`.

---

## Related Repo

[`agentic-campaign-builder`](https://github.com/intothecheynet/Agentic-Campaign-Builder---Future-State) — future-state version. Uses this repo's `campaign_builder` package as a dependency and builds campaigns by calling DSP APIs directly instead of producing download files.
