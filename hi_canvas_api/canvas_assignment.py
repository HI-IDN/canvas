import requests
import os
import logging
import mimetypes
from dotenv import load_dotenv
from typing import Optional, Any
import base64
import json
import re
import nbformat
import traceback
from datetime import datetime, timezone
from nbconvert import MarkdownExporter, PDFExporter
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


def get_submissions_with_options(
    assignment_id: int,
    include: Optional[list[str]] = None,
    grouped: bool = False,
) -> list:
    """Retrieve submissions with optional include/grouped parameters."""
    headers = get_headers()
    submissions_url = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/assignments/{assignment_id}/submissions"
    params = {}
    if include:
        params["include[]"] = include
    if grouped:
        params["grouped"] = "true"

    submissions = []
    first_request = True
    while submissions_url:
        if first_request:
            response = requests.get(submissions_url, headers=headers, params=params)
            first_request = False
        else:
            response = requests.get(submissions_url, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve submissions for assignment {assignment_id}: "
                f"{response.status_code} - {response.text}"
            )

        data = response.json()
        submissions.extend(data)

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


class StripImageOutputsPreprocessor(Preprocessor):
    """Remove image outputs so Markdown stays text-focused."""

    IMAGE_MIME_TYPES = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/svg+xml",
        "application/pdf",
    }

    def preprocess_cell(self, cell, resources, index):
        if "outputs" not in cell:
            return cell, resources

        cleaned_outputs = []
        for output in cell["outputs"]:
            data = output.get("data")
            if not data:
                cleaned_outputs.append(output)
                continue

            cleaned_data = {
                mime: value for mime, value in data.items() if mime not in self.IMAGE_MIME_TYPES
            }
            if cleaned_data:
                output["data"] = cleaned_data
                cleaned_outputs.append(output)

        cell["outputs"] = cleaned_outputs
        return cell, resources


class StripMarkdownImagesPreprocessor(Preprocessor):
    """Remove image markup from markdown cells."""

    def preprocess_cell(self, cell, resources, index):
        if cell.get("cell_type") != "markdown" or "source" not in cell:
            return cell, resources

        source = cell["source"]
        if isinstance(source, list):
            text = "".join(source)
            cell["source"] = [strip_markdown_images(text)]
        else:
            cell["source"] = strip_markdown_images(source)

        return cell, resources

def clean_markdown(md_content):
    """Removes <div>, <style>, and execution warnings from Markdown content."""
    md_content = re.sub(r"<style.*?>.*?</style>", "", md_content, flags=re.DOTALL)  # Remove <style> elements
    md_content = re.sub(r"<div.*?>.*?</div>", "", md_content, flags=re.DOTALL)  # Remove <div> elements
    md_content = re.sub(r"<ipython-input-.*?>.*?</ipython-input-.*?>", "", md_content, flags=re.DOTALL)  # Remove execution warnings
    md_content = strip_ansi(md_content)  # Remove terminal color codes (if any)
    return md_content


def strip_markdown_images(md_content):
    """Remove Markdown/HTML image tags to keep output text-only."""
    image_exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".tif")

    md_content = re.sub(r"<img\b[^>]*>", "", md_content, flags=re.IGNORECASE)
    md_content = re.sub(r"!\[[^]]*\]\[[^]]*\]", "", md_content)

    def strip_inline_images(match):
        url = match.group(1).strip().lower()
        if "data:image" in url or any(ext in url for ext in image_exts):
            return ""
        return match.group(0)

    md_content = re.sub(
        r"!\[[^]]*\]\(([^)]*)\)",
        strip_inline_images,
        md_content,
        flags=re.DOTALL,
    )

    def strip_image_refs(match):
        url = match.group(1).strip().lower()
        if url.startswith("data:image"):
            return ""
        if url.endswith(image_exts):
            return ""
        return match.group(0)

    md_content = re.sub(
        r"^\s*\[[^]]+\]:\s*(\S+).*$",
        strip_image_refs,
        md_content,
        flags=re.MULTILINE,
    )
    md_content = re.sub(r"\n{3,}", "\n\n", md_content)
    return md_content

def convert_ipynb_to_md(notebook_path: str, output_filename: str, drop_images: bool = True) -> str:
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
    #md_exporter.register_preprocessor(RemoveHTMLPreprocessor, enabled=True)
    if drop_images:
        md_exporter.register_preprocessor(StripImageOutputsPreprocessor, enabled=True)
        md_exporter.register_preprocessor(StripMarkdownImagesPreprocessor, enabled=True)

    md_exporter.exclude_output = False  # Ensure outputs are included
    md_exporter.exclude_output_prompt = False  # Include output prompts
    md_exporter.exclude_input_prompt = False  # Include input prompts

    # Convert notebook to Markdown
    markdown_output, _ = md_exporter.from_notebook_node(notebook_content)

    # Further clean the output with regex (for remaining <div> and <style>)
    #markdown_output = clean_markdown(markdown_output)
    if drop_images:
        markdown_output = strip_markdown_images(markdown_output)

    md_path = os.path.join(output_folder, output_filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    print(f"Notebook converted to Markdown: {md_path}")
    return md_path


def convert_ipynb_to_pdf(notebook_path: str, output_filename: str) -> str:
    """Convert a Jupyter notebook to a PDF file."""
    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    output_folder = os.path.dirname(notebook_path)
    os.makedirs(output_folder, exist_ok=True)

    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_content = nbformat.read(f, as_version=4)

    notebook_content = _rewrite_markdown_data_images(notebook_content, output_folder, notebook_path)

    pdf_exporter = PDFExporter()
    pdf_exporter.exclude_output = False
    pdf_exporter.exclude_output_prompt = False
    pdf_exporter.exclude_input_prompt = False
    resources = {"metadata": {"path": output_folder}}
    pdf_output, _ = pdf_exporter.from_notebook_node(notebook_content, resources=resources)

    pdf_path = os.path.join(output_folder, output_filename)
    with open(pdf_path, "wb") as f:
        f.write(pdf_output)

    print(f"Notebook converted to PDF: {pdf_path}")
    return pdf_path


def _write_pdf_export_error(log_path: str, notebook_path: str, error: Exception) -> None:
    """Write a PDF export error log for later debugging."""
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Notebook: {notebook_path}\n")
        f.write(f"Error: {error}\n\n")
        f.write(traceback.format_exc())


def parse_canvas_time(timestamp: Optional[str]) -> Optional[datetime]:
    if not timestamp:
        return None
    ts = timestamp.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sanitize_folder_name(value: str) -> str:
    cleaned = re.sub(r"[\\\\/:*?\"<>|]+", "_", value.strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def get_group_category_groups(group_category_id: int) -> dict:
    """Return a mapping of group_id -> group_name for a group category."""
    headers = get_headers()
    url = f"{INSTITUTION_URL}/api/{API_VERSION}/group_categories/{group_category_id}/groups"
    groups = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve groups for category {group_category_id}: "
                f"{response.status_code} - {response.text}"
            )
        data = response.json()
        groups.extend(data)

        url = None
        if "Link" in response.headers:
            links = response.headers["Link"].split(",")
            for link in links:
                if 'rel="next"' in link:
                    url = link[link.find("<") + 1 : link.find(">")]
                    break

    return {group["id"]: group["name"] for group in groups if "id" in group}


def get_group_members(group_id: int) -> list:
    """Return a list of group members (id, name)."""
    headers = get_headers()
    url = f"{INSTITUTION_URL}/api/{API_VERSION}/groups/{group_id}/users"
    members = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve members for group {group_id}: "
                f"{response.status_code} - {response.text}"
            )
        data = response.json()
        members.extend(data)

        url = None
        if "Link" in response.headers:
            links = response.headers["Link"].split(",")
            for link in links:
                if 'rel="next"' in link:
                    url = link[link.find("<") + 1 : link.find(">")]
                    break

    return [{"id": m.get("id"), "name": m.get("name")} for m in members]


def _rewrite_markdown_data_images(notebook_content, output_folder: str, notebook_path: str):
    """Extract data:image URIs in markdown cells into files and rewrite links."""
    image_ext_map = {
        "png": "png",
        "jpeg": "jpg",
        "jpg": "jpg",
        "gif": "gif",
        "svg+xml": "svg",
        "webp": "webp",
        "bmp": "bmp",
        "tiff": "tiff",
        "tif": "tif",
    }
    pattern = re.compile(r"!\[[^]]*\]\((data:image/[^)]*)\)", flags=re.DOTALL)
    basename = os.path.splitext(os.path.basename(notebook_path))[0]
    counter = 0

    for cell in notebook_content.get("cells", []):
        if cell.get("cell_type") != "markdown" or "source" not in cell:
            continue

        source = cell["source"]
        text = "".join(source) if isinstance(source, list) else source

        def replace_match(match):
            nonlocal counter
            data_uri = match.group(1)
            if not data_uri.startswith("data:image/"):
                return match.group(0)

            header, b64_data = data_uri.split(",", 1)
            mime_match = re.match(r"data:image/([^;]+)", header)
            if not mime_match:
                return match.group(0)

            mime = mime_match.group(1).lower()
            ext = image_ext_map.get(mime, "png")
            counter += 1
            filename = f"{basename}_img_{counter:03d}.{ext}"
            image_path = os.path.join(output_folder, filename)

            try:
                decoded = base64.b64decode(re.sub(r"\\s+", "", b64_data))
                with open(image_path, "wb") as f:
                    f.write(decoded)
            except Exception:
                return match.group(0)

            return match.group(0).replace(data_uri, filename)

        text = pattern.sub(replace_match, text)
        cell["source"] = [text] if isinstance(source, list) else text

    return notebook_content


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

def save_submissions_with_attachments(
    assignment_id: int,
    folder_path: str,
    export_pdf: bool = False,
    drop_images: bool = True,
) -> None:
    """Download all attachments for submissions of an assignment and save them locally."""
    # Create the folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logging.info(f"Created folder: {folder_path}")

    print("Assignment ID:", assignment_id)

    assignment_details = get_single_assignment(assignment_id)
    group_category_id = assignment_details.get("group_category_id") if assignment_details else None
    is_group_assignment = bool(group_category_id)

    if is_group_assignment:
        group_name_by_id = {
            str(group_id): name for group_id, name in get_group_category_groups(group_category_id).items()
        }
        group_members_cache = {}
        submissions = get_submissions_with_options(assignment_id, include=["user", "group"])

        group_latest = {}
        ungrouped_latest = {}
        for submission in submissions:
            if submission.get("workflow_state") not in {"submitted", "graded"}:
                continue
            group_id = submission.get("group_id") or submission.get("group", {}).get("id")
            ts = parse_canvas_time(
                submission.get("updated_at")
                or submission.get("submitted_at")
                or submission.get("graded_at")
            )
            if group_id:
                group_id_str = str(group_id)
                existing = group_latest.get(group_id_str)
                if not existing or (ts and ts > existing[1]):
                    group_latest[group_id_str] = (submission, ts)
            else:
                user_id = submission.get("user_id")
                if not user_id:
                    continue
                existing = ungrouped_latest.get(user_id)
                if not existing or (ts and ts > existing[1]):
                    ungrouped_latest[user_id] = (submission, ts)

        submissions_to_process = (
            [entry[0] for entry in group_latest.values()]
            + [entry[0] for entry in ungrouped_latest.values()]
        )
    else:
        submissions_to_process = get_submissions_with_options(assignment_id, include=["user"])

    for submission in submissions_to_process:
        # Only process submissions that have been submitted
#        print(submission)
        if submission.get("workflow_state") not in {"submitted", "graded"}:
            logging.info(f"Skipping user ID {submission.get('user_id')} as they have not submitted.")
            continue

        user_id = submission.get("user_id")
        user_name = submission.get("user", {}).get("name", f"User_{user_id}")
        group_id = submission.get("group_id") or submission.get("group", {}).get("id")
        group_id_str = str(group_id) if group_id is not None else None
        group_name = submission.get("group", {}).get("name")
        if is_group_assignment and group_id_str and not group_name:
            group_name = group_name_by_id.get(group_id_str)

        if is_group_assignment and group_id_str:
            target_folder = os.path.join(folder_path, f"Group_{group_id_str}")
        elif is_group_assignment:
            target_folder = os.path.join(folder_path, f"User_{user_id}")
        else:
            target_folder = os.path.join(folder_path, user_name)

        if is_group_assignment and not os.path.exists(target_folder):
            os.makedirs(target_folder)

        # Check for attachments
        attachments = submission.get("attachments", [])
        if attachments:
            for attachment in attachments:
                file_name = attachment.get("display_name", "unknown_file")
                file_url = attachment.get("url")
                if file_url:
                    # Save file to the folder
                    if not os.path.exists(target_folder):
                        os.makedirs(target_folder)

                    save_path = os.path.join(target_folder, file_name)
                    download_attachment(file_url, save_path)
                    # After downloading each .ipynb file
                    if file_name.endswith(".ipynb"):
                        json_output_path = os.path.join(
                            target_folder,
                            f"{os.path.splitext(file_name)[0]}_cells.json",
                        )
                        #process_ipynb(save_path, json_output_path)
                        # Convert the notebook to Markdown
                        convert_ipynb_to_md(save_path, "assignment.md", drop_images=drop_images)
                        if export_pdf:
                            try:
                                convert_ipynb_to_pdf(save_path, "assignment.pdf")
                            except Exception as exc:
                                logging.error("PDF export failed for %s: %s", save_path, exc)
                                error_log_path = os.path.join(target_folder, "assignment_pdf_error.log")
                                _write_pdf_export_error(error_log_path, save_path, exc)
        else:
            logging.info(f"No attachments found for submission by {user_name}.")

        if is_group_assignment:
            if group_id_str:
                group_id_int = (
                    int(group_id) if isinstance(group_id, (int, str)) and str(group_id).isdigit() else None
                )
                if group_id_str not in group_members_cache and group_id_int is not None:
                    try:
                        group_members_cache[group_id_str] = get_group_members(group_id_int)
                    except Exception as exc:
                        logging.error("Failed to load members for group %s: %s", group_id, exc)
                        group_members_cache[group_id_str] = []

                members_path = os.path.join(target_folder, "group_members.json")
                with open(members_path, "w", encoding="utf-8") as f:
                    json.dump(group_members_cache.get(group_id_str, []), f, ensure_ascii=False, indent=2)

            meta = {
                "group_id": group_id,
                "group_name": group_name,
                "submitted_by_user_id": user_id,
                "submitted_by_user_name": user_name,
                "submitted_at": submission.get("submitted_at"),
                "updated_at": submission.get("updated_at"),
                "workflow_state": submission.get("workflow_state"),
            }
            meta_path = os.path.join(target_folder, "submission_meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)


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


def upload_graded_rubric(
    student_id: int,
    assignment_id: int,
    graded_rubric_path: str,
    comment_file_ids: Optional[list[int]] = None,
    comment_text: Optional[str] = None,
) -> None:
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

    if comment_text is not None:
        query_params["comment[text_comment]"] = comment_text
    if comment_file_ids:
        query_params["comment[file_ids][]"] = comment_file_ids

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


def post_submission_comment(
    student_id: int,
    assignment_id: int,
    comment_text: str,
    group_comment: bool = False,
    file_ids: Optional[list[int]] = None,
):
    """Post a comment to a student's assignment submission."""
    if not comment_text.strip() and not file_ids:
        logging.warning("Empty comment for student %s; skipping.", student_id)
        return False, None, "empty comment"

    submission_url = (
        f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}"
        f"/assignments/{assignment_id}/submissions/{student_id}"
    )
    comment_url = (
        f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}"
        f"/assignments/{assignment_id}/submissions/{student_id}/comments"
    )
    headers = get_headers()
    payload = {"comment[text_comment]": comment_text}
    if file_ids:
        payload["comment[file_ids][]"] = file_ids
    if group_comment:
        payload["comment[group_comment]"] = "true"

    response = requests.put(submission_url, headers=headers, params=payload)
    if response.status_code in {200, 201}:
        logging.info("Posted comment for student %s via submissions endpoint.", student_id)
        return True, response.status_code, response.text

    response = requests.post(comment_url, headers=headers, data=payload)
    if response.status_code in {200, 201}:
        logging.info("Posted comment for student %s via comments endpoint.", student_id)
        return True, response.status_code, response.text

    logging.error(
        "Failed to post comment for student %s: %s - %s",
        student_id,
        response.status_code,
        response.text,
    )
    return False, response.status_code, response.text


def _extract_file_id(upload_info: Any) -> Optional[int]:
    if not isinstance(upload_info, dict):
        return None
    if isinstance(upload_info.get("id"), int):
        return upload_info["id"]
    attachment = upload_info.get("attachment")
    if isinstance(attachment, dict) and isinstance(attachment.get("id"), int):
        return attachment["id"]
    file_obj = upload_info.get("file")
    if isinstance(file_obj, dict) and isinstance(file_obj.get("id"), int):
        return file_obj["id"]
    return None


def upload_submission_comment_file(
    student_id: int,
    assignment_id: int,
    file_path: str,
) -> Optional[int]:
    """Upload a file for a submission comment and return the new file ID."""
    if not os.path.exists(file_path):
        logging.warning("Attachment not found: %s", file_path)
        return None

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(file_path)

    init_url = (
        f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}"
        f"/assignments/{assignment_id}/submissions/{student_id}/comments/files"
    )
    payload = {"name": file_name, "size": file_size}
    if content_type:
        payload["content_type"] = content_type

    init_response = requests.post(init_url, headers=get_headers(), data=payload)
    if init_response.status_code not in {200, 201}:
        logging.error(
            "Failed to initiate attachment upload for student %s: %s - %s",
            student_id,
            init_response.status_code,
            init_response.text,
        )
        return None

    upload_data = init_response.json()
    upload_url = upload_data.get("upload_url")
    upload_params = upload_data.get("upload_params", {})
    if not upload_url:
        logging.error("Invalid upload init response: %s", upload_data)
        return None

    with open(file_path, "rb") as file:
        upload_response = requests.post(
            upload_url,
            data=upload_params,
            files={"file": (file_name, file)},
            allow_redirects=False,
        )

    file_info = None
    location = upload_response.headers.get("Location")
    if upload_response.status_code in {301, 302, 303, 307, 308} and location:
        finalize_response = requests.get(location, headers=get_headers())
        if finalize_response.status_code in {200, 201}:
            try:
                file_info = finalize_response.json()
            except ValueError:
                file_info = None
    else:
        try:
            file_info = upload_response.json()
        except ValueError:
            file_info = None

    if (not file_info) and location:
        finalize_response = requests.get(location, headers=get_headers())
        if finalize_response.status_code in {200, 201}:
            try:
                file_info = finalize_response.json()
            except ValueError:
                file_info = None

    file_id = _extract_file_id(file_info)
    if not file_id:
        logging.error("Failed to complete attachment upload for student %s.", student_id)
        return None

    logging.info("Uploaded attachment for student %s (file_id=%s).", student_id, file_id)
    return file_id
