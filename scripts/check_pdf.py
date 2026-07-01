import sys
from pathlib import Path

from app import get_db_connection


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_pdf.py <walkthrough_id>")
        return
    wid = int(sys.argv[1])
    conn = get_db_connection()
    row = conn.execute("SELECT pdf_url FROM walkthroughs WHERE id = ?", (wid,)).fetchone()
    print(row.get("pdf_url") if row else None)


if __name__ == '__main__':
    main()
