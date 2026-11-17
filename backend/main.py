import re
import json
import traceback
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from backend.agents.research_agent import run_professor_research
from backend.integrations.whatsapp_sender import send_whatsapp_message
from backend.tools.conference_tool import search_conferences, parse_date


BASE_DIR = Path(__file__).resolve().parent
PROFILE_PATH = BASE_DIR / "profiles" / "professor_001.json"
LATEST_RESEARCH_FILE = BASE_DIR / "data" / "latest_research.json"
LATEST_RESEARCH_FILE.parent.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# SCHEDULE & COOLDOWN CONFIGURATION
# --------------------------------------------------
MANUAL_COOLDOWN_HOURS = 24       # Change to e.g. 0.01 (~36 sec) for live demos, or 24 for production
WEEKLY_SCHEDULE_DAY = "mon"      # "mon", "tue", "wed", "thu", "fri", "sat", "sun"
WEEKLY_SCHEDULE_HOUR = 9         # 0–23 (24-hour clock)
WEEKLY_SCHEDULE_MINUTE = 0       # 0–59


# --------------------------------------------------
# PROFESSOR PROFILE
# --------------------------------------------------

def load_professor_profile():

    with open(PROFILE_PATH, "r", encoding="utf-8") as file:
        profile = json.load(file)

    interests = profile.get("research_interests", [])

    if isinstance(interests, str):
        interests = [interests]

    return profile, interests


# --------------------------------------------------
# CONFERENCE RELEVANCE
# --------------------------------------------------

def calculate_relevance(conference, interests):

    interest_text = " ".join(interests).lower()

    title = str(conference.get("title") or "").lower()
    track = str(conference.get("track") or "").lower()

    searchable_text = f"{title} {track}"

    interest_areas = {
        "Artificial Intelligence": {
            "enabled": "artificial intelligence" in interest_text
                       or " ai" in interest_text,
            "keywords": [
                "aaai", "ijcai", "ecai", "pricai",
                "dai", "artificial intelligence"
            ]
        },
        "AI Agents": {
            "enabled": "agent" in interest_text,
            "keywords": [
                "aamas", "agent", "multi-agent",
                "multi agent", "agentic"
            ]
        },
        "Machine Learning": {
            "enabled": "machine learning" in interest_text,
            "keywords": [
                "icml", "iclr", "neurips", "aistats",
                "colt", "ijcnn", "esann",
                "machine learning"
            ]
        },
        "Natural Language Processing": {
            "enabled": "natural language processing" in interest_text
                       or "nlp" in interest_text,
            "keywords": [
                "acl", "naacl", "eacl", "emnlp",
                "coling", "nlp",
                "natural language processing"
            ]
        },
        "Large Language Models": {
            "enabled": "large language model" in interest_text
                       or "llm" in interest_text,
            "keywords": [
                "llm", "large language model",
                "language model", "acl", "naacl",
                "eacl", "emnlp"
            ]
        }
    }

    matched = []

    for area, config in interest_areas.items():

        if not config["enabled"]:
            continue

        for keyword in config["keywords"]:

            if keyword.isalpha() and len(keyword) <= 6:
                found = re.search(
                    rf"\b{re.escape(keyword)}\b",
                    searchable_text
                )
            else:
                found = keyword in searchable_text

            if found:
                matched.append(area)
                break

    matched = list(dict.fromkeys(matched))

    if len(matched) >= 2:
        score = 95
        level = "Very high"

    elif len(matched) == 1:
        score = 80
        level = "High"

    else:
        score = 0
        level = "Needs further review"

    return {
        "relevance_score": score,
        "relevance_level": level,
        "matched_interests": matched
    }


# --------------------------------------------------
# CONFERENCE CALENDAR
# --------------------------------------------------

def get_conference_calendar(records, interests, today, horizon):

    grouped = {}

    for record in records:

        event_date = (
            parse_date(record.get("start"))
            or parse_date(record.get("conference_date"))
        )

        if not event_date:
            continue

        if not (today <= event_date <= horizon):
            continue

        title = str(record.get("title") or "").strip()
        year = str(record.get("year") or "")

        key = (
            re.sub(r"[^a-z0-9]", "", title.lower()),
            year
        )

        if key not in grouped:

            grouped[key] = {
                "title": title,
                "year": year,
                "conference_date": record.get("conference_date"),
                "event_start": record.get("start"),
                "event_end": record.get("end"),
                "event_date": event_date.isoformat(),
                "location": record.get("city"),
                "website": record.get("link"),
                "rankings": record.get("rankings"),
                "sources": [],
                "date_variants": [],
                "submission_deadlines": []
            }

        item = grouped[key]

        if record.get("source") not in item["sources"]:
            item["sources"].append(record["source"])

        variant = {
            "conference_date": record.get("conference_date"),
            "location": record.get("city"),
            "source": record.get("source")
        }

        if variant not in item["date_variants"]:
            item["date_variants"].append(variant)

        if not item["website"] and record.get("link"):
            item["website"] = record["link"]

        if not item["rankings"] and record.get("rankings"):
            item["rankings"] = record["rankings"]

        if record.get("deadline"):

            deadline_item = {
                "type": record.get("deadline_type"),
                "label": record.get("deadline_label"),
                "deadline": record.get("deadline"),
                "status": record.get("status"),
                "track": record.get("track"),
                "source": record.get("source")
            }

            if deadline_item not in item["submission_deadlines"]:
                item["submission_deadlines"].append(deadline_item)

    results = list(grouped.values())

    for item in results:

        item["submission_deadlines"].sort(
            key=lambda x: x.get("deadline") or "9999"
        )

        item["relevance"] = calculate_relevance(
            item, interests
        )

        future_deadlines = [
            x for x in item["submission_deadlines"]
            if x["status"] == "Upcoming submission deadline"
        ]

        if future_deadlines:
            item["submission_status"] = "Upcoming deadline"

        elif item["submission_deadlines"]:
            item["submission_status"] = "Deadline passed"

        else:
            item["submission_status"] = "No deadline listed"

    results.sort(
        key=lambda x: (
            -x["relevance"]["relevance_score"],
            x["event_date"]
        )
    )

    return results


# --------------------------------------------------
# CFP DEADLINES
# --------------------------------------------------

def get_upcoming_cfp_deadlines(records, interests):

    results = []

    for record in records:

        if record.get("status") != "Upcoming submission deadline":
            continue

        item = dict(record)

        item["relevance"] = calculate_relevance(
            item, interests
        )

        results.append(item)

    results.sort(
        key=lambda x: x.get("deadline") or "9999"
    )

    return results


# --------------------------------------------------
# TEXT EXTRACTION & WHATSAPP DIGEST FORMATTING
# --------------------------------------------------

def extract_section(analysis, start_pattern, end_pattern):

    match = re.search(
        rf"{start_pattern}(.*?){end_pattern}",
        analysis,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(1).strip()

    return "Section not available in the research report."


def clean_wa_param(text: str, max_len: int = 240) -> str:
    """Meta template parameters reject newlines/tabs and >4 consecutive spaces."""
    cleaned = re.sub(r"[\r\n\t]+", " ", str(text or ""))
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned[:max_len - 3].rstrip() + "..." if len(cleaned) > max_len else cleaned


def get_top_deadlines_text(interests, max_items=3):
    try:
        records = search_conferences(limit=500, horizon_days=365)
        deadlines = get_upcoming_cfp_deadlines(records, interests)
        deadlines.sort(
            key=lambda x: (
                -x.get("relevance", {}).get("relevance_score", 0),
                x.get("deadline") or "9999"
            )
        )
        top = deadlines[:max_items]
        if not top:
            return ""
        items = []
        for d in top:
            due = str(d.get("deadline") or "")[:10]
            url = d.get("website") or d.get("link") or d.get("url") or ""
            label = f"{d.get('title')} ({due})"
            if url:
                label += f" {url}"
            items.append(label)
        return clean_wa_param(" | ".join(items), max_len=300)
    except Exception:
        return ""


def format_whatsapp_digest(result: dict, interests: list[str]) -> tuple[str, str, str]:
    papers = result.get("papers") or []
    paper_links = []
    for i, p in enumerate(papers[:3], 1):
        title = str(p.get("title") or "Paper").strip()
        if len(title) > 45:
            title = title[:42].rstrip() + "..."
        link = p.get("doi") or p.get("url") or p.get("link") or ""
        paper_links.append(f"{i}) {title} {link}".strip())

    findings = clean_wa_param(
        " | ".join(paper_links) if paper_links else "New papers ready on dashboard.",
        max_len=320
    )

    analysis = result.get("analysis") or ""
    raw_idea = extract_section(
        analysis,
        r"##\s*3\.\s*Proposed Research Idea",
        r"##\s*4\.\s*Limitations"
    )
    first_line = next(
        (line.strip("-*# ") for line in raw_idea.splitlines() if line.strip()),
        "New research idea ready."
    )
    idea = clean_wa_param(f"{first_line} | Dashboard: http://127.0.0.1:8000", max_len=240)
    deadlines = get_top_deadlines_text(interests, max_items=3)

    return findings, idea, deadlines


# --------------------------------------------------
# PERSISTENCE & CORE EXECUTION
# --------------------------------------------------

def save_latest_research(payload: dict):
    with open(LATEST_RESEARCH_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_latest_research() -> dict | None:
    if not LATEST_RESEARCH_FILE.exists():
        return None
    try:
        with open(LATEST_RESEARCH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def execute_and_persist_research(trigger_type: str = "manual") -> dict:
    """
    Runs the research agent, sends the short link-rich WhatsApp digest,
    and persists the result with trigger metadata ('weekly_auto' or 'manual').
    """
    result = run_professor_research("professor_001")
    analysis = result["analysis"]

    topic = clean_wa_param(", ".join(result["research_interests"]), max_len=120)
    findings, proposed_idea, deadlines_summary = format_whatsapp_digest(
        result, result["research_interests"]
    )

    try:
        whatsapp_result = send_whatsapp_message(
            topic=topic,
            findings=findings,
            idea=proposed_idea,
            deadlines_summary=deadlines_summary
        )
        whatsapp_status = "sent"
    except Exception as whatsapp_error:
        print(f"[WhatsApp Error] {whatsapp_error}")
        whatsapp_status = "failed"
        whatsapp_result = str(whatsapp_error)

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "status": "success",
        "trigger_type": trigger_type,
        "last_updated": now_iso,
        "last_manual_at": now_iso if trigger_type == "manual" else (
            (load_latest_research() or {}).get("last_manual_at")
        ),
        "professor": result["professor"],
        "research_interests": result["research_interests"],
        "analysis": analysis,
        "papers": result["papers"],
        "whatsapp_status": whatsapp_status,
        "whatsapp_result": whatsapp_result
    }
    save_latest_research(payload)
    return payload


# --------------------------------------------------
# WEEKLY STANDALONE SCHEDULER
# --------------------------------------------------

scheduler = BackgroundScheduler()


def scheduled_weekly_job():
    print("[Scheduler] Running weekly standalone research & WhatsApp briefing...")
    try:
        execute_and_persist_research(trigger_type="weekly_auto")
        print("[Scheduler] Weekly briefing completed and saved.")
    except Exception as e:
        print(f"[Scheduler] Weekly job failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        scheduled_weekly_job,
        "cron",
        day_of_week=WEEKLY_SCHEDULE_DAY,
        hour=WEEKLY_SCHEDULE_HOUR,
        minute=WEEKLY_SCHEDULE_MINUTE,
        id="weekly_radar"
    )
    scheduler.start()
    yield
    scheduler.shutdown()


# --------------------------------------------------
# FASTAPI APP INITIALIZATION
# --------------------------------------------------

app = FastAPI(
    title="ResearchRadar AI",
    description="AI Research Assistant",
    version="1.0.0",
    lifespan=lifespan
)


# --------------------------------------------------
# HEALTH
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "application": "ResearchRadar AI"
    }


# --------------------------------------------------
# RESEARCH & WHATSAPP API
# --------------------------------------------------

@app.get("/api/research/latest")
def get_latest_research():
    cached = load_latest_research()
    if not cached:
        return {"status": "empty"}
    return cached


@app.post("/api/research/run")
def run_research():
    try:
        cached = load_latest_research()
        last_manual_str = (cached or {}).get("last_manual_at")

        if cached and last_manual_str:
            last_dt = datetime.fromisoformat(last_manual_str)
            cooldown = timedelta(hours=MANUAL_COOLDOWN_HOURS)
            elapsed = datetime.now(timezone.utc) - last_dt
            if elapsed < cooldown:
                remaining_sec = int((cooldown - elapsed).total_seconds())
                wait_label = (
                    f"~{max(1, remaining_sec // 3600)}h"
                    if remaining_sec >= 3600
                    else f"{max(1, remaining_sec)}s"
                )
                return {
                    **cached,
                    "status": "rate_limited",
                    "message": f"Cannot run again within {MANUAL_COOLDOWN_HOURS}h. Try again in {wait_label}."
                }

        return execute_and_persist_research(trigger_type="manual")

    except Exception as error:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/whatsapp/send-briefing")
def send_manual_whatsapp_briefing():
    try:
        profile, interests = load_professor_profile()
        topic = clean_wa_param(", ".join(interests), max_len=120)
        deadlines_summary = get_top_deadlines_text(interests)

        whatsapp_result = send_whatsapp_message(
            topic=topic,
            findings=clean_wa_param("ResearchRadar AI check: monitoring recent papers and emerging trends."),
            idea=clean_wa_param("Ready for targeted submission to upcoming top AI/NLP venues."),
            deadlines_summary=deadlines_summary
        )

        return {
            "status": "sent",
            "deadlines_included": deadlines_summary,
            "whatsapp_result": whatsapp_result
        }
    except Exception as error:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(error))


# --------------------------------------------------
# CONFERENCE API
# --------------------------------------------------

@app.get("/api/conferences")
def get_conferences(
    event_horizon_days: int = Query(default=180, ge=1, le=730),
    deadline_horizon_days: int = Query(default=365, ge=1, le=730)
):

    try:

        today = date.today()

        event_horizon = today + timedelta(
            days=event_horizon_days
        )

        deadline_horizon = today + timedelta(
            days=deadline_horizon_days
        )

        profile, interests = load_professor_profile()

        # Retrieve opportunities using the longer window.
        records = search_conferences(
            limit=500,
            horizon_days=deadline_horizon_days
        )

        upcoming_conferences = get_conference_calendar(
            records,
            interests,
            today,
            event_horizon
        )

        upcoming_deadlines = get_upcoming_cfp_deadlines(
            records,
            interests
        )

        return {
            "status": "success",
            "professor": profile.get("name"),
            "research_interests": interests,
            "generated_on": today.isoformat(),

            "event_window": {
                "from": today.isoformat(),
                "to": event_horizon.isoformat(),
                "days": event_horizon_days
            },

            "deadline_window": {
                "from": today.isoformat(),
                "to": deadline_horizon.isoformat(),
                "days": deadline_horizon_days
            },

            "summary": {
                "upcoming_conferences": len(upcoming_conferences),
                "upcoming_cfp_deadlines": len(upcoming_deadlines)
            },

            "upcoming_conferences": upcoming_conferences,
            "upcoming_cfp_deadlines": upcoming_deadlines
        }

    except Exception as error:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------

FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent / "frontend"
)

app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True
    ),
    name="frontend"
)