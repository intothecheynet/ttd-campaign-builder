"""
Rule-based TTD campaign mapper.

Platform: The Trade Desk (TTD) ONLY
Shared parsing utilities: shared_utils.py

Takes parsed Excel data for all 4 input files and returns TTD bulk upload
data ready for the CampaignSets / Campaigns / Ad Groups / Budget Flights tabs.
"""

import json
import os
from datetime import datetime

from .shared_utils import (
    CHANNEL_MAP, normalise_channel,
    parse_media_brief, parse_media_plan, parse_trafficking_sheet,
    extract_lob, build_campaign_name,
    apply_platform_defaults, get_default,
    parse_flight_dates,
)

_DIR = os.path.dirname(__file__)
DEFAULTS_PATH          = os.path.join(_DIR, "ttd_defaults.json")
PLATFORM_DEFAULTS_PATH = os.path.join(_DIR, "ttd_platform_defaults.json")

# DSP column values that route rows to TTD
TTD_DSP_NAMES = {"ttd"}


# ── Audience Matrix ───────────────────────────────────────────────────────────

def parse_audience_matrix(sheet_data: dict) -> list:
    """Returns audience segments intended for TTD activation/suppression."""
    rows = sheet_data.get("Sheet1", {}).get("rows", [])
    segments = []
    for row in rows:
        platform  = str(row.get("Platform Name", "")).strip().lower()
        indicator = str(row.get("Activation/Suppression Indicator", "")).strip().lower()
        if (platform in ("", "ttd", "the trade desk", "tradedesk")
                or "ttd" in platform or "trade desk" in platform):
            segments.append({
                "segment": row.get("Segment Description", ""),
                "type":    row.get("Targeting Typ", ""),
                "action":  indicator,
                "source":  row.get("Data Source", ""),
            })
    return segments


def audience_string(segments: list, action: str = "activation") -> str:
    """Build a semicolon-separated audience string for TTD."""
    names = [s["segment"] for s in segments
             if s["action"].lower() == action.lower() and s["segment"]]
    return "; ".join(names)


# ── Defaults ──────────────────────────────────────────────────────────────────

def load_defaults() -> dict:
    with open(DEFAULTS_PATH) as f:
        return json.load(f)


def load_platform_defaults() -> dict:
    with open(PLATFORM_DEFAULTS_PATH) as f:
        return json.load(f)


# ── TTD-specific name builders ────────────────────────────────────────────────

def build_ad_group_name(row: dict) -> str:
    """Ad Group name = Campaign | Channel | Tactic | Audience."""
    parts = [
        row.get("Campaign", ""),
        row.get("Channel", ""),
        row.get("Tactic", ""),
        row.get("Audience", ""),
    ]
    return " | ".join(p for p in parts if p)


# ── Main mapping function ─────────────────────────────────────────────────────

def map_to_ttd(files_data: dict) -> dict:
    """
    Entry point. Takes parsed Excel data for all 4 input files.
    Returns TTD bulk upload data dict.
    """
    defaults = load_defaults()
    platform = load_platform_defaults()

    brief       = parse_media_brief(files_data.get("Media Brief", {}))
    plan_lines  = parse_media_plan(files_data.get("Media Plan", {}), TTD_DSP_NAMES)
    audiences   = parse_audience_matrix(files_data.get("Audience Matrix", {}))
    trafficking = parse_trafficking_sheet(files_data.get("Trafficking Sheet", {}))

    lob           = extract_lob(brief, trafficking[0] if trafficking else None)
    campaign_name = build_campaign_name(brief, trafficking)
    audience_str  = audience_string(audiences, "activation")
    excluder_str  = audience_string(audiences, "suppression")

    # ── CAMPAIGN SETS ────────────────────────────────────────────────────────
    campaign_sets = [{
        "IO ID":             brief.get("Brief ID", ""),
        "Campaign Set Name": campaign_name,
    }]

    # ── CAMPAIGNS ────────────────────────────────────────────────────────────
    unique_campaigns = (
        list({r.get("Campaign", campaign_name) for r in trafficking})
        if trafficking else [campaign_name]
    )

    campaigns = []
    for camp_name in unique_campaigns:
        primary_channel_raw = next(
            (pl.get("Channel", "") for pl in plan_lines if pl.get("Channel")), ""
        )
        channel = normalise_channel(primary_channel_raw) if primary_channel_raw else ""

        campaigns.append({
            "Campaign Name":                 camp_name,
            "Description":                   brief.get("Media Objectives",
                                             brief.get("Communications Objective", "")),
            "Objective":                     get_default(defaults, "Objective", channel, lob),
            "Primary Channel":               get_default(defaults, "Primary Channel", channel, lob),
            "Goals":                         get_default(defaults, "Goals", channel, lob),
            "Time Zone ID":                  get_default(defaults, "Time Zone ID"),
            "Pacing Mode":                   get_default(defaults, "Pacing Mode", channel, lob),
            "Manually Prioritize Ad Groups": get_default(defaults, "Manually Prioritize Ad Groups"),
            "IO Contract":                   brief.get("Brief ID", ""),
            "Campaign PO #":                 brief.get("Campaign PO #", ""),
        })

    # ── AD GROUPS ────────────────────────────────────────────────────────────
    ad_groups = []
    source_rows = plan_lines if plan_lines else trafficking

    for row in source_rows:
        raw_channel    = row.get("Channel", "")
        channel        = normalise_channel(raw_channel)
        camp_name      = row.get("Campaign", campaign_name)
        row_audience   = row.get("Audience", "")
        final_audience = row_audience if row_audience else audience_str

        if plan_lines:
            ag_name = (f"{camp_name} | {channel} | "
                       f"{row.get('Partner/Tactic', row.get('Tactic', ''))}")
        else:
            ag_name = build_ad_group_name(row)

        ad_groups.append({
            "Ad Group Name":                  ag_name,
            "Channel":                        channel,
            "Goal Type":                      get_default(defaults, "Goal Type", channel, lob),
            "Goal Value":                     get_default(defaults, "Goal Value", channel, lob),
            "Base Bid":                       get_default(defaults, "Base Bid", channel, lob),
            "Max Bid":                        get_default(defaults, "Max Bid", channel, lob),
            "Priority":                       get_default(defaults, "Priority"),
            "Predictive Clearing Enabled":    get_default(defaults, "Predictive Clearing Enabled"),
            "Auto Enable Upcoming Features":  get_default(defaults, "Auto Enable Upcoming Features"),
            "Marketplace":                    get_default(defaults, "Marketplace", channel, lob),
            "Audience":                       final_audience,
            "Audience Excluder":              excluder_str,
        })

    # ── BUDGET FLIGHTS ───────────────────────────────────────────────────────
    budget_flights = []
    source_rows = plan_lines if plan_lines else trafficking

    for row in source_rows:
        raw_channel = row.get("Channel", "")
        channel     = normalise_channel(raw_channel)
        camp_name   = row.get("Campaign", campaign_name)

        if plan_lines:
            ag_name = f"{camp_name} | {channel} | {row.get('Partner/Tactic', '')}"
        else:
            ag_name = build_ad_group_name(row)

        flight_raw = row.get("Flight", row.get("Creative Flight Date", ""))
        start_date, end_date = parse_flight_dates(flight_raw, output_format="ttd")

        budget_flights.append({
            "Campaign":                                  camp_name,
            "Ad Group":                                  ag_name,
            "Flight Budget (in advertiser currency)":    row.get("Budget",
                                                         row.get("Est Media Cost", "")),
            "Daily Spend Cap (in advertiser currency)":  "",
            "Impression Budget":                         row.get("Planned Impressions", ""),
            "Daily Impression Cap":                      "",
            "Start Date Inclusive UTC":                  start_date or "",
            "End Date Exclusive UTC":                    end_date or "",
            "Action":                                    get_default(defaults, "Action"),
        })

    campaigns      = [apply_platform_defaults(r, "campaigns",      platform) for r in campaigns]
    ad_groups      = [apply_platform_defaults(r, "ad_groups",      platform) for r in ad_groups]
    budget_flights = [apply_platform_defaults(r, "budget_flights", platform) for r in budget_flights]

    return {
        "campaign_sets":  campaign_sets,
        "campaigns":      campaigns,
        "ad_groups":      ad_groups,
        "budget_flights": budget_flights,
        "campaign_fees":  list(platform.get("campaign_fees", [])),
        "ad_group_fees":  list(platform.get("ad_group_fees", [])),
    }
