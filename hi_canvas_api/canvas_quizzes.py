import requests
import os
import json
import logging
from dotenv import load_dotenv
from typing import Optional, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables
INSTITUTION_URL = os.getenv("INSTITUTION_URL")
API_VERSION = os.getenv("API_VERSION", "v1")
API_TOKEN = os.getenv("API_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")

if not all([INSTITUTION_URL, API_TOKEN, COURSE_ID]):
    raise ValueError(
        "Missing environment variables. Please set INSTITUTION_URL, API_TOKEN and COURSE_ID."
    )

# Base URL for the Classic Quizzes API
QUIZZES_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}/quizzes"


def get_headers() -> dict:
    """Returns the headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def load_quiz(file_path: str) -> dict:
    """Loads quiz JSON data from a file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_quiz(quiz_data: dict) -> tuple:
    """
    Validate the structure of a quiz definition before sending it to Canvas.

    Each question must be a single-answer multiple choice question with exactly
    one option marked as ``correct``.

    Args:
        quiz_data (dict): Quiz data loaded from JSON.

    Returns:
        tuple: (is_valid: bool, messages: list[str])
    """
    errors = []

    if "title" not in quiz_data:
        errors.append("❌ Quiz is missing 'title' field.")

    questions = quiz_data.get("questions")
    if not questions:
        errors.append("❌ Quiz has no 'questions'.")
        return False, errors

    for idx, question in enumerate(questions, start=1):
        label = question.get("question_name") or f"#{idx}"

        if not question.get("question_text"):
            errors.append(f"❌ Question {label} is missing 'question_text'.")

        answers = question.get("answers", [])
        if len(answers) < 2:
            errors.append(f"❌ Question {label} needs at least two answers.")
            continue

        correct_count = sum(1 for a in answers if a.get("correct"))
        if correct_count != 1:
            errors.append(
                f"❌ Question {label} must have exactly one correct answer "
                f"(found {correct_count})."
            )

        for a_idx, answer in enumerate(answers, start=1):
            if not answer.get("text"):
                errors.append(f"❌ Question {label}, answer #{a_idx} is missing 'text'.")

    if errors:
        return False, errors
    return True, ["✅ Quiz definition is valid."]


def create_quiz(quiz_data: dict) -> Optional[int]:
    """
    Create an (empty) Classic Quiz in Canvas.

    Args:
        quiz_data (dict): Quiz metadata. Recognised keys: ``title`` (required),
            ``description``, ``quiz_type`` (default ``assignment``),
            ``time_limit`` (minutes), ``shuffle_answers`` (bool, default True),
            ``allowed_attempts`` (int, -1 = unlimited), ``published`` (bool).

    Returns:
        int | None: The new quiz ID, or None if creation failed.
    """
    quiz_payload = {
        "title": quiz_data["title"],
        "description": quiz_data.get("description", ""),
        "quiz_type": quiz_data.get("quiz_type", "assignment"),
        "shuffle_answers": quiz_data.get("shuffle_answers", True),
        "published": quiz_data.get("published", False),
    }
    if "time_limit" in quiz_data and quiz_data["time_limit"] is not None:
        quiz_payload["time_limit"] = quiz_data["time_limit"]
    if "allowed_attempts" in quiz_data:
        quiz_payload["allowed_attempts"] = quiz_data["allowed_attempts"]

    response = requests.post(QUIZZES_URL, headers=get_headers(), json={"quiz": quiz_payload})

    if response.status_code in (200, 201):
        quiz_id = response.json().get("id")
        logging.info(f"Quiz '{quiz_data['title']}' created successfully with ID: {quiz_id}")
        return quiz_id

    raise Exception(
        f"Failed to create quiz '{quiz_data['title']}': "
        f"{response.status_code} - {response.text}"
    )


def add_quiz_question(
    quiz_id: int, question: dict, quiz_group_id: Optional[int] = None
) -> Optional[int]:
    """
    Add a single multiple-choice question to an existing quiz.

    Args:
        quiz_id (int): The quiz to add the question to.
        question (dict): A question definition with keys ``question_text``
            (required), optional ``question_name``, ``points_possible``
            (default 1) and ``answers`` — a list of ``{"text": str,
            "correct": bool}`` dicts with exactly one correct answer.
        quiz_group_id (int, optional): If given, the question is placed inside
            this quiz question group (used for randomly drawn question banks).
            The question's ``quiz_group_id`` key overrides this argument.

    Returns:
        int | None: The new question ID, or None on failure.
    """
    answers_payload = [
        {
            "answer_text": answer["text"],
            "answer_weight": 100 if answer.get("correct") else 0,
        }
        for answer in question["answers"]
    ]

    question_body = {
        "question_name": question.get("question_name", ""),
        "question_text": question["question_text"],
        "question_type": "multiple_choice_question",
        "points_possible": question.get("points_possible", 1),
        "answers": answers_payload,
    }

    group_id = question.get("quiz_group_id", quiz_group_id)
    if group_id is not None:
        question_body["quiz_group_id"] = group_id

    question_payload = {"question": question_body}

    url = f"{QUIZZES_URL}/{quiz_id}/questions"
    response = requests.post(url, headers=get_headers(), json=question_payload)

    if response.status_code in (200, 201):
        question_id = response.json().get("id")
        logging.info(
            f"Added question '{question.get('question_name', '')}' (ID: {question_id})."
        )
        return question_id

    raise Exception(
        f"Failed to add question '{question.get('question_name', '')}': "
        f"{response.status_code} - {response.text}"
    )


def create_quiz_with_questions(quiz_data: dict, validate: bool = True) -> Optional[int]:
    """
    Create a full multiple-choice quiz in one call: create the quiz, then add
    every question from ``quiz_data['questions']``.

    Args:
        quiz_data (dict): Quiz definition (see ``create_quiz``) that also
            contains a ``questions`` list (see ``add_quiz_question``).
        validate (bool): If True (default), run ``validate_quiz`` first and abort
            on any error.

    Returns:
        int | None: The new quiz ID, or None if validation failed.
    """
    if validate:
        is_valid, messages = validate_quiz(quiz_data)
        for message in messages:
            logging.info(message)
        if not is_valid:
            logging.error("Quiz definition is invalid. Aborting.")
            return None

    quiz_id = create_quiz(quiz_data)
    for question in quiz_data["questions"]:
        add_quiz_question(quiz_id, question)

    logging.info(
        f"Quiz '{quiz_data['title']}' now has {len(quiz_data['questions'])} question(s)."
    )
    return quiz_id


def list_quizzes() -> list:
    """Lists all quizzes in the course and returns them as a list."""
    response = requests.get(QUIZZES_URL, headers=get_headers())

    if response.status_code != 200:
        raise Exception(
            f"Failed to retrieve quizzes: {response.status_code} - {response.text}"
        )

    quizzes = response.json()
    if quizzes:
        logging.info("📌 Available quizzes:")
        for quiz in quizzes:
            logging.info(f"- {quiz['title']} (ID: {quiz['id']})")
    else:
        logging.info("ℹ️ No quizzes found.")
    return quizzes


def set_quiz_published(quiz_id: int, published: bool) -> None:
    """
    Publish or unpublish an existing quiz.

    Args:
        quiz_id (int): The quiz to update.
        published (bool): True to publish, False to move it back to draft.
    """
    url = f"{QUIZZES_URL}/{quiz_id}"
    response = requests.put(url, headers=get_headers(), json={"quiz": {"published": published}})

    if response.status_code in (200, 201):
        state = "published" if published else "unpublished"
        logging.info(f"Quiz ID {quiz_id} {state}.")
    else:
        raise Exception(
            f"Failed to update quiz {quiz_id} publish state: "
            f"{response.status_code} - {response.text}"
        )


def delete_quiz(quiz_id: int) -> None:
    """Deletes a quiz by ID."""
    url = f"{QUIZZES_URL}/{quiz_id}"
    response = requests.delete(url, headers=get_headers())

    if response.status_code == 200:
        logging.info(f"Quiz ID {quiz_id} deleted successfully.")
    else:
        raise Exception(
            f"Failed to delete quiz {quiz_id}: {response.status_code} - {response.text}"
        )
