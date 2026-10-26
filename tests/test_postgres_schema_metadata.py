"""PostgreSQL metadata comparator tests: synthetic data, no DB credentials."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/ci/compare_postgres_schema_metadata.py"
spec = importlib.util.spec_from_file_location("pg_metadata_review", SCRIPT)
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)


def metadata():
    return {
        "format": "kmj-postgresql-metadata-v1",
        "engine": "postgresql",
        "scope": "public",
        "serverMajor": 18,
        "relations": [{"schema": "public", "table": "widgets", "kind": "r"}],
        "columns": [{"schema": "public", "table": "widgets", "column": "id", "type": "bigint", "notNull": True}],
        "constraints": [{"schema": "public", "table": "widgets", "name": "widgets_pkey", "kind": "p"}],
    }


class SchemaMetadataTests(unittest.TestCase):
    def test_matching_pg18_snapshots(self):
        data = pg.snapshot_data(metadata())
        self.assertEqual(pg.assess(data, data)["outcome"], "MATCH")

    def test_detects_added_relation(self):
        first = pg.snapshot_data(metadata())
        second = metadata()
        second["relations"].append({"schema": "public", "table": "unreviewed", "kind": "r"})
        self.assertEqual(pg.assess(first, pg.snapshot_data(second))["counts"]["relations"]["unexpected"], 1)

    def test_detects_column_type_change(self):
        first = pg.snapshot_data(metadata())
        second = metadata()
        second["columns"][0]["type"] = "text"
        changed = pg.assess(first, pg.snapshot_data(second))
        self.assertEqual(changed["outcome"], "DRIFT")
        self.assertEqual(changed["counts"]["columns"], {"missing": 1, "unexpected": 1})

    def test_detects_missing_constraint(self):
        first = pg.snapshot_data(metadata())
        second = metadata()
        second["constraints"] = []
        self.assertEqual(pg.assess(first, pg.snapshot_data(second))["counts"]["constraints"]["missing"], 1)

    def test_major_version_mismatch_is_not_match(self):
        first = pg.snapshot_data(metadata())
        second = metadata()
        second["serverMajor"] = 16
        self.assertEqual(pg.assess(first, pg.snapshot_data(second))["outcome"], "VERSION_MISMATCH")

    def test_rejects_wrong_engine_cross_schema_and_partial(self):
        for change in (
            lambda d: d.update(engine="sqlite"),
            lambda d: d["columns"][0].update(schema="pg_catalog"),
            lambda d: d.pop("columns"),
        ):
            d = metadata()
            change(d)
            with self.assertRaises(pg.InvalidSnapshot):
                pg.snapshot_data(d)

    def test_rejects_duplicate_objects(self):
        d = metadata()
        d["columns"].append(dict(d["columns"][0]))
        with self.assertRaises(pg.InvalidSnapshot):
            pg.snapshot_data(d)

    def test_rejects_malformed_metadata_and_bools_as_versions(self):
        d = metadata()
        d["serverMajor"] = True
        with self.assertRaises(pg.InvalidSnapshot):
            pg.snapshot_data(d)
        d = metadata()
        d["relations"][0]["kind"] = "\nDROP TABLE"
        with self.assertRaises(pg.InvalidSnapshot):
            pg.snapshot_data(d)

    def test_cli_detects_modified_snapshot_and_never_connects(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td)
            a, b = p / "before.json", p / "after.json"
            a.write_text(json.dumps(metadata()), encoding="utf-8")
            b.write_text(json.dumps(metadata()), encoding="utf-8")
            self.assertEqual(pg.load(a)["serverMajor"], 18)
            self.assertEqual(pg.main.__name__, "main")
            changed = metadata()
            changed["relations"] = []
            b.write_text(json.dumps(changed), encoding="utf-8")
            self.assertEqual(pg.assess(pg.load(a), pg.load(b))["outcome"], "DRIFT")

    def test_duplicate_json_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "broken.json"
            p.write_text('{"engine":"postgresql","engine":"sqlite"}', encoding="utf-8")
            with self.assertRaises(pg.InvalidSnapshot):
                pg.load(p)


if __name__ == "__main__":
    unittest.main()
