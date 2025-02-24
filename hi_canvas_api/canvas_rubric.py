import requests
import os
import json
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Config
COURSE_ID = os.getenv("COURSE_ID")
BASE_URL = os.getenv("INSTITUTION_URL")
API_TOKEN = os.getenv("API_TOKEN")
CREATE_URL = f"{BASE_URL}/api/v1/courses/{COURSE_ID}/rubrics"

# Validate environment variables
if not COURSE_ID or not BASE_URL or not API_TOKEN:
    raise ValueError("Missing environment variables. Please set COURSE_ID, INSTITUTION_URL, and API_TOKEN.")

# Headers for API requests
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

def load_rubric(file_path: str) -> dict:
    """Loads rubric JSON data from file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)

def format_rubric_criteria(criteria_data: list) -> dict:
    """Formats rubric criteria to match Canvas API requirements."""
    rubric_criteria = {}
    for idx, criterion in enumerate(criteria_data, start=1):
        rubric_criteria[str(idx)] = {
            "description": criterion["description"],
            "ratings": {
                key: {
                    "description": value["description"],
                    "long_description": value.get("long_description", ""),
                    "points": value["points"]
                }
                for key, value in criterion["ratings"].items()  # Lyklar í stað lista
            }
        }
    return rubric_criteria


def create_rubric(rubric_data: dict):
    """Creates a rubric in Canvas."""
    rubric_title = rubric_data["title"]
    rubric_criteria = format_rubric_criteria(rubric_data["criteria"])

    payload = {
        "rubric_association": {
            "association_type": "Course",
            "association_id": COURSE_ID,
            "use_for_grading": True,
            "title": rubric_title,
        },
        "rubric": {
            "title": rubric_title,
            "criteria": rubric_criteria,
        },
    }

    response = requests.post(CREATE_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"✅ Rubric '{rubric_title}' created successfully!")
    else:
        print(f"❌ Failed to create rubric '{rubric_title}': {response.status_code}")
        print(response.json())

def rubric_to_graderubric(rubric):
    """
    Converts an original assignment rubric into a grading rubric template.

    Args:
        rubric (list): A list of rubric criteria from the assignment.

    Returns:
        list: A grading rubric template where scores and comments are initialized.
    """
    grading_rubric = []

    for criterion in rubric:
        grading_rubric.append({
            "criterion_id": criterion["id"],
            "criterion_name": criterion["description"],  # Criterion name
            "max_points": criterion["points"],  # Max possible score
            "score": 0,  # Default score before grading
            "comment": ""  # Placeholder for comments
        })

    return grading_rubric


def main():
    """Main function to handle CLI input and upload rubric."""
    parser = argparse.ArgumentParser(description="Upload a rubric to Canvas using a JSON file.")
    parser.add_argument("--file", type=str, default="rubric.json", help="Path to the rubric JSON file.")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return

    rubric_data = load_rubric(args.file)
    create_rubric(rubric_data)

if __name__ == "__main__":
    main()
