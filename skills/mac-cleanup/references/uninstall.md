# Uninstalling apps completely

Dragging an app to the Trash removes the bundle but usually leaves data, launch
agents, package receipts and — for suites like Adobe's — registry entries that
later block the vendor's uninstaller. This is the procedure that avoids that.

## Contents

1. [General procedure](#general-procedure)
2. [When the uninstaller fails](#when-the-uninstaller-fails)
3. [Vendor notes](#vendor-notes): Adobe, Logitech, Microsoft, Homebrew, Java-based apps, App Store apps

## General procedure

1. **Confirm it is unused and not needed by something else.** Ask the user; for
   CLIs check `brew uses --installed <formula>`; for frameworks check what links
   to them.
2. **Use the vendor's uninstaller** if one exists: inside the app's folder in
   `/Applications`, in `/Applications/Utilities`, or in the app's own menu. These
   remove helpers, drivers and launch daemons that dragging misses.
3. **Otherwise move the bundle to the Trash** (`/usr/bin/trash /Applications/Foo.app`
   or Finder). Root-owned bundles make Finder ask for the password, which is fine.
4. **Sweep leftovers** (`scripts/leftovers.sh` finds most of them), matching by
   bundle id (`defaults read /Applications/Foo.app/Contents/Info.plist CFBundleIdentifier`)
   and by name:
   - `~/Library/Application Support/<App>` and `/Library/Application Support/<App>`
   - `~/Library/Containers/<bundle-id>*`, `~/Library/Group Containers/*<id or team>*`
   - `~/Library/Caches/<bundle-id>*`, `~/Library/HTTPStorages/<bundle-id>*`, `~/Library/WebKit/<bundle-id>`
   - `~/Library/Preferences/<bundle-id>*.plist`, `~/Library/Saved Application State/<bundle-id>.savedState`
   - `~/Library/Logs/<App>`
   - Launch agents/daemons: `~/Library/LaunchAgents`, `/Library/LaunchAgents`, `/Library/LaunchDaemons`
   - Privileged helpers: `/Library/PrivilegedHelperTools/<bundle-id>*`
   - Package receipts: `pkgutil --pkgs | grep -i <vendor>`
   Move user-owned items to the Trash; show their size before and after.
5. **Stop orphaned background services before deleting their plists.**
   - User agent: `launchctl bootout gui/$(id -u)/<label>` (no sudo needed, even for
     agents in `/Library/LaunchAgents`).
   - System daemon: `sudo launchctl bootout system/<label>` (the user runs it).
   - A service whose program is missing keeps relaunching and failing
     (`launchctl print gui/$(id -u)/<label>` shows `last exit code = 78: EX_CONFIG`).
6. **Root-owned leftovers**: hand the user a single command, e.g.
   `! sudo rm -rf "/Library/Application Support/Foo" /Library/LaunchDaemons/com.foo.helper.plist && sudo pkgutil --forget com.foo.pkg`
   and tell them `Forgot package 'com.foo.pkg' on '/'` means success.
7. **Verify**: re-run `leftovers.sh` or `ls` the paths, and re-measure free space.

## When the uninstaller fails

Typical messages and causes:

| Symptom | Likely cause | What to do |
|---|---|---|
| "Not installed" / "can't find the application" | The app bundle was already deleted; the uninstaller looks for it. | Remove the leftovers by hand (procedure above). |
| "Other programs still depend on it" | The vendor's registry still lists products whose files are gone. | Find the registry, deregister those products with the vendor's own tool, then retry. |
| Window opens and closes instantly, nothing happens | The launcher hands off to another process and exits. | Check `pgrep -fl -i <vendor>` and wait for the real worker to finish before judging. |
| Uninstall crashes midway | Vendor app crashed (look for a crash reporter process). | Retry through the vendor's CLI if it has one. |

Never force-remove a suite's shared frameworks while its registry still lists
products; it makes later reinstalls and uninstalls harder.

## Vendor notes

### Adobe (Creative Cloud, Acrobat, Illustrator, Lightroom...)

- The Creative Cloud uninstaller is
  `/Applications/Utilities/Adobe Creative Cloud/Utils/Creative Cloud Uninstaller.app`.
  It refuses while any product is registered.
- Registry: `/Library/Application Support/Adobe/caps/hdpim.db` (SQLite). List
  registered products and where they were installed:
  ```bash
  sqlite3 -readonly "/Library/Application Support/Adobe/caps/hdpim.db" \
    "SELECT SAPCode, ProductVersion FROM product_installation_info;"
  sqlite3 -readonly "/Library/Application Support/Adobe/caps/hdpim.db" \
    "SELECT SAPCode, Key, Value FROM product_installation_meta_info WHERE Key IN ('Name','InstallDir','BaseVersion','Platform');"
  ```
  `CCXP`, `COSY`, `LIBS`, `CORE`, `COCM`, `CORG` are Creative Cloud's own components
  and go away with it; anything else (ILST Illustrator, LTRM Lightroom Classic,
  PHSP Photoshop, SPRKBE XD...) must be deregistered first.
- Per-product uninstallers live in `/Library/Application Support/Adobe/Uninstall/<SAP>_<version>.app`.
  They hand off to Creative Cloud and exit immediately; Creative Cloud may then
  crash for products whose files are gone.
- Reliable way, run by the user (values from the registry query above):
  ```bash
  sudo "/Library/Application Support/Adobe/Adobe Desktop Common/HDBox/Setup" \
    --uninstall=1 --sapCode=ILST --baseVersion=29.0 --platform=macuniversal --deleteUserPreferences=false
  ```
- Last resort: Adobe's "Creative Cloud Cleaner Tool".
- Afterwards, leftovers: `~/Library/Application Support/Adobe` (contains
  `CameraRaw` presets the user may want to keep), `com.adobe.*` under Caches,
  Preferences, HTTPStorages, WebKit, Containers; `JQ525L2MZD.com.adobe.*` group
  containers; `/Library/Application Support/Adobe`, `/Library/LaunchDaemons/com.adobe.agsservice.plist`
  (Genuine Service), `/Library/LaunchAgents/com.adobe.*`, `/Applications/Utilities/Adobe *`,
  and `pkgutil --pkgs | grep -i adobe` receipts.

### Logitech

- **Logi Options+** (current) keeps every downloaded update in
  `/Library/Application Support/Logi/LogiOptionsPlus/depots`. Keep the depots whose id
  appears in `current.json`, `next.json` or `installation.json` next to it; the rest
  are stale (often GBs).
- **Logitech Options** (legacy, pre-2022) leaves `/Library/Application Support/Logitech.localized/Logitech Options.localized`
  (with a kernel extension), `/Library/LaunchAgents/com.logitech.manager.daemon.plist`
  and the `com.logitech.manager.pkg` receipt. Its "LogiMgr Uninstaller" reports the
  app as missing once `/Applications/Logi Options.app` is gone; remove the leftovers
  by hand (bootout the agent first).
- Logi Tune (webcams/headsets), Options+ (mice/keyboards) and Logi Bolt (receiver
  pairing) are separate apps; keep only the ones the user's devices need.

### Microsoft

- Office apps share `~/Library/Group Containers/UBF8T346G9.Office`; remove it only
  when no Office app remains.
- Microsoft AutoUpdate lives in `/Library/Application Support/Microsoft/MAU2.0`.

### Homebrew

- Formula: `brew uses --installed <f>` → `brew uninstall <f>` → `brew autoremove`
  (removes dependencies nothing else needs) → `brew cleanup -s`.
- Cask: `brew uninstall --cask --zap <cask>` also removes the app's support files.
- Removing Homebrew entirely: the official uninstall script, never `rm -rf /opt/homebrew`.

### Java-based apps (e.g. Brazil's IRPF tax programs)

- Usually a folder in `/Applications` (sometimes with an uninstaller inside) plus a
  runtime in `/Library/Application Support/<App>`. Data may live in
  `~/ProgramasRFB` (IRPF); check before deleting.

### App Store apps

- Delete from Launchpad or Finder; the sandbox container in `~/Library/Containers`
  usually remains and can be trashed afterwards.
- iPhone/iPad apps installed on Apple Silicon Macs leave containers named by UUID;
  the bundle id is in `<container>/.com.apple.containermanagerd.metadata.plist`
  (`MCMMetadataIdentifier`).
