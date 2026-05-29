import sys
import os
import runpy
from pathlib import Path

if os.environ.get("DATABASE_URL"):
    from app import process_walkthrough_in_context, get_db_connection
else:
    local_app = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".codex_run_kas.py"))
    process_walkthrough_in_context = local_app["kas_app"].process_walkthrough_in_context
    get_db_connection = local_app["get_local_db_connection"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/regenerate_pdf.py <walkthrough_id>")
        return
    wid = int(sys.argv[1])
    with get_db_connection() as conn:
        row = conn.execute("SELECT video_path, video_url FROM walkthroughs WHERE id = ?", (wid,)).fetchone()
        if not row:
            print(f"Walkthrough {wid} not found in DB")
            return
        video_path = row.get("video_path")
        if not video_path:
            print(f"No local video_path for walkthrough {wid}; cannot regenerate PDF automatically.")
            return
    p = Path(video_path)
    if not p.exists():
        print(f"Video file not found: {p}")
        return
    print(f"Regenerating walkthrough {wid} using video {p}...")
    try:
        process_walkthrough_in_context(wid, p)
        print("Done. Check the app UI or DB for updated pdf_url.")
    except Exception as e:
        print(f"Error during regeneration: {e}")


if __name__ == '__main__':
    main()
