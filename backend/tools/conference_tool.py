
import re
import requests
import yaml
import io
import zipfile

from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


# --------------------------------------------------
# SOURCES
# --------------------------------------------------

HF_API = (
    "https://api.github.com/repos/"
    "huggingface/ai-deadlines/contents/src/data/conferences"
)

HF_RAW = (
    "https://raw.githubusercontent.com/"
    "huggingface/ai-deadlines/main/src/data/conferences/"
)

CCF_API = (
    "https://api.github.com/repos/"
    "ccfddl/ccf-deadlines/contents/conference"
)

CCF_RAW = (
    "https://raw.githubusercontent.com/"
    "ccfddl/ccf-deadlines/main/conference/"
)

CCF_CATEGORIES = ["AI", "DS", "DB", "SE", "SC", "NW"]

HEADERS = {"User-Agent": "ResearchRadarAI/1.0"}

SUBMISSION_TYPES = {"abstract", "paper", "submission"}

KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "natural language processing",
    "large language model",
    "language model",
    "llm",
    "agent",
    "data mining",
    "data science",
    "information retrieval",
    "knowledge representation",
    "neural network",
    "computer vision",
    "robotics",
    "multi-agent",
    "software engineering",
    "cybersecurity",
    "network intelligence",
    "internet of things",
    "database",
    "recommender",
    "computational linguistics",
]


# --------------------------------------------------
# DATE UTILITIES
# --------------------------------------------------


def parse_date(value):
    """Parse the START date from ISO and human-readable date ranges."""
    if not value:
        return None

    text = str(value).strip()

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    month_pattern = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    )

    match = re.search(
        rf"\b(?P<month>{month_pattern})\s+"
        r"(?P<day>\d{1,2})"
        rf"(?:\s*[-–]\s*(?:(?P<end_month>{month_pattern})\s*)?"
        r"(?P<end_day>\d{1,2}))?"
        r",?\s+(?P<year>\d{4})\b",
        text,
        re.IGNORECASE
    )

    if match:
        try:
            return datetime.strptime(
                f"{match.group('month')[:3]} "
                f"{match.group('day')} "
                f"{match.group('year')}",
                "%b %d %Y"
            ).date()
        except ValueError:
            pass

    match = re.search(
        r"\b(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})",
        text,
        re.IGNORECASE
    )

    if match:
        try:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)}",
                "%d %B %Y"
            ).date()
        except ValueError:
            pass

    return None


def parse_date_end(value):
    """Parse the END date from a human-readable conference date range."""
    if not value:
        return None

    text = str(value).strip()

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    month_pattern = (
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    )

    match = re.search(
        rf"\b(?P<month>{month_pattern})\s+"
        r"(?P<day>\d{1,2})"
        rf"\s*[-–]\s*(?:(?P<end_month>{month_pattern})\s*)?"
        r"(?P<end_day>\d{1,2}),?\s+(?P<year>\d{4})\b",
        text,
        re.IGNORECASE
    )

    if match:
        end_month = match.group("end_month") or match.group("month")

        try:
            return datetime.strptime(
                f"{end_month[:3]} "
                f"{match.group('end_day')} "
                f"{match.group('year')}",
                "%b %d %Y"
            ).date()
        except ValueError:
            pass

    return parse_date(value)



def is_in_horizon(target_date, today, horizon):
    return bool(target_date and today <= target_date <= horizon)


# --------------------------------------------------
# RELEVANCE FILTER
# --------------------------------------------------

def is_relevant(data, category=None):
    text = " ".join([
        str(data.get("title", "")),
        str(data.get("full_name", "")),
        str(data.get("description", "")),
        str(data.get("sub", "")),
        " ".join(map(str, data.get("tags", [])))
    ]).lower()

    if any(keyword in text for keyword in KEYWORDS):
        return True

    # AI category is relevant by definition.
    return category == "AI"


# --------------------------------------------------
# GITHUB FILE RETRIEVAL
# --------------------------------------------------

import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "conference_cache"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_DURATION = 24 * 60 * 60  # 24 hours



HF_ARCHIVE_URL = (
    "https://codeload.github.com/"
    "huggingface/ai-deadlines/zip/refs/heads/main"
)

HF_CACHE_DIR = CACHE_DIR / "hf_yaml"
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

CCF_ARCHIVE_URL = (
    "https://codeload.github.com/"
    "ccfddl/ccf-deadlines/zip/refs/heads/main"
)

CCF_CACHE_DIR = CACHE_DIR / "ccf_yaml"
CCF_CACHE_DIR.mkdir(parents=True, exist_ok=True)



def ensure_hf_archive():
    """
    Download the Hugging Face repository archive and cache its
    conference YAML files locally. Refresh the cache every 24 hours.
    """
    cache_duration = 24 * 60 * 60

    cached_files = list(HF_CACHE_DIR.rglob("*.yaml"))
    cached_files += list(HF_CACHE_DIR.rglob("*.yml"))

    cache_is_fresh = (
        cached_files
        and time.time() - min(
            file.stat().st_mtime for file in cached_files
        ) < cache_duration
    )

    if cache_is_fresh:
        return

    try:
        print("Downloading Hugging Face conference archive...")

        response = requests.get(
            HF_ARCHIVE_URL,
            headers=HEADERS,
            timeout=60
        )
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            prefix = "ai-deadlines-main/src/data/conferences/"

            for member in archive.namelist():
                if not member.startswith(prefix):
                    continue

                relative_name = member[len(prefix):]

                if not relative_name.endswith((".yaml", ".yml")):
                    continue

                # Prevent unsafe archive paths.
                relative_path = Path(relative_name)

                if ".." in relative_path.parts:
                    continue

                destination = HF_CACHE_DIR / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)

                with archive.open(member) as source:
                    destination.write_bytes(source.read())

        print("Hugging Face conference archive cached successfully.")

    except Exception as error:
        # Keep using an older cache if the refresh fails.
        existing = list(HF_CACHE_DIR.rglob("*.yaml"))
        existing += list(HF_CACHE_DIR.rglob("*.yml"))

        if not existing:
            raise RuntimeError(
                f"Could not download Hugging Face archive: {error}"
            ) from error

        print(f"Archive refresh failed; using existing cache: {error}")


def ensure_ccf_archive():
    """
    Download and cache CCF conference YAML files locally.
    Refresh the archive every 24 hours.
    """
    cache_marker = CCF_CACHE_DIR / ".cache_timestamp"
    cache_files = [
        path for path in CCF_CACHE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in (".yaml", ".yml")
    ]

    cache_is_fresh = (
        cache_marker.exists()
        and time.time() - cache_marker.stat().st_mtime < 86400
        and cache_files
    )

    if cache_is_fresh:
        return

    try:
        print("Downloading CCF conference archive...")

        response = requests.get(
            CCF_ARCHIVE_URL,
            headers=HEADERS,
            timeout=90
        )
        response.raise_for_status()

        categories = set(CCF_CATEGORIES)
        prefix = "ccf-deadlines-main/conference/"

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for member in archive.namelist():

                if not member.startswith(prefix):
                    continue

                relative_name = member[len(prefix):]
                parts = Path(relative_name).parts

                if len(parts) != 2:
                    continue

                category, filename = parts

                if category not in categories:
                    continue

                if not filename.lower().endswith((".yaml", ".yml")):
                    continue

                destination = CCF_CACHE_DIR / category / filename
                destination.parent.mkdir(parents=True, exist_ok=True)

                with archive.open(member) as source:
                    destination.write_bytes(source.read())

        cache_marker.touch()
        print("CCF conference archive cached successfully.")

    except Exception as error:
        existing_files = [
            path for path in CCF_CACHE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.lower() in (".yaml", ".yml")
        ]

        if not existing_files:
            raise RuntimeError(
                f"Could not download CCF archive: {error}"
            ) from error

        print(f"CCF refresh failed; using existing cache: {error}")

def get_yaml_files(api_url):
    """
    Return YAML filenames from local archives.
    No GitHub API requests are required.
    """

    # Hugging Face source
    if "huggingface/ai-deadlines" in api_url:
        ensure_hf_archive()

        return [
            {"name": path.relative_to(HF_CACHE_DIR).as_posix()}
            for path in HF_CACHE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.lower() in (".yaml", ".yml")
        ]

    # CCF source
    if "ccfddl/ccf-deadlines" in api_url:
        ensure_ccf_archive()

        category = api_url.rstrip("/").split("/")[-1]

        if category not in CCF_CATEGORIES:
            return []

        category_dir = CCF_CACHE_DIR / category

        return [
            {"name": path.name}
            for path in category_dir.glob("*")
            if path.is_file()
            and path.suffix.lower() in (".yaml", ".yml")
        ]

    raise ValueError(f"Unsupported conference source: {api_url}")




def fetch_hf_file(filename):
    """
    Read a Hugging Face conference YAML file from the local cache.
    Supports both filename strings and GitHub-style file dictionaries.
    """

    if isinstance(filename, dict):
        filename = filename.get("name")

    if not filename:
        return []

    file_path = HF_CACHE_DIR / filename

    if not file_path.exists():
        print(f"Cached conference file not found: {filename}")
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    return []






def fetch_ccf_file(category, filename):
    """
    Read a CCF YAML file from the local archive cache.
    """

    if isinstance(filename, dict):
        filename = filename.get("name")

    if not filename or category not in CCF_CATEGORIES:
        return []

    file_path = CCF_CACHE_DIR / category / filename

    if not file_path.exists():
        print(f"CCF cached file not found: {category}/{filename}")
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return [data]

    return []




def normalize_rankings(rankings):
    """
    Standardize ranking information from different sources.

    Example:
    {
        "ccf": "A",
        "core": "A*",
        "thcpl": "A"
    }
    """
    if not rankings:
        return None

    if isinstance(rankings, dict):
        normalized = {}

        for key, value in rankings.items():
            if value is None:
                continue

            normalized_key = str(key).strip().lower()
            normalized_key = normalized_key.replace(" ", "_")

            normalized[normalized_key] = value

        return normalized or None

    if isinstance(rankings, str):
        normalized = {}

        for match in re.finditer(
            r"\b(CCF|CORE|THCPL)\s*:\s*([^,;|]+)",
            rankings,
            re.IGNORECASE
        ):
            key = match.group(1).lower()
            value = match.group(2).strip()
            normalized[key] = value

        if normalized:
            return normalized

        return {"source_reported": rankings.strip()}

    return {"source_reported": rankings}


# --------------------------------------------------
# NORMALIZED RECORDS
# --------------------------------------------------

def make_record(
    title,
    year,
    link,
    conference_date,
    start_date,
    end_date,
    city,
    country,
    venue,
    deadline,
    deadline_type,
    deadline_label,
    track,
    rankings,
    source,
    today,
    status
):
    deadline_date = parse_date(deadline)
    event_start = parse_date(start_date) or parse_date(conference_date)

    event_end = (
        parse_date(end_date)
        or parse_date_end(conference_date)
        or event_start
    )

    return {
        "title": title,
        "year": year,
        "link": link,
        "conference_date": conference_date,
        "start": event_start.isoformat() if event_start else None,
        "end": event_end.isoformat() if event_end else None,
        "city": city,
        "country": country,
        "venue": venue,
        "deadline": str(deadline) if deadline else None,
        "deadline_type": deadline_type,
        "deadline_label": deadline_label,
        "track": track,
        "days_until_deadline": (
            (deadline_date - today).days
            if deadline_date else None
        ),
        "status": status,
        "rankings": normalize_rankings(rankings),
        "source": source,
        "verification_status": "Not yet verified",
        "indexing_status": "Not verified"
    }


# --------------------------------------------------
# HUGGING FACE NORMALIZATION
# --------------------------------------------------

def normalize_hf(conference, today, horizon):
    if not is_relevant(conference):
        return []

    start = conference.get("start")
    end = conference.get("end")

    event_start = parse_date(start) or parse_date(
        conference.get("date")
    )

    event_upcoming = is_in_horizon(
        event_start, today, horizon
    )

    deadlines = []

    for item in conference.get("deadlines", []):
        deadline_type = str(
            item.get("type", "")
        ).lower().strip()

        if deadline_type not in SUBMISSION_TYPES:
            continue

        deadline = item.get("date")
        deadline_date = parse_date(deadline)

        if deadline_date:
            deadlines.append({
                "date": deadline,
                "date_obj": deadline_date,
                "type": deadline_type,
                "label": item.get("label"),
                "timezone": item.get("timezone")
            })

    future = [
        item for item in deadlines
        if is_in_horizon(item["date_obj"], today, horizon)
    ]

    records = []

    common = {
        "title": conference.get("title")
            or conference.get("full_name"),
        "year": conference.get("year"),
        "link": conference.get("link"),
        "conference_date": conference.get("date"),
        "start_date": start,
        "end_date": end,
        "city": conference.get("city"),
        "country": conference.get("country"),
        "venue": conference.get("venue"),
        "rankings": conference.get("rankings"),
    }

    if future:
        for item in future:
            records.append(make_record(
                **common,
                deadline=item["date"],
                deadline_type=item["type"],
                deadline_label=item["label"],
                track=item.get("timezone"),
                source="Hugging Face AI Deadlines",
                today=today,
                status="Upcoming submission deadline"
            ))

    elif event_upcoming:
        past = [
            item for item in deadlines
            if item["date_obj"] < today
        ]

        latest_past = max(
            past,
            key=lambda item: item["date_obj"],
            default=None
        )

        records.append(make_record(
            **common,
            deadline=latest_past["date"] if latest_past else None,
            deadline_type=latest_past["type"] if latest_past else None,
            deadline_label=latest_past["label"] if latest_past else None,
            track=None,
            source="Hugging Face AI Deadlines",
            today=today,
            status=(
                "Deadline passed"
                if latest_past
                else "No future deadline listed"
            )
        ))

    return records


# --------------------------------------------------
# CCF NORMALIZATION
# --------------------------------------------------

def normalize_ccf(conference, category, today, horizon):
    if not is_relevant(conference, category):
        return []

    title = conference.get("title")
    description = conference.get("description")

    records = []

    editions = conference.get("confs", [])

    for edition in editions:
        year = edition.get("year")
        link = edition.get("link") or conference.get("dblp")
        conference_date = edition.get("date")
        place = edition.get("place")

        event_start = parse_date(conference_date)

        event_upcoming = is_in_horizon(
            event_start, today, horizon
        )

        # Preserve CCF ranking information as reported by the dataset.
        rankings = conference.get("rank")

        deadlines = []

        for timeline in edition.get("timeline", []):
            for key in ["abstract_deadline", "deadline"]:
                deadline = timeline.get(key)
                deadline_date = parse_date(deadline)

                if not deadline_date:
                    continue

                deadlines.append({
                    "date": deadline,
                    "date_obj": deadline_date,
                    "type": (
                        "abstract"
                        if key == "abstract_deadline"
                        else "paper"
                    ),
                    "label": (
                        "Abstract submission"
                        if key == "abstract_deadline"
                        else "Paper submission"
                    ),
                    "track": timeline.get("comment")
                })

        future = [
            item for item in deadlines
            if is_in_horizon(item["date_obj"], today, horizon)
        ]

        if future:
            for item in future:
                records.append(make_record(
                    title=title,
                    year=year,
                    link=link,
                    conference_date=conference_date,
                    start_date=None,
                    end_date=None,
                    city=place,
                    country=None,
                    venue=None,
                    deadline=item["date"],
                    deadline_type=item["type"],
                    deadline_label=item["label"],
                    track=item["track"],
                    rankings=rankings,
                    source=f"CCF Deadlines ({category})",
                    today=today,
                    status="Upcoming submission deadline"
                ))

        elif event_upcoming:
            past = [
                item for item in deadlines
                if item["date_obj"] < today
            ]

            latest_past = max(
                past,
                key=lambda item: item["date_obj"],
                default=None
            )

            records.append(make_record(
                title=title,
                year=year,
                link=link,
                conference_date=conference_date,
                start_date=None,
                end_date=None,
                city=place,
                country=None,
                venue=None,
                deadline=latest_past["date"] if latest_past else None,
                deadline_type=latest_past["type"] if latest_past else None,
                deadline_label=latest_past["label"] if latest_past else None,
                track=latest_past["track"] if latest_past else None,
                rankings=rankings,
                source=f"CCF Deadlines ({category})",
                today=today,
                status=(
                    "Deadline passed"
                    if latest_past
                    else "No future deadline listed"
                )
            ))

    return records


# --------------------------------------------------
# DEDUPLICATION
# --------------------------------------------------

def conference_key(record):
    title = str(record.get("title") or "").lower()

    title = re.sub(r"\b(19|20)\d{2}\b", "", title)
    title = re.sub(r"[^a-z0-9]", "", title)

    return title or str(record.get("year", ""))


def deduplicate(records):
    unique = {}

    for record in records:
        key = (
            conference_key(record),
            str(record.get("year")),
            record.get("deadline_type"),
            str(record.get("deadline"))
        )

        if key not in unique:
            record["sources"] = [record["source"]]
            unique[key] = record
        else:
            existing = unique[key]

            if record["source"] not in existing["sources"]:
                existing["sources"].append(record["source"])

            # Prefer the record with more complete conference details.
            for field in [
                "link", "city", "country", "venue",
                "rankings", "conference_date"
            ]:
                if not existing.get(field) and record.get(field):
                    existing[field] = record[field]

    return list(unique.values())


# --------------------------------------------------
# MAIN SEARCH FUNCTION
# --------------------------------------------------

def search_conferences(limit=100, horizon_days=365):
    """
    Search Hugging Face AI Deadlines and six CCF categories.

    Includes:
    - Future abstract and paper submission deadlines.
    - Upcoming conferences even when submission deadlines passed.
    """

    today = date.today()
    horizon = today + timedelta(days=horizon_days)

    all_records = []
    jobs = []

    # Hugging Face files
    hf_files = get_yaml_files(HF_API)

    for filename in hf_files:
        jobs.append((
            "hf",
            filename,
            None
        ))

    # CCF files from selected categories
    for category in CCF_CATEGORIES:
        try:
            filenames = get_yaml_files(
                f"{CCF_API}/{category}"
            )

            for filename in filenames:
                jobs.append((
                    "ccf",
                    filename,
                    category
                ))

        except Exception as error:
            print(f"Could not list CCF category {category}: {error}")

    print(f"Conference files to inspect: {len(jobs)}")

    # Retrieve YAML files concurrently
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {}

        for source, filename, category in jobs:
            if source == "hf":
                future = executor.submit(
                    fetch_hf_file, filename
                )
            else:
                future = executor.submit(
                    fetch_ccf_file, category, filename
                )

            futures[future] = (source, filename, category)

        for future in as_completed(futures):
            source, filename, category = futures[future]

            try:
                conferences = future.result()

                for conference in conferences:
                    if source == "hf":
                        all_records.extend(
                            normalize_hf(
                                conference, today, horizon
                            )
                        )
                    else:
                        all_records.extend(
                            normalize_ccf(
                                conference,
                                category,
                                today,
                                horizon
                            )
                        )

            except Exception as error:
                print(
                    f"Could not retrieve {source}/{category or ''}/"
                    f"{filename}: {error}"
                )

    results = deduplicate(all_records)

    # Deadlines first; conferences without a deadline follow.
    results.sort(
        key=lambda item: (
            item["deadline"] is None,
            item["deadline"] or "9999-12-31",
            item["title"] or ""
        )
    )

    print(f"Unique conference opportunities: {len(results)}")

    return results[:limit]
