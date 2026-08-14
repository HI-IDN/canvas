"""Build iRAT/tRAT quiz pairs from a single question definition, and transfer a
tRAT team's grade onto the individual team members.

A RAT ("Readiness Assurance Test") is taken first individually (iRAT) and then
by the team (tRAT) using the same questions. Canvas has no real group quiz, so
the tRAT is taken by one team member and the first question collects the names
of everyone who took it; ``transfer_trat_grades`` then copies that submission's
score onto each listed team member.
"""
import re
import requests
import logging
from typing import Optional

from .canvas_quizzes import (
    INSTITUTION_URL,
    API_VERSION,
    COURSE_ID,
    QUIZZES_URL,
    get_headers,
    create_quiz,
    add_quiz_question,
    create_quiz_group,
    set_quiz_published,
)

COURSE_URL = f"{INSTITUTION_URL}/api/{API_VERSION}/courses/{COURSE_ID}"

# Default RAT configuration; override any key via rat_data["config"].
DEFAULT_CONFIG = {
    "irat_time_limit": 15,          # minutes
    "trat_time_limit": 30,          # minutes
    "max_team_size": 3,             # rows in the tRAT team-names question
    "shuffle_answers": True,
    "hide_results": "always",       # "always" | "until_after_last_attempt" | None
    "show_correct_answers": True,
    "show_correct_answers_at": None,
    "trat_one_question_at_a_time": True,
    "trat_cant_go_back": True,
    "published": False,
    # Intro shown above the team-names table in the tRAT (kept course-neutral).
    "team_note": (
        "Canvas býður ekki upp á eiginleg hópapróf, svo aðeins einn úr hópnum svarar prófinu. "
        "Kennari sér svo um að yfirfæra einkunnir hópstjóra yfir á aðra hópmeðlimi að prófi loknu."
    ),
}

NAMES_QUESTION_NAME = "Teymi"


def _iter_questions(rat_data: dict):
    for group in rat_data["groups"]:
        for question in group["questions"]:
            yield question


def _team_names_question(max_team_size: int, team_note: str) -> dict:
    """Build the tRAT first question: a 0-point fill-in-the-blank table that
    collects one (name, username) pair per team member."""
    rows = "".join(
        f"<tr><td>Nemandi {i}:&nbsp;</td><td>[n{i}]</td><td>&nbsp;[u{i}]</td></tr>"
        for i in range(1, max_team_size + 1)
    )
    text = (
        f"<p>{team_note}</p>"
        "<p>Skrifið alla sem þreyttu þetta próf saman — nafn og notendanafn. "
        f"Hámarksfjöldi í hóp {max_team_size}.</p>"
        '<table style="border-collapse:collapse"><tbody>'
        "<tr><td></td><td><strong>Nafn</strong></td><td><strong>Notendanafn</strong></td></tr>"
        f"{rows}</tbody></table>"
    )
    answers = []
    for i in range(1, max_team_size + 1):
        answers.append({"blank_id": f"n{i}", "answer_text": "x", "answer_weight": 100})
        answers.append({"blank_id": f"u{i}", "answer_text": "x", "answer_weight": 100})
    return {
        "question": {
            "question_name": NAMES_QUESTION_NAME,
            "question_text": text,
            "question_type": "fill_in_multiple_blanks_question",
            "points_possible": 0,
            "answers": answers,
        }
    }


def _add_groups(quiz_id: int, rat_data: dict) -> list:
    """Add every group and its questions; all questions are shown (pick_count =
    group size). Returns the group ids in order."""
    group_ids = []
    for group in rat_data["groups"]:
        questions = group["questions"]
        gid = create_quiz_group(quiz_id, group["name"], pick_count=len(questions))
        for question in questions:
            add_quiz_question(quiz_id, question, quiz_group_id=gid)
        group_ids.append(gid)
    return group_ids


def _recompute(quiz_id: int, title: str) -> None:
    """A no-op PUT forces Canvas to recompute question_count / points_possible."""
    requests.put(f"{QUIZZES_URL}/{quiz_id}", headers=get_headers(), json={"quiz": {"title": title}})


def create_rat(rat_data: dict) -> dict:
    """
    Create a matching iRAT + tRAT pair from one definition.

    Args:
        rat_data (dict): ``{"title": str, "groups": [{"name": str,
            "questions": [<question>, ...]}, ...], "config": {...}}``. Each
            question follows the ``add_quiz_question`` schema (``question_text``,
            ``answers`` with one ``correct``). See ``examples/rat.json``.

    Returns:
        dict: ``{"irat": <quiz_id>, "trat": <quiz_id>}``.
    """
    cfg = {**DEFAULT_CONFIG, **rat_data.get("config", {})}
    title = rat_data["title"]

    common = {
        "shuffle_answers": cfg["shuffle_answers"],
        "hide_results": cfg["hide_results"],
        "show_correct_answers": cfg["show_correct_answers"],
        "show_correct_answers_at": cfg["show_correct_answers_at"],
        "published": cfg["published"],
    }

    # --- iRAT ---
    irat_id = create_quiz({
        "title": f"[iRAT] {title}",
        "description": rat_data.get("irat_description", ""),
        "time_limit": cfg["irat_time_limit"],
        **common,
    })
    _add_groups(irat_id, rat_data)
    _recompute(irat_id, f"[iRAT] {title}")

    # --- tRAT ---
    trat_id = create_quiz({
        "title": f"[tRAT] {title}",
        "description": rat_data.get("trat_description", ""),
        "time_limit": cfg["trat_time_limit"],
        "one_question_at_a_time": cfg["trat_one_question_at_a_time"],
        "cant_go_back": cfg["trat_cant_go_back"],
        **common,
    })
    trat_group_ids = _add_groups(trat_id, rat_data)

    # Team-names question, moved to the front.
    names_q = _team_names_question(cfg["max_team_size"], cfg["team_note"])
    r = requests.post(f"{QUIZZES_URL}/{trat_id}/questions", headers=get_headers(), json=names_q)
    if r.status_code not in (200, 201):
        raise Exception(f"Failed to add team-names question: {r.status_code} - {r.text}")
    names_qid = r.json()["id"]
    order = [{"type": "question", "id": names_qid}] + [{"type": "group", "id": g} for g in trat_group_ids]
    requests.post(f"{QUIZZES_URL}/{trat_id}/reorder", headers=get_headers(), json={"order": order})
    _recompute(trat_id, f"[tRAT] {title}")

    logging.info(f"Created RAT '{title}': iRAT={irat_id}, tRAT={trat_id}")
    return {"irat": irat_id, "trat": trat_id}


# ---------------------------------------------------------------------------
# tRAT group-grade transfer ("hack" for Canvas' lack of real group quizzes)
# ---------------------------------------------------------------------------

def _student_lookup() -> dict:
    """Map each student's login_id (username) -> user_id for the course."""
    lookup = {}
    url = f"{COURSE_URL}/users?enrollment_type[]=student&per_page=100&include[]=email"
    while url:
        resp = requests.get(url, headers=get_headers())
        resp.raise_for_status()
        for user in resp.json():
            login = (user.get("login_id") or user.get("sis_user_id") or "").strip().lower()
            if login:
                lookup[login] = user["id"]
        # follow pagination
        url = None
        for part in resp.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part[part.find("<") + 1:part.find(">")]
    return lookup


def _read_team_usernames(quiz_id: int, submission) -> list:
    """Extract the usernames (u1..uN blanks) a submitter entered in the team
    question, from the quiz submission's submission_data."""
    usernames = []
    for entry in (submission.get("submission_data") or []):
        for key, value in entry.items():
            m = re.match(r"answer_for_u\d+$", key)
            if m and value and str(value).strip():
                usernames.append(str(value).strip().lower())
    return usernames


def transfer_trat_grades(trat_quiz_id: int, dry_run: bool = True) -> list:
    """
    Copy each tRAT submission's score onto every team member listed in that
    submission's team-names question.

    Args:
        trat_quiz_id (int): The tRAT quiz id.
        dry_run (bool): If True (default), only compute and log the planned
            transfers without writing any grades. Set False to apply them.

    Returns:
        list[dict]: One record per planned/applied transfer:
            ``{"username", "user_id", "score", "applied"}``.
    """
    quiz = requests.get(f"{QUIZZES_URL}/{trat_quiz_id}", headers=get_headers()).json()
    assignment_id = quiz.get("assignment_id")
    if not assignment_id:
        raise Exception(f"Quiz {trat_quiz_id} has no assignment_id (not gradable).")

    subs = requests.get(
        f"{QUIZZES_URL}/{trat_quiz_id}/submissions?include[]=submission&per_page=100",
        headers=get_headers(),
    ).json().get("quiz_submissions", [])

    students = _student_lookup()
    results = []

    for sub in subs:
        score = sub.get("kept_score", sub.get("score"))
        if score is None:
            continue
        submission = sub.get("submission") or {}
        usernames = _read_team_usernames(trat_quiz_id, submission)
        for username in usernames:
            user_id = students.get(username)
            record = {"username": username, "user_id": user_id, "score": score, "applied": False}
            if not user_id:
                logging.warning(f"No student found for username '{username}'.")
                results.append(record)
                continue
            if not dry_run:
                r = requests.put(
                    f"{COURSE_URL}/assignments/{assignment_id}/submissions/{user_id}",
                    headers=get_headers(),
                    json={"submission": {"posted_grade": score},
                          "comment": {"text_comment": "Einkunn færð úr tRAT teymisprófinu."}},
                )
                record["applied"] = r.status_code in (200, 201)
                if not record["applied"]:
                    logging.error(f"Failed to grade {username}: {r.status_code} - {r.text}")
            logging.info(
                f"{'[dry-run] ' if dry_run else ''}{username} (id {user_id}) <- score {score}"
            )
            results.append(record)

    return results
