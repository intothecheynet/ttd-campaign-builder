"""
Rule-based Amazon DSP campaign mapper.
Mirrors the TTD mapper shape: parses the 4 input files (Media Brief,
Media Plan, Audience Matrix, Trafficking Sheet) and emits dicts that
match the Amazon DSP bulksheet template tabs.

Target template tabs:
  - ORDERS
  - DISPLAY LINE ITEMS
  - VIDEO LINE ITEMS         (Streaming TV + Online Video)
  - AUDIO LINE ITEMS
  - PODCAST LINE ITEMS
  - CREATIVE ASSOCIATIONS

All Amazon-specific reference values (Product Categories, Supply Source,
Line Type, etc.) come from `defaults.json` and `platform_defaults.json`
so they can be tuned without touching code.
"""

import json
import os
from datetime import datetime

DEFAULTS_PATH          = os.path.join(os.path.dirname(__file__), "amazon_defaults.json")
PLATFORM_DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "amazon_platform_defaults.json")


# ── DSP filter (Media Plan "DSP" column values that route to Amazon) ────────
AMAZON_DSP_NAMES = {"amazon", "amzn", "amazon dsp", "adsp"}

# ── Audience Matrix "Platform Name" values that count as Amazon ─────────────
AMAZON_PLATFORM_HINTS = {"amazon", "amzn", "amazon dsp", "adsp"}


# ── Channel → Amazon "Media Type" + line-item sheet routing ─────────────────
# Each entry: (Amazon Media Type, sheet, video_ad_content_type, line_type)
# - sheet:                  which Amazon template tab this row belongs in
# - video_ad_content_type:  required for VIDEO LINE ITEMS only ("STREAMING_TV" / "ONLINE_VIDEO")
# - line_type:              Amazon DSP "Line type*" value (from Don't Delete tab)
CHANNEL_ROUTING = {
    # CTV / Streaming TV → VIDEO with STREAMING_TV content type
    "video ctv":        ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "ctv":              ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "connected tv":     ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "streaming tv":     ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),

    # Online video / pre-roll → VIDEO with ONLINE_VIDEO content type
    "video olv":        ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "olv":              ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "online video":     ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "pre-roll":         ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),

    # Display → DISPLAY LINE ITEMS
    "display":          ("Display",      "display", "",             "Standard display"),
    "banner":           ("Display",      "display", "",             "Standard display"),
    "native":           ("Display",      "display", "",             "Standard display"),

    # Audio (non-podcast) → AUDIO LINE ITEMS
    "audio":            ("Audio",        "audio",   "",             "Standard display"),
    "audio streaming audio": ("Audio",   "audio",   "",             "Standard display"),
    "streaming audio":  ("Audio",        "audio",   "",             "Standard display"),
    "connected car":    ("Audio",        "audio",   "",             "Standard display"),
    "connected home":   ("Audio",        "audio",   "",             "Standard display"),

    # Podcasts → PODCAST LINE ITEMS
    "audio podcasts":   ("Audio",        "podcast", "",             "Standard display"),
    "podcast":          ("Audio",        "podcast", "",             "Standard display"),
    "podcasts":         ("Audio",        "podcast", "",             "Standard display"),

    # DOOH — Amazon DSP doesn't have a dedicated tab. Skip with a warning.
    # (handled in route_row by returning None)
}


# ── Parsers (same input shape as TTD mapper) ────────────────────────────────

def parse_media_brief(sheet_data: dict) -> dict:
    """Media Brief: column A = label, column B = value. Returns flat dict."""
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
    """Media Plan: second row is the real header. Filter DSP == Amazon."""
    raw_rows = sheet_data.get("Sheet1", {}).get("rows", [])
    if len(raw_rows) < 2:
        return []
    headers = list(raw_rows[0].values())

    lines = []
    for row in raw_rows[1:]:
        vals = list(row.values())
        record = dict(zip(headers, vals))
        dsp = str(record.get("DSP", "")).strip().lower()
        if dsp in AMAZON_DSP_NAMES:
            lines.append(record)
    return lines


def parse_audience_matrix(sheet_data: dict) -> list:
    """Return audience segments targeted to Amazon."""
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    segments = []
    for row in rows:
        platform  = str(row.get("Platform Name", "")).strip().lower()
        indicator = str(row.get("Activation/Suppression Indicator", "")).strip().lower()
        if platform in ("",) or platform in AMAZON_PLATFORM_HINTS or "amazon" in platform:
            segments.append({
                "segment":   row.get("Segment Description", ""),
                "type":      row.get("Targeting Typ", ""),
                "action":    indicator,
                "source":    row.get("Data Source", ""),
                "amazon_id": row.get("Amazon Audience ID", ""),  # if your sheet has it
            })
    return segments


def parse_trafficking_sheet(sheet_data: dict) -> list:
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    return [r for r in rows if r.get("Campaign")]


# ── Defaults lookup ─────────────────────────────────────────────────────────

def load_defaults() -> dict:
    if not os.path.exists(DEFAULTS_PATH):
        return {}
    with open(DEFAULTS_PATH) as f:
        return json.load(f)


def load_platform_defaults() -> dict:
    if not os.path.exists(PLATFORM_DEFAULTS_PATH):
        return {}
    with open(PLATFORM_DEFAULTS_PATH) as f:
        return json.load(f)


def apply_platform_defaults(row: dict, tab: str, platform: dict) -> dict:
    """Base layer: row values win, blank platform defaults are skipped."""
    base = platform.get(tab, {})
    for field, value in base.items():
        if value != "" and field not in row:
            row[field] = value
    return row


def get_default(defaults: dict, field: str, channel: str = None, lob: str = None):
    """Most-specific-wins: by_lob_and_channel > by_channel > by_lob > global."""
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


# ── Field helpers ────────────────────────────────────────────────────────────

def route_row(raw_channel: str):
    """Return (media_type, sheet, video_ad_content_type, line_type) or None."""
    key = (raw_channel or "").strip().lower()
    return CHANNEL_ROUTING.get(key)


def extract_lob(brief: dict, trafficking_row: dict = None) -> str:
    for key in ("LOB:", "LOB", "LOB/Corporate Function"):
        if brief.get(key):
            return str(brief[key]).strip()
    if trafficking_row:
        key = str(trafficking_row.get("Campaign Key", "")).strip()
        if key:
            return key
    return ""


def build_order_name(brief: dict, trafficking_rows: list) -> str:
    """Order = top-level container. Use first Trafficking Campaign,
    falling back to LOB + Product/Service from Media Brief."""
    for row in trafficking_rows:
        name = (row.get("Campaign") or "").strip()
        if name:
            return name
    parts = [
        brief.get("LOB:", brief.get("LOB", "")),
        brief.get("Product/Service:", brief.get("Product/Service", "")),
    ]
    return " - ".join(p for p in parts if p) or "Unnamed Amazon Order"


def build_line_name(camp_name: str, media_type: str, row: dict) -> str:
    """Line item name = Order | Media Type | Partner-or-Tactic | Audience."""
    parts = [
        camp_name,
        media_type,
        row.get("Partner/Tactic", row.get("Tactic", "")),
        row.get("Audience", ""),
    ]
    return " | ".join(str(p) for p in parts if p)


def parse_flight_dates(flight_str):
    """Parse Media Plan 'Flight' column.
    Source format: 'M/D/YYYY - M/D/YYYY'
    Output: tuple of (start, end) as 'MM-DD-YYYY-HH-MM' (Amazon format).
    Start defaults to 00-01 (00:01); end defaults to 23-59.
    """
    if not flight_str:
        return None, None

    if isinstance(flight_str, datetime):
        return flight_str.strftime("%m-%d-%Y-00-01"), None

    s = str(flight_str).strip()

    def to_amazon(p: str, end: bool = False) -> str | None:
        p = p.strip()
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(p, fmt)
                return dt.strftime("%m-%d-%Y-23-59" if end else "%m-%d-%Y-00-01")
            except ValueError:
                continue
        return None

    if " - " in s:
        a, b = s.split(" - ", 1)
        return to_amazon(a, end=False), to_amazon(b, end=True)

    return to_amazon(s, end=False), None


def build_flight_budget_string(budget, start: str, end: str) -> str:
    """Build Amazon's required 'Flight budget and dates*' format:
       Flight1:[budget, start, end]; Flight2:[...]
    """
    if not (start and end and budget):
        return ""
    # Strip currency symbols and commas from budget
    b = str(budget).replace("$", "").replace(",", "").strip()
    return f"Flight1:[{b}, {start}, {end}]"


def build_frequency_caps(freq_per: str = "10", per_value: str = "7", per_unit: str = "Days") -> str:
    """Amazon format: FrequencyCap#:[User, N, Interval, Unit]; ..."""
    return f"FrequencyCap1:[User, {freq_per}, {per_value}, {per_unit}]"


def audience_string(segments: list, action: str = "activation") -> str:
    """Amazon expects exact audience IDs separated by semicolons.
    Falls back to segment names if no Amazon ID column is present."""
    out = []
    for s in segments:
        if s["action"].lower() != action.lower():
            continue
        if s.get("amazon_id"):
            out.append(str(s["amazon_id"]).strip())
        elif s.get("segment"):
            out.append(str(s["segment"]).strip())
    return "; ".join(out)


def goal_kpi_string(defaults: dict, channel: str, lob: str) -> str:
    """Combined 'Goal and Goal KPI*' field, e.g. 'Awareness - Reach'."""
    return get_default(defaults, "Goal and Goal KPI", channel, lob) \
           or "Awareness - Reach"


# ── Main mapping function ───────────────────────────────────────────────────

def map_to_amazon(files_data: dict) -> dict:
    """Entry point. Takes parsed Excel data for all 4 input files.
    Returns Amazon bulk upload data dict, one key per template tab."""
    defaults = load_defaults()
    platform = load_platform_defaults()

    brief       = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines  = parse_media_plan(files_data.get("Media Plan", {}))
    audiences   = parse_audience_matrix(files_data.get("Audience Matrix", {}))
    trafficking = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    lob        = extract_lob(brief, trafficking[0] if trafficking else None)
    order_name = build_order_name(brief, trafficking)

    audience_str = audience_string(audiences, "activation")
    # Amazon doesn't have a dedicated "Audience Excluder" — exclusions are done
    # within the Audiences expression syntax. Captured here for future use.
    _ = audience_string(audiences, "suppression")

    # ── ORDERS ──────────────────────────────────────────────────────────────
    # One Order per unique Trafficking Campaign (fallback: single Order from brief)
    unique_orders = list({(r.get("Campaign") or order_name) for r in trafficking}) \
                    if trafficking else [order_name]

    # Aggregate plan_lines per order to compute total budget + flight window
    plan_by_order: dict[str, list[dict]] = {}
    for pl in plan_lines:
        camp = (pl.get("Campaign") or order_name)
        plan_by_order.setdefault(camp, []).append(pl)

    # Collect distinct Media Types across the plan for each order
    def media_types_for(order: str) -> str:
        types = []
        for pl in plan_by_order.get(order, []):
            route = route_row(pl.get("Channel", ""))
            if route and route[0] not in types:
                types.append(route[0])
        return ", ".join(types)

    # Total order budget = sum of Media Plan Budget for that order
    def order_budget_and_flight(order: str):
        total = 0.0
        starts, ends = [], []
        for pl in plan_by_order.get(order, []):
            b = pl.get("Budget", pl.get("Est Media Cost", "")) or 0
            try:
                total += float(str(b).replace("$", "").replace(",", ""))
            except ValueError:
                pass
            s, e = parse_flight_dates(pl.get("Flight", ""))
            if s: starts.append(s)
            if e: ends.append(e)
        # Use earliest start, latest end across plan lines
        s_str = sorted(starts)[0] if starts else ""
        e_str = sorted(ends)[-1]  if ends   else ""
        flight_str = build_flight_budget_string(int(total) if total else "", s_str, e_str)
        return flight_str

    orders = []
    for o_name in unique_orders:
        primary_channel_raw = ""
        for pl in plan_by_order.get(o_name, []):
            if pl.get("Channel"):
                primary_channel_raw = pl["Channel"]
                break

        route = route_row(primary_channel_raw) or (None, None, None, None)
        channel = route[0] or ""

        orders.append({
            "Order ID":                       "",  # leave blank → Amazon assigns
            "Advertiser ID*":                 get_default(defaults, "Advertiser ID"),
            "Advertiser name":                get_default(defaults, "Advertiser name"),
            "Order name*":                    o_name,
            "Active/Inactive":                get_default(defaults, "Active/Inactive") or "Active",
            "PO number":                      brief.get("Campaign PO #", ""),
            "Media Type":                     media_types_for(o_name),
            "Goal and Goal KPI*":             goal_kpi_string(defaults, channel, lob),
            "Target KPI":                     get_default(defaults, "Target KPI", channel, lob),
            "Bidding Priority":               get_default(defaults, "Bidding Priority") \
                                              or "Prioritize spending full budget",
            "Frequency group ID":             "",
            "Budget Management Strategy":     get_default(defaults, "Budget Management Strategy") \
                                              or "Automate budget allocation",
            "Frequency Caps":                 build_frequency_caps(),
            "Flight budget and dates*":       order_budget_and_flight(o_name),
            "Budget Rollover":                get_default(defaults, "Budget Rollover") \
                                              or "Do not change flight budgets",
            "Budget cap":                     "",
            "Agency fee":                     get_default(defaults, "Agency fee"),
            "Products":                       "",
            "Off-Amazon conversions":         "",
        })

    # ── LINE ITEMS (split by sheet) ─────────────────────────────────────────
    display_line_items = []
    video_line_items   = []
    audio_line_items   = []
    podcast_line_items = []

    for row in plan_lines:
        raw_channel = row.get("Channel", "")
        route = route_row(raw_channel)
        if not route:
            print(f"[Amazon Mapper] Skipping row — no routing for channel '{raw_channel}'")
            continue

        media_type, sheet, vct, line_type = route
        camp_name = (row.get("Campaign") or order_name)
        line_name = build_line_name(camp_name, media_type, row)
        start, end = parse_flight_dates(row.get("Flight", row.get("Creative Flight Date", "")))

        row_audience  = row.get("Audience", "")
        final_aud_str = row_audience if row_audience else audience_str

        base_supply_bid = get_default(defaults, "Base supply bid", media_type, lob) or "5.00"
        max_avg_cpm     = get_default(defaults, "Maximum average CPM", media_type, lob) or "15.00"
        budget          = row.get("Budget", row.get("Est Media Cost", ""))
        try:
            budget_clean = float(str(budget).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            budget_clean = ""

        # Common fields across all line-item sheets
        common = {
            "Line ID":                          "",
            "Advertiser ID*":                   get_default(defaults, "Advertiser ID"),
            "Advertiser name":                  get_default(defaults, "Advertiser name"),
            "Order ID*":                        camp_name,  # filled in post-create with real Order ID
            "Line type*":                       line_type,
            "Line name*":                       line_name,
            "External ID":                      "",
            "Line start date":                  start or "",
            "Line end date":                    end or "",
            "Active/Inactive":                  "Book/Deliver",
            "Product categories*":              get_default(defaults, "Product categories", media_type, lob),
            "Frequency Caps":                   build_frequency_caps("3", "1", "Days"),
            "Supply source":                    get_default(defaults, "Supply source", media_type, lob),
            "Audiences - include":              final_aud_str,
            "Reach similar audiences":          "No",
            "Line item budget":                 budget_clean,
            "Base supply bid*":                 base_supply_bid,
            "Maximum average CPM":              max_avg_cpm,
            "Creative ID":                      row.get("Creative", ""),
        }

        if sheet == "display":
            display_line_items.append({
                **common,
                "Device type":                  get_default(defaults, "Device type", media_type, lob) \
                                                or "Desktop and mobile (web)",
                "Environment Type":             get_default(defaults, "Environment Type", media_type, lob) \
                                                or "Both",
                "Pacing profile":               get_default(defaults, "Pacing profile") or "Evenly",
                "Automated optimization":       "Yes",
            })
        elif sheet == "video":
            video_line_items.append({
                **common,
                "Video Ad Content Type*":       vct,
                "Device type":                  get_default(defaults, "Device type", media_type, lob) \
                                                or "Desktop and mobile (web)",
                "Mobile environment":           get_default(defaults, "Mobile environment", media_type, lob),
                "Video initiation type":        get_default(defaults, "Video initiation type", media_type, lob) \
                                                or "Any",
                "In-stream position":           get_default(defaults, "In-stream position", media_type, lob),
                "Video player size":            get_default(defaults, "Video player size", media_type, lob) \
                                                or "Any",
                "Video completion":             get_default(defaults, "Video completion", media_type, lob) \
                                                or "No targeting",
                "Pacing profile":               get_default(defaults, "Pacing profile") or "Evenly",
                "Automated optimization":       "Yes",
            })
        elif sheet == "audio":
            audio_line_items.append({
                **common,
                "Device type":                  get_default(defaults, "Device type", media_type, lob) \
                                                or "All devices (desktop, mobile, connected TV, smart speaker)",
                "Content and Genre Blocking":   get_default(defaults, "Content and Genre Blocking"),
            })
        elif sheet == "podcast":
            # Podcast sheet is a strict subset — drop fields it doesn't have.
            podcast_keep = {
                "Line ID", "Advertiser ID*", "Advertiser name", "Order ID*",
                "Line type*", "Line name*", "External ID",
                "Line start date", "Line end date", "Active/Inactive",
                "Product categories*", "Frequency Caps",
                "Line item budget", "Creative ID",
            }
            podcast_row = {k: v for k, v in common.items() if k in podcast_keep}
            podcast_row.update({
                "Category Blocking": get_default(defaults, "Category Blocking"),
                "Content Blocking":  get_default(defaults, "Content Blocking") \
                                     or "Exclude explicit content",
            })
            podcast_line_items.append(podcast_row)

    # ── CREATIVE ASSOCIATIONS ───────────────────────────────────────────────
    # One row per (line_name, creative). Real Line IDs filled in after upload.
    creative_associations = []
    for row in plan_lines:
        creative = (row.get("Creative") or "").strip()
        if not creative:
            continue
        route = route_row(row.get("Channel", ""))
        if not route:
            continue
        media_type = route[0]
        camp_name  = (row.get("Campaign") or order_name)
        line_name  = build_line_name(camp_name, media_type, row)
        creative_associations.append({
            "Line ID":         "",
            "Line name":       line_name,
            "Advertiser ID*":  get_default(defaults, "Advertiser ID"),
            "Advertiser name": get_default(defaults, "Advertiser name"),
            "Operation Type*": "Create",
            "Ad Creative Id*": creative,
            "Start Date":      "",
            "End Date":        "",
            "Active/Inactive": "Active",
            "Weight":          "",
        })

    # Apply platform defaults as base layer to each tab
    orders             = [apply_platform_defaults(r, "orders",             platform) for r in orders]
    display_line_items = [apply_platform_defaults(r, "display_line_items", platform) for r in display_line_items]
    video_line_items   = [apply_platform_defaults(r, "video_line_items",   platform) for r in video_line_items]
    audio_line_items   = [apply_platform_defaults(r, "audio_line_items",   platform) for r in audio_line_items]
    podcast_line_items = [apply_platform_defaults(r, "podcast_line_items", platform) for r in podcast_line_items]

    return {
        "orders":                orders,
        "display_line_items":    display_line_items,
        "video_line_items":      video_line_items,
        "audio_line_items":      audio_line_items,
        "podcast_line_items":    podcast_line_items,
        "creative_associations": creative_associations,
    }
