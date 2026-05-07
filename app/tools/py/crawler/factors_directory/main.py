from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from discover import get_all_factor_urls
from fetcher import fetch
from parser import extract_factor_data
from storage import save_jsonl


def process(url):
    html = fetch(url)
    data = extract_factor_data(html)

    if data:
        data["source_url"] = url
        save_jsonl(data)
        return True
    return False


def main():
    urls = get_all_factor_urls()
    print("Total:", len(urls))

    ok = 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(tqdm(pool.map(process, urls), total=len(urls)))

    ok = sum(1 for r in results if r)
    print(f"Done: {ok}/{len(urls)}")


if __name__ == "__main__":
    main()