#!/usr/bin/env python3
"""docs_audit.py - read-only audit of a repo's README.md and AGENTS.md.

Prints three things:
  1. Inventory: the facts the docs should agree with (stack, package manager,
     runnable commands from package.json / Makefile / justfile / pyproject /
     Taskfile, CI commands, env vars from .env.example, version pins, existing
     agent instruction files and how they relate).
  2. Drift: claims in README*.md / AGENTS.md / CLAUDE.md that the repo
     contradicts - commands that do not exist, relative links and paths that
     are gone, env vars missing from the example file, length budgets.

Never writes anything. Stdlib only.

  3. Changes since each root doc was last committed, grouped by the kind of
     file that usually forces a doc edit (scripts, env, CI, CLI, schema).

Usage: docs_audit.py <repo-root> [--json]
"""

import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "out", "target",
             "vendor", ".venv", "venv", "__pycache__", ".turbo", ".cache",
             "coverage", ".handoffs", ".crew"}
AGENT_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
               ".cursorrules", ".windsurfrules"]
AGENTS_MD_SOFT_LIMIT = 150   # lines; past this, move detail out (progressive disclosure)
AGENTS_MD_HARD_LIMIT = 200   # Claude Code docs: keep CLAUDE.md under 200 lines
CODEX_MAX_BYTES = 32 * 1024  # Codex stops loading project docs past project_doc_max_bytes
TRIGGERS = [  # changed files that usually mean a doc must change
    ("manifest/scripts", re.compile(r"(^|/)(package\.json|pyproject\.toml|Cargo\.toml|go\.mod|composer\.json|Gemfile|Makefile|justfile|Taskfile\.ya?ml|pnpm-workspace\.yaml|turbo\.json)$")),
    ("env/config", re.compile(r"(^|/)(\.env\.(example|sample|template)|docker-compose\.ya?ml|compose\.ya?ml|Dockerfile|\.nvmrc|\.python-version|\.tool-versions)$|(^|/)(config|env)\.(ts|js|py)$")),
    ("ci", re.compile(r"^\.github/workflows/|^\.gitlab-ci\.yml$|^\.circleci/")),
    ("lint/format/test config", re.compile(r"(^|/)(eslint|biome|prettier|ruff|vitest|jest|playwright|tsconfig)[\w.-]*\.(json|js|cjs|mjs|ts|toml|ya?ml)$|(^|/)\.(eslintrc|prettierrc)")),
    ("cli/entry points", re.compile(r"(^|/)(bin|cli|cmd)/|^(src/)?(main|cli|index|__main__)\.(ts|js|mjs|py|go|rs)$")),
    ("migrations/schema", re.compile(r"(^|/)(migrations?|prisma|drizzle|schema)(/|\.)")),
]
README_SOFT_LIMIT = 500


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def git_files(root):
    """Tracked + untracked-not-ignored files, or a walk when not a git repo."""
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            return [f for f in out.stdout.splitlines() if f]
    except (OSError, subprocess.TimeoutExpired):
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            files.append(os.path.relpath(os.path.join(dirpath, f), root))
    return files


# ---------------------------------------------------------------- inventory

def package_manager(root):
    for lock, pm in [("pnpm-lock.yaml", "pnpm"), ("bun.lockb", "bun"), ("bun.lock", "bun"),
                     ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("uv.lock", "uv"),
                     ("poetry.lock", "poetry"), ("Pipfile.lock", "pipenv"), ("Cargo.lock", "cargo"),
                     ("go.sum", "go"), ("Gemfile.lock", "bundler"), ("composer.lock", "composer")]:
        if os.path.exists(os.path.join(root, lock)):
            return pm, lock
    pkg = read(os.path.join(root, "package.json"))
    if pkg:
        m = re.search(r'"packageManager"\s*:\s*"(\w+)@', pkg)
        if m:
            return m.group(1), "package.json#packageManager"
    return None, None


def commands(root, files):
    """Map of runnable entry points: {'npm': {...}, 'make': {...}, ...}."""
    found = {}
    for f in files:
        if os.path.basename(f) != "package.json" or "node_modules" in f:
            continue
        try:
            data = json.loads(read(os.path.join(root, f)) or "{}")
        except json.JSONDecodeError:
            continue
        scripts = data.get("scripts") or {}
        if scripts:
            found.setdefault("npm", {})[f] = sorted(scripts)
    mk = read(os.path.join(root, "Makefile"))
    if mk:
        targets = sorted(set(re.findall(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)", mk, re.M)) - {".PHONY"})
        found["make"] = {"Makefile": targets}
    jf = read(os.path.join(root, "justfile")) or read(os.path.join(root, "Justfile"))
    if jf:
        found["just"] = {"justfile": sorted(set(re.findall(r"^@?([A-Za-z0-9][\w-]*)[^\n:=]*:(?!=)", jf, re.M)))}
    tf = read(os.path.join(root, "Taskfile.yml")) or read(os.path.join(root, "Taskfile.yaml"))
    if tf:
        block = tf.split("tasks:", 1)[-1]
        found["task"] = {"Taskfile.yml": sorted(set(re.findall(r"^  ([\w:-]+):\s*$", block, re.M)))}
    py = read(os.path.join(root, "pyproject.toml"))
    if py:
        for section in ("project.scripts", "tool.poetry.scripts", "tool.pdm.scripts",
                        "tool.hatch.envs.default.scripts", "tool.poe.tasks"):
            m = re.search(r"^\[" + re.escape(section) + r"\]\s*\n(.*?)(?=^\[|\Z)", py, re.M | re.S)
            if m:
                names = re.findall(r"^([\w.-]+)\s*=", m.group(1), re.M)
                if names:
                    found.setdefault("python", {})[f"pyproject.toml [{section}]"] = sorted(names)
    comp = read(os.path.join(root, "composer.json"))
    if comp:
        try:
            s = json.loads(comp).get("scripts") or {}
            if s:
                found["composer"] = {"composer.json": sorted(s)}
        except json.JSONDecodeError:
            pass
    return found


CI_TOOLS = re.compile(r"^(?:pnpm|npm|npx|yarn|bun|bunx|make|just|task|uv|uvx|python3?|pytest|poetry|pip|go|cargo|"
                      r"deno|docker|bundle|rake|composer|php|mvn|gradle|\./gradlew|dotnet|turbo|nx|bash|sh|\./)\b")


def ci_commands(root, files):
    """Build/test commands from GitHub Actions `run:` steps. Block scalars are
    read by indentation (`>` folded into one line); only lines that start with
    a build tool are kept, so shell plumbing (if/fi/echo) stays out."""
    runs = []
    for f in files:
        if not (f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))):
            continue
        lines = (read(os.path.join(root, f)) or "").splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^(\s*)(?:-\s*)?run:\s*(.*)$", lines[i])
            i += 1
            if not m:
                continue
            indent, rest = len(m.group(1)), m.group(2).strip()
            if rest and rest[0] not in "|>":
                cmds = [rest]
            else:
                body = []
                while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                    body.append(lines[i].strip())
                    i += 1
                cmds = [" ".join(b for b in body if b)] if rest.startswith(">") else body
            for c in cmds:
                if c and CI_TOOLS.match(c):
                    runs.append((f, c[:160]))
    for name in (".gitlab-ci.yml", ".circleci/config.yml", "bitbucket-pipelines.yml"):
        if name in files:
            runs.append((name, "(CI config present - read it for the canonical commands)"))
    return runs


def env_vars(root, files):
    names, sources = set(), []
    for f in files:
        base = os.path.basename(f)
        if base in (".env.example", ".env.sample", ".env.template", ".env.dist", "example.env"):
            sources.append(f)
            for line in (read(os.path.join(root, f)) or "").splitlines():
                m = re.match(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", line)
                if m:
                    names.add(m.group(1))
    return sorted(names), sources


def version_pins(root):
    pins = {}
    for f in (".nvmrc", ".node-version", ".python-version", ".ruby-version", ".tool-versions",
              "rust-toolchain", "rust-toolchain.toml", ".go-version"):
        t = read(os.path.join(root, f))
        if t:
            pins[f] = " ".join(t.split())[:80]
    pkg = read(os.path.join(root, "package.json"))
    if pkg:
        try:
            eng = json.loads(pkg).get("engines")
            if eng:
                pins["package.json#engines"] = json.dumps(eng)
        except json.JSONDecodeError:
            pass
    py = read(os.path.join(root, "pyproject.toml"))
    if py:
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', py)
        if m:
            pins["pyproject requires-python"] = m.group(1)
    gm = read(os.path.join(root, "go.mod"))
    if gm:
        m = re.search(r"^go\s+(\S+)", gm, re.M)
        if m:
            pins["go.mod go"] = m.group(1)
    return pins


def agent_files(root, files):
    """Every agent-instruction file in the tree, with symlink / import info."""
    out = []
    names = {os.path.basename(a) for a in AGENT_FILES}
    for f in sorted(files):
        if vendored(f) and not f.startswith((".github/", ".cursor/rules/")):
            continue
        if os.path.basename(f) in names or f in AGENT_FILES or (
                f.startswith(".cursor/rules/") or f.startswith(".github/instructions/")):
            p = os.path.join(root, f)
            info = {"path": f}
            if os.path.islink(p):
                info["symlink_to"] = os.readlink(p)
            text = read(p) or ""
            info["lines"] = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            imports = re.findall(r"^@(\S+)", text, re.M)
            if imports:
                info["imports"] = imports
            out.append(info)
    return out


def stack(root, files):
    marks = []
    top = set(files)
    for f, label in [("package.json", "node"), ("tsconfig.json", "typescript"), ("pyproject.toml", "python"),
                     ("requirements.txt", "python"), ("go.mod", "go"), ("Cargo.toml", "rust"),
                     ("Gemfile", "ruby"), ("composer.json", "php"), ("pom.xml", "java/maven"),
                     ("build.gradle", "jvm/gradle"), ("build.gradle.kts", "jvm/gradle"),
                     ("pubspec.yaml", "dart/flutter"), ("Package.swift", "swift"),
                     ("Dockerfile", "docker"), ("docker-compose.yml", "docker-compose"),
                     ("compose.yaml", "docker-compose"), ("pnpm-workspace.yaml", "monorepo:pnpm"),
                     ("turbo.json", "monorepo:turbo"), ("nx.json", "monorepo:nx"),
                     ("lerna.json", "monorepo:lerna"), ("go.work", "monorepo:go-work")]:
        if f in top and label not in marks:
            marks.append(label)
    pkg = read(os.path.join(root, "package.json"))
    if pkg and '"workspaces"' in pkg and "monorepo:workspaces" not in marks:
        marks.append("monorepo:workspaces")
    if any(f.endswith(".csproj") for f in files):
        marks.append("dotnet")
    return marks


def vendored(path):
    """Docs that ship with installed tools, not with the project: anything under
    a hidden folder (.agents/skills, .claude/skills...) or a vendor folder."""
    parts = path.split("/")[:-1]
    return any(p.startswith(".") or p in SKIP_DIRS or p in ("third_party", "third-party", "external")
               for p in parts)


def doc_files(files):
    wanted = ("README", "CONTRIBUTING", "CHANGELOG", "SECURITY", "CODE_OF_CONDUCT", "LICENSE",
              "ARCHITECTURE", "DEVELOPMENT")
    return sorted(f for f in files if os.path.basename(f).upper().startswith(wanted)
                  and os.path.splitext(f)[1].lower() in ("", ".md", ".txt", ".rst")
                  and not vendored(f))[:60]


# -------------------------------------------------------------------- drift

CODE_SPAN = re.compile(r"```[^\n]*\n(.*?)```|`([^`\n]+)`", re.S)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PATHLIKE = re.compile(r"^(?:\./)?(?:[\w@.-]+/)+[\w@.-]*$|^[\w-]+\.(?:md|json|ya?ml|toml|py|ts|tsx|js|mjs|sh|go|rs)$")


def code_lines(text):
    for m in CODE_SPAN.finditer(text):
        block = m.group(1) if m.group(1) is not None else m.group(2)
        for line in block.splitlines():
            line = line.strip().lstrip("$> ").strip()
            if line and not line.startswith("#"):
                yield line


def check_commands(doc, text, cmds, pm):
    issues = []
    npm_scripts = set()
    for scripts in cmds.get("npm", {}).values():
        npm_scripts.update(scripts)
    builtin = {"install", "i", "ci", "add", "remove", "exec", "dlx", "create", "init", "publish",
               "link", "update", "upgrade", "audit", "outdated", "why", "list", "ls", "x", "pack",
               "version", "login", "config", "cache", "rebuild", "prune", "dedupe", "help", "env",
               "global", "store", "import", "fetch", "patch", "setup", "self-update", "info", "view"}
    implicit = {"start", "test", "stop", "restart"}  # `npm start`/`npm test` without `run`
    make_t = set(sum(cmds.get("make", {}).values(), []))
    just_t = set(sum(cmds.get("just", {}).values(), []))
    task_t = set(sum(cmds.get("task", {}).values(), []))
    used_pms = set()
    for line in code_lines(text):
        for seg in re.split(r"&&|\|\||;|\|", line):
            words = seg.strip().split()
            if not words:
                continue
            tool = words[0]
            if tool in ("npm", "pnpm", "yarn", "bun"):
                used_pms.add(tool)
                if npm_scripts and len(words) > 1:
                    if words[1] == "run" and len(words) > 2:
                        name = words[2]
                    elif words[1] in builtin or words[1].startswith("-"):
                        continue
                    elif tool == "npm" and words[1] not in implicit:
                        continue
                    else:
                        name = words[1]
                    if name not in npm_scripts and not name.startswith("-"):
                        issues.append(f"{doc}: `{seg.strip()}` - no script '{name}' in any package.json")
            elif tool == "make" and make_t and len(words) > 1 and not words[1].startswith("-"):
                if words[1] not in make_t and "=" not in words[1]:
                    issues.append(f"{doc}: `{seg.strip()}` - no target '{words[1]}' in Makefile")
            elif tool == "just" and just_t and len(words) > 1 and not words[1].startswith("-"):
                if words[1] not in just_t:
                    issues.append(f"{doc}: `{seg.strip()}` - no recipe '{words[1]}' in justfile")
            elif tool == "task" and task_t and len(words) > 1 and not words[1].startswith("-"):
                if words[1] not in task_t:
                    issues.append(f"{doc}: `{seg.strip()}` - no task '{words[1]}' in Taskfile")
    if pm in ("npm", "pnpm", "yarn", "bun"):
        other = sorted(used_pms - {pm, "npm" if pm != "npm" else ""} - {""})
        if other:
            issues.append(f"{doc}: uses {', '.join(other)} but the lockfile says {pm}")
        if pm != "npm" and "npm" in used_pms and re.search(r"\bnpm (?:install|i|ci|run)\b", text):
            issues.append(f"{doc}: tells readers to use npm but the lockfile says {pm}")
    return issues


def ignored(root, rel):
    """True when git ignores the path: local files like .env or build output."""
    try:
        return subprocess.run(["git", "-C", root, "check-ignore", "-q", rel],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_links(root, doc, text, files_set, dirs_set):
    issues = []
    base = os.path.dirname(doc)
    prose = CODE_SPAN.sub("", text)  # links inside code samples are examples
    for target in LINK.findall(prose):
        if re.match(r"^(?:[a-z]+:|#|//)", target):
            continue
        path = target.split("#", 1)[0].split("?", 1)[0]
        if not path:
            continue
        rel = os.path.normpath(os.path.join(base, path)) if not path.startswith("/") else path.lstrip("/")
        if rel.startswith(".."):
            continue  # leaves the repo: GitHub web routes like ../../releases
        if rel not in files_set and rel not in dirs_set and not os.path.exists(os.path.join(root, rel)):
            issues.append(f"{doc}: broken link -> {target}")
    # Only paths that claim to be inside this repo: their first segment exists
    # here and they name a file. Generic folders (`.claude/skills/`) are skipped.
    top = {p.split("/", 1)[0] for p in files_set | dirs_set}
    for line in code_lines(text):
        for tok in line.split():
            tok = tok.strip("'\"(),:;`")
            if (not PATHLIKE.match(tok) or tok.endswith("/") or "/" not in tok
                    or tok.startswith(("http", "~", "/", "<", "$")) or re.search(r"[*<>{}]|\.\.\.", tok)):
                continue
            rel = os.path.normpath(os.path.join(base, tok))
            rel_root = os.path.normpath(tok)
            first = rel_root.split("/", 1)[0]
            if tok.startswith("@") or (first not in top and os.path.normpath(os.path.join(base, first)) not in dirs_set | files_set):
                continue
            if not any(p in files_set or p in dirs_set or os.path.exists(os.path.join(root, p))
                       for p in (rel, rel_root)) and not ignored(root, rel_root):
                issues.append(f"{doc}: mentions `{tok}`, not found in the repo (renamed, deleted, or generated?)")
    return sorted(set(issues))


ENV_FORMS = re.compile(
    r"(?:^|[\s`'\"])([A-Z][A-Z0-9_]{2,})=|\$\{?([A-Z][A-Z0-9_]{2,})\b|"
    r"(?:process\.env|import\.meta\.env|os\.environ|Deno\.env|env)(?:\.|\[[\"']|\.get\([\"'])([A-Z][A-Z0-9_]{2,})")
ENV_LINE = re.compile(r"\.env\b|environment|env var|variáve(?:l|is) de ambiente|variable de entorno", re.I)


def check_env(doc, text, env_names, env_sources):
    """Env vars the doc names as env vars (NAME=, $NAME, process.env.NAME, or
    an UPPER_SNAKE name on a line that talks about .env) but the example file
    lacks. Plain constants in prose are left alone."""
    if not env_sources:
        return []
    mentioned = set()
    for m in ENV_FORMS.finditer(text):
        mentioned.add(next(g for g in m.groups() if g))
    for line in text.splitlines():
        if ENV_LINE.search(line):
            mentioned.update(re.findall(r"`([A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9])`", line))  # not a prefix like NEXT_PUBLIC_
    skip = ("GITHUB_", "CI_", "NODE_", "npm_", "RUNNER_", "HOME", "PATH", "PWD", "USER", "SHELL")
    missing = sorted(n for n in mentioned - set(env_names) if not n.startswith(skip))
    issues = [f"{doc}: names env var {n}, not in {', '.join(env_sources)} (stale, or missing from the example file)"
              for n in missing[:15]]
    # The other direction, only for a doc that documents configuration at all.
    if mentioned & set(env_names) and os.path.basename(doc) == "README.md":
        undocumented = [n for n in env_names if n not in text]
        if undocumented:
            issues.append(f"{doc}: documents env vars but not {', '.join(undocumented[:20])} from {', '.join(env_sources)} "
                          "(fine if it lists only the main ones and links the example file)")
    return issues


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=30)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def changes_since(root, doc):
    """Commits and trigger-matching files changed since `doc` was last committed."""
    last = git(root, "log", "-1", "--format=%h %cs", "--", doc).strip()
    if not last:
        return None
    sha = last.split()[0]
    count = git(root, "rev-list", "--count", f"{sha}..HEAD").strip() or "0"
    changed = [f for f in git(root, "diff", "--name-only", f"{sha}..HEAD").splitlines() if f and f != doc]
    dirty = [l[3:] for l in git(root, "status", "--porcelain").splitlines() if l[3:] and l[3:] != doc]
    hits = {}
    for f in sorted(set(changed + dirty)):
        for label, rx in TRIGGERS:
            if rx.search(f):
                hits.setdefault(label, []).append(f)
                break
    return {"doc": doc, "last_commit": last, "commits_since": int(count),
            "files_changed": len(set(changed)), "uncommitted": len(dirty), "triggers": hits}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        sys.exit(2)
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    files = git_files(root)
    files_set = set(os.path.normpath(f) for f in files)
    dirs_set = set()
    for f in files_set:
        d = os.path.dirname(f)
        while d and d not in dirs_set:
            dirs_set.add(d)
            d = os.path.dirname(d)

    pm, lock = package_manager(root)
    cmds = commands(root, files)
    env_names, env_sources = env_vars(root, files)
    agents = agent_files(root, files)
    inv = {
        "root": root,
        "stack": stack(root, files),
        "package_manager": {"name": pm, "from": lock},
        "commands": cmds,
        "ci_commands": ci_commands(root, files)[:40],
        "env_example": {"files": env_sources, "vars": env_names},
        "version_pins": version_pins(root),
        "agent_files": agents,
        "doc_files": doc_files(files),
        "file_count": len(files),
    }

    drift = []
    targets = sorted(f for f in files if os.path.basename(f) in ("README.md", "AGENTS.md", "CLAUDE.md")
                     and not vendored(f))
    for doc in targets:
        text = read(os.path.join(root, doc)) or ""
        drift += check_commands(doc, text, cmds, pm)
        drift += check_links(root, doc, text, files_set, dirs_set)
        drift += check_env(doc, text, env_names, env_sources)
        n = text.count("\n") + 1
        base = os.path.basename(doc)
        if base in ("AGENTS.md", "CLAUDE.md"):
            if n > AGENTS_MD_HARD_LIMIT:
                drift.append(f"{doc}: {n} lines - far past budget ({AGENTS_MD_SOFT_LIMIT}); split by directory or move detail to linked docs")
            elif n > AGENTS_MD_SOFT_LIMIT:
                drift.append(f"{doc}: {n} lines - over the ~{AGENTS_MD_SOFT_LIMIT}-line budget")
            if len(text.encode()) > CODEX_MAX_BYTES:
                drift.append(f"{doc}: {len(text.encode()) // 1024} KiB - Codex stops reading at 32 KiB")
            if re.search(r"[├└]──", text):
                drift.append(f"{doc}: has a directory tree - agents read the tree themselves; overviews cost tokens without helping (ETH 2026)")
        elif n > README_SOFT_LIMIT:
            drift.append(f"{doc}: {n} lines - consider moving reference material to docs/")

    # AGENTS.md / CLAUDE.md relationship at each directory level.
    by_dir = {}
    for a in agents:
        by_dir.setdefault(os.path.dirname(a["path"]), {})[os.path.basename(a["path"])] = a
    for d, group in sorted(by_dir.items()):
        where = d or "."
        ag, cl = group.get("AGENTS.md"), group.get("CLAUDE.md")
        if cl and not ag:
            drift.append(f"{where}: CLAUDE.md without AGENTS.md - other agents (Codex, Cursor, Copilot, Gemini...) will not read it")
        if cl and ag and not cl.get("symlink_to") and "AGENTS.md" not in " ".join(cl.get("imports", [])) \
                and re.search(r"AGENTS\.md", read(os.path.join(root, cl["path"])) or "") and cl["lines"] < 15:
            drift.append(f"{where}: CLAUDE.md only points to AGENTS.md in prose - use an `@AGENTS.md` import line so it is loaded, not just mentioned")
        elif ag and cl and not cl.get("symlink_to") and "AGENTS.md" not in " ".join(cl.get("imports", [])):
            drift.append(f"{where}: AGENTS.md and CLAUDE.md are separate copies - they will diverge; make CLAUDE.md import (@AGENTS.md) or symlink it")
    local = os.path.join(root, "CLAUDE.local.md")
    root_cl = by_dir.get("", {}).get("CLAUDE.md")
    if os.path.exists(local) and by_dir.get("", {}).get("AGENTS.md") and not (
            root_cl and (root_cl.get("symlink_to") or "AGENTS.md" in " ".join(root_cl.get("imports", [])))):
        drift.append(".: CLAUDE.local.md exists and nothing imports AGENTS.md - Claude Code then skips AGENTS.md; add a CLAUDE.md with `@AGENTS.md`")
    if not any(a["path"] == "AGENTS.md" for a in agents):
        drift.append(".: no root AGENTS.md")
    if "README.md" not in files_set and not any(f.lower() == "readme.md" for f in files_set):
        drift.append(".: no root README.md")

    since = [c for c in (changes_since(root, d) for d in targets if not d.count("/")) if c]

    if as_json:
        print(json.dumps({"inventory": inv, "drift": drift, "changes_since_docs": since}, indent=2))
        return

    print("== Inventory ==")
    print(f"root: {root}  ({len(files)} files)")
    print(f"stack: {', '.join(inv['stack']) or '(not detected)'}")
    print(f"package manager: {pm or '(none)'}" + (f"  [{lock}]" if lock else ""))
    for kind, sources in cmds.items():
        for src, names in sources.items():
            shown = ", ".join(names[:30]) + (" ..." if len(names) > 30 else "")
            print(f"{kind} ({src}): {shown}")
    if inv["ci_commands"]:
        print("ci run steps:")
        for f, line in inv["ci_commands"]:
            print(f"  {f}: {line}")
    if env_sources:
        print(f"env example ({', '.join(env_sources)}): {', '.join(env_names) or '(empty)'}")
    for k, v in inv["version_pins"].items():
        print(f"pin {k}: {v}")
    print("agent files:" if agents else "agent files: (none)")
    for a in agents:
        extra = []
        if "symlink_to" in a:
            extra.append(f"symlink -> {a['symlink_to']}")
        if "imports" in a:
            extra.append(f"imports {', '.join(a['imports'])}")
        print(f"  {a['path']} ({a['lines']} lines){'  ' + '; '.join(extra) if extra else ''}")
    print(f"docs: {', '.join(inv['doc_files']) or '(none)'}")

    if since:
        print("\n== Changed since each doc was last committed ==")
        for c in since:
            print(f"{c['doc']}: last {c['last_commit']}; {c['commits_since']} commits, "
                  f"{c['files_changed']} files changed since, {c['uncommitted']} uncommitted")
            for label, fs in c["triggers"].items():
                shown = ", ".join(fs[:8]) + (f" (+{len(fs) - 8})" if len(fs) > 8 else "")
                print(f"  {label}: {shown}")

    print("\n== Drift ==")
    if not drift:
        print("(nothing detected - still read the docs against the code; this only catches mechanical drift)")
    for d in drift:
        print(f"- {d}")


if __name__ == "__main__":
    main()
