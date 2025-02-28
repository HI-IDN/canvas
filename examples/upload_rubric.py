import sys
import requests
import os
import argparse
from dotenv import load_dotenv

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)

from hi_canvas_api.canvas_rubric import (load_rubric, validate_rubric, delete_rubric,
                                         list_rubrics, create_rubric)


def main():
    """Main function to handle CLI input and upload rubric."""
    parser = argparse.ArgumentParser(description="Manage Canvas rubrics via API.")
    parser.add_argument("--file", type=str, default="rubric.json",
                        help="Path to the rubric JSON file.")
    parser.add_argument("--list", action="store_true", help="List all rubrics.")
    parser.add_argument("--delete", type=str, help="Delete rubric by ID.")

    args = parser.parse_args()

    if args.list:
        list_rubrics()
        return

    if args.delete:
        delete_rubric(args.delete)
        return

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return

    rubric_data = load_rubric(args.file)
    valid, errors = validate_rubric(rubric_data)
    if not valid:
        print("\n".join(errors))
        return
    create_rubric(rubric_data)


if __name__ == "__main__":
    main()
