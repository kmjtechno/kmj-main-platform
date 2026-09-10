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
    print("KMJ free-cloud router policy PASS")


if __name__ == "__main__":
    main()
