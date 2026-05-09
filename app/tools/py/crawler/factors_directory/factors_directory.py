import re
import json
import requests

url = "https://factors.directory/_next/static/chunks/080cf51fd6b95f88.js"

js = requests.get(url).text

match = re.search(r"JSON\.parse\('(.*)'\)", js)

raw = match.group(1)

# 第一次：JS 字符串转义
unescaped = raw.encode().decode("unicode_escape")

# 第二次：JSON 解析
data = json.loads(unescaped)

# 把解析得到的 data 写入格式化的 JSON 文件，便于查看与后续处理
# output_path = 'data.json'
# with open(output_path, 'w', encoding='utf-8') as out_f:
# 	json.dump(data, out_f, ensure_ascii=False, indent=2)
#
# print(f'Wrote formatted JSON to {output_path}')
#
# # 另外写一个压缩（无空白）的 JSON 版本，适合传输或作为机器输入
# min_path = 'data.min.json'
# with open(min_path, 'w', encoding='utf-8') as out_min:
# 	# separators 去掉多余空白以减小文件体积
# 	json.dump(data, out_min, ensure_ascii=False, separators=(',', ':'))
#
# print(f'Wrote minified JSON to {min_path}')


import re


def slugify(text: str) -> str:
    """
    生成 markdown anchor
    """
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


md = []

# =========================
# Title
# =========================

md.append("# Factors Directory")
md.append("")
md.append("Auto-generated from factors.directory")
md.append("")

# =========================
# TOC
# =========================

md.append("# Table of Contents")
md.append("")

for category in data:

    category_name = category["name"]
    category_anchor = slugify(category_name)

    md.append(f"- [{category_name}](#{category_anchor})")

    for factor in category["factors"]:

        factor_title = factor.get("title", factor.get("name", "Unnamed"))
        factor_anchor = slugify(factor_title)

        md.append(f"  - [{factor_title}](#{factor_anchor})")

md.append("")
md.append("---")
md.append("")

# =========================
# Content
# =========================

for category in data:

    category_name = category["name"]

    md.append(f"# {category_name}")
    md.append("")

    factors = category.get("factors", [])

    for factor in factors:

        title = factor.get("title", "")
        description = factor.get("description", "")
        explanation = factor.get("explanation", "")
        formulas = factor.get("formulas", [])
        formula_explanation = factor.get("formulaExplanation", {})
        related = factor.get("related", [])

        # ---------------------
        # Title
        # ---------------------

        md.append(f"## {title}")
        md.append("")

        # ---------------------
        # Description
        # ---------------------

        if description:
            md.append("### Description")
            md.append("")
            md.append(description)
            md.append("")

        # ---------------------
        # Explanation
        # ---------------------

        if explanation:
            md.append("### Explanation")
            md.append("")
            md.append(explanation)
            md.append("")

        # ---------------------
        # Formulas
        # ---------------------

        if formulas:

            md.append("### Formulas")
            md.append("")

            for formula in formulas:

                text = formula.get("text", "")
                latex = formula.get("latex", "")

                if text:
                    md.append(f"**{text}**")
                    md.append("")

                if latex:
                    md.append("$$")
                    md.append(latex)
                    md.append("$$")
                    md.append("")

        # ---------------------
        # Formula Explanation
        # ---------------------

        if formula_explanation:

            md.append("### Formula Explanation")
            md.append("")

            formula_text = formula_explanation.get("text", "")

            if formula_text:
                md.append(formula_text)
                md.append("")

            symbols = formula_explanation.get("symbols", [])

            if symbols:

                md.append("| Symbol | Meaning |")
                md.append("|---|---|")

                for symbol in symbols:

                    s = symbol.get("symbol", "")
                    m = symbol.get("meaning", "")

                    md.append(f"| `{s}` | {m} |")

                md.append("")

        # ---------------------
        # Related Factors
        # ---------------------

        if related:

            md.append("### Related Factors")
            md.append("")

            for r in related:

                factor_name = r.get("factorName", "")

                if factor_name:
                    md.append(f"- {factor_name}")

            md.append("")

        md.append("---")
        md.append("")


# =========================
# Write markdown
# =========================

markdown_output = "\n".join(md)

with open("factors.md", "w", encoding="utf-8") as f:
    f.write(markdown_output)

print("Generated factors.md")