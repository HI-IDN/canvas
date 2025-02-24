import requests
import os
import logging
from dotenv import load_dotenv
from typing import Optional, Any
import json
import re
from traitlets.config import Config
import nbformat
from nbconvert import MarkdownExporter
from nbconvert.filters import strip_ansi
from nbconvert.preprocessors import Preprocessor

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

def list_assignments() -> None:
    """List all published assignments with their IDs."""
    assignments = get_all_assignments()
    
    # Filter for published assignments
    published_assignments = [
        {"id": assignment["id"], "name": assignment["name"]}
        for assignment in assignments
        if assignment.get("published", False)
    ]
    
    if not published_assignments:
        print("No published assignments found.")
        return
    
    print("Published Assignments:")
    for assignment in published_assignments:
        print(f"ID: {assignment['id']}, Name: {assignment['name']}")

def get_submissions(assignment_id: int) -> list:
    """Retrieve all submissions for a given assignment, handling pagination."""
    headers = get_headers()
    submissions_url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}/submissions"

    submissions = []
    while submissions_url:
        response = requests.get(submissions_url, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve submissions for assignment {assignment_id}: "
                f"{response.status_code} - {response.text}"
            )
        
        data = response.json()
        submissions.extend(data)

        # Get the next page URL from the Link header
        submissions_url = None
        if "Link" in response.headers:
            links = response.headers["Link"].split(",")
            for link in links:
                if 'rel="next"' in link:
                    submissions_url = link[link.find("<") + 1 : link.find(">")]
                    break

    return submissions


def download_attachment(file_url: str, save_path: str) -> None:
    """Download a file from the given URL and save it to the specified path."""
    headers = get_headers()
    response = requests.get(file_url, headers=headers, stream=True)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Downloaded file to {save_path}")
    else:
        logging.error(f"Failed to download file from {file_url}: {response.status_code} - {response.text}")


def process_ipynb(notebook_path: str, output_json_path: str) -> None:
    """Extract all cells from a Jupyter notebook and save to a JSON file.

    Args:
        notebook_path (str): Path to the .ipynb file.
        output_json_path (str): Path to save the output JSON file.
    """
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Read the .ipynb file
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_data = json.load(f)

    # Check for 'cells' field
    if "cells" not in notebook_data:
        raise ValueError("Invalid notebook format: 'cells' field not found")

    # Extract cell information
    extracted_cells = []
    for cell in notebook_data["cells"]:
        cell_type = cell.get("cell_type", "unknown")
        source = "".join(cell.get("source", []))  # Join lines of content
        extracted_cells.append({
            "type": cell_type,  # Either 'code' or 'markdown'
            "content": source.strip()
        })

    # Save extracted cells to a JSON file
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_cells, f, ensure_ascii=False, indent=4)

    print(f"Processed notebook saved to: {output_json_path}")

class RemoveHTMLPreprocessor(Preprocessor):
    """Custom preprocessor to remove unwanted HTML elements and execution warnings."""
    
    def preprocess_cell(self, cell, resources, index):
        # Remove execution warnings
        if "outputs" in cell:
            cell["outputs"] = []
        
        # Remove specific unwanted metadata
        cell.metadata.pop("execution", None)
        cell.metadata.pop("tags", None)
        
        return cell, resources

def clean_markdown(md_content):
    """Removes <div>, <style>, and execution warnings from Markdown content."""
    md_content = re.sub(r"<style.*?>.*?</style>", "", md_content, flags=re.DOTALL)  # Remove <style> elements
    md_content = re.sub(r"<div.*?>.*?</div>", "", md_content, flags=re.DOTALL)  # Remove <div> elements
    md_content = re.sub(r"<ipython-input-.*?>.*?</ipython-input-.*?>", "", md_content, flags=re.DOTALL)  # Remove execution warnings
    md_content = strip_ansi(md_content)  # Remove terminal color codes (if any)
    return md_content

def convert_ipynb_to_md(notebook_path: str, output_filename: str) -> str:
    """Convert a Jupyter notebook to a Markdown file and clean it up."""
    
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    output_folder = os.path.dirname(notebook_path)
    os.makedirs(output_folder, exist_ok=True)

    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_content = nbformat.read(f, as_version=4)

    # Set up the Markdown exporter
    md_exporter = MarkdownExporter()
    
    # Register a custom preprocessor to remove HTML elements and execution warnings
    md_exporter.register_preprocessor(RemoveHTMLPreprocessor, enabled=True)

    md_exporter.exclude_output = False  # Ensure outputs are included
    md_exporter.exclude_output_prompt = False  # Include output prompts
    md_exporter.exclude_input_prompt = False  # Include input prompts

    # Convert notebook to Markdown
    markdown_output, _ = md_exporter.from_notebook_node(notebook_content)

    # Further clean the output with regex (for remaining <div> and <style>)
    markdown_output = clean_markdown(markdown_output)

    md_path = os.path.join(output_folder, output_filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    print(f"Notebook converted to Markdown: {md_path}")
    return md_path


def convert_ipynb_to_md_X(notebook_path: str, output_filename: str) -> str:
    """Convert a Jupyter notebook (.ipynb) to a Markdown (.md) file using nbconvert,
       removing unnecessary <div> and <style> elements.

    Args:
        notebook_path (str): Path to the .ipynb file.
        output_filename (str): Desired name for the Markdown file (e.g., "assignment.md").

    Returns:
        str: Path to the generated Markdown file.
    """
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    output_folder = os.path.dirname(notebook_path)
    os.makedirs(output_folder, exist_ok=True)

    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_content = nbformat.read(f, as_version=4)

    # Set up the Markdown exporter with a TagRemovePreprocessor
    md_exporter = MarkdownExporter()
    preprocessor = TagRemovePreprocessor()
    
    # Remove cells that contain HTML elements
    preprocessor.remove_cell_tags = {"html"}
    preprocessor.remove_all_outputs_tags = {"html"}
    
    md_exporter.register_preprocessor(preprocessor, enabled=True)

    # Convert notebook to Markdown
    markdown_output, _ = md_exporter.from_notebook_node(notebook_content)

    md_path = os.path.join(output_folder, output_filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    print(f"Notebook converted to Markdown: {md_path}")
    return md_path

def convert_ipynb_to_md_(notebook_path: str, output_filename: str) -> str:
    """Convert a Jupyter notebook (.ipynb) to a Markdown (.md) file using nbconvert.
       The Markdown file will be saved in the same folder as the original notebook.

    Args:
        notebook_path (str): Path to the .ipynb file.
        output_filename (str): Desired name for the Markdown file (e.g., "assignment.md").

    Returns:
        str: Path to the generated Markdown file.
    """
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Get the folder where the notebook is located
    output_folder = os.path.dirname(notebook_path)

    # Ensure the output folder exists (should already exist)
    os.makedirs(output_folder, exist_ok=True)

    # Read the notebook content
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_content = nbformat.read(f, as_version=4)

    # Set up the Markdown exporter
    md_exporter = MarkdownExporter()

    # Convert notebook to Markdown
    markdown_output, _ = md_exporter.from_notebook_node(notebook_content)

    # Define full path for the output Markdown file
    md_path = os.path.join(output_folder, output_filename)

    # Save the Markdown content
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    print(f"Notebook converted to Markdown: {md_path}")
    return md_path

def save_submissions_with_attachments(assignment_id: int, folder_path: str) -> None:
    """Download all attachments for submissions of an assignment and save them locally."""
    # Create the folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logging.info(f"Created folder: {folder_path}")

    print("Assignment ID:", assignment_id)

    submissions = get_submissions(assignment_id)
    print(submissions)
    for submission in submissions:
        # Only process submissions that have been submitted
#        print(submission)
        if submission.get("workflow_state") != "submitted":
            logging.info(f"Skipping user ID {submission.get('user_id')} as they have not submitted.")
            continue

        user_id = submission.get("user_id")
        user_name = submission.get("user", {}).get("name", f"User_{user_id}")

        # Check for attachments
        attachments = submission.get("attachments", [])
        if attachments:
            for attachment in attachments:
                file_name = attachment.get("display_name", "unknown_file")
                file_url = attachment.get("url")
                if file_url:
                    # Save file to the folder
                    user_folder = os.path.join(folder_path, user_name)
                    if not os.path.exists(user_folder):
                        os.makedirs(user_folder)

                    save_path = os.path.join(user_folder, file_name)
                    download_attachment(file_url, save_path)
                    # After downloading each .ipynb file
                    if file_name.endswith(".ipynb"):
                        json_output_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}_cells.json")
                        #process_ipynb(save_path, json_output_path)
                        # Convert the notebook to Markdown
                        convert_ipynb_to_md(save_path, "assignment.md")
        else:
            logging.info(f"No attachments found for submission by {user_name}.")


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
            "score": 0,  # Instructor fills this in
            "comment": ""   # Optional comment
        })

    return grading_rubric


def save_empty_grading_rubric(folder_path: str, assignment_id: int) -> None:
    """
    Saves an empty grading rubric for an assignment in JSON format.

    Args:
        folder_path (str): Path where the rubric file should be saved.
        assignment_id (int): The ID of the assignment.
    """
    # Retrieve the rubric from Canvas
    rubric = get_assignment_rubric(assignment_id)

    if not rubric:
        logging.warning(f"No rubric found for assignment {assignment_id}.")
        return

    # Generate the grading rubric
    grading_rubric = rubric_to_graderubric(rubric)

    # Save the grading rubric as JSON
    grading_rubric_path = os.path.join(folder_path, "grading_rubric.json")
    with open(grading_rubric_path, "w", encoding="utf-8") as f:
        json.dump(grading_rubric, f, ensure_ascii=False, indent=4)

    logging.info(f"Empty grading rubric saved: {grading_rubric_path}")


def save_rubric_to_json(folder_path: str, assignment_id: int) -> None:
    """
    Vista matsviðmið (rubric) fyrir verkefni í JSON skrá.

    Args:
        folder_path (str): Mappa þar sem rubrikuskjalið verður vistað.
        assignment_id (int): Auðkenni verkefnisins.
    """
    rubric = get_assignment_rubric(assignment_id)

    if not rubric:
        logging.warning(f"Engin rubric fannst fyrir verkefni {assignment_id}.")
        return

    file_path = os.path.join(folder_path, "assignment_rubric.json")
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(rubric, file, ensure_ascii=False, indent=4)

    logging.info(f"Matsviðmið vistað í {file_path}")

def get_assignment_rubric(assignment_id: int) -> list:
    """
    Retrieve the rubric attached to a given assignment.

    Args:
        assignment_id (int): The ID of the assignment.

    Returns:
        list: A list of rubric criteria with descriptions and point values.
    """
    headers = get_headers()
    #rubric_url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}/rubric"
    rubric_url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}?include[]=rubric_association"
    response = requests.get(rubric_url, headers=headers)
    if response.status_code != 200:
        logging.error(f"Failed to retrieve rubric for assignment {assignment_id}: {response.status_code} - {response.text}")
        return []

    rubric_data = response.json()['rubric']
    return rubric_data

def check_submission_exists(assignment_id: int, student_id: int):
    """
    Checks if a student has a submission for the given assignment.
    """
    headers = get_headers()
    url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}/submissions/{student_id}"

    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        submission = response.json()
        if submission.get("workflow_state") in ["submitted", "graded"]:
            print(f"✅ Student {student_id} has a valid submission.")
            return True
        else:
            print(f"⚠️ Student {student_id} has not submitted yet (state: {submission.get('workflow_state')}).")
            return False
    else:
        print(f"❌ Error checking submission: {response.status_code} - {response.text}")
        return False


def upload_graded_rubric(student_id: int, assignment_id: int, graded_rubric_path: str) -> None:
    """
    Uploads the graded rubric to Canvas using query parameters and updates the final grade.

    Args:
        student_id (int): ID of the student being graded.
        assignment_id (int): ID of the assignment.
        graded_rubric_path (str): Path to the student's JSON file where the rubric is stored.
    """

    if not os.path.exists(graded_rubric_path):
        logging.warning(f"⚠️ Graded rubric not found for student {student_id}.")
        return

    # Load graded rubric
    with open(graded_rubric_path, "r", encoding="utf-8") as f:
        graded_rubric = json.load(f)

    # Sum up the rubric points for the final grade
    total_score = sum(float(criterion["score"]) for criterion in graded_rubric if "score" in criterion)

    # Build query parameters (instead of JSON)
    query_params = {
        "rubric_assessment[user_id]": student_id,
        "rubric_assessment[assessment_type]": "grading",
        "submission[posted_grade]": total_score,
    }

    # ✅ Modify criterion_id format for Canvas compatibility
    for criterion in graded_rubric:
        criterion_id = criterion['criterion_id']  # ✅ Change from `criterion__id` to `criterion_id`
        query_params[f"rubric_assessment[{criterion_id}][points]"] = float(criterion["score"])

        # Only add comments if they exist (Canvas API may reject empty strings)
        if "comment" in criterion and criterion["comment"].strip():
            query_params[f"rubric_assessment[{criterion_id}][comments]"] = criterion["comment"]

    # ✅ Correct Canvas API endpoint
    grading_url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}/submissions/{student_id}"

    headers = get_headers()

    # Debugging: Print API request details
    logging.info(f"🔍 Sending request to: {grading_url}")
    logging.info(f"📤 Query Parameters: {query_params}")

    # Send request using query parameters (NOT JSON)
    response = requests.put(grading_url, headers=headers, params=query_params)

    if response.status_code == 200:
        logging.info(f"✅ Successfully uploaded graded rubric for student {student_id}. Final grade: {total_score}")
    else:
        logging.error(f"❌ Failed to upload rubric for student {student_id}: {response.status_code} - {response.text}")

