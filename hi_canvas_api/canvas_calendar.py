"""
Canvas Calendar Management Script
---------------------------------
This script provides functionality to manage calendar events for a Canvas course.

Features:
- Delete all calendar events for a specific course.
- Create calendar events with specified details.

Environment Variables:
- INSTITUTION_URL: Base URL of the Canvas institution.
- API_VERSION: API version (e.g., v1).
- API_TOKEN: Canvas API token.
- COURSE_ID: ID of the Canvas course.
- START_DATE: Start date for event management.
- END_DATE: End date for event management.
"""

import requests
import os
import logging
from dotenv import load_dotenv
from typing import Any

# Load environment variables from the .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables
INSTITUTION_URL = os.getenv("INSTITUTION_URL")
API_VERSION = os.getenv("API_VERSION")
API_TOKEN = os.getenv("API_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")
START_DATE = os.getenv("START_DATE")
END_DATE = os.getenv("END_DATE")


def validate_env_vars() -> None:
    """Validates essential environment variables."""
    if not API_TOKEN:
        raise ValueError("API_TOKEN is missing. Please set it in the .env file.")
    if not COURSE_ID:
        raise ValueError("COURSE_ID is missing. Please set it in the .env file.")
    if not INSTITUTION_URL:
        raise ValueError("INSTITUTION_URL is missing. Please set it in the .env file.")
    if not START_DATE or not END_DATE or END_DATE < START_DATE:
        raise ValueError("Invalid START_DATE or END_DATE. Check the .env file.")


# Validate environment variables
validate_env_vars()

# Construct the base URL dynamically
CALENDAR_EVENTS_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/calendar_events"


def get_headers() -> dict[str, str]:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def delete_calendar_event(event_id: int) -> None:
    """Delete a specific calendar event in Canvas."""
    api_url = f"{CALENDAR_EVENTS_URL}/{event_id}"
    headers = get_headers()

    response = requests.delete(api_url, headers=headers)

    if response.status_code == 204:
        logging.info(f"Event {event_id} deleted successfully.")
    elif response.status_code == 200:
        event_details = response.json()
        if event_details.get("workflow_state") == "deleted":
            logging.warning(f"Event {event_id} is already deleted. Skipping.")
        else:
            raise Exception(f"Failed to delete event {event_id}: Unexpected workflow state.")
    else:
        raise Exception(
            f"Failed to delete event {event_id}: {response.status_code} - {response.text}")


def delete_all_calendar_events() -> None:
    """Deletes all calendar events for the specified course."""
    headers = get_headers()
    params = {
        "context_codes[]": f"course_{COURSE_ID}",
        "type": "event",
        "per_page": 100,
        "start_date": START_DATE,
        "end_date": END_DATE,
    }

    response = requests.get(CALENDAR_EVENTS_URL, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve events: {response.status_code} - {response.text}")

    events = response.json()
    for event in events:
        if event.get("workflow_state") == "deleted":
            logging.warning(f"Skipping event {event['id']} as it is already deleted.")
            continue
        delete_calendar_event(event["id"])


def create_calendar_event(title: str, date: str, start_time: str, end_time: str,
                          description: str) -> None:
    """Creates a new calendar event for the specified course."""
    headers = get_headers()
    payload = {
        "calendar_event": {
            "context_code": f"course_{COURSE_ID}",
            "title": title,
            "description": description,
            "start_at": f"{date}T{start_time}:00Z",
            "end_at": f"{date}T{end_time}:00Z",
        }
    }

    response = requests.post(CALENDAR_EVENTS_URL, headers=headers, json=payload)
    if response.status_code == 201:
        logging.info(f"Event '{title}' created successfully for {date} at {start_time}.")
    else:
        raise Exception(
            f"Failed to create event '{title}': {response.status_code} - {response.text}")
