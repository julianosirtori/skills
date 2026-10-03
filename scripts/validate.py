#!/usr/bin/env python3
"""Validate every skill in skills/ against the Agent Skills spec
(https://agentskills.io/specification) and keep the Claude Code marketplace
manifest in sync with the skills on disk.

Usage: python3 scripts/validate.py
Exits non-zero on any error. No third-party dependencies.
"""

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
MARKETPLACE = os.path.join(ROOT, ".claude-plugin", "marketplace.json")

ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_SKILL_LINES = 500

errors = []
warnings = []


def error(msg):
    errors.append(msg)


def parse_frontmatter(text):
    """Minimal YAML frontmatter reader: top-level keys with inline, folded,
    quoted or nested (indented) values. Enough for SKILL.md headers."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    fields, key = {}, None
    for line in text[4:end].splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            fields[key] = "" if value in (">", "|", ">-", "|-") else value.strip("\"'")
        elif key and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def check_skill(name):
    path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    where = f"skills/{name}"
    if not os.path.isfile(path):
        error(f"{where}: missing SKILL.md")
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fm = parse_frontmatter(text)
    if fm is None:
        error(f"{where}: SKILL.md must start with YAML frontmatter between '---' lines")
        return

    unknown = set(fm) - ALLOWED_KEYS
    if unknown:
        error(f"{where}: unsupported frontmatter keys {sorted(unknown)} (claude.ai uploads reject them)")

    skill_name = fm.get("name", "")
    if not skill_name:
        error(f"{where}: 'name' is required")
    elif skill_name != name:
        error(f"{where}: name '{skill_name}' must match the folder name")
    elif len(skill_name) > 64 or not NAME_RE.match(skill_name):
        error(f"{where}: name must be 1-64 chars of a-z, 0-9 and single hyphens")

    desc = fm.get("description", "")
    if not desc:
        error(f"{where}: 'description' is required")
    elif len(desc) > 1024:
        error(f"{where}: description is {len(desc)} chars (max 1024)")

    if len(fm.get("compatibility", "")) > 500:
        error(f"{where}: compatibility is longer than 500 chars")
    if "license" not in fm:
        warnings.append(f"{where}: no 'license' field")

    lines = text.count("\n") + 1
    if lines > MAX_SKILL_LINES:
        error(f"{where}: SKILL.md has {lines} lines (keep it under {MAX_SKILL_LINES}; move detail to references/)")

    # Files mentioned as scripts/... or references/... must exist.
    for ref in sorted(set(re.findall(r"\b((?:scripts|references|assets)/[\w./-]+\.\w+)", text))):
        if not os.path.exists(os.path.join(SKILLS_DIR, name, ref)):
            error(f"{where}: SKILL.md mentions {ref}, which does not exist")

    scripts = os.path.join(SKILLS_DIR, name, "scripts")
    if os.path.isdir(scripts):
        for f in sorted(os.listdir(scripts)):
            p = os.path.join(scripts, f)
            if f.endswith((".sh", ".py")) and not os.access(p, os.X_OK):
                error(f"{where}/scripts/{f}: not executable (chmod +x)")


def check_marketplace(skill_names):
    try:
        with open(MARKETPLACE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        error(f".claude-plugin/marketplace.json: {exc}")
        return
    listed = set()
    for plugin in data.get("plugins", []):
        for s in plugin.get("skills", []):
            listed.add(os.path.basename(os.path.normpath(s)))
            if not os.path.isfile(os.path.join(ROOT, s, "SKILL.md")):
                error(f"marketplace.json: plugin '{plugin.get('name')}' points to missing skill {s}")
    for name in sorted(set(skill_names) - listed):
        error(f"marketplace.json: skills/{name} is not listed in any plugin")


def shellcheck():
    if not shutil.which("shellcheck"):
        warnings.append("shellcheck not installed; shell scripts were not linted")
        return
    scripts = []
    for dirpath, _, files in os.walk(SKILLS_DIR):
        scripts += [os.path.join(dirpath, f) for f in files if f.endswith(".sh")]
    if scripts:
        result = subprocess.run(["shellcheck", "-S", "warning", *sorted(scripts)], capture_output=True, text=True)
        if result.returncode != 0:
            error("shellcheck:\n" + result.stdout.strip())


def main():
    names = sorted(d for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d)) and not d.startswith("."))
    for name in names:
        check_skill(name)
    check_marketplace(names)
    shellcheck()

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(names)} skill(s) checked, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
