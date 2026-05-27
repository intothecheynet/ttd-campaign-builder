"""
Rule-based Amazon DSP campaign mapper.

Platform: Amazon DSP ONLY
Shared parsing utilities: shared_utils.py

Maps 4 source input files to the Amazon DSP bulksheet template tabs:
  ORDERS / DISPLAY LINE ITEMS / VIDEO LINE ITEMS / AUDIO LINE ITEMS /
  PODCAST LINE ITEMS / CREATIVE ASSOCIATIONS
"""

import json
import os

from .shared_utils import (
    parse_media_brief, parse_media_plan, parse_trafficking_sheet,
    extract_lob, build_campaign_name,
    apply_platform_defaults, get_default,
    parse_flight_dates,
)

_DIR = os.path.dirname(__file__)
DEFAULTS_PATH          = os.path.join(_DIR, "amazon_defaults.json")
PLATFORM_DEFAULTS_PATH = os.path.join(_DIR, "amazon_platform_defaults.json")

# ── DSP filter ────────────────────────────────────────────────────────────────
AMAZON_DSP_NAMES     = {"amazon", "amzn", "amazon dsp", "adsp"}
AMAZON_PLATFORM_HINTS = {"amazon", "amzn", "amazon dsp", "adsp"}

# ── Channel → Amazon tab routing ─────────────────────────────────────────────
# (Amazon Media Type, sheet, video_ad_content_type, line_type)
CHANNEL_ROUTING = {
    "video ctv":        ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "ctv":              ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "connected tv":     ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "streaming tv":     ("Streaming TV", "video",   "STREAMING_TV", "Standard display"),
    "video olv":        ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "olv":              ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "online video":     ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "pre-roll":         ("Online Video", "video",   "ONLINE_VIDEO", "Standard display"),
    "display":          ("Display",      "display", "",             "Standard display"),
    "banner":           ("Display",      "display", "",             "Standard display"),
    "native":           ("Display",      "display", "",             "Standard display"),
    "audio":            ("Audio",        "audio",   "",             "Standard display"),
    "audio streaming audio": ("Audio",   "audio",   "",             "Standard display"),
    "streaming audio":  ("Audio",        "audio",   "",             "Standard display"),
    "connected car":    ("Audio",        "audio",   "",             "Standard display"),
    "connected home":   ("Audio",        "audio",   "",             "Standard display"),
    "audio podcasts":   ("Audio",        "podcast", "",             "Standard display"),
    "podcast":          ("Audio",        "podcast", "",             "Standard display"),
    "podcasts":         ("Audio",        "podcast", "",             "Standard display"),
}


# ── Amazon-specific parsers ───────────────────────────────────────────────────

def parse_audience_matrix(sheet_data: dict) -> list:
    """Returns audience segments targeted to Amazon."""
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
                "amazon_id": row.get("Amazon Audience ID", ""),
            })
    return segments


def audience_string(segments: list, action: str = "activation") -> str:
    """Amazon expects audience IDs; falls back to segment names if no ID column."""
    out = []
    for s in segments:
        if s["action"].lower() != action.lower():
            continue
        if s.get("amazon_id"):
            out.append(str(s["amazon_id"]).strip())
        elif s.get("segment"):
            out.append(str(s["segment"]).strip())
    return "; ".join(out)


# ── Defaults ──────────────────────────────────────────────────────────────────

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


# ── Amazon-specific helpers ───────────────────────────────────────────────────

def route_row(raw_channel: str):
    """Return (media_type, sheet, video_ad_content_type, line_type) or None."""
    return CHANNEL_ROUTING.get((raw_channel or "").strip().lower())


def build_line_name(camp_name: str, media_type: str, row: dict) -> str:
    """Line item name = Order | Media Type | Partner-or-Tactic | Audience."""
    parts = [camp_name, media_type,
             row.get("Partner/Tactic", row.get("Tactic", "")),
             row.get("Audience", "")]
    return " | ".join(str(p) for p in parts if p)


def build_flight_budget_string(budget, start: str, end: str) -> str:
    """Amazon 'Flight budget and dates*' format: Flight1:[budget, start, end]"""
    if not (start and end and budget):
        return ""
    b = str(budget).replace("$", "").replace(",", "").strip()
    return f"Flight1:[{b}, {start}, {end}]"


def build_frequency_caps(freq_per: str = "10",
                         per_value: str = "7", per_unit: str = "Days") -> str:
    return f"FrequencyCap1:[User, {freq_per}, {per_value}, {per_unit}]"


def goal_kpi_string(defaults: dict, channel: str, lob: str) -> str:
    return get_default(defaults, "Goal and Goal KPI", channel, lob) or "Awareness - Reach"


# ── Main mapping function ─────────────────────────────────────────────────────

def map_to_amazon(files_data: dict) -> dict:
    """
    Entry point. Takes parsed Excel data for all 4 input files.
    Returns Amazon bulk upload data dict, one key per template tab.
    """
    defaults = load_defaults()
    platform = load_platform_defaults()

    brief       = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines  = parse_media_plan(files_data.get("Media Plan", {}), AMAZON_DSP_NAMES)
    audiences   = parse_audience_matrix(files_data.get("Audience Matrix", {}))
    trafficking = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    lob         = extract_lob(brief, trafficking[0] if trafficking else None)
    order_name  = build_campaign_name(brief, trafficking,
                                      fallback="Unnamed Amazon Order")
    audience_str = audience_string(audiences, "activation")

    # ── ORDERS ───────────────────────────────────────────────────────────────
    unique_orders = (
        list({(r.get("Campaign") or order_name) for r in trafficking})
        if trafficking else [order_name]
    )

    plan_by_order: dict[str, list[dict]] = {}
    for pl in plan_lines:
        camp = (pl.get("Campaign") or order_name)
        plan_by_order.setdefault(camp, []).append(pl)

    def media_types_for(order: str) -> str:
        types = []
        for pl in plan_by_order.get(order, []):
            r = route_row(pl.get("Channel", ""))
            if r and r[0] not in types:
                types.append(r[0])
        return ", ".join(types)

    def order_budget_and_flight(order: str) -> str:
        total = 0.0
        starts, ends = [], []
        for pl in plan_by_order.get(order, []):
            b = pl.get("Budget", pl.get("Est Media Cost", "")) or 0
            try:
                total += float(str(b).replace("$", "").replace(",", ""))
            except ValueError:
                pass
            s, e = parse_flight_dates(pl.get("Flight", ""), output_format="amazon")
            if s: starts.append(s)
            if e: ends.append(e)
        s_str = sorted(starts)[0] if starts else ""
        e_str = sorted(ends)[-1]  if ends   else ""
        return build_flight_budget_string(int(total) if total else "", s_str, e_str)

    orders = []
    for o_name in unique_orders:
        primary_channel_raw = next(
            (pl["Channel"] for pl in plan_by_order.get(o_name, []) if pl.get("Channel")), ""
        )
        route   = route_row(primary_channel_raw) or (None, None, None, None)
        channel = route[0] or ""

        orders.append({
            "Order ID":                   "",
            "Advertiser ID*":             get_default(defaults, "Advertiser ID"),
            "Advertiser name":            get_default(defaults, "Advertiser name"),
            "Order name*":                o_name,
            "Active/Inactive":            get_default(defaults, "Active/Inactive") or "Active",
            "PO number":                  brief.get("Campaign PO #", ""),
            "Media Type":                 media_types_for(o_name),
            "Goal and Goal KPI*":         goal_kpi_string(defaults, channel, lob),
            "Target KPI":                 get_default(defaults, "Target KPI", channel, lob),
            "Bidding Priority":           get_default(defaults, "Bidding Priority")
                                          or "Prioritize spending full budget",
            "Frequency group ID":         "",
            "Budget Management Strategy": get_default(defaults, "Budget Management Strategy")
                                          or "Automate budget allocation",
            "Frequency Caps":             build_frequency_caps(),
            "Flight budget and dates*":   order_budget_and_flight(o_name),
            "Budget Rollover":            get_default(defaults, "Budget Rollover")
                                          or "Do not change flight budgets",
            "Budget cap":                 "",
            "Agency fee":                 get_default(defaults, "Agency fee"),
            "Products":                   "",
            "Off-Amazon conversions":     "",
        })

    # ── LINE ITEMS ────────────────────────────────────────────────────────────
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
        camp_name     = (row.get("Campaign") or order_name)
        line_name     = build_line_name(camp_name, media_type, row)
        start, end    = parse_flight_dates(
            row.get("Flight", row.get("Creative Flight Date", "")),
            output_format="amazon"
        )
        final_aud_str = row.get("Audience", "") or audience_str

        budget = row.get("Budget", row.get("Est Media Cost", ""))
        try:
            budget_clean = float(str(budget).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            budget_clean = ""

        common = {
            "Line ID":               "",
            "Advertiser ID*":        get_default(defaults, "Advertiser ID"),
            "Advertiser name":       get_default(defaults, "Advertiser name"),
            "Order ID*":             camp_name,
            "Line type*":            line_type,
            "Line name*":            line_name,
            "External ID":           "",
            "Line start date":       start or "",
            "Line end date":         end or "",
            "Active/Inactive":       "Book/Deliver",
            "Product categories*":   get_default(defaults, "Product categories", media_type, lob),
            "Frequency Caps":        build_frequency_caps("3", "1", "Days"),
            "Supply source":         get_default(defaults, "Supply source", media_type, lob),
            "Audiences - include":   final_aud_str,
            "Reach similar audiences": "No",
            "Line item budget":      budget_clean,
            "Base supply bid*":      get_default(defaults, "Base supply bid", media_type, lob) or "5.00",
            "Maximum average CPM":   get_default(defaults, "Maximum average CPM", media_type, lob) or "15.00",
            "Creative ID":           row.get("Creative", ""),
        }

        if sheet == "display":
            display_line_items.append({
                **common,
                "Device type":          get_default(defaults, "Device type", media_type, lob)
                                        or "Desktop and mobile (web)",
                "Environment Type":     get_default(defaults, "Environment Type", media_type, lob)
                                        or "Both",
                "Pacing profile":       get_default(defaults, "Pacing profile") or "Evenly",
                "Automated optimization": "Yes",
            })
        elif sheet == "video":
            video_line_items.append({
                **common,
                "Video Ad Content Type*": vct,
                "Device type":           get_default(defaults, "Device type", media_type, lob)
                                         or "Desktop and mobile (web)",
                "Mobile environment":    get_default(defaults, "Mobile environment", media_type, lob),
                "Video initiation type": get_default(defaults, "Video initiation type", media_type, lob)
                                         or "Any",
                "In-stream position":    get_default(defaults, "In-stream position", media_type, lob),
                "Video player size":     get_default(defaults, "Video player size", media_type, lob) or "Any",
                "Video completion":      get_default(defaults, "Video completion", media_type, lob)
                                         or "No targeting",
                "Pacing profile":        get_default(defaults, "Pacing profile") or "Evenly",
                "Automated optimization": "Yes",
            })
        elif sheet == "audio":
            audio_line_items.append({
                **common,
                "Device type":               get_default(defaults, "Device type", media_type, lob)
                                             or "All devices (desktop, mobile, connected TV, smart speaker)",
                "Content and Genre Blocking": get_default(defaults, "Content and Genre Blocking"),
            })
        elif sheet == "podcast":
            podcast_keep = {
                "Line ID", "Advertiser ID*", "Advertiser name", "Order ID*",
                "Line type*", "Line name*", "External ID",
                "Line start date", "Line end date", "Active/Inactive",
                "Product categories*", "Frequency Caps", "Line item budget", "Creative ID",
            }
            podcast_row = {k: v for k, v in common.items() if k in podcast_keep}
            podcast_row.update({
                "Category Blocking": get_default(defaults, "Category Blocking"),
                "Content Blocking":  get_default(defaults, "Content Blocking")
                                     or "Exclude explicit content",
            })
            podcast_line_items.append(podcast_row)

    # ── CREATIVE ASSOCIATIONS ────────────────────────────────────────────────
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
        creative_associations.append({
            "Line ID":         "",
            "Line name":       build_line_name(camp_name, media_type, row),
            "Advertiser ID*":  get_default(defaults, "Advertiser ID"),
            "Advertiser name": get_default(defaults, "Advertiser name"),
            "Operation Type*": "Create",
            "Ad Creative Id*": creative,
            "Start Date":      "",
            "End Date":        "",
            "Active/Inactive": "Active",
            "Weight":          "",
        })

    # Apply platform defaults
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
