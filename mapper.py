"""
Rule-based TTD campaign mapper.
Replaces the Claude API call for environments without AI access.
All mapping logic is explicit and auditable.
"""

import json
import os
from datetime import datetime, timedelta

DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "defaults.json")
FEEDBACK_PATH = os.path.join(os.path.dirname(__file__), "feedback.json")

# ── DSP values used in Media Plan "DSP" column ───────────────────────────────
TTD_DSP_NAMES    = {"ttd"}
DV360_DSP_NAMES  = {"dv360"}
AMAZON_DSP_NAMES = {"amazon"}

# ── Channel normalisation: source values → TTD canonical names ───────────────
CHANNEL_MAP = {
    "ctv":              "CTV",
    "connected tv":     "CTV",
    "streaming tv":     "CTV",
    "olv":              "OLV",
    "online video":     "OLV",
    "pre-roll":         "OLV",
    "display":          "Display",
    "banner":           "Display",
    "native":           "Native",
    "audio":            "Audio",
    "streaming audio":  "Audio",
    "dooh":             "DOOH",
    "out of home":      "DOOH",
    "digital ooh":      "DOOH",
}


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_media_brief(sheet_data: dict) -> dict:
    """
    Media Brief is a label-value form.
    Column A = field label, Column B = value.
    Returns a flat dict of label → value.
    """
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
    Media Plan has two header rows:
      Row 1: 'Flight Date' (merged, ignored)
      Row 2: actual column headers — Buy Type, Channel, DSP, Partner/Tactic,
             Flight, Audience, Geo, Creative, Landing Page URL,
             Planned Impressions, Budget, Planning CPM, ...
    Returns only rows where DSP matches a TTD alias.
    """
    raw_rows = sheet_data.get("Sheet1", {}).get("rows", [])
    if len(raw_rows) < 2:
        return []

    # Row index 1 (0-based after header strip) contains the real column headers
    # Our excel_to_dict uses row 0 as headers, so "rows" starts at row 2 of the sheet.
    # Row index 0 of rows[] = the "Buy Type, Channel, DSP..." header row.
    header_row = raw_rows[0]
    headers = list(header_row.values())

    lines = []
    for row in raw_rows[1:]:
        vals = list(row.values())
        record = dict(zip(headers, vals))
        dsp = str(record.get("DSP", "")).strip().lower()
        if dsp in TTD_DSP_NAMES:
            lines.append(record)
    return lines


def parse_audience_matrix(sheet_data: dict) -> list:
    """
    Returns audience segments intended for TTD activation.
    Filters: Platform Name contains 'TTD' or 'Trade Desk',
             or no platform specified (treat as all platforms).
    """
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    segments = []
    for row in rows:
        platform = str(row.get("Platform Name", "")).strip().lower()
        indicator = str(row.get("Activation/Suppression Indicator", "")).strip().lower()
        if platform in ("", "ttd", "the trade desk", "tradedesk") or \
                "ttd" in platform or "trade desk" in platform:
            segments.append({
                "segment": row.get("Segment Description", ""),
                "type":    row.get("Targeting Typ", ""),
                "action":  indicator,  # "activation" or "suppression"
                "source":  row.get("Data Source", ""),
            })
    return segments


def parse_trafficking_sheet(sheet_data: dict) -> list:
    """
    Returns all rows from the Trafficking Sheet.
    Filters out rows with no Campaign value.
    """
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    return [r for r in rows if r.get("Campaign")]


# ── Defaults lookup ───────────────────────────────────────────────────────────

def load_defaults() -> dict:
    with open(DEFAULTS_PATH) as f:
        return json.load(f)


def get_default(defaults: dict, field: str, channel: str = None, lob: str = None):
    """
    Returns the most specific default for a field.
    Priority: by_lob_and_channel > by_channel > by_lob > global
    """
    value = defaults.get("global", {}).get(field)

    if channel and channel in defaults.get("by_channel", {}):
        v = defaults["by_channel"][channel].get(field)
        if v is not None:
            value = v

    if lob and lob in defaults.get("by_lob", {}):
        v = defaults["by_lob"][lob].get(field)
        if v is not None:
            value = v

    if lob and channel:
        v = defaults.get("by_lob_and_channel", {}) \
                    .get(lob, {}).get(channel, {}).get(field)
        if v is not None:
            value = v

    return value


# ── Field helpers ─────────────────────────────────────────────────────────────

def normalise_channel(raw: str) -> str:
    """Map source channel strings to TTD canonical channel names."""
    return CHANNEL_MAP.get(raw.strip().lower(), raw.strip())


def extract_lob(brief: dict, trafficking_row: dict = None) -> str:
    """
    Extract Line of Business.
    Sources: Media Brief 'LOB:', 'LOB/Corporate Function'; Trafficking 'Campaign Key'.
    """
    for key in ("LOB:", "LOB", "LOB/Corporate Function"):
        if brief.get(key):
            return str(brief[key]).strip()
    if trafficking_row:
        key = str(trafficking_row.get("Campaign Key", "")).strip()
        if key:
            return key
    return ""


def build_campaign_name(brief: dict, trafficking_rows: list) -> str:
    """
    Campaign name = first Campaign value in Trafficking Sheet.
    Fallback: LOB + Product/Service from Media Brief.
    """
    for row in trafficking_rows:
        name = row.get("Campaign", "").strip()
        if name:
            return name
    parts = [
        brief.get("LOB:", brief.get("LOB", "")),
        brief.get("Product/Service:", brief.get("Product/Service", "")),
    ]
    return " - ".join(p for p in parts if p) or "Unnamed Campaign"


def build_ad_group_name(row: dict) -> str:
    """
    Ad Group name = Campaign | Channel | Tactic | Audience (from trafficking row).
    """
    parts = [
        row.get("Campaign", ""),
        row.get("Channel", ""),
        row.get("Tactic", ""),
        row.get("Audience", ""),
    ]
    return " | ".join(p for p in parts if p)


def parse_flight_dates(flight_str: str):
    """
    Parse flight date strings. Expects 'MM/DD - MM/DD', 'MM/DD/YYYY - MM/DD/YYYY',
    or a datetime object. Returns (start_str, end_str) in 'YYYY-MM-DD 00:00:00'.
    """
    if not flight_str:
        return None, None

    if isinstance(flight_str, datetime):
        return flight_str.strftime("%Y-%m-%d 00:00:00"), None

    s = str(flight_str).strip()
    year = datetime.now().year

    for sep in [" - ", "-", " to ", "/"]:
        if sep in s:
            parts = s.split(sep, 1)
            try:
                def parse_part(p):
                    p = p.strip()
                    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m/%d", "%Y-%m-%d"):
                        try:
                            d = datetime.strptime(p, fmt)
                            if d.year == 1900:  # strptime default when no year
                                d = d.replace(year=year)
                            return d.strftime("%Y-%m-%d 00:00:00")
                        except ValueError:
                            continue
                    return None
                return parse_part(parts[0]), parse_part(parts[1])
            except Exception:
                pass

    return None, None


def audience_string(segments: list, action: str = "activation") -> str:
    """Build a comma-separated audience string for TTD from segments."""
    names = [
        s["segment"] for s in segments
        if s["action"].lower() == action.lower() and s["segment"]
    ]
    return "; ".join(names)


# ── Main mapping function ─────────────────────────────────────────────────────

def map_to_ttd(files_data: dict) -> dict:
    """
    Entry point. Takes parsed Excel data for all 4 input files.
    Returns TTD bulk upload data dict.
    """
    defaults = load_defaults()

    brief        = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines   = parse_media_plan(files_data.get("Media Plan", {}))
    audiences    = parse_audience_matrix(files_data.get("Audience Matrix", {}))
    trafficking  = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    lob           = extract_lob(brief, trafficking[0] if trafficking else None)
    campaign_name = build_campaign_name(brief, trafficking)

    audience_str  = audience_string(audiences, "activation")
    excluder_str  = audience_string(audiences, "suppression")

    # ── CAMPAIGN SETS ────────────────────────────────────────────────────────
    # One campaign set per campaign.
    # IO ID comes from Media Brief "Brief ID"; blank if missing.
    campaign_sets = [{
        "IO ID":              brief.get("Brief ID", ""),
        "Campaign Set Name":  campaign_name,
    }]

    # ── CAMPAIGNS ────────────────────────────────────────────────────────────
    # One campaign row per unique campaign name found in trafficking sheet.
    # If no trafficking data, create one campaign from the brief.
    unique_campaigns = list({r.get("Campaign", campaign_name) for r in trafficking}) \
                       if trafficking else [campaign_name]

    campaigns = []
    for camp_name in unique_campaigns:
        # Determine primary channel from first matching plan line or trafficking row
        primary_channel_raw = ""
        for pl in plan_lines:
            if pl.get("Channel"):
                primary_channel_raw = pl.get("Channel", "")
                break

        channel = normalise_channel(primary_channel_raw) if primary_channel_raw else ""

        campaigns.append({
            "Campaign Name":               camp_name,
            "Description":                 brief.get("Media Objectives", brief.get("Communications Objective", "")),
            "Objective":                   get_default(defaults, "Objective", channel, lob),
            "Primary Channel":             get_default(defaults, "Primary Channel", channel, lob),
            "Goals":                       get_default(defaults, "Goals", channel, lob),
            "Time Zone ID":                get_default(defaults, "Time Zone ID"),
            "Pacing Mode":                 get_default(defaults, "Pacing Mode", channel, lob),
            "Manually Prioritize Ad Groups": get_default(defaults, "Manually Prioritize Ad Groups"),
            "IO Contract":                 brief.get("Brief ID", ""),
            "Campaign PO #":               brief.get("Campaign PO #", ""),
        })

    # ── AD GROUPS ────────────────────────────────────────────────────────────
    # One ad group per line in the Media Plan that targets TTD.
    # If no plan lines, fall back to one ad group per trafficking row.
    ad_groups = []
    source_rows = plan_lines if plan_lines else trafficking

    for row in source_rows:
        raw_channel = row.get("Channel", "")
        channel     = normalise_channel(raw_channel)
        camp_name   = row.get("Campaign", campaign_name)

        # Audience from the row itself, or fall back to Audience Matrix
        row_audience = row.get("Audience", "")
        final_audience = row_audience if row_audience else audience_str

        ad_groups.append({
            "Ad Group Name":             build_ad_group_name(row) if not plan_lines
                                         else f"{camp_name} | {channel} | {row.get('Partner/Tactic', row.get('Tactic', ''))}",
            "Channel":                   channel,
            "Goal Type":                 get_default(defaults, "Goal Type", channel, lob),
            "Goal Value":                get_default(defaults, "Goal Value", channel, lob),
            "Base Bid":                  get_default(defaults, "Base Bid", channel, lob),
            "Max Bid":                   get_default(defaults, "Max Bid", channel, lob),
            "Priority":                  get_default(defaults, "Priority"),
            "Predictive Clearing Enabled": get_default(defaults, "Predictive Clearing Enabled"),
            "Auto Enable Upcoming Features": get_default(defaults, "Auto Enable Upcoming Features"),
            "Marketplace":               get_default(defaults, "Marketplace", channel, lob),
            "Audience":                  final_audience,
            "Audience Excluder":         excluder_str,
        })

    # ── BUDGET FLIGHTS ───────────────────────────────────────────────────────
    # One flight row per ad group.
    # Dates from Media Plan "Flight" column; fallback to Trafficking "Creative Flight Date".
    budget_flights = []
    source_rows = plan_lines if plan_lines else trafficking

    for i, row in enumerate(source_rows):
        raw_channel = row.get("Channel", "")
        channel     = normalise_channel(raw_channel)
        camp_name   = row.get("Campaign", campaign_name)

        # Match the ad group name
        if plan_lines:
            ag_name = f"{camp_name} | {channel} | {row.get('Partner/Tactic', '')}"
        else:
            ag_name = build_ad_group_name(row)

        # Dates
        flight_raw = row.get("Flight", row.get("Creative Flight Date", ""))
        start_date, end_date = parse_flight_dates(flight_raw)

        budget_flights.append({
            "Campaign":                                  camp_name,
            "Ad Group":                                  ag_name,
            "Flight Budget (in advertiser currency)":    row.get("Budget", row.get("Est Media Cost", "")),
            "Daily Spend Cap (in advertiser currency)":  "",   # calculated manually
            "Impression Budget":                         row.get("Planned Impressions", ""),
            "Daily Impression Cap":                      "",
            "Start Date Inclusive UTC":                  start_date or "",
            "End Date Exclusive UTC":                    end_date or "",
            "Action":                                    get_default(defaults, "Action"),
        })

    return {
        "campaign_sets":  campaign_sets,
        "campaigns":      campaigns,
        "ad_groups":      ad_groups,
        "budget_flights": budget_flights,
        "campaign_fees":  [],
        "ad_group_fees":  [],
    }
