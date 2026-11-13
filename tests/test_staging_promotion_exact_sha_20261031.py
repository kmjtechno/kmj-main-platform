"""Exact-SHA owner authorization contract for staging auto-promotion.

Runs without GitHub tokens, network, secrets, or staging/production access.
The intentionally broken synthetic cases must fail closed.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROMOTION = ROOT / ".github/workflows/staging-promotion-gate.yml"
DEPLOY = ROOT / ".github/workflows/staging-vps-deploy-fixed.yml"
OWNER_VAR = "KMJ_STAGING_PROMOTION_APPROVED_SHA"


def job_block(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z][A-Za-z0-9_-]*:\n|\Z)", source)
    if not match:
        raise ValueError("EXPECTED_JOB_NOT_FOUND")
    return match.group(1)


def job_condition(source: str, name: str) -> str:
    match = re.search(r"(?m)^    if: \$\{\{ ([^\n]+) \}\}$", job_block(source, name))
    if not match:
        raise ValueError("EXPECTED_SINGLE_JOB_CONDITION_NOT_FOUND")
    if len(re.findall(r"(?m)^    if:", job_block(source, name))) != 1:
        raise ValueError("DUPLICATE_JOB_CONDITION")
    return match.group(1)


def authorized_promotion(source: str) -> bool:
    try:
        cond = job_condition(source, "promote")
        block = job_block(source, "promote")
        write = block.split("      - name: Move staging-approved only after all verification passes\n", 1)[1]
        write_gate = write.split("        env:\n", 1)[0].strip()
        skipped = block.split("      - name: Record blocked staging promotion when exact owner SHA is absent\n", 1)[1]
        no_approval_gate = skipped.split("        run:\n", 1)[0].strip()
    except (ValueError, IndexError):
        return False
    required = (
        "needs.verify.result == 'success'",
        "needs.owner_auth.result == 'success'",
        "needs.locked_visual.result == 'success'",
        "needs.postgres.result == 'success'",
    )
    allowed_write = (
        "if: ${{ github.ref == 'refs/heads/main' && "
        "vars." + OWNER_VAR + " == github.sha }}"
    )
    blocked_write = (
        "if: ${{ github.ref != 'refs/heads/main' || "
        "vars." + OWNER_VAR + " != github.sha }}"
    )
    return (all(cond.count(x) == 1 for x in required)
            and " || " not in cond
            and write_gate == allowed_write
            and no_approval_gate.startswith(blocked_write))



def authorized_workflow_run(source: str) -> bool:
    try:
        cond = job_condition(source, "deploy")
    except ValueError:
        return False
    required = (
        "github.event_name == 'workflow_run'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.conclusion == 'success'",
        "vars." + OWNER_VAR + " == github.event.workflow_run.head_sha",
    )
    # Explicit dispatch and schedule are allowed; the workflow_run OR branch
    # must be grouped with success AND exact-SHA approval (never free-standing).
    expected = (
        "github.event_name == 'workflow_dispatch' || "
        "github.event_name == 'schedule' || "
        "(github.event_name == 'workflow_run' && "
        "github.event.workflow_run.head_branch == 'main' && "
        "github.event.workflow_run.conclusion == 'success' && "
        "vars." + OWNER_VAR + " == github.event.workflow_run.head_sha)"
    )
    return all(cond.count(x) == 1 for x in required) and cond == expected


class ExactShaStagingApprovalContract(unittest.TestCase):
    def test_promote_needs_all_existing_qa_gates_and_exact_owner_sha(self):
        raw = PROMOTION.read_text()
        self.assertTrue(authorized_promotion(raw))
        job = job_block(raw, "promote")
        self.assertIn("contents: write", job)
        self.assertIn("staging-approved", job)

    def test_workflow_run_must_be_owner_exact_sha_authorized(self):
        raw = DEPLOY.read_text()
        self.assertTrue(authorized_workflow_run(raw))
        self.assertIn("ref: staging-approved", job_block(raw, "deploy"))

    def test_unapproved_green_push_cannot_promote(self):
        source = PROMOTION.read_text()
        for broken in (
            source.replace(" && vars." + OWNER_VAR + " == github.sha", ""),
            source.replace("vars." + OWNER_VAR + " == github.sha", "true"),
            source.replace("github.ref == 'refs/heads/main'", "true"),
            source.replace("needs.owner_auth.result == 'success'", "true"),
        ):
            self.assertFalse(authorized_promotion(broken))

    def test_workflow_run_without_sha_gate_cannot_launch(self):
        source = DEPLOY.read_text()
        for broken in (
            source.replace(" && vars." + OWNER_VAR + " == github.event.workflow_run.head_sha", ""),
            source.replace("vars." + OWNER_VAR + " == github.event.workflow_run.head_sha", "true"),
            source.replace("github.event.workflow_run.conclusion == 'success'", "true"),
        ):
            self.assertFalse(authorized_workflow_run(broken))

    def test_skipped_promotion_has_explicit_no_deployment_receipt(self):
        job = job_block(PROMOTION.read_text(), "promote")
        skipped = job.split(
            "      - name: Record blocked staging promotion when exact owner SHA is absent\n", 1
        )[1].split("      - name: Move staging-approved only after all verification passes\n", 1)[0]
        self.assertIn("id: skipped", skipped)
        self.assertIn("echo 'performed=false' >> \"$GITHUB_OUTPUT\"", skipped)
        self.assertIn("STAGING_PROMOTION=SKIPPED_NO_EXACT_OWNER_SHA", skipped)
        self.assertIn("Staging promotion NOT performed", skipped)
        self.assertIn(
            "owner_sha_missing: ${{ steps.skipped.outputs.performed == 'false' }}", job
        )

    def test_approved_ref_update_never_claims_staging_server_deployment(self):
        job = job_block(PROMOTION.read_text(), "promote")
        promote = job.split(
            "      - name: Move staging-approved only after all verification passes\n", 1
        )[1]
        self.assertIn("id: promoted", promote)
        self.assertIn("echo 'performed=true' >> \"$GITHUB_OUTPUT\"", promote)
        self.assertIn("STAGING_PROMOTION=REF_ADVANCED_EXACT_OWNER_SHA", promote)
        self.assertIn("STAGING_SERVER_DEPLOYMENT=NOT_ATTESTED_BY_THIS_JOB", promote)
        self.assertIn("ref_advanced: ${{ steps.promoted.outputs.performed == 'true' }}", job)
        self.assertNotIn("STAGING_SERVER_DEPLOYMENT=PASS", job)

    def test_no_environment_or_credential_bypass_added(self):
        for path in (PROMOTION, DEPLOY):
            raw = path.read_text()
            self.assertNotIn("StrictHostKeyChecking=no", raw)
            self.assertNotIn("production_activate", raw)
            self.assertNotIn("force\\\":true", raw)


if __name__ == "__main__":
    unittest.main()
