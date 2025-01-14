import sys
import os
import json
import argparse

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)

from hi_canvas_api.canvas_calendar import delete_all_calendar_events, create_calendar_event


def load_calendar(file_path):
    """
    Loads calendar data from a JSON file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_calendar(json_path):
    """
    Updates the Canvas calendar with events loaded from a JSON file.
    """
    print(f"Loading calendar events from: {json_path}")
    calendar = load_calendar(json_path)

    print("Deleting all existing calendar events...")
    delete_all_calendar_events()

    print("Creating new calendar events...")
    for week, event in enumerate(calendar):
        print(f"Updating Week {week + 1}: {event['title']}")
        create_calendar_event(
            title=event["title"],
            date=event["date"],
            start_time=event["time"],
            end_time=event["etime"],
            description=event["description"]
        )
    print("Calendar updated successfully.")


if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Update Canvas calendar events using a JSON file.")
    parser.add_argument(
        "--file",
        type=str,
        default="calendar.json",
        help="Path to the JSON file containing calendar events (default: calendar.json)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Check if the specified file exists
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    # Update calendar with the specified or default JSON file
    update_calendar(args.file)
