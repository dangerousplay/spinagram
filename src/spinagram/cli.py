"""Command line: ``spinagram render``, ``check``, ``facts``, ``layout``, ``deck``, ``serve`` and ``skills``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, api, qa
from .autolayout.engines import EngineUnavailable
from .backends import available
from .theme import Theme
from .yaml_io import load


def _collect(paths: list[str], only: list[str] | None, tags: list[str] | None = None,
             category: str | None = None):
    from .metadata import matches

    diagrams = [d for p in paths for d in load(p)]
    if only:
        diagrams = [d for d in diagrams if d.id in set(only)]
    if tags or category is not None:
        diagrams = [d for d in diagrams if matches(d, tags or (), category)]
    if not diagrams:
        sys.exit("no diagrams found")
    return diagrams


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (ValueError, KeyError, FileNotFoundError, EngineUnavailable) as exc:  # incl. FactError (unknown fact id)
        print(f"spinagram: error: {exc}", file=sys.stderr)
        return 2


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spinagram", description=__doc__)
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "check", "facts", "layout"):
        p = sub.add_parser(name, help="freeze automatic positions into an explicit YAML spec" if name == "layout"
                           else None)
        p.add_argument("paths", nargs="+", help="spec files or directories (*.yaml, *.py)")
        p.add_argument("-t", "--theme", help="theme directory or built-in name (env SPINAGRAM_THEME)")
        p.add_argument("--only", nargs="*", help="diagram ids to include")
        p.add_argument("--tag", action="append", metavar="TAG",
                       help="only diagrams with this tag, declared or inferred (aws, gcp, kubernetes…); repeatable")
        p.add_argument("--category", help="only diagrams in this category (declared, or the dominant provider)")
        p.add_argument("--layout", metavar="ENGINE",
                       help="layout engine for specs with `layout:` (flex, dot, elk, d2; env SPINAGRAM_LAYOUT)")
        if name == "layout":
            p.add_argument("-o", "--out", help="output YAML (default: stdout)")
        if name == "check":
            p.add_argument("--styles", action="store_true",
                           help="explain each element's computed style: matching rules, overrides, inheritance")
            p.add_argument("--select", metavar="SELECTOR", help="with --styles: only elements matching this CSS selector")
            p.add_argument("--json", action="store_true", help="print the style report as JSON (implies --styles)")
            p.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                           help="colour the style report (auto: when stdout is a terminal and NO_COLOR is unset)")
            p.add_argument("--fix", action="store_true",
                           help="apply safe fixes: YAML specs get a <name>.fixed.yaml copy, Python specs get "
                                "suggested edits; sources are never modified")
        if name == "render":
            p.add_argument("-f", "--formats", default="svg,png",
                           help=f"comma list from: {', '.join(sorted(available()))}")
            p.add_argument("-o", "--out", default="out")
            p.add_argument("--no-gallery", action="store_true")
            p.add_argument("--name-from", choices=("slug", "id", "file"), default="slug",
                           help="output file names: <id>-<title> (slug, default), the diagram id, or the spec file; "
                                "a diagram's own `output:` always wins")
            p.add_argument("--relayout", action="store_true",
                           help="apply check's safe fixes in memory before rendering (hand-placed diagrams)")
    ic = sub.add_parser("icons", help="icon packs: list, fetch, search, add, remove")
    isub = ic.add_subparsers(dest="icmd", required=True)
    isub.add_parser("list", help="registered packs and whether they are downloaded")
    f = isub.add_parser("fetch", help="download packs into the cache (default: all)")
    f.add_argument("packs", nargs="*")
    f.add_argument("--force", action="store_true", help="download again even if cached")
    q = isub.add_parser("search", help="find icon names (fetched packs only)")
    q.add_argument("query")
    q.add_argument("--pack", action="append", help="limit to these packs")
    q.add_argument("--limit", type=int, default=40)
    a = isub.add_parser("add", help="register an icon pack (user registry, or --project)")
    a.add_argument("name")
    src = a.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", metavar="URL", help="zip or tar archive URL (file:// works)")
    src.add_argument("--npm", metavar="PKG[@VER]", help="npm package")
    src.add_argument("--github", metavar="OWNER/REPO[@REF]", help="GitHub repository")
    src.add_argument("--dir", metavar="PATH", help="local directory with .svg/.png files")
    a.add_argument("--registry", help="npm registry URL for --npm (default registry.npmjs.org), e.g. Artifactory")
    a.add_argument("--include", action="append", default=[], help="glob(s) inside the source, e.g. 'icons/*'")
    a.add_argument("--match", help="regex with a (?P<stem>…) group; default: the file name")
    a.add_argument("--name-template", default="{stem}", help="icon name template from the regex groups")
    a.add_argument("--strip", action="append", default=[], help="regex removed from names to make short aliases")
    a.add_argument("--title", default="")
    a.add_argument("--license", default="")
    a.add_argument("--project", action="store_true", help="write ./spinagram-icons.yaml instead of the user registry")
    a.add_argument("--no-fetch", action="store_true", help="only register; download on first use")
    im = isub.add_parser("import", help="register every pack of a descriptor YAML (e.g. a package's spinagram-icons.yaml)")
    im.add_argument("file")
    im.add_argument("--project", action="store_true")
    rp = isub.add_parser("report", help="every icon the diagrams use: resolved reference and source "
                                        "(official, theme, fallback:<n>, missing)")
    rp.add_argument("paths", nargs="+", help="spec files or directories")
    rp.add_argument("-t", "--theme", help="theme directory or built-in name (env SPINAGRAM_THEME)")
    r = isub.add_parser("remove", help="unregister a user or project pack")
    r.add_argument("name")
    r.add_argument("--project", action="store_true")

    v = sub.add_parser("vectorize", help="trace PNG icons into SVG, gated by a fidelity check")
    v.add_argument("paths", nargs="+", help="PNG files or directories")
    v.add_argument("-o", "--out", help="output directory (default: next to each PNG)")
    v.add_argument("--force", action="store_true", help="write the SVG even when the fidelity gate rejects it")

    p = sub.add_parser("deck", help="self-contained HTML presentation from a deck.yaml")
    p.add_argument("deck", help="deck.yaml (title, authors, sections → slides → diagram ids)")
    p.add_argument("-t", "--theme", help="theme directory or built-in name (env SPINAGRAM_THEME)")
    p.add_argument("-o", "--out", help="output .html (default: next to deck.yaml)")
    sk = sub.add_parser("skills", help="agent skills for coding assistants: list, show, path, install")
    ssub = sk.add_subparsers(dest="scmd", required=True)
    ssub.add_parser("list", help="bundled skills")
    p = ssub.add_parser("show", help="print a skill's SKILL.md (paste it where your agent reads instructions)")
    p.add_argument("name")
    p = ssub.add_parser("path", help="folder of a skill, or of all skills")
    p.add_argument("name", nargs="?")
    p = ssub.add_parser("install", help="copy skills into the folder a coding agent reads")
    p.add_argument("names", nargs="*", help="skills to install (default: all)")
    p.add_argument("-a", "--agent", action="append", metavar="AGENT",
                   help="target agent, repeatable: " + ", ".join(_skill_agents()) + " (default: agents)")
    p.add_argument("--dest", help="install into this folder instead (any other tool)")
    p.add_argument("--user", action="store_true", help="install for the user (home folder), not this project")
    p.add_argument("--link", action="store_true", help="symlink instead of copying (follows spinagram upgrades)")
    p.add_argument("--force", action="store_true", help="replace skills that are already installed")
    p = sub.add_parser("mcp", help="MCP server for coding agents (stdio, or --http); `mcp install` configures agents")
    p.add_argument("-t", "--theme", help="default theme for tool calls (directory or built-in name)")
    p.add_argument("--layout", metavar="ENGINE", help="default layout engine for specs with `layout:`")
    p.add_argument("--formats", help="default render formats, comma list (default: svg,png)")
    p.add_argument("--root", help="folder every tool path must stay inside (default: current folder)")
    p.add_argument("--http", type=int, metavar="PORT", help="serve streamable HTTP at http://HOST:PORT/mcp")
    p.add_argument("--host", default="127.0.0.1", help="with --http: address to bind (default 127.0.0.1)")
    msub = p.add_subparsers(dest="mcmd")
    i = msub.add_parser("install", help="add the server to a coding agent's MCP config")
    i.add_argument("-a", "--agent", action="append", metavar="AGENT",
                   help="target agent, repeatable: claude, codex, copilot, cursor, gemini, opencode")
    i.add_argument("--user", action="store_true", help="the agent's user config (home folder), not this project's")
    i.add_argument("--name", default="spinagram", help="server name in the config (default: spinagram)")
    i.add_argument("--force", action="store_true", help="replace an entry with the same name")
    i.add_argument("--uvx", action="store_true", help="launch with uvx (pinned to this version) instead of this Python")
    i.add_argument("--url", help="connect to a running `spinagram mcp --http` at this URL instead of launching one")
    i.add_argument("-t", "--theme", help="server default theme")
    i.add_argument("--root", help="server root folder (stored as an absolute path)")
    i.add_argument("--formats", help="server default render formats, comma list")
    i.add_argument("--layout", metavar="ENGINE", help="server default layout engine")
    p = sub.add_parser("serve", help="live-reload UI: diagrams, theme token sheets, icon packs")
    p.add_argument("paths", nargs="*", default=["."], help="spec files or folders (default: .)")
    p.add_argument("-t", "--theme", help="theme directory or built-in name (env SPINAGRAM_THEME)")
    p.add_argument("--layout", help="initial layout engine for diagrams with `layout:`")
    p.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (0 = any free port)")
    p.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args(argv)
    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "mcp":
        return _mcp(args)
    if args.cmd == "icons":
        return _icons(args)
    if args.cmd == "skills":
        return _skills(args)
    if args.cmd == "vectorize":
        return _vectorize(args)
    if args.cmd == "deck":
        from .deck import build_deck

        print(build_deck(args.deck, args.theme, args.out))
        return 0
    diagrams = _collect(args.paths, args.only, args.tag, args.category)
    theme = Theme.load(args.theme)
    if args.cmd == "layout":
        import yaml

        from .autolayout import apply_layout
        from .yaml_io import dump

        docs = [dump(apply_layout(d, theme, args.layout)) for d in diagrams]
        text = yaml.safe_dump(docs if len(docs) > 1 else docs[0], sort_keys=False, allow_unicode=True, width=120)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(args.out)
        else:
            print(text, end="")
        return 0
    if args.cmd == "facts":
        for sc in api.scenes(diagrams, theme, args.layout):
            for r in sc.sources:
                print(f"{sc.id}\t{r['id']}\t{r['display']}\t{r.get('system', r.get('formula', ''))}\t"
                      f"{r.get('query', '')}\t{r.get('computed_at', '')}")
        return 0
    if args.cmd == "check":
        return _check(args, diagrams, theme)
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if args.relayout:
        from .engine.fix import fix_until_clean

        diagrams = [d if d.auto else fix_until_clean(d, theme)[0] for d in diagrams]
    written = api.render(diagrams, args.out, theme=theme, formats=formats, gallery=not args.no_gallery,
                         layout=args.layout, name_from=args.name_from)
    for p in written:
        print(p)
    return 0


def _fix(diagrams, theme) -> int:
    """``check --fix``: fixed YAML copies next to YAML specs, suggestions for Python specs."""
    import yaml

    from .engine.fix import fix_until_clean, suggest_python
    from .yaml_io import dump

    by_source: dict = {}
    for d in diagrams:
        by_source.setdefault(d.__dict__.get("_source"), []).append(d)
    remaining_p0 = 0
    for src, ds in by_source.items():
        results = [fix_until_clean(d, theme) for d in ds]
        applied = [i for _, a, _ in results for i in a]
        remaining = [i for _, _, r in results for i in r]
        remaining_p0 += sum(1 for i in remaining if i.severity == "P0")
        if src is not None and Path(src).suffix in (".yaml", ".yml"):
            if applied:
                docs = [dump(f) for f, _, _ in results]
                out = Path(src).with_name(Path(src).stem + ".fixed.yaml")
                out.write_text(yaml.safe_dump(docs if len(docs) > 1 else docs[0], sort_keys=False,
                                              allow_unicode=True, width=120), encoding="utf-8")
                print(f"{out}: {len(applied)} fix(es) applied")
        else:
            for line in suggest_python(applied):
                print(f"{src}: {line}" if src else line)
        for i in remaining:
            print(i)
    print(f"{len(diagrams)} diagram(s), {remaining_p0} P0 issue(s) left")
    return 1 if remaining_p0 else 0


def _check(args, diagrams, theme) -> int:
    from . import css, inspect_fmt

    if args.fix:
        return _fix(diagrams, theme)

    reports = [css.inspect(d, theme) for d in diagrams]
    selected = [css.select(d, args.select) if args.select else None for d in diagrams]
    if args.json:
        # SPEC_DEVIATION: CHK-03 asks for issues as JSON; --json already prints the style report, so the issues
        # join each diagram's report under "issues" instead of replacing it (keeps the report contract).
        scs = api.scenes(diagrams, theme, args.layout)
        for r, keys, sc in zip(reports, selected, scs):
            if keys is not None:
                r["elements"] = [e for e in r["elements"] if e["key"] in keys]
            r["issues"] = [i.to_dict() for i in qa.check(sc)]
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2, ensure_ascii=False))
        return 0
    color = inspect_fmt.use_color(args.color, sys.stdout)
    if args.styles:
        base = Path.cwd()
        for r, keys in zip(reports, selected):
            print(inspect_fmt.render(r, color=color, keys=keys, base=base, unused_selectors=False))
    issues = [i for sc in api.scenes(diagrams, theme, args.layout) for i in qa.check(sc)]
    for i in issues:
        print(i)
    for u in inspect_fmt.unused(reports):
        print(f"info: unused selector {u['selector']} ({u['origin']}:{u['line']})")
    print(f"{len(diagrams)} diagram(s), {len(issues)} issue(s)")
    return 1 if issues else 0


def _vectorize(args) -> int:
    from . import vectorize

    if not vectorize.available():
        print("needs the 'vector' extra: uv add 'spinagram[vector]'  (vtracer + resvg-py)", file=sys.stderr)
        return 2
    files = []
    for p in map(Path, args.paths):
        files += sorted(p.rglob("*.png")) if p.is_dir() else [p]
    ok = 0
    print(f"{'file':48} {'mean':>6} {'strong':>8}  result")
    for f in files:
        res = vectorize.vectorize_bytes(f.read_bytes())
        svg = res.svg
        if svg is None and args.force and res.score is not None:
            svg = vectorize.png_to_svg(f.read_bytes())[0]
        dst = (Path(args.out) / f.with_suffix(".svg").name) if args.out else f.with_suffix(".svg")
        if svg:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(svg, encoding="utf-8")
        sc = res.score
        state = "accepted" if res.accepted else ("forced" if svg else f"kept PNG ({res.reason})")
        print(f"{str(f)[-48:]:48} {sc.mean if sc else '-':>6} {sc.strong if sc else '-':>8}  {state}")
        ok += res.accepted
    print(f"{ok}/{len(files)} accepted (gate: mean ≤ {vectorize.MAX_MEAN}, strong ≤ {vectorize.MAX_STRONG:.0%})")
    return 0


def _skill_agents() -> list[str]:
    from .skills import AGENTS

    return list(AGENTS)


def _skills(args) -> int:
    from . import skills

    if args.scmd == "list":
        for s in skills.available().values():
            print(f"{s.name:16} {s.summary}")
        return 0
    if args.scmd == "show":
        print(skills.get(args.name).path.joinpath("SKILL.md").read_text(encoding="utf-8"), end="")
        return 0
    if args.scmd == "path":
        print(skills.get(args.name).path if args.name else skills.ROOT)
        return 0
    if args.dest and (args.agent or args.user):
        raise ValueError("--dest replaces --agent and --user; pass one or the other")
    dests = [Path(args.dest)] if args.dest else \
        list(dict.fromkeys(skills.target(a, args.user) for a in (args.agent or ["agents"])))
    try:
        for dest in dests:
            for out in skills.install(args.names, dest, link=args.link, force=args.force):
                print(f"{'linked' if args.link else 'installed'} {out}")
    except FileExistsError as exc:
        print(f"spinagram: {exc}", file=sys.stderr)
        return 1
    return 0


def _icons(args) -> int:
    import json

    from . import icons

    if args.icmd == "report":
        theme = Theme.load(args.theme)
        diagrams = [d for p in args.paths for d in load(p)]
        rows = 0
        for sc in api.scenes(diagrams, theme):
            for name, (ref, source) in sorted(sc.icon_sources.items()):
                print(f"{sc.id}\t{name}\t{ref or '-'}\t{source}")
                rows += 1
        print(f"{len(diagrams)} diagram(s), {rows} icon(s)")
        return 0
    packs = icons.registry()
    if args.icmd == "list":
        for p in packs.values():
            idx = p.dir / "index.json"
            n = len(json.loads(idx.read_text())["icons"]) if idx.exists() else None
            state = f"{n} icons" if n is not None else "not downloaded"
            print(f"{p.name:12} {p.version[:12]:12} {p.source.get('type', '?'):6} {p.origin:8} {state:16} {p.title}")
        print(f"cache: {icons.cache_root()}")
        return 0
    if args.icmd == "fetch":
        names = args.packs or list(packs)
        for n in names:
            if n not in packs:
                print(f"unknown pack {n!r}; known: {', '.join(packs)}", file=sys.stderr)
                return 2
            d = icons.fetch(packs[n], force=args.force)
            print(f"{n}: {len(json.loads((d / 'index.json').read_text())['icons'])} icons → {d}")
        return 0
    if args.icmd == "search":
        sel = [packs[n] for n in (args.pack or packs) if n in packs]
        hits = icons.search(args.query, sel)
        for pack, name, target in hits[: args.limit]:
            print(f"{pack}:{name}" + (f"  → {pack}:{target}" if target != name else ""))
        if not hits:
            print("no match (only downloaded packs are searched: spinagram icons fetch)")
        return 0 if hits else 1
    if args.icmd == "add":
        if args.zip:
            source = {"type": "zip", "url": args.zip}
        elif args.npm:
            pkg, _, ver = args.npm.rpartition("@") if args.npm.count("@") > (1 if args.npm.startswith("@") else 0) \
                else (args.npm, "", "latest")
            source = {"type": "npm", "package": pkg, "version": ver or "latest"}
            if args.registry:
                source["registry"] = args.registry
        elif args.github:
            repo, _, ref = args.github.partition("@")
            source = {"type": "github", "repo": repo, "ref": ref or "main"}
        else:
            source = {"type": "dir", "path": str(Path(args.dir).expanduser().resolve())}
        if args.include:
            source["include"] = args.include
        rules = [{"match": args.match, "name": args.name_template}] if args.match else None
        path = icons.register(args.name, source, rules=rules, strip=args.strip, title=args.title,
                              license=args.license, project=args.project)
        print(f"registered {args.name!r} in {path}")
        if not args.no_fetch:
            pack = icons.registry()[args.name]
            d = icons.fetch(pack, force=True)
            print(f"{args.name}: {len(json.loads((d / 'index.json').read_text())['icons'])} icons → {d}")
        return 0
    if args.icmd == "import":
        import yaml

        data = yaml.safe_load(Path(args.file).read_text(encoding="utf-8")) or {}
        for name, d in (data.get("packs", data) or {}).items():
            path = icons.register(name, d["source"], rules=d.get("rules"), strip=d.get("strip"),
                                  title=d.get("title", ""), license=d.get("license", ""), project=args.project)
            print(f"registered {name!r} in {path} (downloads on first use)")
        return 0
    if args.icmd == "remove":
        ok = icons.unregister(args.name, project=args.project)
        print("removed" if ok else f"{args.name!r} not found in the {'project' if args.project else 'user'} registry")
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


def _serve(args) -> int:
    try:
        from .ui.server import run
    except ImportError as exc:
        print(f"spinagram: serve needs the ui extra ({exc.name} missing): pip install 'spinagram[ui]'",
              file=sys.stderr)
        return 2
    return run(args.paths, theme=args.theme, layout=args.layout, port=args.port, open_browser=not args.no_open)


def _mcp(args) -> int:
    import ipaddress

    if args.mcmd == "install":
        return _mcp_install(args)

    try:
        from .mcp_server import server
    except ImportError:
        print("spinagram: mcp needs the mcp extra: pip install 'spinagram[mcp]'", file=sys.stderr)
        return 2
    from .mcp_server.tools import Tools

    formats = [f.strip() for f in args.formats.split(",") if f.strip()] if args.formats else None
    app = server.build(Tools(args.root, args.theme, args.layout, formats))
    if args.http is None:
        app.run()
        return 0
    try:
        loopback = args.host == "localhost" or ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        print(f"warning: no authentication on {args.host}:{args.http}", file=sys.stderr)
    app.run("streamable-http", host=args.host, port=args.http)
    return 0


def _mcp_install(args) -> int:
    from .mcp_server import install as ins

    known = ", ".join(ins.AGENTS)
    if not args.agent:
        raise ValueError(f"pass -a AGENT (known: {known})")
    for a in args.agent:
        ins.config_path(a)  # every agent checked before any file is written
    command = None if args.url else ins.launch(ins.server_args(args.theme, args.root, args.formats, args.layout),
                                               uvx=args.uvx)
    try:
        for a in dict.fromkeys(args.agent):
            path = ins.install(a, command=command, url=args.url, user=args.user, name=args.name, force=args.force)
            print(f"installed {args.name} in {path}")
    except FileExistsError as exc:
        print(f"spinagram: {exc}", file=sys.stderr)
        return 1
    return 0
