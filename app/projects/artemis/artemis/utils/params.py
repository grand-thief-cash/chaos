from __future__ import annotations

from typing import Any, List


def parse_list_param(value: Any) -> List[str]:
    """Parse a param that may be list/tuple/set, comma-separated string, or scalar.

    Generic utility (NOT code-specific):
    - None -> []
    - list/tuple/set -> strip each item, drop empty
    - string -> split by ',', strip, drop empty
    - scalar -> str(value).strip() as single item if non-empty

    Output:
    - keeps order
    - de-duplicates
    """

    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        items = [str(x).strip() for x in value if str(x).strip()]
    elif isinstance(value, str):
        items = [x.strip() for x in value.split(",") if x.strip()]
    else:
        s = str(value).strip()
        items = [s] if s else []

    seen = set()
    out: List[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out

