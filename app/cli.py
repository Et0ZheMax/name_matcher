from __future__ import annotations

import argparse
from pathlib import Path

from app.exporter import export_result
from app.pipeline.bootstrap import build_runtime


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Enrich RU organization names with EN candidates + PubMed validation")
    p.add_argument("input_file", type=Path)
    p.add_argument("--output", type=Path, default=Path("outputs/result.xlsx"))
    p.add_argument("--org-column", type=str, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--mode", choices=["strict", "balanced", "aggressive"], default="balanced")
    p.add_argument("--first-column-as-org", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    runtime = build_runtime(args.mode, no_cache=args.no_cache, debug=args.debug)

    # --resume prepared for future granular checkpointing; cache already helps avoid repeated network calls.
    if args.resume:
        runtime.runner.logger.info("Resume mode enabled: using cached source responses where available.")

    result = runtime.runner.run(
        args.input_file,
        org_column=args.org_column,
        first_column_as_org=args.first_column_as_org,
        limit=args.limit,
    )
    export_result(result, args.output)
    runtime.runner.logger.info("Done. Output written to %s", args.output)


if __name__ == "__main__":
    main()
