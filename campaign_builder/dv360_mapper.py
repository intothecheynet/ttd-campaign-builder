"""
Rule-based DV360 Insertion Order mapper.

Platform: Google Display & Video 360 (DV360) ONLY
Shared parsing utilities: shared_utils.py

Maps 4 source input files to DV360 SDF v9.2 Insertion Order CSV format.
Only fields derivable from source documents are populated; all other fields
are left blank for manual entry post-export.
"""

from .shared_utils import (
    normalise_channel,
    parse_media_brief, parse_media_plan, parse_trafficking_sheet,
    extract_lob, build_campaign_name,
    parse_flight_dates,
)

# ── DSP filter ────────────────────────────────────────────────────────────────
DV360_DSP_NAMES = {"dv360"}

# ── CTV channels → "Regular Over The Top" IO Subtype ─────────────────────────
CTV_CHANNELS = {"video ctv", "ctv", "connected tv", "streaming tv"}

# ── SDF v9.2 IO column order ──────────────────────────────────────────────────
DV360_IO_COLUMNS = [
    "Io ID", "Campaign Id", "Name", "Timestamp", "Status", "Io Type", "Io Subtype",
    "Io Objective", "Fees", "Integration", "Details", "Pacing", "Pacing Rate",
    "Pacing Amount", "Frequency Enabled", "Frequency Exposures", "Frequency Period",
    "Frequency Amount", "Kpi Type", "Kpi Value", "Kpi Algorithm Id", "Measure DAR",
    "Measure DAR Channel", "Budget Type", "Budget Segments", "Auto Budget Allocation",
    "Geography Targeting - Include", "Geography Targeting - Exclude",
    "Proximity Targeting", "Proximity Location List Targeting",
    "Language Targeting - Include", "Language Targeting - Exclude",
    "Device Targeting - Include", "Device Targeting - Exclude",
    "Browser Targeting - Include", "Browser Targeting - Exclude",
    "Digital Content Labels - Exclude", "Brand Safety Sensitivity Setting",
    "Brand Safety Custom Settings", "Third Party Verification Services",
    "Third Party Verification Labels", "Channel Targeting - Include",
    "Channel Targeting - Exclude", "Site Targeting - Include",
    "Site Targeting - Exclude", "App Targeting - Include", "App Targeting - Exclude",
    "App Collection Targeting - Include", "App Collection Targeting - Exclude",
    "Category Targeting - Include", "Category Targeting - Exclude",
    "Content Genre Targeting - Include", "Content Genre Targeting - Exclude",
    "Keyword Targeting - Include", "Keyword Targeting - Exclude",
    "Audience Targeting - Include", "Audience Targeting - Exclude",
    "Affinity & In Market Targeting - Include",
    "Affinity & In Market Targeting - Exclude", "Custom List Targeting",
    "Inventory Source Targeting - Authorized Seller Options",
    "Inventory Source Targeting - Include", "Inventory Source Targeting - Exclude",
    "Inventory Source Targeting - Target New Exchanges",
    "Daypart Targeting", "Daypart Targeting Time Zone", "Environment Targeting",
    "Viewability Omid Targeting Enabled", "Viewability Targeting Active View",
    "Position Targeting - Display on Screen", "Position Targeting - Video on Screen",
    "Position Targeting - Display Position in Content",
    "Position Targeting - Video Position in Content",
    "Position Targeting - Audio Position in Content",
    "Video Player Size Targeting", "Content Duration Targeting",
    "Content Stream Type Targeting", "Audio Content Type Targeting",
    "Demographic Targeting Gender", "Demographic Targeting Age",
    "Demographic Targeting Household Income", "Demographic Targeting Parental Status",
    "Connection Speed Targeting", "Carrier Targeting - Include",
    "Carrier Targeting - Exclude", "Insertion Order Optimization",
    "Bid Strategy Unit", "Bid Strategy Do Not Exceed",
    "Apply Floor Price for Deals", "Algorithm ID",
]


# ── DV360-specific helpers ────────────────────────────────────────────────────

def io_subtype(channel: str) -> str:
    """CTV → Regular Over The Top; everything else → Default."""
    return "Regular Over The Top" if channel.strip().lower() in CTV_CHANNELS else "Default"


def build_budget_segment(budget, start_date, end_date, description) -> str:
    """
    Build a single DV360 budget segment string.
    Format: (Budget;Start Date;End Date;Campaign Budget ID;Description;)
    """
    return (f"({budget or ''};{start_date or ''};{end_date or ''};"
            f";{description or 'Flight Budget'};);")


def build_io_name(row: dict, campaign_name: str) -> str:
    """IO Name = Campaign | Channel | Partner/Tactic"""
    channel = normalise_channel(row.get("Channel", ""))
    tactic  = row.get("Partner/Tactic", row.get("Tactic", ""))
    return " | ".join(p for p in [campaign_name, channel, tactic] if p)


# ── Main mapping function ─────────────────────────────────────────────────────

def map_to_dv360(files_data: dict) -> dict:
    """
    Entry point. Takes parsed Excel data for all 4 input files.
    Returns dict with 'insertion_orders' list of row dicts.
    Unpopulated fields are blank (left for manual entry post-export).
    """
    brief       = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines  = parse_media_plan(files_data.get("Media Plan", {}), DV360_DSP_NAMES)
    trafficking = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    campaign_name = build_campaign_name(brief, trafficking)
    io_objective  = brief.get("Media Objectives",
                              brief.get("Communications Objective", ""))

    insertion_orders = []

    for row in plan_lines:
        raw_channel  = row.get("Channel", "")
        channel      = normalise_channel(raw_channel)
        budget       = row.get("Budget", row.get("Est Media Cost", ""))
        flight_raw   = row.get("Flight", row.get("Creative Flight Date", ""))
        start, end   = parse_flight_dates(flight_raw, output_format="dv360")
        io_name      = build_io_name(row, campaign_name)
        budget_seg   = build_budget_segment(budget, start, end, io_name)

        io_row = {col: "" for col in DV360_IO_COLUMNS}
        io_row["Name"]            = io_name
        io_row["Io Objective"]    = io_objective
        io_row["Io Type"]         = "standard"
        io_row["Io Subtype"]      = io_subtype(raw_channel)
        io_row["Budget Type"]     = "Amount"
        io_row["Budget Segments"] = budget_seg

        insertion_orders.append(io_row)

    return {"insertion_orders": insertion_orders}
