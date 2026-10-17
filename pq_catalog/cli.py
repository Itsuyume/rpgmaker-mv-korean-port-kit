"""Explicit local CLI; no network, model service or implicit game discovery."""
import argparse
from pathlib import Path

from .commands import add_plugins, apply, build, check


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="RPG Maker MV guarded localization catalog")
    sub = root.add_subparsers(dest="command", required=True)
    core = sub.add_parser("build-core", help="Freeze a core catalog and six contextual input groups")
    core.add_argument("--www", type=Path, required=True)
    core.add_argument("--source-manifest", type=Path, required=True)
    core.add_argument("--glossary", type=Path, required=True)
    core.add_argument("--project", type=Path, required=True)
    plugin = sub.add_parser("add-plugins", help="Append audited plugin input without repartitioning core")
    plugin.add_argument("--www", type=Path, required=True)
    plugin.add_argument("--source-manifest", type=Path, required=True)
    plugin.add_argument("--glossary", type=Path, required=True)
    plugin.add_argument("--audit-spec", type=Path, required=True)
    plugin.add_argument("--project", type=Path, required=True)
    validate = sub.add_parser("validate", help="Validate saved flat JSON translation shards")
    validate.add_argument("--project", type=Path, required=True)
    validate.add_argument("--group", type=int, choices=range(1, 7), required=True)
    validate.add_argument("--pending", type=int)
    validate.add_argument("--phase", choices=("all", "core", "additions"), default="all")
    validate.add_argument("--require-complete", action="store_true")
    validate.add_argument("--report", type=Path)
    application = sub.add_parser("apply", help="Apply complete translations to a separate prepared www")
    application.add_argument("--project", type=Path, required=True)
    application.add_argument("--source-www", type=Path, required=True)
    application.add_argument("--target-www", type=Path, required=True)
    application.add_argument("--audit-spec", type=Path)
    application.add_argument("--node", default="node", help="Local Node executable for static syntax checks")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "build-core":
        build(args.www, args.source_manifest, args.glossary, args.project)
        return 0
    if args.command == "add-plugins":
        add_plugins(args.www, args.source_manifest, args.glossary, args.audit_spec, args.project)
        return 0
    if args.command == "apply":
        apply(args.project, args.source_www, args.target_www, args.audit_spec, args.node)
        return 0
    if args.pending is not None and args.pending < 1:
        raise ValueError("--pending must be positive.")
    return check(args.project, args.group, args.pending, args.require_complete, args.report, args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
