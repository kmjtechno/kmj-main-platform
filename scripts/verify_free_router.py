import os
from unittest.mock import patch

from controller.model_router import FreeCloudRouter


def main() -> None:
    router = FreeCloudRouter()

    cases = [
        ("openrouter/example-model:free", "openrouter", True),
        ("openrouter/example-model", "openrouter", False),
        ("qwen/qwen-coder", "qwen", True),
        ("iflow/coder", "iflow", True),
        ("kiro/coding", "kiro", True),
        ("opencode/free-coder", "opencode", True),
        ("glm/paid-model", "glm", False),
        ("unknown/model", "unknown", False),
    ]

    for model_id, owner, expected in cases:
        actual, reason = router._eligible(model_id, owner)
        assert actual is expected, f"{model_id}: expected {expected}, got {actual} ({reason})"

    ranked = router.rank(
        [
            {"id": "qwen/qwen-coder", "owned_by": "qwen"},
            {"id": "unknown/super-coder", "owned_by": "unknown"},
            {"id": "openrouter/fallback:free", "owned_by": "openrouter"},
        ],
        "coding",
    )
    assert ranked, "expected at least one verified-zero route"
    assert all("unknown/" not in item.model_id for item in ranked)
    direct_ok, _ = router._eligible("openrouter/free", "openrouter", "openrouter")
    assert direct_ok, "OpenRouter free auto-router must remain eligible"

    direct_paid_risk, _ = router._eligible("qwen/qwen-coder", "qwen", "groq")
    assert not direct_paid_risk, "direct provider account must not inherit 9Router owner trust"

    with patch.dict(os.environ, {"KMJ_VERIFIED_FREE_PROVIDERS": "groq"}, clear=False):
        verified_router = FreeCloudRouter()
        verified_ok, reason = verified_router._eligible("qwen/qwen-coder", "qwen", "groq")
        assert verified_ok and reason == "verified-free-provider-account"

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
        provider_router = FreeCloudRouter()
        assert "openrouter" in {provider.name for provider in provider_router.providers()}

    print("KMJ federated free-cloud router policy PASS")


if __name__ == "__main__":
    main()
