# Canvas API Integration

This repository provides tools for importing, exporting, and managing data for Canvas courses using the Canvas API.

## Folder Structure

```plaintext
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
├── examples/                   # Example scripts
│   ├── update_calendar_events.py  # Example for managing calendar events
│   ├── ...                     # Other example scripts
```

## Design

The package is designed to be modular:

- `hi_canvas_api/`: Contains the primary modules for interacting with the Canvas API.
  - `canvas_calendar.py`: Manages calendar events.
  - `canvas_rubrics.py`: (Future) Placeholder for rubric management functionality.
  - `__init__.py`: Centralizes imports for easier access.
- `README.md`: Documentation for setting up and using the package.
- `.env.example`: Template for setting up environment variables.
- `requirements.txt`: Lists Python dependencies.
- `examples/`: Contains scripts demonstrating the package’s capabilities.

---

## Installation

1. Clone the repository:
   ```bash
   git clone git@github.com:HI-IDN/canvas.git
   ```

2. Navigate to the project directory:
   ```bash
   cd canvas
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Setting Up Your `.env` File

The `.env` file stores your Canvas API credentials and course information. Create a `.env` file in the root directory using the following template:

```plaintext
INSTITUTION_URL=https://your_institution.instructure.com
API_VERSION=v1
API_TOKEN=your_token_here
COURSE_ID=your_course_id_here
START_DATE=2025-01-01
END_DATE=2025-12-31
```

### Example `.env` File
An example `.env` file is provided in the repository as `.env.example`. Copy and modify it:
```bash
cp .env.example .env
```

### How to Find Your Institution URL

1. Log in to your **Canvas** account using your university credentials.
2. Look at the URL in your browser's address bar. It should look something like this:

   ```plaintext
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

### How to Find Your Canvas Course ID

1. Log in to your **Canvas** account using your university credentials.
2. Navigate to the course you want to manage.
3. Look at the URL in your browser's address bar. It should look something like this:

   ```plaintext
   https://your_institution.instructure.com/courses/1234567
   ```

4. The number after `/courses/` is your **Course ID**. In this example, the Course ID is `12345`.
5. Add this Course ID to your `.env` file.

---

## Usage

To use the package, import the desired module and call its functions. For example:

```python
from hi_canvas_api.canvas_calendar import delete_all_calendar_events, create_calendar_event

# Delete all events
delete_all_calendar_events()

# Create a new event
create_calendar_event(
    title="Project Presentation",
    date="2025-03-14",
    start_time="10:00",
    end_time="12:00",
    description="<p>Final group project presentations</p>",
)
```

### Examples
See the `examples/` directory for ready-to-run scripts. For instance, you can update calendar events using:

```bash
python examples/update_calendar_events.py
```

---

## Contributing
Contributions are welcome! Please open an issue or submit a pull request with suggestions or improvements.

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

