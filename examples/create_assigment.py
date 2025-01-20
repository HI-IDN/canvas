import sys
import os
import json
import argparse

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)

from hi_canvas_api.canvas_assignment import add_assignment, get_assignment_groups
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def find_group_id(group_name, groups):
    """Find the group ID for a given group name."""
    for id, name in groups.items():
        if group_name.lower() == name.lower():
            return id
    return None


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Create a new assignment for a specific Canvas assignment group.")
    parser.add_argument("--input_json", type=str, required=True,
                        default="assignment.json",
                        help="Path to the JSON file containing assignment details (default: %(default)s)")

    args = parser.parse_args()

    try:
        # Load assignment details from JSON file
        with open(args.input_json, "r", encoding="utf-8") as f:
            assignment_data = json.load(f)

        # Validue_at required fields in JSON
        required_fields = ["group_name", "name", "due_at"]
        for field in required_fields:
            if field not in assignment_data:
                raise ValueError(f"Missing required field in JSON: {field}")

        # Retrieve assignment groups
        groups = get_assignment_groups()
        group_id = find_group_id(assignment_data["group_name"], groups)

        if not group_id:
            raise ValueError(f"Assignment group '{assignment_data['group_name']}' not found.")

        description_file = assignment_data.get("description_file")
        # Read the html file and assign it to the description key
        if description_file:
            # Check if the file exists
            if not os.path.exists(description_file):
                raise FileNotFoundError(f"Description file not found: {description_file}")
            with open(description_file, "r", encoding="utf-8") as f:
                description = f.read()
        else:
            description = assignment_data.get("description", "")

        # Prepare assignment payload
        payload = {
            "id": assignment_data.get("id", None),
            "name": assignment_data["name"],
            "description": description,
            "due_at": assignment_data["due_at"],
            "points_possible": assignment_data.get("points_possible", 0),
            "grading_type": assignment_data.get("grading_type", "points"),
            "submission_types": assignment_data.get("submission_types", ["online_upload"]),
            "published": assignment_data.get("published", False),
            "allowed_extensions": assignment_data.get("allowed_extensions", []),
        }

        # Create the assignment
        add_assignment(payload, group_id)

    except Exception as e:
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
