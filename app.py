import os
import json
import io
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import anthropic
import openpyxl

app = FastAPI()
templates = Jinja2Templates(directory="templates")
client = anthropic.Anthropic()

TTD_TEMPLATE_PATH = os.path.expanduser("~/Downloads/TTD BULKSHEET.xlsx")

TTD_SCHEMA = {
    "CampaignSets": [
        "IO ID", "Campaign Set ID", "Campaign Set Name"
    ],
    "Campaigns": [
        "Campaign Name", "Description", "Objective", "Primary Channel",
        "Goals", "Time Zone ID", "Pacing Mode", "IO Contract", "Campaign PO #"
    ],
    "Ad Groups": [
        "Ad Group Name", "Channel", "Goal Type", "Goal Value",
        "Base Bid", "Max Bid", "Marketplace", "Audience"
    ],
    "Budget Flights": [
        "Campaign", "Ad Group", "Flight Budget (in advertiser currency)",
        "Daily Spend Cap (in advertiser currency)", "Impression Budget",
        "Daily Impression Cap", "Start Date Inclusive UTC", "End Date Exclusive UTC", "Action"
    ],
    "Campaign Fees": ["Fee Name", "Value"],
    "Ad Group Fees": ["Ad Group Fee Name", "Value"]
}

SYSTEM_PROMPT = """You are an expert programmatic advertising specialist who translates media briefs into The Trade Desk (TTD) campaign bulk upload sheets.

You will receive data from 4 Excel input files:
1. Media Brief - campaign objectives, KPIs, targeting details, brand guidelines
2. Media Plan - channel breakdowns, flight dates, budgets, impressions, CPMs, DSP
3. Audience Matrix - audience segments, targeting types, segment descriptions, activation/suppression
4. Trafficking Sheet - campaign structure, creative details, flight information, city targeting

Map this data to the TTD bulk upload format and return valid JSON only."""


def excel_to_dict(file_bytes: bytes) -> dict:
    """Convert Excel file bytes to a dict of sheets -> rows."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    result = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        headers = None
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(row)]
            else:
                if any(cell is not None for cell in row):
                    row_dict = {headers[j]: v for j, v in enumerate(row) if v is not None}
                    if row_dict:
                        rows.append(row_dict)
        result[sheet_name] = {"headers": headers, "rows": rows}
    return result


def create_ttd_excel(ttd_data: dict) -> bytes:
    """Write mapped data into the TTD bulk upload template."""
    with open(TTD_TEMPLATE_PATH, "rb") as f:
        wb = openpyxl.load_workbook(io.BytesIO(f.read()))

    sheet_key_map = {
        "campaign_sets": "CampaignSets",
        "campaigns": "Campaigns",
        "ad_groups": "Ad Groups",
        "budget_flights": "Budget Flights",
        "campaign_fees": "Campaign Fees",
        "ad_group_fees": "Ad Group Fees"
    }

    for data_key, sheet_name in sheet_key_map.items():
        rows = ttd_data.get(data_key, [])
        if not rows or sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        headers = [cell.value for cell in ws[1]]
        for i, row_data in enumerate(rows, start=2):
            for j, header in enumerate(headers, start=1):
                if header in row_data:
                    ws.cell(row=i, column=j, value=row_data[header])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate_ttd(
    media_brief: UploadFile = File(...),
    media_plan: UploadFile = File(...),
    audience_matrix: UploadFile = File(...),
    trafficking_sheet: UploadFile = File(...)
):
    # Read and parse all 4 input files
    files_data = {}
    for label, upload in [
        ("Media Brief", media_brief),
        ("Media Plan", media_plan),
        ("Audience Matrix", audience_matrix),
        ("Trafficking Sheet", trafficking_sheet),
    ]:
        content = await upload.read()
        files_data[label] = excel_to_dict(content)

    prompt = f"""Here is the data extracted from the 4 input files:

{json.dumps(files_data, indent=2, default=str)}

Map this to the TTD bulk upload format. Return a JSON object with exactly these keys:
- campaign_sets: list of row dicts for CampaignSets tab
- campaigns: list of row dicts for Campaigns tab
- ad_groups: list of row dicts for Ad Groups tab
- budget_flights: list of row dicts for Budget Flights tab
- campaign_fees: list of row dicts for Campaign Fees tab (empty list if none)
- ad_group_fees: list of row dicts for Ad Group Fees tab (empty list if none)

TTD field names to use (skip any marked [Read Only]):
{json.dumps(TTD_SCHEMA, indent=2)}

Field mapping guidance:
- Skip all fields marked [Read Only] — TTD populates these automatically
- Time Zone ID: use "Eastern Time (US & Canada)" unless specified otherwise
- Pacing Mode: "Even" unless otherwise specified
- Dates (Start Date Inclusive UTC / End Date Exclusive UTC): format as "YYYY-MM-DD 00:00:00"
- Goal Type: map KPIs to TTD values (e.g. CPC, CPM, CPA, ROAS, VCR)
- Base Bid / Max Bid: dollar amounts in CPM
- Action (Budget Flights): "New" for new line items
- Each line in the Media Plan that targets TTD should become its own Ad Group and Budget Flight row
- Use audience segment names from the Audience Matrix in the Ad Group Audience field

Return ONLY valid JSON with no markdown, no explanation."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = next(b.text for b in response.content if b.type == "text")

    # Strip markdown code fences if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    ttd_data = json.loads(response_text)
    excel_bytes = create_ttd_excel(ttd_data)

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=TTD_Campaign_Bulk_Upload.xlsx"}
    )
