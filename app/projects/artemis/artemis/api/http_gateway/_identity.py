"""Shared strict identity-param parsers for the HTTP gateway routes.

HTTP gateway routes parse ``security_id`` (singular) and ``security_ids``
(comma-separated) query/path params with the same strict
semantics: absent → None; a present value that is empty / non-numeric /
non-positive / contains an empty token → 400 (never silently treated as
absent, which would let an explicit empty identity degrade to an unfiltered
query downstream).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException


def _parse_security_ids(raw: Optional[str]) -> Optional[List[int]]:
    """Parse a comma-separated security_ids string → list[int] (strict).

    None (absent) → None. A present value is parsed strictly: empty tokens
    (leading/trailing/consecutive comma, or bare ``?security_ids=``),
    non-numeric tokens, and non-positive ids → 400. Never returns an empty
    list for a present value.
    """
    if raw is None:
        return None
    out: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="security_ids contains an empty token")
        try:
            v = int(token)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"invalid security_id token: {token!r}")
        if v <= 0:
            raise HTTPException(status_code=400, detail=f"security_id must be a positive integer, got {v}")
        out.append(v)
    if not out:
        raise HTTPException(status_code=400, detail="security_ids is empty")
    return out


def _parse_security_id(raw: Optional[str]) -> Optional[int]:
    """Parse a singular security_id string → int (strict).

    None (absent) → None. A present value is parsed strictly: empty,
    non-numeric, or non-positive → 400 — never silently treated as absent
    (which would let an explicit empty identity degrade to an unfiltered
    query downstream). Mirrors ``_parse_security_ids`` so both identity
    shapes return a uniform 400 + ``{"detail": "..."}`` envelope instead of
    FastAPI's 422 validation array.
    """
    if raw is None:
        return None
    token = raw.strip()
    if not token:
        raise HTTPException(status_code=400, detail="security_id is empty")
    try:
        v = int(token)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid security_id: {token!r}")
    if v <= 0:
        raise HTTPException(status_code=400, detail=f"security_id must be a positive integer, got {v}")
    return v
