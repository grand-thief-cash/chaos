import re

from fetcher import fetch

BASE = "https://factors.directory"

def get_categories():
    html = fetch(f"{BASE}/en/factors")
    return list(set(re.findall(r'/en/factors/([a-z\-]+)"', html)))


def get_factor_urls(category):
    html = fetch(f"{BASE}/en/factors/{category}")
    urls = re.findall(r'/en/factors/[a-z\-]+/[a-z0-9\-]+', html)
    return list(set(urls))


def get_all_factor_urls():
    categories = get_categories()
    all_urls = set()

    for c in categories:
        print("Category:", c)
        urls = get_factor_urls(c)
        for u in urls:
            all_urls.add(BASE + u)

    return list(all_urls)