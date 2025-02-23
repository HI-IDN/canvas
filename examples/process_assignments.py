import sys
import os
import json
import argparse

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)
from hi_canvas_api.canvas_assignment import get_assignments, list_assignments, save_submissions_with_attachments
from hi_canvas_api.canvas_quizzie import get_detailed_quiz_responses, get_published_quizzes, get_quiz_questions
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def map_student_answers_to_questions(student_answers, quiz_questions):
    """
    Maps student answers to the corresponding quiz question options.

    Args:
        student_answers (list): List of student answers, each containing a question_id and answer.
        quiz_questions (list): List of quiz questions with their possible answers.

    Returns:
        dict: A mapping of question IDs to the selected answer text.
    """
    answer_mapping = {}

    for answer in student_answers:
        question_id = answer['question_id']
        selected_answer_id = int(answer['text']) if answer['text'].isdigit() else None

        # Find the question and map the selected answer
        for question in quiz_questions:
            if question['id'] == question_id:
                for option in question['answers']:
                    if option['id'] == selected_answer_id:
                        answer_mapping[question_id] = option['text']
                        break

    return answer_mapping

def save_quiz_responses_to_json(folder_path, user_id, quiz_responses):
    """
    Saves quiz responses to a JSON file in the specified folder for a user.

    Args:
        folder_path (str): Path to the folder where the file will be saved.
        user_id (int): The ID of the user.
        quiz_responses (list): The list of responses to save.

    Returns:
        None
    """
    user_folder = os.path.join(folder_path, f"User_{user_id}")
    os.makedirs(user_folder, exist_ok=True)

    file_path = os.path.join(user_folder, "student_self_evaluation_rubric.json")
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(quiz_responses, file, ensure_ascii=False, indent=4)


def process_assignments_and_quiz(assignment_id, quiz_id, folder_path):
    """
    Processes both the assignment submissions and quiz responses.

    Args:
        assignment_id (int): The ID of the assignment.
        quiz_id (int): The ID of the quiz.
        folder_path (str): Path to the folder where submissions will be saved.

    Returns:
        None
    """
    try:
        # Step 1: Fetch assignment submissions and attachments
        save_submissions_with_attachments(assignment_id, folder_path)

        # Step 2: Fetch detailed quiz responses and questions
        detailed_responses = get_detailed_quiz_responses(quiz_id)
        quiz_questions = get_quiz_questions(quiz_id)

        for response in detailed_responses:
            user_id = response['user_id']
            quiz_responses = []

            for data in response['submission_data']:
                question_id = data['question_id']
                answer_text = data['text']

                # Map cryptic integer answers to human-readable text
                if answer_text.isdigit():
                    mapped_answers = map_student_answers_to_questions(
                        [{"question_id": question_id, "text": answer_text}], quiz_questions
                    )
                    answer_text = mapped_answers.get(question_id, f"Unknown Answer ID: {answer_text}")

                # Append the response to the list
                quiz_responses.append({
                    "question_id": question_id,
                    "answer": answer_text,
                })

            # Save the responses to JSON in the user's folder
            save_quiz_responses_to_json(folder_path, user_id, quiz_responses)

            logging.info(f"Saved quiz responses for User ID: {user_id}")

    except Exception as e:
        logging.error(f"API error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Retrieve all assignments for a Canvas course and save to a JSON file.")
    parser.add_argument(
        "--output",
        type=str,
        default="assignments.json",
        help="Path to the output JSON file where assignments will be saved (default: %(default)s)"
    )

    args = parser.parse_args()

    # Get assignments and save to the specified file
    try:
        list_assignments()
        assignment_id = 150298  # Replace with your assignment ID
        quiz_id = 17549
        folder_path = "./assignments/assignment_150298"  # Replace with your desired folder path
        process_assignments_and_quiz(assignment_id, quiz_id, folder_path)
    except Exception as e:
        print(f"Unexpected error: {e}")
        #with open(args.output, "w", encoding="utf-8") as f:
        #    json.dump(assignments, f, ensure_ascii=False, indent=2)
        #logging.info(f"Assignments have been successfully saved to {args.output}.")
        # Iterate through submissions and get details
        #print(quizzes)
        

    except Exception as e:
        logging.error(f"Failed to retrieve assignments: {e}")


if __name__ == "__main__":
    main()
