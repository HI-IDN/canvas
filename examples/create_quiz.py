import sys
import os
import argparse
import logging

# Make emoji-containing output safe on Windows consoles (cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)

from hi_canvas_api.canvas_quizzes import (
    load_quiz,
    validate_quiz,
    create_quiz_with_questions,
    list_quizzes,
    delete_quiz,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    """CLI for creating a multiple-choice quiz in Canvas from a JSON file."""
    parser = argparse.ArgumentParser(description="Create a Canvas quiz via the API.")
    parser.add_argument("--file", type=str, default="quiz.json",
                        help="Path to the quiz JSON file (default: %(default)s).")
    parser.add_argument("--list", action="store_true", help="List all quizzes and exit.")
    parser.add_argument("--delete", type=int, help="Delete a quiz by ID and exit.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate the JSON file without sending it to Canvas.")

    args = parser.parse_args()

    if args.list:
        list_quizzes()
        return

    if args.delete:
        delete_quiz(args.delete)
        return

    if not os.path.exists(args.file):
        logging.error(f"File not found: {args.file}")
        return

    quiz_data = load_quiz(args.file)

    if args.validate_only:
        is_valid, messages = validate_quiz(quiz_data)
        for message in messages:
            print(message)
        return

    create_quiz_with_questions(quiz_data)


if __name__ == "__main__":
    main()
