"""
Canvas Group Management Script
---------------------------------
This script provides functionality to create groups and assign students to these groups for a Canvas course.

Features:
- Reads the groups.csv file and generates and assigns students to these groups.

Environment Variables:
- INSTITUTION_URL: Base URL of the Canvas institution.
- API_VERSION: API version (e.g., v1).
- API_TOKEN: Canvas API token.
- COURSE_ID: ID of the Canvas course.
"""

import requests
import csv
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
BASE_URL = f"{INSTITUTION_URL}/api/{API_VERSION}"

def get_headers() -> dict[str, str]:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}

def fetch_group_category(course_id, category_name):
    """
    Fetch the group category ID by name if it exists; create it if not.
    """
    url = f"{BASE_URL}/courses/{course_id}/group_categories"
    headers = get_headers()
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    categories = response.json()
    
    # Check if the group category already exists
    for category in categories:
        if category["name"] == category_name:
            print(f"Group category '{category_name}' already exists with ID: {category['id']}")
            return category["id"]
    
    # If not found, create the group category
    print(f"Group category '{category_name}' does not exist. Creating a new one.")
    payload = {"name": category_name}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    new_category = response.json()
    print(f"Created group category '{category_name}' with ID: {new_category['id']}")
    return new_category["id"]


def fetch_existing_groups(group_category_id):
    """Fetch existing groups in a group category and return a mapping of names to IDs."""
    url = f"{BASE_URL}/group_categories/{group_category_id}/groups"
    headers = get_headers()
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    groups = response.json()
    
    # Map group names to group IDs
    return {group["name"]: group["id"] for group in groups}

def create_group(group_category_id, group_name):
    """Create a group in a specific group category."""
    url = f"{BASE_URL}/group_categories/{group_category_id}/groups"
    payload = {"name": group_name}
    headers = get_headers()
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["id"]

def assign_student_to_group_(group_id, canvas_id):
    """Assign a student to a specific group."""
    url = f"{BASE_URL}/groups/{group_id}/memberships"
    payload = {"user_id": canvas_id}
    headers = get_headers()
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 409:
        print(f"User {canvas_id} is already in the group.")
    else:
        response.raise_for_status()

def validate_group(group_id):
    url = f"{BASE_URL}/groups/{group_id}"
    headers = get_headers()
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        raise Exception(f"Group {group_id} not found.")
    response.raise_for_status()
    print(f"DEBUG: Group details: {response.json()}")

def assign_student_to_group(group_id, canvas_id):
    """Assign a student to a specific group."""
    # Ensure canvas_id is clean
    canvas_id = canvas_id.strip()
    if not canvas_id.isdigit():
        raise ValueError(f"Invalid Canvas ID: {canvas_id}")

    url = f"{BASE_URL}/groups/{group_id}/memberships"
    payload = {"user_id": int(canvas_id)}
    print(f"DEBUG: Making POST request to {url} with payload {payload}")

    response = requests.post(url, headers=headers, json=payload)
    print(f"DEBUG: Response Status Code: {response.status_code}")
    print(f"DEBUG: Response Text: {response.text}")

    if response.status_code == 404:
        raise Exception(f"Group {group_id} or endpoint not found. Response: {response.text}")
    elif response.status_code == 409:
        print(f"User {canvas_id} is already in the group.")
    else:
        response.raise_for_status()
        print(f"Assigned user {canvas_id} to group {group_id}")

def process_groups(file_path, course_id, group_category_name):
    # Step 1: Fetch or create the group category
    group_category_id = fetch_group_category(course_id, group_category_name)
    print(f"Using group category with ID: {group_category_id}")

    # Step 2: Fetch existing groups
    existing_groups = fetch_existing_groups(group_category_id)
    print(f"Existing groups: {existing_groups}")

    # Step 3: Read CSV and process groups and students
    groups = existing_groups  # Use fetched groups as the starting point
    
    with open(file_path, mode="r", encoding="utf-8-sig") as file:
        reader = csv.reader(file, delimiter=";")
        for row in reader:
            canvas_id, group_number, student_name = row
            canvas_id = canvas_id.strip()  # Ensure no extra spaces
            group_number = int(group_number)
            group_name = f"Test-{group_number}"

            # Step 4: Create the group if it doesn't exist
            if group_name not in groups:
                group_id = create_group(group_category_id, group_name)
                groups[group_name] = group_id
                print(f"Created group: {group_name} (ID: {group_id})")

            # Step 5: Assign the student to the group
            assign_student_to_group(groups[group_name], canvas_id)
            print(f"Assigned {student_name} (Canvas ID: {canvas_id}) to {group_name}")

if __name__ == "__main__":
    # File path to the groups.csv
    CSV_FILE = "groups.csv"
    GROUP_CATEGORY_NAME = "Test" # þetta eru hópasett.
    process_groups(CSV_FILE, COURSE_ID, GROUP_CATEGORY_NAME)