import json
from pathlib import Path


def load_professor_profile(professor_id: str):
    profile_path = (
        Path(__file__).parent
        / "profiles"
        / f"{professor_id}.json"
    )

    with open(profile_path, "r", encoding="utf-8") as file:
        profile = json.load(file)

    return profile