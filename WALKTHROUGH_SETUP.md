# AI Walkthrough Feature - Setup & Usage Guide

## Overview
The AI Walkthrough feature enables crew members to record a video walkthrough of a jobsite, and AI automatically:
- Transcribes speech to text (using OpenAI Whisper)
- Generates a structured report (using GPT)
- Extracts key frames from video (every 10 seconds)
- Creates a professional PDF report

## Prerequisites

### System Requirements
- **ffmpeg** installed and on PATH (for audio extraction)
- **WeasyPrint system dependencies** (for PDF generation):
  - **Windows**: Via Chocolatey: `choco install gtk+3`
  - **macOS**: `brew install python3-cairo python3-pango`
  - **Linux (Ubuntu)**: `sudo apt-get install libcairo2-dev libpango-1.0-0 libpango-cairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libssl-dev`

### Python Dependencies
Already added to `requirements.txt`:
- `openai>=1.0.0` — for Whisper transcription and GPT report generation
- `weasyprint>=58.0` — for PDF creation
- `opencv-python>=4.7` — for frame extraction

Install with:
```bash
python -m pip install -r requirements.txt
```

### Environment Variables
Required:
```
DATABASE_URL=postgresql://user:password@host/dbname
OPENAI_API_KEY=sk-...  # Your OpenAI API key
SECRET_KEY=your-secret-key
```

Optional (for Supabase storage):
```
SUPABASE_URL=https://your.supabase.url
SUPABASE_KEY=service_role_key  # NOT the public key
```

## Installation & Setup

### 1. Install System Dependencies

**Windows (using Chocolatey):**
```powershell
choco install ffmpeg
choco install gtk+3
```

**macOS:**
```bash
brew install ffmpeg
brew install cairo pango gdk-pixbuf
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg libcairo2-dev libpango-1.0-0 libpango-cairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libssl-dev
```

### 2. Verify ffmpeg Installation
```bash
ffmpeg -version
```

### 3. Install Python Dependencies
```bash
cd d:\KAS_APP
python -m pip install -r requirements.txt
```

### 4. Configure Environment
Create or update `.env`:
```
DATABASE_URL=postgresql://...your connection string...
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key
```

### 5. Initialize Database
The tables are created automatically on app startup, but you can manually verify:
```bash
python -c "from app import init_db; init_db()"
```

### 6. Start the App
```bash
python app.py
```

The app will run on `http://localhost:5000` by default.

## How to Use

### Recording a Walkthrough

1. **Open a Job** in the app (visit a job's update page)
2. **Look for the "AI Walkthrough" panel** with blue action buttons
3. **Click "▶️ Start Walkthrough"**:
   - Browser requests camera and microphone access
   - Camera feed appears as a small preview (bottom-right)
   - A timer shows elapsed recording time
4. **Walk the jobsite and speak naturally**:
   - Describe work completed, materials used, issues found, next steps
   - Camera captures video and audio
5. **Click "⏹️ Stop & Upload"** when done:
   - Video is uploaded to the server
   - Status notifications appear (top-right)
   - Processing begins automatically

### Processing Flow

**On the server:**
1. Video is saved to `uploads/walkthroughs/`
2. Audio extracted from video (16kHz mono WAV)
3. OpenAI Whisper transcribes speech to text
4. OpenAI GPT generates structured report (JSON):
   - Project Summary
   - Completed Work
   - Materials Used
   - Issues Found
   - Safety Notes
   - Next Steps
5. OpenCV extracts frames every 10 seconds
6. PDF report generated with transcript, AI summary, and frame timeline
7. All data saved to database

### Viewing the Report

After processing (takes 30-60 seconds depending on video length):
1. You'll be redirected to `/walkthroughs/<id>` automatically
2. **Report page shows**:
   - AI Summary (structured sections)
   - Photo Timeline (extracted frames with timestamps)
   - Full Transcript
   - "📥 Download PDF" button

### Downloading the PDF

- Click **"📥 Download PDF"** on the report page
- PDF includes:
  - Company branding
  - Project details
  - Crew member name and date
  - AI-generated summary sections
  - Photo timeline with timestamps
  - Full transcript
  - Professional formatting

## Database Schema

### Table: `walkthroughs`
Stores the main walkthrough record:
```sql
id (BIGINT) — Primary key
job_id (BIGINT) — References jobs(id)
video_path (TEXT) — Local or Supabase path to video file
video_url (TEXT) — URL to access video
transcript (TEXT) — Full transcribed text from Whisper
ai_summary (TEXT) — JSON with AI-generated report
report_text (TEXT) — Formatted report text
pdf_url (TEXT) — URL to download PDF report
created_by (BIGINT) — References users(id)
created_at (TEXT) — ISO timestamp
```

### Table: `walkthrough_frames`
Stores extracted frames for timeline:
```sql
id (BIGINT) — Primary key
walkthrough_id (BIGINT) — References walkthroughs(id)
frame_path (TEXT) — Local or Supabase path
frame_url (TEXT) — URL to access frame
timestamp_seconds (DOUBLE) — When in video the frame was taken
created_at (TEXT) — ISO timestamp
```

### Table: `walkthrough_reports`
Stores generated reports:
```sql
id (BIGINT) — Primary key
walkthrough_id (BIGINT) — References walkthroughs(id)
report_text (TEXT) — Full report text
pdf_url (TEXT) — URL to PDF file
created_by (BIGINT) — References users(id)
created_at (TEXT) — ISO timestamp
```

## API Endpoints

### POST `/api/walkthroughs/upload`
Upload a video and create a walkthrough.

**Request:**
```
Content-Type: multipart/form-data
video (file) — video file (mp4, mov, webm, mkv)
job_id (int) — ID of the job
```

**Response:**
```json
{
  "id": 123,
  "video_url": "https://..."
}
```

### GET `/walkthroughs/<id>`
View walkthrough report (HTML page).

**Returns:** Rendered HTML with summary, timeline, transcript, and download link.

### GET `/walkthroughs/<id>/download_pdf`
Download the PDF report.

**Returns:** PDF file for download.

### GET `/walkthroughs/media/<filename>`
Serve video, frames, or reports (internal use).

## Supabase Integration (Optional)

If you configure Supabase storage, all files will be uploaded:

1. **Videos** → `job-videos` bucket
2. **Frames** → `walkthrough-frames` bucket
3. **Reports** → `reports` bucket

Files are still processed locally but also stored in Supabase for backup and long-term access.

### Enabling Supabase Storage

1. Set environment variables:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

2. Ensure Supabase buckets exist (they'll be auto-created if the app can):
   - job-videos
   - walkthrough-frames
   - reports

3. Restart the app

## Troubleshooting

### Camera/Microphone Not Working
- **Check browser permissions**: Allow camera and mic access when prompted
- **Try a different browser**: Safari, Chrome, Firefox support MediaRecorder
- **Check HTTPS**: If on production, camera requires HTTPS (or localhost)
- **Verify hardware**: Ensure device has camera/microphone

### Audio Quality Issues
- **Speak clearly** at normal volume
- **Reduce background noise** (close windows, turn off machinery)
- **Use a headset mic** for better quality
- Whisper is accurate but improves with clear audio

### PDF Generation Fails
- **Check WeasyPrint dependencies**: Run `pip install --upgrade weasyprint`
- **Verify system libs**: Install platform-specific packages (see Prerequisites)
- **Check logs**: Look for error messages in Flask output

### Processing Takes Too Long
- **Video is too long?** Walkthrough processing time ≈ 20-60s depending on duration
- **First run?** First OpenAI API calls may be slower
- **Large frames?** Frame extraction can take time for long videos
- Consider moving processing to background worker (Celery/RQ)

### "OpenAI API Key" Error
- **Verify OPENAI_API_KEY** is set and valid
- **Check API key format**: Should start with `sk-`
- **Verify account**: Ensure OpenAI account has API access enabled
- **Check balance**: Ensure account has credits/billing set up

### Transcript is Garbled or Empty
- **Check audio quality**: See "Audio Quality Issues" above
- **Verify Whisper is available**: `python -c "import openai; openai.Audio"`
- **Long pauses**: Whisper may not detect audio in silent segments
- **Wrong language**: Whisper defaults to English

## Performance Tips

### Optimize for Production

1. **Move processing to background worker**:
   - Use Celery/RQ to process videos asynchronously
   - Return 202 immediately with status endpoint
   - Poll `/api/walkthroughs/<id>` for completion

2. **Stream uploads directly to Supabase**:
   - Use signed URLs for client-side direct upload
   - Reduces server bandwidth

3. **Compress frames before PDF**:
   - Current code stores JPEG; consider lower quality
   - Saves storage and PDF generation time

4. **Use smaller videos**:
   - 2-5 minute walkthroughs are optimal
   - Transcription cost scales with duration

## Cost Considerations

### OpenAI API Charges
- **Whisper**: ~$0.006 per minute of audio
- **GPT (gpt-4o-mini)**: ~$0.015 per 1K input tokens
- Typical 3-minute walkthrough: ~$0.04

### Storage (Supabase)
- **Videos**: Typically 1-10MB per minute → $0.06/GB/month
- **Frames**: 1-2MB total per walkthrough → minimal
- **PDFs**: 1-5MB per report → minimal

## API Examples

### cURL: Upload a Walkthrough
```bash
curl -X POST http://localhost:5000/api/walkthroughs/upload \
  -F "video=@/path/to/video.webm" \
  -F "job_id=123"
```

### Python: Fetch Walkthrough Data
```python
import requests

# View report page
resp = requests.get("http://localhost:5000/walkthroughs/123")
print(resp.text)

# Download PDF
resp = requests.get("http://localhost:5000/walkthroughs/123/download_pdf")
with open("report.pdf", "wb") as f:
    f.write(resp.content)
```

## File Structure

```
uploads/
├── walkthroughs/
│   ├── video_uuid.webm         # Recorded videos
│   └── frames/
│       └── walk_id_0.jpg       # Extracted frames
└── reports/
    └── walkthrough_id.pdf      # Generated PDFs

templates/
├── walkthrough.html            # Report view page
└── walkthrough_report.html     # PDF template

static/
├── walkthrough.js              # Recorder JavaScript
└── walkthrough.css             # Recorder styles
```

## Next Steps / Improvements

- [ ] Background job processing (Celery/RQ)
- [ ] Client-side direct-to-Supabase upload
- [ ] Advanced recorder UI (preview, compression, filters)
- [ ] Offline recording support (service worker)
- [ ] Photo upload integration (CompanyCam-style bulk upload)
- [ ] Report sharing & client comments
- [ ] Scheduled walkthroughs / reminders

## Support & Issues

If you encounter issues:
1. Check Flask logs for errors
2. Verify environment variables are set
3. Ensure all system dependencies are installed
4. Test API endpoints with cURL or Postman
5. Check browser console for client-side errors

For OpenAI issues, visit: https://platform.openai.com/account/api-keys
