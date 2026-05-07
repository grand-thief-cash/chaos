import json

def save_jsonl(data, path="factors.jsonl"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")