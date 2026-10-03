---
name: mac-cleanup
description: Analyze and safely free up disk space on macOS. Measures what is using storage (~/Library, Caches, Containers, Group Containers, Application Support, Photos, iCloud Drive, WhatsApp, Homebrew, node_modules, Xcode, Docker, /Library, /usr/local, Applications), cleans only caches that rebuild themselves, finds leftovers of uninstalled apps, and guides the removals that need the user's judgment. Use this whenever the user says their Mac is full or low on storage, asks what they can delete, wants to free space or clear caches, asks why a folder or app is so big, or an uninstaller failed and left files behind, even if they never say "cleanup" (e.g. "meu mac está sem espaço", "o que posso apagar?", "why is ~/Library 60 GB?").
license: MIT
compatibility: macOS 13 or later. Uses the stock bash 3.2, du, df, mdfind, plutil and codesign; optionally brew, npm, pnpm, pip, jq and sqlite3 when present.
metadata:
  author: julianosirtori
  version: "1.0.0"
---

# Mac Cleanup

Free disk space on a Mac without losing anything the user cares about.

Most of a full disk is usually a handful of things: app media (WhatsApp, Photos),
local copies of cloud files (iCloud Drive), developer caches, and leftovers of
apps that were dragged to the Trash. The work is to measure, explain each item
in plain language, clean what is truly disposable, and let the user decide the
rest. Being wrong is expensive here — a deleted photo or a corrupted library
does not come back — so precision beats speed.

Reply in the user's language and explain technical names briefly (many people
asking for this are not developers).

## Three tiers

Classify every finding before suggesting anything:

| Tier | What | How to act |
|---|---|---|
| **A. Regenerable** | Caches and build artifacts that tools recreate on demand (npm/pnpm/pip/Homebrew caches, Xcode DerivedData, `CachedExtensionVSIXs`, obsolete editor extensions, browser caches, updater download caches) | Show the list with sizes, ask once, then clean with `scripts/safe-clean.sh --apply`. |
| **B. User's call** | Documents, downloads, media, chats, apps, projects, `node_modules`, Homebrew formulae, browser profiles | Explain size and consequence. Act only on what the user picks. Prefer the Trash; uninstall apps the proper way (see `references/uninstall.md`). |
| **C. Do not touch** | Inside `*.photoslibrary`, `~/Library/Biome`, `~/Library/Caches/CloudKit`, `com.apple.*` containers, the sealed system volume (`/System`, `/usr` except `/usr/local`), `/Library/Developer/CommandLineTools`, `/Library/Updates` | Explain why it is off-limits and the supported alternative, if any. |

`references/locations.md` says which tier each common location belongs to and the
right way to shrink it. Read the relevant section before advising on a location
you have not verified in this session.

## Ground rules, and why

- **Measure first.** Never estimate sizes or guess what a folder is. Folder names
  mislead: `~/Library/Biome` is macOS Siri/Spotlight data, not the Biome JS linter.
- **Reversible by default.** Anything that is not a cache goes to the Trash
  (`/usr/bin/trash <path>` on macOS 14+, or Finder via `osascript`), so the user
  can "Put Back". Do not `rm -rf` user data. Emptying the Trash is the user's call;
  remind them that space is only freed afterwards.
- **No passwords.** Never try to obtain or pipe an admin password. When a step
  needs root, give the exact command for the user to run themselves (in Claude
  Code, prefixed with `!`, e.g. `! sudo rm -rf "/Library/Application Support/Foo"`).
  Tell them what success looks like — `pkgutil --forget` prints "Forgot package …",
  which people often read as an error.
- **Quit before cleaning an app's cache.** Check with `pgrep -x "<App Name>"`;
  deleting Chrome's, Xcode's or an Electron app's cache while it runs can break it.
- **Shared Macs.** Browser profiles, Photos libraries and home-folder data may
  belong to someone else. Name whose data it appears to be and leave it alone
  unless the user confirms.
- **Respect a permission denial.** If a deletion is blocked by the tool's
  permission system, do not retry it another way: show the user the exact command
  so they can run it, or ask them to adjust permissions.
- **Don't edit a script while it runs.** Bash reads scripts incrementally; copy a
  script before modifying it if a run is in progress.

## Workflow

### 1. Baseline

Run the read-only scan from this skill's directory (it takes 1–4 minutes; run it
in the background if you can):

```bash
bash <skill-dir>/scripts/scan.sh
```

It prints free space, the Trash, the biggest folders in the home folder,
`~/Library` and its main subfolders, `/Applications`, `/Library`, a list of known
hotspots, Downloads candidates (old items, already-extracted archives, installers),
`node_modules` with days since last install, the largest Homebrew formulae and
what depends on them, and **what changed since the previous scan** (history in
`~/.local/state/mac-cleanup/`). Use `--min-mb N` to see smaller items.

If many folders read as 0 or "Operation not permitted", the terminal lacks Full
Disk Access: System Settings → Privacy & Security → Full Disk Access.

### 2. Explain where the space goes

Summarize in a table, biggest first: item, size, what it is in plain words, tier,
recommendation. Lead with the two or three items that matter most; a 40 KB
cache is noise.

To drill into a folder the scan did not break down:

```bash
du -skx "<dir>"/* "<dir>"/.[!.]* 2>/dev/null | sort -rn | head -20
```

In zsh, an unmatched glob aborts the whole command (`no matches found`); run
such loops in bash or with `setopt NULL_GLOB`.

### 3. Quick wins (tier A)

```bash
bash <skill-dir>/scripts/safe-clean.sh          # dry run: what would be freed
bash <skill-dir>/scripts/safe-clean.sh --apply  # after the user agrees
```

`--list` shows the targets; `--only a,b` / `--skip a,b` select them. It skips
browser and Xcode caches while those apps are open — ask the user to quit them
(Cmd+Q) and run it again if worthwhile.

### 4. Leftovers of removed apps

```bash
bash <skill-dir>/scripts/leftovers.sh
```

Read-only. Finds containers and group containers with no installed app, large
Application Support folders that match no app, launch agents/daemons whose program
is gone (they keep failing in the background), broken command-line links,
unreferenced Logi Options+ update depots, and Adobe products still registered after
their files were deleted. These are candidates: confirm each one (bundle id, path,
`ls`, contents) before proposing removal, and follow `references/uninstall.md`.

### 5. Guided decisions (tier B)

For each large personal item, give the options with their trade-offs and let the
user choose. The playbooks for the usual suspects — WhatsApp, Photos, iCloud Drive,
Chrome profiles and extensions, Downloads, `node_modules`, Xcode, Docker, Homebrew —
are in `references/locations.md`. The two that cause the most confusion:

- **WhatsApp**: media lives in its group container. Deleting files there by hand
  leaves broken media in the Mac app but does not affect the phone. The cleanest
  options are Settings → Storage → Manage storage, or logging the Mac out and back
  in. Media that exists only on the Mac would be lost — ask before.
- **Photos**: never touch the library's internals. With "Optimize Mac Storage" on,
  previews still need roughly 100–150 KB per item. An oversized search index can be
  rebuilt with the Photos repair tool (hold Option+Command while opening Photos).

### 6. Uninstalling apps

Use the vendor's uninstaller when there is one, then sweep leftovers. When an
uninstaller fails ("not installed", "other apps depend on it"), investigate the
cause instead of forcing it — typically a stale registry entry left by an app
that was dragged to the Trash. `references/uninstall.md` has the procedure and
vendor notes (Adobe, Logitech, Microsoft, Homebrew, Java-based apps).

### 7. Verify and report

Re-measure (`df -h /System/Volumes/Data`) and close with:

- free space before → after, and what is waiting in the Trash;
- what was cleaned, moved to the Trash, or uninstalled;
- anything pending on the user (a `sudo` command, quitting an app, an in-app step);
- the next best opportunities, if any.

## Automation

If the user wants this to happen on its own, the tier A cleanup can run monthly
via `launchd`; `references/automation.md` has a ready LaunchAgent. Only tier A
belongs in an unattended job — everything else needs a person.
