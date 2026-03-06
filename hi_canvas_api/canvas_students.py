"""
Canvas Student & Group Management Script
---------------------------------
This script fetches:
- All students in a Canvas course with their ID.
- All groups (teams) and their students.

Environment Variables:
- INSTITUTION_URL: Base URL of the Canvas institution.
- API_VERSION: API version (e.g., v1).
- API_TOKEN: Canvas API token.
- COURSE_ID: ID of the Canvas course.
"""

import requests
import csv
import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables
INSTITUTION_URL = os.getenv("INSTITUTION_URL")
API_VERSION = os.getenv("API_VERSION", "v1")
API_TOKEN = os.getenv("API_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")

# Validate environment variables
def validate_env_vars():
    """ Validates essential environment variables. """
    if not API_TOKEN:
        raise ValueError("API_TOKEN is missing. Please set it in the .env file.")
    if not COURSE_ID:
        raise ValueError("COURSE_ID is missing. Please set it in the .env file.")
    if not INSTITUTION_URL:
        raise ValueError("INSTITUTION_URL is missing. Please set it in the .env file.")

validate_env_vars()

# Construct the base URL
BASE_URL = f"{INSTITUTION_URL}/api/{API_VERSION}"

def get_headers():
    """ Returns the headers for API requests. """
    return {"Authorization": f"Bearer {API_TOKEN}"}

def get_course_groups():
    """ Fetches all groups (teams) in the course and returns a dict {group_id: group_name}. """
    url = f"{BASE_URL}/courses/{COURSE_ID}/groups"
    headers = get_headers()
    groups = {}

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        for group in response.json():
            groups[group["id"]] = group["name"]

        # Handle pagination
        url = response.links.get("next", {}).get("url")

    return groups

def get_group_members(group_id):
    """ Fetches all students within a specific group. """
    url = f"{BASE_URL}/groups/{group_id}/users"
    headers = get_headers()
    members = []

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        for member in response.json():
            members.append({"id": member["id"], "name": member["name"]})

        # Handle pagination
        url = response.links.get("next", {}).get("url")

    return members

def get_all_students():
    """ Fetches all students in a given course. Returns a list of dicts. """
    headers = get_headers()
    students = []
    url = f"{BASE_URL}/courses/{COURSE_ID}/users"
    
    params = {"enrollment_type": ["student"], "per_page": 100}

    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        for user in response.json():
            students.append({
                "id": user["id"],
                "name": user["name"],
                "login_id": user.get("login_id", ""),
            })
        
        # Handle pagination
        url = response.links.get("next", {}).get("url")

    return students

def get_all_groups_with_members():
    """ Retrieves all groups and their students. Returns a dictionary {group_name: [students]} """
    groups = get_course_groups()
    students_per_group = {}

    for group_id, group_name in groups.items():
        students_per_group[group_name] = get_group_members(group_id)

    return students_per_group

if __name__ == "__main__":
    # Fetch students
    student_list = get_all_students()
    logging.info(f"Retrieved {len(student_list)} students.")

    # Save students to CSV
    with open("students.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["id", "name", "login_id"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(student_list)
    logging.info("Student list saved to students.csv.")

    # Fetch groups and members
    all_groups = get_all_groups_with_members()
    logging.info(f"Retrieved {len(all_groups)} groups with members.")

    # Save groups to JSON
    with open("groups_students.json", "w", encoding="utf-8") as json_file:
        json.dump(all_groups, json_file, ensure_ascii=False, indent=4)
    logging.info("Group-student mapping saved to groups_students.json.")
