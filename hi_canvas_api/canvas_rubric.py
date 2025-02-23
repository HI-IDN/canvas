import requests
import os
import json
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

# Validate environment variables
def validate_env_vars() -> None:
    """Validates essential environment variables."""
    if not API_TOKEN:
        raise ValueError("API_TOKEN is missing. Please set it in the .env file.")
    if not COURSE_ID:
        raise ValueError("COURSE_ID is missing. Please set it in the .env file.")
    if not INSTITUTION_URL:
        raise ValueError("INSTITUTION_URL is missing. Please set it in the .env file.")

validate_env_vars()

# API URL for rubrics
RUBRICS_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/rubrics"

def get_headers() -> dict[str, str]:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

def load_rubric_from_json(file_path: str) -> dict[str, Any]:
    """Loads rubric data from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)

def create_rubric(rubric_data: dict[str, Any]) -> None:
    """Creates a rubric in Canvas from the given JSON data."""
    headers = get_headers()

    # Prepare the rubric payload
    payload = {
        "title": rubric_data["title"],
        "criteria": [
            {
                "description": criterion["description"],
                "long_description": criterion.get("long_description", ""),
                "points": criterion["points"]
            }
            for criterion in rubric_data["criteria"]
        ],
        "course_id": COURSE_ID
    }

    # Make the API request
    response = requests.post(RUBRICS_URL, headers=headers, json=payload)

    if response.status_code == 201:
        logging.info(f"Rubric '{rubric_data['title']}' created successfully.")
    else:
        raise Exception(
            f"Failed to create rubric '{rubric_data['title']}': {response.status_code} - {response.text}"
        )

def rubric_to_graderubric(rubric: list) -> list:
    """
    Transforms the retrieved rubric into a grading rubric where the instructor can input scores and comments.

    Args:
        rubric (list): The rubric retrieved from Canvas.

    Returns:
        list: A structured rubric ready for grading, with empty score and comment fields.
    """
    grading_rubric = []
    
    for criterion in rubric:
        grading_rubric.append({
            "criterion_id": criterion["id"],
            "criterion_name": criterion["description"],
            "max_points": criterion["points"],
            "score": 0,  
            "comment": ""  
        })

    return grading_rubric


