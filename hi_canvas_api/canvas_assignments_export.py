import argparse
import json
import logging
import os
import re

from bs4 import BeautifulSoup

from canvas_assignment import (
    get_single_assignment,
    get_assignment_rubric,
    list_assignments,
    save_empty_grading_rubric,
    save_rubric_to_json,
    save_submissions_with_attachments,
)
from canvas_quizzie import (
    download_new_quiz_report,
    get_new_quiz,
    get_detailed_quiz_responses,
    get_published_new_quizzes,
    get_published_quizzes,
    get_quiz_questions,
)
from canvas_rubric import rubric_to_graderubric
from canvas_students import get_all_students


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def is_probable_new_quiz_assignment(assignment: dict) -> bool:
    """Heuristic guard so normal assignments do not hit the New Quizzes report API."""
    submission_types = assignment.get("submission_types") or []
    if "external_tool" in submission_types:
        return True

    external_tool_tag_attributes = assignment.get("external_tool_tag_attributes") or {}
    url = str(external_tool_tag_attributes.get("url") or "").lower()
    if "quiz_lti" in url:
        return True

    return False


def clean_text(text):
    """Remove HTML tags and unnecessary whitespace from text."""
    return BeautifulSoup(text, "html.parser").get_text().strip() if text else ""


def normalize_text(text):
    """Standardize text by removing extra spaces and converting to lowercase."""
    return text.strip().lower() if text else ""


def map_student_answers_to_questions(submission_data, quiz_questions):
    """Map numeric quiz response IDs to descriptions and classify as radio or text."""
    answer_map = {}

    for response in submission_data:
        question_id = response["question_id"]
        answer_text = response["text"].strip() if response["text"] else ""

        question_info = next((q for q in quiz_questions if q["id"] == question_id), None)

        question_type = "text"
        if question_info and "answers" in question_info:
            question_type = "radio"
            if answer_text.isdigit():
                answer_option = next(
                    (a for a in question_info.get("answers", []) if str(a["id"]) == answer_text),
                    None,
                )
                if answer_option:
                    answer_text = answer_option["text"]

        answer_text = clean_text(answer_text)
        answer_map[question_id] = (answer_text, question_type)

    return answer_map


def save_quiz_as_student_grading_rubric(quiz_id, original_rubric, grade_rubric, folder_path):
    """Process quiz responses and map them to the grading rubric."""
    try:
        rubric_map = {
            criterion["id"]: {
                "name": criterion["description"],
                "ratings": {
                    normalize_text(rating["description"]): rating["points"]
                    for rating in criterion.get("ratings", [])
                },
            }
            for criterion in original_rubric
        }

        if not rubric_map:
            logging.error("Original rubric is empty or malformed.")
            return

        detailed_responses = get_detailed_quiz_responses(quiz_id)
        quiz_questions = get_quiz_questions(quiz_id)

        for response in detailed_responses:
            user_id = response["user_id"]

            if "submission_data" not in response:
                logging.warning("No submission data for user %s. Skipping.", user_id)
                continue

            submission_data = response["submission_data"]

            if len(submission_data) != 2 * len(grade_rubric):
                logging.warning(
                    "Mismatch in number of questions for user %s. Expected %s, got %s.",
                    user_id,
                    2 * len(grade_rubric),
                    len(submission_data),
                )
                continue

            mapped_answers = map_student_answers_to_questions(submission_data, quiz_questions)

            comment_responses = submission_data[0::2]
            score_responses = submission_data[1::2]

            completed_rubric = []
            for idx, criterion in enumerate(grade_rubric):
                criterion_id = criterion["criterion_id"]
                rubric_entry = rubric_map.get(criterion_id)

                if rubric_entry is None:
                    logging.warning(
                        "No matching rubric entry for criterion_id %s. Skipping.",
                        criterion_id,
                    )
                    continue

                score_entry = score_responses[idx]
                comment_entry = comment_responses[idx]

                comment, _ = mapped_answers.get(comment_entry["question_id"], ("", "text"))
                selected_description, _ = mapped_answers.get(score_entry["question_id"], ("", "radio"))
                normalized_description = normalize_text(selected_description)

                if not selected_description:
                    logging.warning(
                        "User %s did not answer the radio button for %s. Defaulting to 0.",
                        user_id,
                        rubric_entry["name"],
                    )
                    score = 0
                elif normalized_description in rubric_entry["ratings"]:
                    score = rubric_entry["ratings"][normalized_description]
                else:
                    logging.warning(
                        "Unknown rating description '%s' for %s (user %s).",
                        selected_description,
                        rubric_entry["name"],
                        user_id,
                    )
                    logging.warning(
                        "Available ratings for %s: %s",
                        rubric_entry["name"],
                        list(rubric_entry["ratings"].keys()),
                    )
                    score = 0

                completed_rubric.append(
                    {
                        "criterion_id": criterion_id,
                        "criterion_name": criterion["criterion_name"],
                        "max_points": criterion["max_points"],
                        "score": score,
                        "comment": comment,
                    }
                )

            student_folder = os.path.join(folder_path, f"user_{user_id}")
            os.makedirs(student_folder, exist_ok=True)

            output_file = os.path.join(student_folder, "grading_rubric_student.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(completed_rubric, f, indent=4, ensure_ascii=False)

            logging.info("Saved graded rubric for user %s", user_id)

    except Exception as exc:
        logging.error("Error processing quiz %s: %s", quiz_id, exc)


def generate_student_list_json(root_dir, output_json="students_list.json"):
    """Generate a JSON file mapping students to their grading rubric file paths."""
    if not os.path.exists(root_dir):
        raise FileNotFoundError(f"Root directory '{root_dir}' does not exist.")

    student_list = get_all_students()
    students = {str(student["id"]): student["name"] for student in student_list}

    students_list = []
    seen_student_ids = set()
    for entry in os.listdir(root_dir):
        entry_path = os.path.join(root_dir, entry)
        if not os.path.isdir(entry_path) or entry.startswith("Group_"):
            continue

        meta_path = os.path.join(entry_path, "submission_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as handle:
                    meta = json.load(handle)
            except Exception:
                meta = {}

        user_id = None
        if meta.get("submitted_by_user_id") is not None:
            user_id = str(meta.get("submitted_by_user_id"))
        else:
            match = re.match(r"[Uu]ser_(\d+)", entry)
            if match:
                user_id = match.group(1)

        student_name = (
            meta.get("submitted_by_user_name")
            or (students.get(user_id) if user_id else None)
            or entry
        )
        if user_id and user_id in seen_student_ids:
            continue

        grading_rubric_path = os.path.join(entry_path, "grading_rubric.json")
        evaluation_file_path = (
            os.path.abspath(grading_rubric_path) if os.path.exists(grading_rubric_path) else ""
        )

        students_list.append(
            {
                "student_id": user_id or "",
                "name": student_name,
                "file": evaluation_file_path,
                "folder": os.path.abspath(entry_path),
            }
        )
        if user_id:
            seen_student_ids.add(user_id)

    students_list.sort(key=lambda s: s["name"].split()[0].lower())

    output_json = os.path.join(root_dir, output_json)
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(students_list, json_file, ensure_ascii=False, indent=4)

    print(f"Successfully generated '{output_json}' with {len(students_list)} students.")

    legacy_path = os.path.join(root_dir, "student_list.json")
    if output_json != legacy_path:
        with open(legacy_path, "w", encoding="utf-8") as json_file:
            json.dump(students_list, json_file, ensure_ascii=False, indent=4)


def generate_group_list_json(root_dir, output_json="group_list.json"):
    """Generate a JSON file with group folders, members, and submission metadata."""
    if not os.path.exists(root_dir):
        raise FileNotFoundError(f"Root directory '{root_dir}' does not exist.")

    group_dirs = [
        d
        for d in os.listdir(root_dir)
        if d.startswith("Group_") and os.path.isdir(os.path.join(root_dir, d))
    ]

    groups_list = []
    for group_dir in group_dirs:
        group_path = os.path.join(root_dir, group_dir)
        members_path = os.path.join(group_path, "group_members.json")
        meta_path = os.path.join(group_path, "submission_meta.json")

        members = []
        if os.path.exists(members_path):
            try:
                with open(members_path, "r", encoding="utf-8") as f:
                    members = json.load(f)
            except Exception:
                members = []

        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}

        groups_list.append(
            {
                "group_folder": os.path.abspath(group_path),
                "group_name": meta.get("group_name") or group_dir.replace("Group_", "").strip(),
                "group_id": meta.get("group_id"),
                "submitted_by_user_id": meta.get("submitted_by_user_id"),
                "submitted_by_user_name": meta.get("submitted_by_user_name"),
                "submitted_at": meta.get("submitted_at"),
                "updated_at": meta.get("updated_at"),
                "members": members,
            }
        )

    output_json = os.path.join(root_dir, output_json)
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(groups_list, json_file, ensure_ascii=False, indent=4)

    print(f"Successfully generated '{output_json}' with {len(groups_list)} groups.")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve all assignments for a Canvas course and export rubric data."
    )
    parser.add_argument(
        "--assignment_id",
        type=int,
        default=None,
        help="Optional assignment ID to process. If not provided, available assignments will be listed.",
    )
    parser.add_argument(
        "--quiz_id",
        type=int,
        default=None,
        help="Optional Classic Quiz ID to process (default: None).",
    )
    parser.add_argument(
        "--new_quiz_report_format",
        choices=["csv", "json"],
        default="csv",
        help="Export format for New Quiz student analysis reports.",
    )
    parser.add_argument(
        "--export_pdf",
        action="store_true",
        help="Also export notebook submissions to assignment.pdf (requires PDF export tooling).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing Group_* or user folders before downloading submissions.",
    )

    args = parser.parse_args()

    if args.assignment_id is None:
        print("No assignment ID provided. Listing available assignments:")
        list_assignments()
        for quiz in get_published_quizzes():
            print(f"Classic Quiz ID: {quiz['id']} - {quiz['title']}")
        for quiz in get_published_new_quizzes():
            print(f"New Quiz Assignment ID: {quiz['assignment_id']} - {quiz['title']}")
        return

    assignment_id = args.assignment_id
    quiz_id = args.quiz_id if args.quiz_id else None
    folder_path = f"./assignments/assignment_{assignment_id}"
    os.makedirs(folder_path, exist_ok=True)

    try:
        assignment_details = get_single_assignment(assignment_id)
        new_quiz = None
        if is_probable_new_quiz_assignment(assignment_details):
            new_quiz = get_new_quiz(assignment_id)

        if args.clean:
            for name in os.listdir(folder_path):
                if name.startswith("Group_"):
                    target = os.path.join(folder_path, name)
                    if os.path.isdir(target):
                        for root, dirs, files in os.walk(target, topdown=False):
                            for file in files:
                                os.remove(os.path.join(root, file))
                            for d in dirs:
                                os.rmdir(os.path.join(root, d))
                        os.rmdir(target)
                else:
                    target = os.path.join(folder_path, name)
                    if os.path.isdir(target):
                        for root, dirs, files in os.walk(target, topdown=False):
                            for file in files:
                                os.remove(os.path.join(root, file))
                            for d in dirs:
                                os.rmdir(os.path.join(root, d))
                        os.rmdir(target)

        save_submissions_with_attachments(
            assignment_id,
            folder_path,
            export_pdf=args.export_pdf,
        )

        if new_quiz and not quiz_id:
            output_path = os.path.join(
                folder_path,
                f"new_quiz_student_analysis.{args.new_quiz_report_format}",
            )
            saved_path = download_new_quiz_report(
                assignment_id=assignment_id,
                output_path=output_path,
                report_type="student_analysis",
                report_format=args.new_quiz_report_format,
            )
            logging.info(
                "Exported New Quiz report for assignment %s (%s) to %s",
                assignment_id,
                new_quiz.get("title"),
                saved_path,
            )
        else:
            rubric = get_assignment_rubric(assignment_id)
            grading_rubric = rubric_to_graderubric(rubric) if rubric else []

            if rubric:
                with open(os.path.join(folder_path, "grading_rubric.json"), "w", encoding="utf-8") as f:
                    json.dump(grading_rubric, f, ensure_ascii=False, indent=4)

                save_rubric_to_json(folder_path, assignment_id)
                save_empty_grading_rubric(folder_path, assignment_id)
            else:
                logging.info("Assignment %s has no rubric. Skipping rubric export.", assignment_id)

        if quiz_id:
            save_quiz_as_student_grading_rubric(quiz_id, rubric, grading_rubric, folder_path)

        generate_student_list_json(folder_path)
        generate_group_list_json(folder_path)
    except Exception as exc:
        print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
