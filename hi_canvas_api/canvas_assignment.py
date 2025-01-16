import requests
import os
import logging
from dotenv import load_dotenv
from typing import Optional, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables
INSTITUTION_URL = os.getenv("INSTITUTION_URL")
API_VERSION = os.getenv("API_VERSION")
API_TOKEN = os.getenv("API_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")

if not all([INSTITUTION_URL, API_VERSION, API_TOKEN, COURSE_ID]):
    raise ValueError("Missing one or more required environment variables in .env file.")

# Base URL for Canvas API
ASSIGNMENTS_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments"
GROUPS_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignment_groups"


def get_headers() -> dict:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def add_assignment(assignment, group_id: None) -> None:
    """Create or update an assignment in Canvas."""

    # Prepare the payload
    payload = {
        "assignment": assignment
    }
    if group_id:
        payload["assignment"]["assignment_group_id"] = group_id

    # Check if the assignment already exists by its ID
    assignment_id = assignment.get("id")
    name = assignment.get("name")

    if assignment_id:
        existing_assignment = get_single_assignment(assignment_id)
        if existing_assignment:
            if existing_assignment.get("published"):
                logging.error(
                    f"Assignment '{name}' is already published. Aborting..."
                )
                return
            else:
                # Update the existing assignment
                logging.info(f"Assignment '{name}' exists. Updating assignment...")
                response = requests.put(
                    f"{ASSIGNMENTS_URL}/{assignment_id}",
                    headers=get_headers(),
                    json=payload
                )
                if response.status_code == 200:
                    logging.info(f"Assignment '{name}' updated successfully.")
                else:
                    raise Exception(
                        f"Failed to update assignment '{name}': {response.status_code} - {response.text}"
                    )
                return
        else:
            logging.error(
                f"Assignment '{name}' with ID '{assignment_id}' cannot be found. Creating a new assignment..."
            )

    # If no ID or assignment not found, create a new one
    response = requests.post(ASSIGNMENTS_URL, headers=get_headers(), json=payload)
    if response.status_code == 201:
        assignment_id = response.json().get("id")
        logging.info(f"Assignment '{name}' created successfully with ID: {assignment_id}")
    else:
        raise Exception(
            f"Failed to create assignment '{name}': {response.status_code} - {response.text}"
        )


def get_single_assignment(assignment_id: int) -> dict:
    """Retrieve a single assignment by ID."""
    headers = get_headers()

    response = requests.get(f"{ASSIGNMENTS_URL}/{assignment_id}", headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Failed to retrieve assignment ID {assignment_id}: {response.status_code} -"
            f" {response.text}")

    return response.json()


def get_all_assignments() -> list:
    """Retrieve all assignments.
    """
    headers = get_headers()

    response = requests.get(ASSIGNMENTS_URL, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve assignments: {response.status_code} - {response.text}")

    assignments = response.json()
    return assignments


def get_assignment_groups() -> dict:
    """Retrieve all assignment groups for the course."""
    headers = get_headers()

    response = requests.get(GROUPS_URL, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"Failed to retrieve assignment groups: {response.status_code} - {response.text}")

    return {group["id"]: group["name"] for group in response.json()}


def get_assignments() -> dict[int, dict[str, list[dict]]]:
    """Retrieve all assignments in a simplified format."""
    assignments = get_all_assignments()
    nested_data = {
        group_id: {"name": group_name, "assignments": []}
        for group_id, group_name in get_assignment_groups().items()
    }

    # Simplify and nest assignments under their respective groups
    for assignment in assignments:
        group_id = assignment.get("assignment_group_id", "Ungrouped")
        simplified_assignment = {
            "id": assignment["id"],
            "name": assignment["name"],
            "description": assignment.get("description", "No description provided."),
            "due_at": assignment.get("due_at"),
            "points": assignment.get("points_possible", 0),
            "published": assignment.get("published", False),
            "allowed_extensions": assignment.get("allowed_extensions", []),
        }

        if group_id in nested_data:
            nested_data[group_id]["assignments"].append(simplified_assignment)
        else:
            logging.warning(f"Assignment '{assignment['name']}' is in an unknown group: {group_id}")

    return nested_data
