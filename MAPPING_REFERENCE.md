# TTD Bulk Upload — Field Mapping Reference

Cross-check this document against `mapper.py` to verify all rules are correct.
Update `defaults.json` to change default values without touching code.

**Legend**
- ✅ Mapped from source document
- 🔵 Pulled from `defaults.json`
- ⬜ Left blank (TTD populates automatically or not available in source)
- 🚫 Read Only — TTD populates, never written

---

## Campaign Sets tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| IO ID | ✅ | Media Brief | `Brief ID` | Direct copy. Blank if missing. |
| Campaign Set ID | 🚫 | — | — | Read Only |
| Campaign Set Name | ✅ | Trafficking Sheet | `Campaign` (first row) | First unique Campaign value. Fallback: LOB + Product/Service from Media Brief. |
| Advertiser | 🚫 | — | — | Read Only |

---

## Campaigns tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| Campaign ID | 🚫 | — | — | Read Only |
| Campaign Name | ✅ | Trafficking Sheet | `Campaign` | All unique Campaign values become separate campaign rows. Fallback: `LOB` + `Product/Service` from Media Brief. |
| Advertiser | 🚫 | — | — | Read Only |
| Description | ✅ | Media Brief | `Media Objectives` | Falls back to `Communications Objective` if blank. |
| Objective | 🔵 | defaults.json | `by_lob_and_channel` → `by_channel` → `by_lob` | Most specific LOB+Channel match wins. |
| Primary Channel | 🔵 | defaults.json | `by_channel[channel]["Primary Channel"]` | Derived from the first Channel in the Media Plan. |
| Goals | 🔵 | defaults.json | `by_lob[lob]["Goals"]` | LOB-level goal type. |
| Time Zone ID | 🔵 | defaults.json | `global["Time Zone ID"]` | Default: `Eastern Time (US & Canada)` |
| Pacing Mode | 🔵 | defaults.json | `global["Pacing Mode"]` | Default: `Even` |
| Manually Prioritize Ad Groups | 🔵 | defaults.json | `global` | Default: `No` |
| Comscore Settings | ⬜ | — | — | Not in source documents |
| Comscore CCR Settings | ⬜ | — | — | Not in source documents |
| Nielsen Settings | ⬜ | — | — | Not in source documents |
| Reporting and Attribution | ⬜ | — | — | Not in source documents |
| Custom CPA Calculation | ⬜ | — | — | Not in source documents |
| Custom CPA Pixels and Weights | ⬜ | — | — | Not in source documents |
| iSpot Settings | ⬜ | — | — | Not in source documents |
| IO Contract | ✅ | Media Brief | `Brief ID` | Same as IO ID — Brief ID used as contract reference. |
| Campaign PO # | ⬜ | — | — | Not in source documents |
| Custom ROAS Type | ⬜ | — | — | Not in source documents |
| Custom ROAS Pixels and Weights | ⬜ | — | — | Not in source documents |
| Frequency Group | 🚫 | — | — | Read Only |
| Innovid Settings | ⬜ | — | — | Not in source documents |
| Realytics Settings | ⬜ | — | — | Not in source documents |
| Campaign Seed | ⬜ | — | — | Not in source documents |

---

## Ad Groups tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| Ad Group ID | 🚫 | — | — | Read Only |
| Ad Group Name | ✅ | Media Plan / Trafficking | `Campaign \| Channel \| Partner/Tactic` | Pipe-delimited: Campaign name + Channel + Tactic. Built from Media Plan rows (TTD-only). Fallback: Trafficking Sheet. |
| Campaign | 🚫 | — | — | Read Only (links to Campaign tab) |
| Description | ✅ | Trafficking Sheet | `Tactic` | Tactic value used as description. |
| Status | 🚫 | — | — | Read Only |
| Channel | ✅ | Media Plan / Trafficking | `Channel` | Normalised to TTD channel names via `CHANNEL_MAP`. See channel aliases below. |
| Labels | ⬜ | — | — | Not in source documents |
| Goal Type | 🔵 | defaults.json | `by_lob_and_channel` → `by_channel` → `by_lob` | Most specific match wins. E.g. Auto + CTV = VCR. |
| Goal Value | 🔵 | defaults.json | `by_lob_and_channel` → `by_channel` | Numeric target value for the Goal Type. |
| GRP Overall Frequency | ⬜ | — | — | Not in source documents |
| Base Bid | 🔵 | defaults.json | `by_lob_and_channel` → `by_channel` | CPM dollar amount. |
| Max Bid | 🔵 | defaults.json | `by_lob_and_channel` → `by_channel` | CPM dollar amount. |
| Priority | 🔵 | defaults.json | `global["Priority"]` | Default: `Medium` |
| Predictive Clearing Enabled | 🔵 | defaults.json | `global` | Default: `Yes` |
| Auto Enable Upcoming Features | 🔵 | defaults.json | `global` | Default: `No` |
| Marketplace | 🔵 | defaults.json | `by_channel[channel]["Marketplace"]` | CTV/DOOH default to Private Marketplace. Others default to Open Exchange. |
| Audience | ✅ | Audience Matrix + Media Plan | `Segment Description` (activation rows) | All activation segments for TTD platform, semi-colon separated. Media Plan `Audience` field used if populated. |
| Audience Excluder | ✅ | Audience Matrix | `Segment Description` (suppression rows) | All suppression segments for TTD platform. |
| Cross Device | ⬜ | — | — | Not in source documents |
| Creatives | ✅ | Trafficking Sheet | `Creative` | Creative name from trafficking row. |
| KOA Optimizations | ⬜ | — | — | Not in source documents |
| Funnel Location | ⬜ | — | — | Not in source documents |
| Viewability Suite (Quality Alliance) | ⬜ | — | — | Not in source documents |

---

## Budget Flights tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| Flight ID | 🚫 | — | — | Read Only |
| Campaign | ✅ | Trafficking / Media Plan | `Campaign` | Links flight to campaign by name. |
| Ad Group | ✅ | Trafficking / Media Plan | derived | Matches the Ad Group Name built above. |
| Flight Budget (in advertiser currency) | ✅ | Media Plan | `Budget` | Total flight budget for TTD line. Fallback: `Est Media Cost`. |
| [Kokai Only] Ad Group Allocated Budget | ⬜ | — | — | Not used |
| Daily Spend Cap (in advertiser currency) | ⬜ | — | — | Not in source documents — calculated manually post-export |
| Impression Budget | ✅ | Media Plan | `Planned Impressions` | Direct copy. |
| Daily Impression Cap | ⬜ | — | — | Not in source documents |
| Start Date Inclusive UTC | ✅ | Media Plan | `Flight` (start) | Parsed from flight date range. Fallback: Trafficking `Creative Flight Date`. Format: `YYYY-MM-DD 00:00:00` |
| End Date Exclusive UTC | ✅ | Media Plan | `Flight` (end) | Parsed from flight date range end. Format: `YYYY-MM-DD 00:00:00` |
| Action | 🔵 | defaults.json | `global["Action"]` | Always `New` for new line items. |
| Geography Targets | 🚫 | — | — | Read Only |
| Channel | 🚫 | — | — | Read Only |

---

## Campaign Fees tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| Fee ID | 🚫 | — | — | Read Only |
| Fee Card ID | 🚫 | — | — | Read Only |
| Campaign ID | 🚫 | — | — | Read Only |
| Campaign Name | 🚫 | — | — | Read Only |
| Start Date (UTC) | 🚫 | — | — | Read Only |
| Status | 🚫 | — | — | Read Only |
| Fee Name | ⬜ | — | — | Not in source documents — add manually post-export |
| Fee Type | 🚫 | — | — | Read Only |
| Value | ⬜ | — | — | Not in source documents — add manually post-export |

---

## Ad Group Fees tab

| TTD Field | Status | Source | Source Field | Rule |
|-----------|--------|--------|--------------|------|
| Ad Group Fee ID | 🚫 | — | — | Read Only |
| Ad Group Fee Card ID | 🚫 | — | — | Read Only |
| Ad Group ID | 🚫 | — | — | Read Only |
| Ad Group Name | 🚫 | — | — | Read Only |
| Start Date (UTC) | 🚫 | — | — | Read Only |
| Status | 🚫 | — | — | Read Only |
| Ad Group Fee Name | ⬜ | — | — | Not in source documents — add manually post-export |
| Ad Group Fee Type | 🚫 | — | — | Read Only |
| Value | ⬜ | — | — | Not in source documents — add manually post-export |

---

## Channel Aliases (CHANNEL_MAP)

These source values are normalised to TTD channel names:

| Source Value | → TTD Channel |
|---|---|
| ctv, connected tv, streaming tv | CTV |
| olv, online video, pre-roll | OLV |
| display, banner | Display |
| native | Native |
| audio, streaming audio | Audio |
| dooh, out of home, digital ooh | DOOH |

> If a channel value isn't in this list, it is passed through unchanged. Add entries to `CHANNEL_MAP` in `mapper.py` as needed.

---

## LOB Detection Order

1. Media Brief → `LOB:` field
2. Media Brief → `LOB/Corporate Function` field
3. Trafficking Sheet → `Campaign Key` column
4. Blank if none found

---

## Fields NOT in any source document (require manual entry post-export)

- Campaign PO #
- Daily Spend Cap
- Daily Impression Cap
- Comscore / Nielsen / iSpot settings
- Frequency Group
- Cross Device
- KOA Optimizations
- Funnel Location
- Viewability Suite
- Campaign Fees (Fee Name, Value)
- Ad Group Fees (Ad Group Fee Name, Value)
- Innovid / Realytics Settings

---

## Media Plan DSP filter

Only rows where the `DSP` column matches one of these values are included:
`TTD`, `The Trade Desk`, `TradeDesk`, `Trade Desk` (case-insensitive)
