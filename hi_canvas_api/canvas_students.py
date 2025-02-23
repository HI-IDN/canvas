"""
Canvas Student Management Script
---------------------------------
This script provides functionality to create a list of students and their ID for a Canvas course.

Features:
- List all students and their canvas ID for a specific course.

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

def get_all_students():
    """
    Fetches all students in a given course, returning a list of dicts:
    [
      {
        "id": <Canvas user ID>,
        "name": <Full name>,
        "login_id": <Canvas login/sis ID, if available>
      },
      ...
    ]
    """
    headers = get_headers()
    students = []
    url = f"{BASE_URL}/courses/{COURSE_ID}/users"
    
    # We use a loop to handle pagination in Canvas
    params = {
        "enrollment_type": ["student"],  # Only students
        "per_page": 100                  # Max items per page
    }
    
    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Convert the response JSON into a Python list
        page_data = response.json()
        
        # Extract only relevant info: user ID, name, login ID
        for user in page_data:
            students.append({
                "id": user["id"],
                "name": user["name"],
                "login_id": user.get("login_id", ""),
            })
        
        # Check the Link header to see if there's another page
        next_link = None
        if "Link" in response.headers:
            links = response.headers["Link"].split(",")
            for link in links:
                if 'rel="next"' in link:
                    # Extract the URL inside <>
                    next_link = link[link.find("<")+1 : link.find(">")]
                    break
        
        # Prepare for next iteration
        if next_link:
            url = next_link
            # After the first call, `params` are included in the link so we reset
            params = {}
        else:
            url = None
    
    return students

if __name__ == "__main__":
    # Get a list of all students
    student_list = get_all_students()
    
    # Print them or write them to a CSV file for easy import to Excel
    with open("students.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["id", "name", "login_id"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for s in student_list:
            writer.writerow(s)
    
    print(f"Retrieved {len(student_list)} students. Saved to students.csv.")