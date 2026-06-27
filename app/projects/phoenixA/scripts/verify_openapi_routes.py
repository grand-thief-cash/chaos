#!/usr/bin/env python3
"""
Verify that paths declared in openapi.yaml are registered in
internal/api/router_v2.go, and that the AmazingData-relevant routes
registered in router_v2.go appear in openapi.yaml.

This is a one-way consistency check, not a full OpenAPI lint. It catches the
most common drift: someone adds a route to the router but forgets to document
it, or documents a path that no longer exists.

Scope: only AmazingData dataset APIs (discovery, query, coverage, write).
Other route groups (bars, taxonomy, KG, graph, legacy v1) are out of scope
and ignored on both sides.

Exit code 0 = consistent, 1 = drift detected.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OPENAPI = REPO / "openapi.yaml"
ROUTER = REPO / "internal" / "api" / "router_v2.go"

SCOPE_PREFIXES = (
    "/api/v2/catalog/datasets",
    "/api/v2/catalog/enums",
    "/api/v2/catalog/field-coverage",
    "/api/v2/catalog/securities",
    "/api/v2/financial",
    "/api/v2/corporate-action",
    "/api/v2/equity-structure",
)


def openapi_paths() -> set[str]:
    """Extract declared path templates from openapi.yaml."""
    text = OPENAPI.read_text(encoding="utf-8")
    paths = set()
    in_paths = False
    for line in text.splitlines():
        if line.startswith("paths:"):
            in_paths = True
            continue
        if in_paths:
            if line and not line.startswith(" ") and not line.startswith("#"):
                in_paths = False
                continue
            m = re.match(r"^  (/[^:]+):\s*$", line)
            if m:
                paths.add(m.group(1))
    return paths


def router_paths() -> set[str]:
    """Extract in-scope path templates from router_v2.go.

    Strategy: parse the file with a proper Go-aware brace counter. We walk
    token by token, maintaining a stack of (prefix, brace_depth_when_pushed).
    When we see `r.Route("/X", func(r chi.Router) {`, we push "/X" and
    remember the depth at the moment of the `{`. When braces close back to
    that depth, we pop. When we see `r.{Get,Post,Put,Delete}("/Y", ...)`
    inside a route, we record stack-prefix + "/Y".
    """
    text = ROUTER.read_text(encoding="utf-8")
    # Remove line comments and strings to simplify brace counting.
    text = re.sub(r"//.*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    text = re.sub(r"`(?:[^`])*`", "``", text)

    paths: set[str] = set()
    stack: list[tuple[str, int]] = []  # (prefix, depth_at_open)
    depth = 0
    i = 0
    n = len(text)
    pat_route = re.compile(r'r\.Route\(\s*""\s*,\s*func\([^)]*\)\s*\{')
    pat_method = re.compile(r'r\.(?:Get|Post|Put|Delete)\(\s*""')
    # We replaced strings with "" — but we lost the actual path. Re-approach:
    # instead of stripping strings, leave them and match them in the regex.

    text = ROUTER.read_text(encoding="utf-8")
    text = re.sub(r"//.*", "", text)
    # Don't strip strings — we need them.
    pat_route = re.compile(r'r\.Route\(\s*"([^"]+)"')
    pat_method = re.compile(r'r\.(?:Get|Post|Put|Delete)\(\s*"([^"]+)"')

    depth = 0
    stack: list[tuple[str, int]] = []
    paths: set[str] = set()
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '{':
            depth += 1
            i += 1
            continue
        if ch == '}':
            depth -= 1
            # Pop stack entries whose body has closed.
            while stack and depth < stack[-1][1]:
                stack.pop()
            i += 1
            continue
        # Try to match r.Route or r.Method at this position.
        m_route = pat_route.match(text, i)
        if m_route:
            prefix = m_route.group(1)
            # Find the opening brace of the func body. It's the next '{' after
            # the match (possibly across the func signature). The depth at
            # which this '{' opens is `depth+1` (after we increment).
            # We record (prefix, depth+1) — the depth that, when we drop below
            # it, means this route's body closed.
            stack.append((prefix, depth + 1))
            # Advance past the route prefix; the brace counter will handle the
            # '{' naturally as we continue scanning.
            i = m_route.end()
            continue
        m_method = pat_method.match(text, i)
        if m_method:
            leaf = m_method.group(1)
            full = "".join(p for p, _ in stack) + leaf
            if full.startswith(SCOPE_PREFIXES):
                paths.add(full)
            i = m_method.end()
            continue
        i += 1
    return paths


def main() -> int:
    if not OPENAPI.exists():
        print(f"ERROR: {OPENAPI} not found", file=sys.stderr)
        return 1
    if not ROUTER.exists():
        print(f"ERROR: {ROUTER} not found", file=sys.stderr)
        return 1

    spec_set = openapi_paths()
    router_set = router_paths()

    def norm(s: str) -> str:
        return s.rstrip("/") if s != "/" else s

    spec_set = {norm(p) for p in spec_set}
    router_set = {norm(p) for p in router_set}

    missing_in_spec = router_set - spec_set
    missing_in_router = spec_set - router_set

    if not missing_in_spec and not missing_in_router:
        print(f"OK: {len(spec_set)} in-scope paths consistent between openapi.yaml and router_v2.go")
        return 0

    if missing_in_spec:
        print("ERROR: routes in router_v2.go but NOT in openapi.yaml:", file=sys.stderr)
        for p in sorted(missing_in_spec):
            print(f"  + {p}", file=sys.stderr)
    if missing_in_router:
        print("ERROR: paths in openapi.yaml but NOT in router_v2.go:", file=sys.stderr)
        for p in sorted(missing_in_router):
            print(f"  - {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
