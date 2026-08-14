import sys
import os
import json
import argparse
import logging

# Make emoji-containing output safe on Windows consoles (cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure the root directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, root_dir)

from hi_canvas_api.canvas_rat import create_rat, transfer_trat_grades

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description="Create a matching iRAT + tRAT pair from a JSON question file.")
    parser.add_argument("--file", type=str, default="rat.json",
                        help="Path to the RAT JSON file (default: %(default)s).")
    parser.add_argument("--transfer-grades", type=int, metavar="TRAT_QUIZ_ID",
                        help="Instead of creating: read the given tRAT and copy each "
                             "team's grade onto its members (dry-run unless --apply).")
    parser.add_argument("--apply", action="store_true",
                        help="With --transfer-grades, actually write the grades.")

    args = parser.parse_args()

    if args.transfer_grades:
        results = transfer_trat_grades(args.transfer_grades, dry_run=not args.apply)
        for r in results:
            print(f"  {r['username']:20s} -> user {r['user_id']} score {r['score']} "
                  f"applied={r['applied']}")
        return

    if not os.path.exists(args.file):
        logging.error(f"File not found: {args.file}")
        return

    with open(args.file, "r", encoding="utf-8") as f:
        rat_data = json.load(f)

    ids = create_rat(rat_data)
    print(f"Created iRAT quiz {ids['irat']} and tRAT quiz {ids['trat']}.")


if __name__ == "__main__":
    main()
