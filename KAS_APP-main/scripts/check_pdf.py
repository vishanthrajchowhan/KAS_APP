import sys
import os
import runpy
from pathlib import Path

if os.environ.get("DATABASE_URL"):
    from app import get_db_connection
else:
    local_app = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".codex_run_kas.py"))
    get_db_connection = local_app["get_local_db_connection"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_pdf.py <walkthrough_id>")
        return
    wid = int(sys.argv[1])
    with get_db_connection() as conn:
        row = conn.execute("SELECT pdf_url FROM walkthroughs WHERE id = ?", (wid,)).fetchone()
    print(row.get("pdf_url") if row else None)


if __name__ == '__main__':
    main()
