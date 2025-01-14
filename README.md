# canvas

Import/export fyrir Canvas námskeið

## Folder structure

```
hi_canvas_api/
│
├── hi_canvas_api/
│   ├── __init__.py             # Makes the directory a Python package
│   ├── canvas_calendar.py      # Handles calendar-specific functionality
│   ├── canvas_rubrics.py       # (Future) Handles rubrics-related functionality
│
├── README.md                   # Documentation for setup and usage
├── .env.example                # Example for environment variables
├── requirements.txt            # Python dependencies
├── example_script.py           # Example script for using the package
```

## Design

The package is designed to be modular, with each module handling a specific aspect of the Canvas
API. This allows for easier maintenance and extensibility. The package is structured as follows:
- `hi_canvas_api/`: The main package directory. Contains the package modules.
  - `canvas_calendar.py`: Contains all functions related to managing calendar events.
  - `canvas_rubrics.py`: (Future) Placeholder for rubric-related functionality.
  - `__init__.py`: A central import point for all modules, allowing easier access to the package's
    features.
- `README.md`: Includes examples of how to use the API.
- `.env.example`: An example file for environment variables. You should create a `.env` file with
  your own values.
- `requirements.txt`: A list of Python dependencies required to run the package.
- `example_script.py`: An example script that demonstrates how to use the package.

## Installation

1. Clone the repository:

```bash
git clone git@github.com:HI-IDN/canvas.git
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Setting Up Your `.env` File

The `.env` file stores your Canvas API credentials and course information. Create a `.env` file 
in the root directory using the following template:

```bash
INSTITUTION_URL=https://your_institution.instructure.com
CANVAS_API_TOKEN=your_token_here
COURSE_ID=your_course_id_here
```

### How to Find Your Institution URL

1. Log in to your **Canvas** account using your university credentials.
2. Look at the URL in your browser's address bar. It should look something like this:
  ```
  https://your_institution.instructure.com
  ```
3. Copy the URL and add it to your `.env` file.

### How to Find Your Canvas API Key

1. Log in to your **Canvas** account using your university credentials.
2. In the **Account** menu (typically in the left-hand navigation panel), click on **Settings**.
3. Scroll down to the **Approved Integrations** section.
4. Click the button **+ New Access Token**.
   - Enter a name for the token (e.g., "HI-Canvas API").
   - Set an expiration date for security purposes.
5. Click **Generate Token**.
6. Copy the token displayed on the screen. This is your API key. **Make sure to save it securely**, as you won't be able to view it again.
7. Add the token to your `.env` file.

> ⚠️ **Important**: Keep your API key private and do not share or commit it to any public repository.

## How to Find Your Canvas Course ID

1. Log in to your **Canvas** account using your university credentials.
2. Navigate to the course you want to manage.
3. Look at the URL in your browser's address bar. It should look something like this:
  ```
  https://your_institution.instructure.com/courses/1234567
  ```
4. The number after `/courses/` is your **Course ID**. In this example, the Course ID is `12345`.
5. Add this Course ID to your `.env` file.
