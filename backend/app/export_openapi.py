"""Write the OpenAPI schema to a file, without serving it.

The interactive docs are off by default, so the contract has to be consumable
some other way. `app.openapi()` builds the schema in-process, with no server
listening and no route exposed, which is the right shape for CI and for
generating a client:

    python -m app.export_openapi openapi.json
    python -m app.export_openapi -            # stdout, for diffing

This is deliberately not a route. Adding one would re-create the exposure it
exists to work around.
"""

import argparse
import json
import sys
from pathlib import Path


def build_schema() -> dict:
    """The full OpenAPI document for the current app configuration."""
    from .main import app

    return app.openapi()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "output",
        nargs="?",
        default="-",
        help="file to write, or '-' for stdout (the default)",
    )
    args = parser.parse_args(argv)

    schema = build_schema()
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False)

    if args.output == "-":
        sys.stdout.write(text + "\n")
        return 0

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    print(f"{len(schema.get('paths', {}))} paths -> {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
