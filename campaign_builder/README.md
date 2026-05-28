# campaign_builder — Python Package

The installable core of this repo. Contains all three platform mappers and their config files. Each platform follows the same file pattern: one mapper + one business-defaults JSON + one platform-defaults JSON.

---

## File Map

```
campaign_builder/
│
│  ── SHARED (imported by all three platform mappers) ───────────────────────
├── shared_utils.py               Parser functions, defaults helpers, date
│                                 formatting, and excel_to_dict — everything
│                                 that was previously copy-pasted across all
│                                 three mapper files.
│
│  ── THE TRADE DESK (TTD) ──────────────────────────────────────────────────
├── ttd_mapper.py                 Maps all 4 input files → TTD bulk upload
│                                 format (CampaignSets, Campaigns, Ad Groups,
│                                 Budget Flights, Fees tabs).
│
├── ttd_defaults.json             TTD business defaults by channel + LOB.
│                                 Controls: Goal Type, Base Bid, Max Bid,
│                                 Marketplace, Objective, Pacing Mode, etc.
│
├── ttd_platform_defaults.json    TTD technical field defaults.
│                                 Applied as the base layer under all other
│                                 defaults. Contains TTD account-level fields
│                                 that never appear in source documents.
│
│  ── GOOGLE DV360 ──────────────────────────────────────────────────────────
├── dv360_mapper.py               Maps all 4 input files → DV360 SDF v9.2
│                                 Insertion Orders CSV. Field values not in
│                                 source documents are left blank for manual
│                                 entry post-export.
│
│   (No separate config files — DV360 has fewer configurable defaults and
│    they are hardcoded in dv360_mapper.py. Future: add dv360_defaults.json
│    if per-channel or per-LOB DV360 overrides are needed.)
│
│  ── AMAZON DSP ─────────────────────────────────────────────────────────────
├── amazon_mapper.py              Maps all 4 input files → Amazon DSP
│                                 bulksheet format across 6 tabs:
│                                 ORDERS, DISPLAY LINE ITEMS, VIDEO LINE ITEMS,
│                                 AUDIO LINE ITEMS, PODCAST LINE ITEMS,
│                                 CREATIVE ASSOCIATIONS.
│
├── amazon_defaults.json          Amazon business defaults by media type + LOB.
│                                 Controls: Goal and Goal KPI, Base Supply Bid,
│                                 Maximum Average CPM, Product Categories,
│                                 Supply Source, Device Type, etc.
│
├── amazon_platform_defaults.json Amazon technical field defaults.
│                                 Applied as the base layer to every line-item
│                                 tab. Contains Amazon account-level fields
│                                 that never appear in source documents.
│
│  ── PACKAGE ────────────────────────────────────────────────────────────────
└── __init__.py                   Exports: map_to_ttd, map_to_dv360,
                                  map_to_amazon, excel_to_dict
```

---

## Why each platform has its own config files

| Platform | Mapper | Business Defaults | Platform Defaults |
|---|---|---|---|
| TTD | `ttd_mapper.py` | `ttd_defaults.json` | `ttd_platform_defaults.json` |
| DV360 | `dv360_mapper.py` | *(hardcoded — see note above)* | *(hardcoded)* |
| Amazon DSP | `amazon_mapper.py` | `amazon_defaults.json` | `amazon_platform_defaults.json` |

**Business defaults** (`*_defaults.json`) — values that vary by channel and line-of-business. You tune these to match your account's standard settings (e.g., what Goal Type you use for CTV, what Base Bid you use for Display). These change as strategy evolves.

**Platform defaults** (`*_platform_defaults.json`) — technical fields that are constant for your account but don't come from source documents (e.g., specific fee structures, measurement vendor settings). These rarely change.

---

## Shared functions (shared_utils.py)

| Function | What it does |
|---|---|
| `parse_media_brief()` | Reads Media Brief col A=label, col B=value → flat dict |
| `parse_media_plan(dsp_names)` | Reads Media Plan, filters to rows where DSP column matches the given platform |
| `parse_trafficking_sheet()` | Reads Trafficking Sheet rows that have a Campaign value |
| `extract_lob()` | Pulls Line of Business from Media Brief or Trafficking Sheet |
| `build_campaign_name()` | First Campaign from Trafficking, fallback to LOB + Product from Brief |
| `apply_platform_defaults()` | Merges platform JSON defaults into a row dict (row values always win) |
| `get_default()` | Most-specific-wins lookup: by_lob_and_channel > by_channel > by_lob > global |
| `normalise_channel()` | Maps raw channel strings to canonical names (e.g. "Video CTV" → "CTV") |
| `parse_flight_dates(output_format)` | Parses "M/D/YYYY - M/D/YYYY" → platform-specific date format |
| `excel_to_dict()` | Converts Excel bytes → `{sheet: {headers, rows}}` dict |

`parse_flight_dates` output per platform:
- `"ttd"` → `"YYYY-MM-DD 00:00:00"`
- `"dv360"` → `"MM/DD/YYYY"`
- `"amazon"` → `"MM-DD-YYYY-00-01"` (start) / `"MM-DD-YYYY-23-59"` (end)

---

## Installing

```bash
# From GitHub (use this in requirements.txt)
pip install campaign-builder @ git+https://github.com/intothecheynet/ttd-campaign-builder.git

# Editable local install (for development)
pip install -e /path/to/ttd-campaign-builder
```
