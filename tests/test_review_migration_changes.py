"""No database or external service required; synthetic fixtures only."""
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts/ci/review_migration_changes.py"
spec = importlib.util.spec_from_file_location("migration_review", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def migration(up, down="Schema::dropIfExists('widgets');"):
    return f"""<?php
return new class extends Migration {{
    public function up(): void {{
        {up}
    }}
    public function down(): void {{
        {down}
    }}
}};
"""


class MigrationRiskReviewTests(unittest.TestCase):
    def test_additive_migration_passes_and_down_is_not_a_risk(self):
        self.assertEqual(module.audit_php(migration("Schema::create('widgets', function (Blueprint $table) { $table->id(); });")), [])

    def test_destructive_up_is_blocked(self):
        findings = module.audit_php(migration("Schema::dropIfExists('users');"))
        self.assertIn("SCHEMA_DROP", [name for name, _ in findings])

    def test_raw_sql_flagged_even_when_multiline(self):
        findings = module.audit_php(migration('DB::statement(\n"ALTER TABLE users DROP COLUMN email"\n);'))
        self.assertIn("RAW_DATABASE_STATEMENT", [name for name, _ in findings])
        self.assertIn("UNSAFE_DDL_LITERAL", [name for name, _ in findings])

    def test_comments_are_ignored(self):
        source = migration("// Schema::drop('fake');\n /* DB::unprepared('DROP TABLE x'); */\n Schema::create('safe', function ($t) { $t->id(); });")
        self.assertEqual(module.audit_php(source), [])

    def test_braces_inside_strings_do_not_confuse_up_detection(self):
        source = migration("$x = '}';\n Schema::create('safe', function ($t) { $t->id(); });")
        self.assertEqual(module.audit_php(source), [])

    def test_multiple_or_missing_up_functions_fail_closed(self):
        for source in ("<?php // no migration", migration("return;") + migration("return;")):
            with self.assertRaises(ValueError):
                module.audit_php(source)

    def test_column_changes_and_fk_disable_blocked(self):
        source = migration("$table->dropColumn('email'); Schema::disableForeignKeyConstraints();")
        codes = [code for code, _ in module.audit_php(source)]
        self.assertIn("COLUMN_OR_INDEX_DROP", codes)
        self.assertIn("DISABLE_FK_GUARD", codes)

    def test_invalid_sha_denied_before_git(self):
        with self.assertRaises(ValueError):
            module.changed_migrations("main; rm -rf /", "a" * 40)


if __name__ == "__main__":
    unittest.main()
