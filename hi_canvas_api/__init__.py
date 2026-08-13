# hi_canvas_api/__init__.py

from .canvas_calendar import delete_all_calendar_events, create_calendar_event
from .canvas_assignment import add_assignment, get_assignments, get_assignment_groups
from .canvas_quizzes import (
    load_quiz,
    validate_quiz,
    create_quiz,
    add_quiz_question,
    create_quiz_with_questions,
    list_quizzes,
    set_quiz_published,
    delete_quiz,
)

# Future imports for rubrics or other modules can be added here:
# from .canvas_rubrics import some_rubrics_function

