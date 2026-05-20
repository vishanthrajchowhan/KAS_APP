import sys
import json
from urllib.request import urlopen

if len(sys.argv) < 2:
    print("Usage: python scripts/check_status.py <walkthrough_id>")
    sys.exit(1)

wid = sys.argv[1]
url = f"http://127.0.0.1:5000/api/walkthroughs/{wid}/status"
try:
    with urlopen(url) as r:
        data = json.load(r)
        print(json.dumps(data, indent=2))
except Exception as e:
    print('Error:', e)
