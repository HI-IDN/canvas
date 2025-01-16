import sys
import os
import json
import argparse

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)
from hi_canvas_api.canvas_assignment import get_assignments

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


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
        assignments = get_assignments()
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(assignments, f, ensure_ascii=False, indent=2)
        logging.info(f"Assignments have been successfully saved to {args.output}.")
    except Exception as e:
        logging.error(f"Failed to retrieve assignments: {e}")


if __name__ == "__main__":
    main()
