#!/usr/bin/env python3
"""Compare two authorized PostgreSQL public-schema METADATA snapshots.

Caller supplies JSON; no connections, SQL execution, credentials, row data or
production mutations. PASS only means the supported metadata is equal.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MAX_BYTES = 2_000_000
FORMAT = "kmj-postgresql-metadata-v1"
SHAPES = {
    "relations": {"schema": str, "table": str, "kind": str},
    "columns": {"schema": str, "table": str, "column": str, "type": str, "notNull": bool},
    "constraints": {"schema": str, "table": str, "name": str, "kind": str},
}


class InvalidSnapshot(ValueError):
    pass


def safe_pairs(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidSnapshot("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def snapshot_data(data: object) -> dict[str, frozenset[tuple]]:
    if (
        not isinstance(data, dict)
        or set(data) != {"format", "engine", "scope", "serverMajor", *SHAPES}
        or data["format"] != FORMAT
        or data["engine"] != "postgresql"
        or data["scope"] != "public"
        or type(data["serverMajor"]) is not int
        or not 12 <= data["serverMajor"] <= 25
    ):
        raise InvalidSnapshot("INVALID_METADATA_FORMAT")
    result = {"serverMajor": data["serverMajor"]}
    for name, shape in SHAPES.items():
        rows = data[name]
        if not isinstance(rows, list) or len(rows) > 15000:
            raise InvalidSnapshot("INVALID_METADATA_COLLECTION")
        normalized = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(shape):
                raise InvalidSnapshot("INVALID_METADATA_ROW")
            if any(
                type(row[k]) is not expected
                or (
                    expected is str
                    and (not 1 <= len(row[k]) <= 256
                         or any(ord(char) < 32 for char in row[k]))
                )
                for k, expected in shape.items()
            ):
                raise InvalidSnapshot("INVALID_METADATA_VALUE")
            if row["schema"] != "public":
                raise InvalidSnapshot("CROSS_SCHEMA_NOT_ALLOWED")
            normalized.append(tuple(row[k] for k in shape))
        if len(set(normalized)) != len(normalized):
            raise InvalidSnapshot("DUPLICATE_METADATA_ROW")
        result[name] = frozenset(normalized)
    return result


def load(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise InvalidSnapshot("INVALID_SNAPSHOT_FILE")
    with path.open("r", encoding="utf-8") as source:
        data = json.load(source, object_pairs_hook=safe_pairs)
    return snapshot_data(data)


def assess(before: dict, after: dict) -> dict[str, object]:
    if before["serverMajor"] != after["serverMajor"]:
        return {"outcome": "VERSION_MISMATCH",
                "expectedMajor": before["serverMajor"], "actualMajor": after["serverMajor"]}
    counts = {
        name: {
            "missing": len(before[name] - after[name]),
            "unexpected": len(after[name] - before[name]),
        }
        for name in SHAPES
    }
    return {
        "outcome": "MATCH" if all(
            count == 0 for side in counts.values() for count in side.values()
        ) else "DRIFT",
        "serverMajor": before["serverMajor"],
        "counts": counts,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected", required=True)
    p.add_argument("--actual", required=True)
    args = p.parse_args()
    expected, actual = Path(args.expected), Path(args.actual)
    try:
        if expected.resolve() == actual.resolve():
            raise InvalidSnapshot("SAME_SNAPSHOT_PATH")
        result = assess(load(expected), load(actual))
        print(f"KMJ_POSTGRES_SCHEMA_METADATA={result['outcome']}")
        if "counts" in result:
            print(f"KMJ_POSTGRES_MAJOR={result['serverMajor']}")
            for name, counts in result["counts"].items():
                print(f"{name.upper()}_MISSING={counts['missing']} UNEXPECTED={counts['unexpected']}")
        else:
            print(f"EXPECTED_MAJOR={result['expectedMajor']} ACTUAL_MAJOR={result['actualMajor']}")
        print("SCOPE=PUBLIC_RELATIONS_COLUMNS_CONSTRAINT_NAMES ONLY; "
              "ROLE_VISIBILITY=NOT_ATTESTED PROVENANCE=CALLER_SUPPLIED")
        print("DATA_ROWS_READ=NO DATABASE_CONNECTED=NO PRODUCTION_WRITES=NO")
        return 0 if result["outcome"] == "MATCH" else 1
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        print("KMJ_POSTGRES_SCHEMA_METADATA=BLOCKED_INVALID_SNAPSHOT")
        return 2


if __name__ == "__main__":
    sys.exit(main())
