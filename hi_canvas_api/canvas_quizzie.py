import json
import logging
import os
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
INSTITUTION_URL = os.getenv("INSTITUTION_URL")
API_VERSION = os.getenv("API_VERSION")
API_TOKEN = os.getenv("API_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


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

# Construct the base URL dynamically
BASE_URL = f"{INSTITUTION_URL}/api/{API_VERSION}"
NEW_QUIZ_BASE_URL = f"{INSTITUTION_URL}/api/quiz/v1"

def get_headers() -> dict:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def get_new_quiz_url(path: str) -> str:
    """Build a New Quizzes API URL from a relative path."""
    return f"{NEW_QUIZ_BASE_URL}{path}"

def get_quiz_questions(quiz_id):
    url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}/questions"
    headers = get_headers()
    questions = []

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        questions.extend(response.json())

        # Handle pagination
        next_url = response.links.get("next", {}).get("url")
        url = next_url if next_url else None

    return questions


def get_quiz_responses_now(quiz_id):
    """
    Fetches quiz responses from Canvas API using assignment submissions.
    Returns a dictionary of user responses.
    """
    # Get assignment ID linked to the quiz
    assignment_id = get_quiz_assignment_id(COURSE_ID, quiz_id)

    # Fetch quiz questions to map answer_id to actual text
    questions = get_quiz_questions(quiz_id)
    answer_map = {q["id"]: {a["id"]: a["text"] for a in q["answers"]} for q in questions}

    print("Answer Map:", answer_map)  # Debugging

    # Get all submissions for the assignment
    submissions = get_assignment_submissions(COURSE_ID, assignment_id)

    user_responses = {}

    for submission in submissions:
        user_id = submission["user_id"]

        # If the submission is empty or missing response data
        response_data = submission.get("submission_data", [])

        # If empty, check `submission_history`
        if not response_data and "submission_history" in submission:
            for attempt in reversed(submission["submission_history"]):  # Newest attempt first
                if attempt:
                    if attempt.get("workflow_state") in ["complete","graded"] and attempt.get("submission_data"):
                        response_data = attempt["submission_data"]
                        break  # Use the latest non-empty response

        print(f"\nUser {user_id} Submission Data: {response_data}")  # Debugging

        user_responses[user_id] = {}  # Initialize user response

        for item in response_data:
            question_id = item["question_id"]
            answer_id = item.get("answer_id")

            if answer_id:
                answer_text = answer_map.get(question_id, {}).get(answer_id, "Unknown Answer")
            else:
                answer_text = item.get("text", "Unknown Answer")  # Handle text-based answers

            if question_id == 243912:  # Personality Question
                user_responses[user_id]["personality"] = answer_text
            elif question_id == 243913:  # Discussion Usefulness Question
                user_responses[user_id]["discussion_usefulness"] = answer_text

    print("\nFinal Responses:", user_responses)  # Debugging
    return user_responses


def scrape_quiz_response(result_url):
    """
    Scrapes the quiz response from the result_url by extracting the selected answers.

    Args:
        result_url (str): The Canvas result URL for a student's quiz submission.

    Returns:
        list: A list of selected answers.
    """
    headers = get_headers()
    session = requests.Session()
    session.headers.update(headers)

    try:
        response = session.get(result_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching quiz result page: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    print("soup:", soup)
    # Find all answer elements
    selected_answers = []
    for element in soup.find_all(title=True):  # Looks at all elements with a "title" attribute
        title_text = element.get("title", "")
        if "Þú valdir þetta svar." in title_text:
            # Extract the answer text before "Þú valdir þetta svar."
            answer = title_text.split("Þú valdir þetta svar.")[0].strip()
            print("answer:", answer)
            selected_answers.append(answer)

    return selected_answers

def get_quiz_responses(quiz_id):
    """
    Retrieves individual student responses by scraping the result_url in Canvas.

    Args:
        quiz_id (int): The ID of the quiz.

    Returns:
        dict: A dictionary of student responses mapped to user IDs.
    """
    url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}/submissions"
    headers = get_headers()

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    quiz_submissions = response.json().get("quiz_submissions", [])

    if not quiz_submissions:
        print(f"No quiz submissions found for quiz ID {quiz_id}.")
        return {}

    student_responses = {}

    for submission in quiz_submissions:
        user_id = submission.get("user_id")
        result_url = submission.get("result_url")

        if not result_url:
            print(f"No result URL found for User ID {user_id}. Skipping.")
            student_responses[user_id] = []
            continue

        # Scrape the quiz response from the HTML page
        responses = scrape_quiz_response(result_url)
        student_responses[user_id] = responses

    return student_responses



def get_quiz_responses_old(quiz_id):
    """
    Retrieves individual student responses for a non-anonymous Canvas survey.

    Args:
        quiz_id (int): The ID of the quiz.

    Returns:
        dict: A dictionary of student responses mapped to user IDs.
    """
    url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}/submissions"
    headers = get_headers()
    params = {"include[]": "submission_history"}  # May help fetch responses in some cases

    response = requests.get(url, headers=headers, params=params)

    print("response:", response.json())

    response.raise_for_status()
    
    quiz_submissions = response.json().get("quiz_submissions", [])

    if not quiz_submissions:
        print(f"No quiz submissions found for quiz ID {quiz_id}.")
        return {}

    student_responses = {}

    for submission in quiz_submissions:
        user_id = submission.get("user_id")
        submission_id = submission.get("id")

        # Fetch detailed submission data
        submission_url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}/submissions/{submission_id}"
        try:
            response = requests.get(submission_url, headers=headers)
            response.raise_for_status()
            submission_data = response.json()

            # Extract student responses
            submission_history = submission_data.get("submission_history", [])
            if submission_history and "submission_data" in submission_history[0]:
                responses = submission_history[0]["submission_data"]
                student_responses[user_id] = responses
            else:
                print(f"No responses found for User ID {user_id}.")
                student_responses[user_id] = []

        except requests.exceptions.RequestException as e:
            print(f"Error fetching quiz responses for User ID {user_id}: {e}")
            student_responses[user_id] = []

    return student_responses

def get_published_quizzes() -> list:
    """Fetches all published quizzes in the course."""
    headers = get_headers()
    quizzes_url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes"

    published_quizzes = []
    page = 1

    while True:
        # Fetch quizzes with pagination support
        response = requests.get(quizzes_url, headers=headers, params={"page": page, "per_page": 100})
        response.raise_for_status()

        quizzes = response.json()
        if not quizzes:
            break  # Exit loop if no more quizzes

        for quiz in quizzes:
            if quiz.get("published"):
                published_quizzes.append({
                    "id": quiz.get("id"),
                    "title": quiz.get("title"),
                    "description": quiz.get("description"),
                    "due_at": quiz.get("due_at"),
                })

        page += 1

    return published_quizzes


def list_new_quizzes() -> list:
    """Fetches all New Quizzes in the course."""
    headers = get_headers()
    url = get_new_quiz_url(f"/courses/{COURSE_ID}/quizzes")
    quizzes = []

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        page_data = response.json()
        if not page_data:
            break

        quizzes.extend(page_data)
        url = response.links.get("next", {}).get("url")

    return quizzes


def get_published_new_quizzes() -> list:
    """Fetches all published New Quizzes in the course."""
    published_quizzes = []

    for quiz in list_new_quizzes():
        if quiz.get("published"):
            assignment_id = quiz.get("id")
            if isinstance(assignment_id, str) and assignment_id.isdigit():
                assignment_id = int(assignment_id)
            published_quizzes.append(
                {
                    "assignment_id": assignment_id,
                    "title": quiz.get("title"),
                    "due_at": quiz.get("due_at"),
                }
            )

    return published_quizzes


def get_new_quiz(assignment_id: int):
    """Fetches a single New Quiz by its assignment ID."""
    url = get_new_quiz_url(f"/courses/{COURSE_ID}/quizzes/{assignment_id}")
    response = requests.get(url, headers=get_headers())
    if response.status_code == 404:
        return None
    if response.ok:
        return response.json()
    if response.status_code >= 500:
        logging.warning(
            "Canvas returned %s while probing assignment %s as a New Quiz. Falling back to list lookup.",
            response.status_code,
            assignment_id,
        )
    else:
        response.raise_for_status()

    target_id = str(assignment_id)
    for quiz in list_new_quizzes():
        quiz_id = quiz.get("id")
        if str(quiz_id) == target_id:
            return quiz
    return None


def _unwrap_progress_payload(payload: dict) -> dict:
    """Normalizes Canvas progress responses that may be nested under 'progress'."""
    progress = payload.get("progress")
    if isinstance(progress, dict):
        return progress
    return payload


def create_new_quiz_report(
    assignment_id: int,
    report_type: str = "student_analysis",
    report_format: str = "csv",
) -> dict:
    """Starts a New Quiz report job and returns the progress object."""
    url = get_new_quiz_url(f"/courses/{COURSE_ID}/quizzes/{assignment_id}/reports")
    payload = {
        "quiz_report[report_type]": report_type,
        "quiz_report[format]": report_format,
    }
    response = requests.post(url, headers=get_headers(), data=payload)
    response.raise_for_status()
    return _unwrap_progress_payload(response.json())


def wait_for_progress(progress_url: str, timeout_seconds: int = 300, poll_seconds: int = 2) -> dict:
    """Polls a Canvas progress URL until the job completes or fails."""
    deadline = time.monotonic() + timeout_seconds

    while True:
        response = requests.get(progress_url, headers=get_headers())
        response.raise_for_status()
        progress = _unwrap_progress_payload(response.json())
        workflow_state = progress.get("workflow_state")

        if workflow_state == "completed":
            return progress
        if workflow_state == "failed":
            raise RuntimeError(f"Progress job failed: {json.dumps(progress, ensure_ascii=False)}")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for report generation after {timeout_seconds} seconds."
            )

        time.sleep(poll_seconds)


def download_new_quiz_report(
    assignment_id: int,
    output_path: str,
    report_type: str = "student_analysis",
    report_format: str = "csv",
) -> str:
    """Generates and downloads a New Quiz report to the requested path."""
    progress = create_new_quiz_report(
        assignment_id=assignment_id,
        report_type=report_type,
        report_format=report_format,
    )
    progress_url = progress.get("url")
    if not progress_url:
        raise RuntimeError(
            f"Canvas did not return a progress URL for New Quiz report: {json.dumps(progress, ensure_ascii=False)}"
        )

    completed_progress = wait_for_progress(progress_url)
    report_url = completed_progress.get("results", {}).get("url")
    if not report_url:
        raise RuntimeError(
            "Canvas completed the report job but did not return a download URL."
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    response = requests.get(report_url, headers=get_headers(), stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    return output_path

# Function to get quiz assignment ID
def get_quiz_assignment_id(course_id, quiz_id):
    """Fetches the assignment ID associated with a quiz."""
    url = f"{BASE_URL}/courses/{course_id}/quizzes/{quiz_id}"
    response = requests.get(url, headers=get_headers())
    response.raise_for_status()
    quiz_data = response.json()
    return quiz_data['assignment_id']

# Function to get detailed assignment submissions
def get_assignment_submissions(course_id, assignment_id):
    """
    Fetches all detailed submissions for an assignment, including submission history, with pagination.

    Args:
        course_id (int): The ID of the course.
        assignment_id (int): The ID of the assignment.

    Returns:
        list: A list of all submissions with detailed data.
    """
    submissions = []
    url = f"{BASE_URL}/courses/{course_id}/assignments/{assignment_id}/submissions"
    params = {"include[]": "submission_history"}
    headers = get_headers()

    while url:
        # Fetch data from the current page
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        submissions.extend(response.json())

        # Check if there's a next page in the 'Link' header
        next_url = response.links.get("next", {}).get("url")
        url = next_url if next_url else None

    return submissions

# Function to retrieve detailed quiz responses
def get_detailed_quiz_responses(quiz_id):
    """
    Retrieves detailed quiz responses, including student answers.

    Args:
        course_id (int): The ID of the course.
        quiz_id (int): The ID of the quiz.

    Returns:
        list: A list of detailed quiz responses.
    """
    # Get the assignment ID from the quiz
    assignment_id = get_quiz_assignment_id(COURSE_ID, quiz_id)

    # Get all submissions for the assignment
    submissions = get_assignment_submissions(COURSE_ID, assignment_id)
    print(submissions)
    detailed_responses = []
    for submission in submissions:
        if "submission_history" in submission:
            history = submission["submission_history"]
            if history and "submission_data" in history[0]:
                # Extract answers
                detailed_responses.append({
                    "user_id": submission["user_id"],
                    "submission_data": history[0]["submission_data"]
                })

    return detailed_responses


def add_question_to_quiz(quiz_id: int, question: dict, total_weight: int = 10) -> None:
    """Adds a question to an existing quiz on Canvas."""
    headers = get_headers()
    questions_url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}/questions"

    # Count the number of correct answers
    correct_count = sum(1 for choice in question["choices"] if choice.get("is_correct", False))
    if correct_count == 0:
        raise ValueError(f"No correct answers specified for question: {question['question']}")

    # Calculate weight for each correct answer
    correct_weight = int(total_weight / correct_count)
    print(f"Correct weight: {correct_weight}", total_weight / correct_count)

    # Determine question type
    question_type = "multiple_answers_question" if correct_count > 1 else "multiple_choice_question"

    # Prepare the question payload
    question_payload = {
        "question": {
            "question_name": question["question"],
            "question_text": question["question"],
            "question_type": question_type,
            "points_possible": total_weight,
            "answers": [
                {
                    "answer_text": choice["choice_text"],
                    "answer_weight": correct_weight if choice.get("is_correct", False) else 0,
                    "answer_comment_html": choice["feedback"]  # Feedback for this specific choice
                }
                for choice in question["choices"]
            ]
        }
    }

    # Post the question
    response = requests.post(questions_url, headers=headers, json=question_payload)
    response.raise_for_status()
    print(f"Added question: {question['question']}")



def create_quiz_from_json(json_file: str):
    """Creates a quiz on Canvas from a JSON file and returns the quiz ID and URL."""
    with open(json_file, "r", encoding="utf-8") as file:
        quiz_data = json.load(file)

    # Extract quiz metadata
    quiz_metadata = {
    "quiz": {
        "title": "Imported Quiz",
        "description": "Quiz imported via API",
        "published": False,  # Publish the quiz
        "show_correct_answers": True,  # Show correct answers and feedback
        "show_correct_answers_at": None,
        "hide_correct_answers_at": None,
        "one_question_at_a_time": False
    }
    }

    headers = get_headers()
    quiz_url = f"{BASE_URL}/courses/{COURSE_ID}/quizzes"

    # Create the quiz
    quiz_response = requests.post(quiz_url, headers=headers, json=quiz_metadata)
    quiz_response.raise_for_status()
    quiz_id = quiz_response.json()["id"]

    quiz_url = f"{INSTITUTION_URL}/courses/{COURSE_ID}/quizzes/{quiz_id}"
    print(f"Quiz created successfully: ID {quiz_id}")

    # Add questions to the quiz
    for question in quiz_data:
        add_question_to_quiz(quiz_id, question)

    return quiz_id, quiz_url


if __name__ == "__main__":
    # Specify the JSON file containing quiz data
    quiz_file = "quiz.json"  # Replace with your JSON file name

    try:
        # Create the quiz on Canvas
        create_quiz_from_json(quiz_file)

    except FileNotFoundError:
        print(f"File not found: {quiz_file}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except requests.exceptions.RequestException as e:
        print(f"API error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
