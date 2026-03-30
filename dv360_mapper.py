"""
Rule-based DV360 Insertion Order mapper.
Maps 4 source input files to DV360 SDF v9.2 Insertion Order CSV format.
Only fields derivable from source documents are populated.
All other fields are left blank for manual entry post-export.
"""

import os
from datetime import datetime

# ── DSP filter ────────────────────────────────────────────────────────────────
DV360_DSP_NAMES = {"dv360"}

# ── Channel → DV360 Io Subtype ────────────────────────────────────────────────
# CTV uses "Regular Over The Top"; everything else uses "Default"
CTV_CHANNELS = {"video ctv", "ctv", "connected tv", "streaming tv"}

# ── Channel normalisation (shared with TTD mapper) ────────────────────────────
CHANNEL_MAP = {
    "video ctv":             "CTV",
    "ctv":                   "CTV",
    "connected tv":          "CTV",
    "streaming tv":          "CTV",
    "connected home":        "Audio",
    "video olv":             "OLV",
    "olv":                   "OLV",
    "online video":          "OLV",
    "pre-roll":              "OLV",
    "display":               "Display",
    "banner":                "Display",
    "native":                "Native",
    "audio streaming audio": "Audio",
    "streaming audio":       "Audio",
    "audio podcasts":        "Audio",
    "audio":                 "Audio",
    "connected car":         "Audio",
    "dooh":                  "DOOH",
    "out of home":           "DOOH",
    "digital ooh":           "DOOH",
}

# ── SDF v9.2 IO column order ──────────────────────────────────────────────────
# Deprecated targeting columns are included in the header but left blank.
DV360_IO_COLUMNS = [
    "Io ID",
    "Campaign Id",
    "Name",
    "Timestamp",
    "Status",
    "Io Type",
    "Io Subtype",
    "Io Objective",
    "Fees",
    "Integration",
    "Details",
    "Pacing",
    "Pacing Rate",
    "Pacing Amount",
    "Frequency Enabled",
    "Frequency Exposures",
    "Frequency Period",
    "Frequency Amount",
    "Kpi Type",
    "Kpi Value",
    "Kpi Algorithm Id",
    "Measure DAR",
    "Measure DAR Channel",
    "Budget Type",
    "Budget Segments",
    "Auto Budget Allocation",
    "Geography Targeting - Include",
    "Geography Targeting - Exclude",
    "Proximity Targeting",
    "Proximity Location List Targeting",
    "Language Targeting - Include",
    "Language Targeting - Exclude",
    "Device Targeting - Include",
    "Device Targeting - Exclude",
    "Browser Targeting - Include",
    "Browser Targeting - Exclude",
    "Digital Content Labels - Exclude",
    "Brand Safety Sensitivity Setting",
    "Brand Safety Custom Settings",
    "Third Party Verification Services",
    "Third Party Verification Labels",
    "Channel Targeting - Include",
    "Channel Targeting - Exclude",
    "Site Targeting - Include",
    "Site Targeting - Exclude",
    "App Targeting - Include",
    "App Targeting - Exclude",
    "App Collection Targeting - Include",
    "App Collection Targeting - Exclude",
    "Category Targeting - Include",
    "Category Targeting - Exclude",
    "Content Genre Targeting - Include",
    "Content Genre Targeting - Exclude",
    "Keyword Targeting - Include",
    "Keyword Targeting - Exclude",
    "Audience Targeting - Include",
    "Audience Targeting - Exclude",
    "Affinity & In Market Targeting - Include",
    "Affinity & In Market Targeting - Exclude",
    "Custom List Targeting",
    "Inventory Source Targeting - Authorized Seller Options",
    "Inventory Source Targeting - Include",
    "Inventory Source Targeting - Exclude",
    "Inventory Source Targeting - Target New Exchanges",
    "Daypart Targeting",
    "Daypart Targeting Time Zone",
    "Environment Targeting",
    "Viewability Omid Targeting Enabled",
    "Viewability Targeting Active View",
    "Position Targeting - Display on Screen",
    "Position Targeting - Video on Screen",
    "Position Targeting - Display Position in Content",
    "Position Targeting - Video Position in Content",
    "Position Targeting - Audio Position in Content",
    "Video Player Size Targeting",
    "Content Duration Targeting",
    "Content Stream Type Targeting",
    "Audio Content Type Targeting",
    "Demographic Targeting Gender",
    "Demographic Targeting Age",
    "Demographic Targeting Household Income",
    "Demographic Targeting Parental Status",
    "Connection Speed Targeting",
    "Carrier Targeting - Include",
    "Carrier Targeting - Exclude",
    "Insertion Order Optimization",
    "Bid Strategy Unit",
    "Bid Strategy Do Not Exceed",
    "Apply Floor Price for Deals",
    "Algorithm ID",
]


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_media_brief(sheet_data: dict) -> dict:
    """Media Brief: col A = label, col B = value. Returns flat dict."""
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    brief = {}
    for row in rows:
        values = list(row.values())
        if len(values) >= 2:
            label = str(values[0]).strip()
            value = values[1]
            if value is not None:
                brief[label] = value
    return brief


def parse_media_plan(sheet_data: dict) -> list:
    """
    Media Plan: row 0 of rows[] = real column headers.
    Returns only rows where DSP matches a DV360 alias.
    """
    raw_rows = sheet_data.get("Sheet1", {}).get("rows", [])
    if len(raw_rows) < 2:
        return []

    header_row = raw_rows[0]
    headers = list(header_row.values())

    lines = []
    for row in raw_rows[1:]:
        vals = list(row.values())
        record = dict(zip(headers, vals))
        dsp = str(record.get("DSP", "")).strip().lower()
        if dsp in DV360_DSP_NAMES:
            lines.append(record)
    return lines


def parse_trafficking_sheet(sheet_data: dict) -> list:
    """Returns all rows from the Trafficking Sheet with a Campaign value."""
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    return [r for r in rows if r.get("Campaign")]


# ── Field helpers ─────────────────────────────────────────────────────────────

def normalise_channel(raw: str) -> str:
    return CHANNEL_MAP.get(raw.strip().lower(), raw.strip())


def io_subtype(channel: str) -> str:
    """CTV → Regular Over The Top; everything else → Default."""
    return "Regular Over The Top" if channel.strip().lower() in CTV_CHANNELS else "Default"


def parse_flight_dates(flight_str):
    """
    Parse 'M/D/YYYY - M/D/YYYY' into (start, end) as 'MM/DD/YYYY'.
    DV360 Budget Segments use MM/DD/YYYY format.
    """
    if not flight_str:
        return None, None

    if isinstance(flight_str, datetime):
        return flight_str.strftime("%m/%d/%Y"), None

    s = str(flight_str).strip()
    if " - " in s:
        parts = s.split(" - ", 1)
        def to_dv360(p):
            p = p.strip()
            for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(p, fmt).strftime("%m/%d/%Y")
                except ValueError:
                    continue
            return None
        return to_dv360(parts[0]), to_dv360(parts[1])

    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%m/%d/%Y"), None
        except ValueError:
            continue

    return None, None


def build_budget_segment(budget, start_date, end_date, description) -> str:
    """
    Build a single DV360 budget segment string.
    Format: (Budget;Start Date;End Date;Campaign Budget ID;Description;)
    Campaign Budget ID is left blank.
    """
    budget_val = str(budget) if budget else ""
    start = start_date or ""
    end = end_date or ""
    desc = str(description) if description else "Flight Budget"
    return f"({budget_val};{start};{end};;{desc};);"


def build_io_name(row: dict, campaign_name: str) -> str:
    """IO Name = Campaign | Channel | Partner/Tactic"""
    channel = normalise_channel(row.get("Channel", ""))
    tactic = row.get("Partner/Tactic", row.get("Tactic", ""))
    parts = [campaign_name, channel, tactic]
    return " | ".join(p for p in parts if p)


def extract_lob(brief: dict, trafficking_row: dict = None) -> str:
    for key in ("LOB:", "LOB", "LOB/Corporate Function"):
        if brief.get(key):
            return str(brief[key]).strip()
    if trafficking_row:
        key = str(trafficking_row.get("Campaign Key", "")).strip()
        if key:
            return key
    return ""


def build_campaign_name(brief: dict, trafficking_rows: list) -> str:
    for row in trafficking_rows:
        name = row.get("Campaign", "").strip()
        if name:
            return name
    parts = [
        brief.get("LOB:", brief.get("LOB", "")),
        brief.get("Product/Service:", brief.get("Product/Service", "")),
    ]
    return " - ".join(p for p in parts if p) or "Unnamed Campaign"


# ── Main mapping function ─────────────────────────────────────────────────────

def map_to_dv360(files_data: dict) -> dict:
    """
    Entry point. Takes parsed Excel data for all 4 input files.
    Returns dict with 'insertion_orders' list of row dicts.
    Each row uses DV360_IO_COLUMNS as keys; unpopulated fields are blank.
    """
    brief       = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines  = parse_media_plan(files_data.get("Media Plan", {}))
    trafficking = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    campaign_name = build_campaign_name(brief, trafficking)
    io_objective  = brief.get("Media Objectives", brief.get("Communications Objective", ""))

    insertion_orders = []

    for row in plan_lines:
        raw_channel = row.get("Channel", "")
        channel     = normalise_channel(raw_channel)

        # Budget segment
        budget    = row.get("Budget", row.get("Est Media Cost", ""))
        flight_raw = row.get("Flight", row.get("Creative Flight Date", ""))
        start_date, end_date = parse_flight_dates(flight_raw)
        io_name = build_io_name(row, campaign_name)
        budget_segment = build_budget_segment(budget, start_date, end_date, io_name)

        # Build the IO row — only populate fields from source documents
        io_row = {col: "" for col in DV360_IO_COLUMNS}

        io_row["Name"]               = io_name
        io_row["Io Objective"]       = io_objective
        io_row["Io Type"]            = "standard"
        io_row["Io Subtype"]         = io_subtype(raw_channel)
        io_row["Budget Type"]        = "Amount"
        io_row["Budget Segments"]    = budget_segment

        insertion_orders.append(io_row)

    return {"insertion_orders": insertion_orders}
