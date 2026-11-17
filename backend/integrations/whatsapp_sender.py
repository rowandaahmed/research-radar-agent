import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
WHATSAPP_API_VERSION = "v25.0"


def clean_whatsapp_param(text: str, max_len: int = 1000) -> str:
    """
    Meta WhatsApp template parameters reject newlines, tabs, and >4 consecutive spaces.
    Strips markdown formatting and collapses whitespace into clean single-line text.
    """
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"[#*_`>]+", "", cleaned)
    cleaned = re.sub(r"[\r\n\t]+", " | ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(\s*\|\s*)+", " | ", cleaned).strip(" |")

    if not cleaned:
        return "Not available"

    if len(cleaned) > max_len:
        return cleaned[: max_len - 3].rstrip() + "..."

    return cleaned


def send_whatsapp_message(
    topic: str,
    findings: str,
    idea: str,
    deadlines_summary: str = ""
):
    # Reload .env dynamically on every call so refreshed tokens apply immediately
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    access_token = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip().strip('"').strip("'")
    phone_number_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip().strip('"').strip("'")
    recipient_number = (os.getenv("WHATSAPP_RECIPIENT_NUMBER") or "").strip().strip('"').strip("'")

    if not all([access_token, phone_number_id, recipient_number]):
        raise ValueError("Missing WhatsApp configuration in .env")

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    combined_idea = idea
    if deadlines_summary:
        combined_idea = f"{idea} | Upcoming Deadlines: {deadlines_summary}"

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "template",
        "template": {
            "name": "research_radar_report",
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": clean_whatsapp_param(topic, 1000)
                        },
                        {
                            "type": "text",
                            "text": clean_whatsapp_param(findings, 1000)
                        },
                        {
                            "type": "text",
                            "text": clean_whatsapp_param(combined_idea, 1000)
                        }
                    ]
                }
            ]
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"WhatsApp API error: {response.status_code} - {response.text}"
        )

    return response.json()