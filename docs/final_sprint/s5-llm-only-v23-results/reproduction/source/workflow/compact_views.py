"""Lossless compact-view defaults and verified duplicate Critic claim removal."""
from __future__ import annotations

from copy import deepcopy
import json


LOSSLESS_VIEW_VERSION = "lossless-default-view-v3-s5"
CLAIM_DEFAULTS = {"pi": None, "r": None, "e": [], "f": [], "p": "",
                  "dc": False, "hi": False, "cf": False}
_CLAIM_REQUIRED = {"i", "t", "k", "d", "s", "ss", "q", "c", "cr"}


def _is_claim(value):
    return isinstance(value, dict) and _CLAIM_REQUIRED <= value.keys()


def _wire_claims(value):
    if _is_claim(value):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _wire_claims(child)
    elif isinstance(value, list):
        for child in value:
            yield from _wire_claims(child)


def _deduplicated_wire_claims(wire):
    claims = {}
    for claim in _wire_claims(wire):
        if claim["i"] in claims and claim != claims[claim["i"]]:
            return None
        claims.setdefault(claim["i"], claim)
    return list(claims.values())


def _same_typed_value(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_typed_value(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_typed_value(a, b) for a, b in zip(left, right))
    return left == right


def _constant_columns(group):
    """Factor only literally identical cells; retain normal layout if shorter."""
    rows, columns = group["rows"], group["columns"]
    if len(rows) < 2:
        return group
    constant = {key: rows[0][index] for index, key in enumerate(columns)
        if all(_same_typed_value(rows[0][index], row[index]) for row in rows[1:])}
    varying = [(index, key) for index, key in enumerate(columns) if key not in constant]
    candidate = {"columns": [key for _, key in varying], "positions": group["positions"],
        "constant_columns": constant,
        "rows": [[row[index] for index, _ in varying] for row in rows]}
    size = lambda item: len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    return candidate if constant and size(candidate) < size(group) else group


def _claim_text_cells(view):
    """Locate only known textual claim fields, never evidence/finance ID cells."""
    for capsule in view.get("upstream", []):
        claims = capsule.get("claims")
        if isinstance(claims, list):
            for claim in claims:
                if _is_claim(claim):
                    for key in ("t", "d", "p"):
                        if isinstance(claim.get(key), str):
                            yield claim, key, claim[key]
        elif isinstance(claims, dict) and "groups" in claims:
            for group in claims["groups"]:
                constants = group.get("constant_columns", {})
                for key in ("t", "d", "p"):
                    if isinstance(constants.get(key), str):
                        yield constants, key, constants[key]
                for index, key in enumerate(group["columns"]):
                    if key in ("t", "d", "p"):
                        for row in group["rows"]:
                            if isinstance(row[index], str):
                                yield row, index, row[index]


def _pool_duplicate_claim_text(view):
    """Use exact original strings once, only when the full encoded view shrinks."""
    candidate = deepcopy(view)
    cells = list(_claim_text_cells(candidate))
    counts = {}
    for _, _, value in cells:
        if len(value) >= 32:
            counts[value] = counts.get(value, 0) + 1
    pool = [value for value, count in counts.items() if count > 1]
    if not pool:
        return view
    indexes = {value: index for index, value in enumerate(pool)}
    for container, key, value in cells:
        if value in indexes:
            # Original t/d/p values are strings, so one-index arrays are unambiguous.
            container[key] = [indexes[value]]
    candidate["lossless_view"].update(claim_text_pool=pool,
        claim_text_pool_rule="Only claim t/d/p cells or constants may use [index]; replace with that exact claim_text_pool string. No text is shortened.")
    size = lambda item: len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    return candidate if size(candidate) < size(view) else view


def compact_generation_view(view, role):
    """Return a copy; omitted defaults and duplicate locations are explicit.

    A Critic capsule's claim list is omitted only when the complete list equals
    the first-occurrence-deduplicated claims in its retained reviewed wire.
    No non-default value, original claim text, evidence or unresolved state is
    removed. The default table is scoped only to claim dictionaries.
    """
    result = deepcopy(view)
    if "lossless_view" in result:
        raise ValueError("compact generation view already encoded")
    omitted_capsules = []
    table_capsules = []
    if role == "writer":
        for index, capsule in enumerate(result.get("upstream", [])):
            claims = capsule.get("claims")
            if not isinstance(claims, list) or not claims:
                continue
            first = claims[0]
            if (not _is_claim(first) or not CLAIM_DEFAULTS.keys() <= first.keys() or
                    not all(_is_claim(item) and set(item) == set(first) for item in claims)):
                continue
            groups = {}
            for position, item in enumerate(claims):
                remaining = {key: value for key, value in item.items()
                    if key not in CLAIM_DEFAULTS or type(value) is not type(CLAIM_DEFAULTS[key])
                    or value != CLAIM_DEFAULTS[key]}
                columns = tuple(key for key in first if key in remaining)
                group = groups.setdefault(columns, {"columns": list(columns),
                    "positions": [], "rows": []})
                group["positions"].append(position)
                group["rows"].append([remaining[key] for key in columns])
            # Explicit positions preserve original order across different key sets.
            # Only neutral defaults move to the visible default table; every other
            # original value occupies a cell without changing its type or value.
            capsule["claims"] = {"count": len(claims),
                "groups": [_constant_columns(group) for group in groups.values()]}
            table_capsules.append(index)
    if role.endswith("_critic"):
        reviewed = result.get("reviewed_artifact", {})
        wire = reviewed.get("wire")
        capsules = result.get("upstream", [])
        if isinstance(wire, dict) and len(capsules) == 1:
            capsule = capsules[0]
            reconstructed = _deduplicated_wire_claims(wire)
            if (reconstructed is not None and capsule.get("claims") == reconstructed and
                    capsule.get("version") == reviewed.get("version") and
                    reviewed.get("id") == f"{capsule.get('role')}.initial"):
                del capsule["claims"]
                omitted_capsules.append(0)

    for claim in _wire_claims(result):
        # Existing canonical->wire encoders explicitly emit these defaults.
        # Partial arbitrary dictionaries are left alone rather than reinterpreted.
        if not CLAIM_DEFAULTS.keys() <= claim.keys():
            continue
        for key, default in CLAIM_DEFAULTS.items():
            value = claim[key]
            if type(value) is type(default) and value == default:
                del claim[key]
    result["lossless_view"] = {
        "version": LOSSLESS_VIEW_VERSION,
        "claim_defaults": deepcopy(CLAIM_DEFAULTS),
        "field_meanings": {"r": "source recency 0..1/null; never revenue/result/amount"},
        "rule": "Omitted claim fields use claim_defaults; all non-default values remain explicit.",
        "critic_upstream_claims_from_reviewed_wire": omitted_capsules,
        "critic_reconstruction": "first-occurrence unique claim i in reviewed_artifact.wire",
        "writer_claim_table_capsules": table_capsules,
        "writer_table_rule": "For each claims group, merge constant_columns with columns zipped to each row, restore omitted claim_defaults, and place at its zero-based positions entry; constants are exact equal original values, not inferred.",
    }
    return _pool_duplicate_claim_text(result) if role == "writer" else result
