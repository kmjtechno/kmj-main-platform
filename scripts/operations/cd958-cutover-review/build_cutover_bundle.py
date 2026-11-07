"""Build a standalone cutover review artifact for python3 -I -B."""

import hashlib
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_cutover_bundle.py OUTPUT")
    source_dir = Path(__file__).resolve().parent
    output = Path(sys.argv[1])
    chunks = ["import sys\nimport types\n"]
    for name in ("orchestrator", "native_plan", "native_ops", "cutover_runner"):
        source = (source_dir / (name + ".py")).read_bytes()
        compile(source, name + ".py", "exec")
        chunks.append(
            f"module = types.ModuleType({name!r})\n"
            f"sys.modules[{name!r}] = module\n"
            f"exec(compile({source!r}, {name + '.py'!r}, 'exec'), module.__dict__)\n"
        )
    chunks.append("raise SystemExit(module.main())\n")
    bundle = "".join(chunks).encode("utf-8")
    with output.open("xb") as stream:
        stream.write(bundle)
    print(hashlib.sha256(bundle).hexdigest())


if __name__ == "__main__":
    main()
