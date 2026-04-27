import json
import re


def extract_factor_data(html):
    if not html:
        return None

    # 方案1：__NEXT_DATA__
    m = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            res = deep_find_factor(data)
            if res:
                return res
        except:
            pass

    # 方案2：ld+json
    matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for m in matches:
        try:
            j = json.loads(m)
            if j.get("@type") == "Article":
                return j
        except:
            continue

    # 方案3：RSC兜底（你抓的那个）
    idx = html.find('"factor":')
    if idx != -1:
        try:
            start = html.find("{", idx)
            brace = 0
            for i in range(start, len(html)):
                if html[i] == "{":
                    brace += 1
                elif html[i] == "}":
                    brace -= 1
                    if brace == 0:
                        raw = html[start:i+1]
                        return json.loads(raw)
        except:
            pass

    return None


def deep_find_factor(obj):
    if isinstance(obj, dict):
        if "factor" in obj:
            return obj["factor"]
        for v in obj.values():
            r = deep_find_factor(v)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = deep_find_factor(item)
            if r:
                return r
    return None