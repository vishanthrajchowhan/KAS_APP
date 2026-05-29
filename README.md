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

## Deploy on Render

1. Create a Web Service from this repository.
2. Render will use `runtime.txt` for Python version.
3. Build command:

```text
pip install -r requirements.txt
```

4. Start command:

```text
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

5. Set environment variables in Render:

```text
SECRET_KEY=replace-with-a-strong-secret
DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=5
```

6. In Supabase SQL Editor, run `supabase/schema.sql` before first production launch.
