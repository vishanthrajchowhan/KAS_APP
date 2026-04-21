# KAS

A simple Flask and SQLite web app for tracking construction jobs, field notes, status updates, and before/after photos.

## Features

- View all jobs and current status
- Add a new job with name, location, and description
- Update status as Started, In Progress, or Completed
- Add notes from the field
- Upload multiple job photos
- Store uploaded images locally in `uploads/`
- Store job data in SQLite `database.db`

## Project Structure

```text
app.py
requirements.txt
database.db        # created automatically on first run
templates/
  base.html
  index.html
  add_job.html
  update_job.html
  404.html
  500.html
static/
  styles.css
uploads/
  .gitkeep
```

## Run Locally

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python app.py
```

4. Open the app:

```text
http://127.0.0.1:5000
```

The database and uploads folder are created automatically when the app starts.

## Notes

- Allowed image types: PNG, JPG, JPEG, GIF, WEBP
- Maximum request upload size: 25 MB
- For a real deployment, set a strong `SECRET_KEY` environment variable and run Flask behind a production WSGI server.
