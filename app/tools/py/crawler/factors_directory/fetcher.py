import time

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch(url, retry=3):
    for i in range(retry):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        time.sleep(1 + i)
    return None