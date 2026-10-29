# Where macOS disk space goes

What each common location is, its tier (A = regenerable, B = user's call,
C = do not touch) and the right way to shrink it.

## Contents

1. [Measuring correctly](#measuring-correctly)
2. [~/Library](#library)
3. [Apps with big local data](#apps-with-big-local-data)
4. [Developer tools](#developer-tools)
5. [Downloads, Desktop, Documents](#downloads-desktop-documents)
6. [System-wide locations](#system-wide-locations)

## Measuring correctly

- Use the data volume: `df -h /System/Volumes/Data`. The `/` line shows only the
  sealed system snapshot.
- `du` and Finder can disagree with `df`: APFS clones are counted once on disk but
  once per copy by `du`, and "purgeable" space (cached iCloud files, local
  snapshots) shows as used. `tmutil listlocalsnapshots /` lists local snapshots;
  macOS deletes them when it needs the space.
- Folder sizes jump around while iCloud, Photos or WhatsApp are syncing.
  Re-measure after big changes instead of trusting earlier numbers.

## ~/Library

| Path | Tier | Notes |
|---|---|---|
| `Caches/` | A, mostly | Per-app caches, rebuilt on demand. Clean the big ones by name first. Wiping the rest (`safe-clean.sh --only user-caches`) is fine once the apps are quit, but a few apps keep login state there, so it is opt-in. It skips open apps and the exceptions below. |
| `Caches/CloudKit`, `Caches/com.apple.bird`, `com.apple.akd`, `FamilyCircle` | C | iCloud and Apple Account state (`com.apple.bird` = iCloud Drive). Shrinks by itself when Optimize Mac Storage is on. Deleting it forces resyncs. |
| `Caches/com.apple.nsurlsessiond`, `com.apple.HomeKit`, `com.apple.containermanagerd`, `com.apple.ap.adprivacyd` | C | System daemons' state (background downloads in flight, Home, container registry). Leave them alone. |
| `Logs/` | A | App logs and crash reports (`DiagnosticReports`). Disposable; usually small. |
| `Preferences/`, `Saved Application State/`, `HTTPStorages/`, `WebKit/`, `Cookies/`, `Application Scripts/` | B | One item per bundle id. Belongs to the app; only items of apps that are gone are leftovers (`leftovers.sh` lists them). |
| `Caches/Google/Chrome` | A | Browser cache. Quit Chrome (Cmd+Q) first. |
| `Caches/ms-playwright` | B | Browser binaries for Playwright tests; re-downloaded by `npx playwright install` (hundreds of MB each). |
| `Application Support/` | B | Real app data (databases, projects, settings). Look inside before anything; some subfolders are pure cache (`Cache`, `Code Cache`, `GPUCache`, `CachedData`, `CachedExtensionVSIXs`). |
| `Application Support/MobileSync/Backup` | B | iPhone/iPad backups made by Finder; often tens of GB. Manage them in Finder → device → Manage Backups. Delete only backups the user no longer needs. |
| `Application Support/Google/GoogleUpdater/crx_cache` | A | Downloaded Chrome update packages. |
| `Application Support/Code/CachedExtensionVSIXs` | A | Copies of VS Code extension installers. Same for `Cursor/`. |
| `Containers/` | mixed | Sandboxed app data, one folder per bundle id. ~90% are `com.apple.*` (C). Third-party containers hold the app's real data (B); inside them `Data/Library/Caches` and Electron `Cache`/`Code Cache` folders are A when the app is closed. Containers of uninstalled apps: see `leftovers.sh`. |
| `Group Containers/` | mixed | Data shared between an app and its extensions. Usually dominated by WhatsApp or Telegram media. Named `group.<id>` or `<TEAMID>.<suffix>` (e.g. `UBF8T346G9.Office` belongs to every Microsoft Office app). |
| `Mobile Documents/` | B | Local copies of iCloud Drive files. See [iCloud Drive](#icloud-drive). |
| `Biome/` | C | macOS Siri, Spotlight and Screen Time data. Large `streams/restricted/ProactiveHarvesting.Mail` means Siri is learning from Mail: System Settings → Siri (or Apple Intelligence & Siri) → Apps → Mail → turn off "Learn from this App", and macOS prunes it over time. |
| `Suggestions/`, `DuetExpertCenter/`, `IntelligencePlatform/` | C | Other macOS on-device intelligence stores. |
| `Messages/` | B | iMessage attachments. Settings → General → Keep messages, or delete large attachments in Messages → Settings. |
| `Keychains/`, `CloudStorage/` | C | Passwords and certificates; Dropbox/Google Drive/OneDrive file-provider folders. Never delete; manage cloud files in their apps. |
| `Mail/` | C (by hand) | Mail's database. Shrink by deleting mail or turning off "download attachments" in Mail settings, never by deleting files. |
| `Developer/` | A/B | Xcode data; see [Xcode](#xcode). |

## Apps with big local data

### WhatsApp

- Lives in `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Message/Media`.
- The phone keeps its own copies: removing media from the Mac never deletes it on
  the phone. Deleting *messages* inside the app is different; "delete for me" is
  not meant to propagate to linked devices, but do not promise it.
- Options, from safest:
  1. In the app: Settings → Storage → Manage storage (files > 5 MB, chats by size).
  2. Stop regrowth: Settings → Storage → automatic media download → untick
     videos/documents.
  3. Log out of WhatsApp on the Mac and link it again: frees nearly everything;
     history resyncs without old media.
  4. Delete the Media folder by hand with WhatsApp closed: frees everything but the
     Mac app shows missing media afterwards.
- Before 3 or 4, ask whether anything exists only on the Mac (files already deleted
  from the phone) and have the user save it.
- Telegram is similar: Settings → Data and Storage → Storage Usage.

### Photos

- Never delete or edit anything inside `*.photoslibrary`. It corrupts the library.
- Check that Optimize Mac Storage is working: `originals/` should be small if it
  is on (Photos → Settings → iCloud).
- Even optimized, previews (`resources/derivatives`) need roughly 100–150 KB per
  item, plus grid thumbnails; that part only shrinks with fewer photos.
- Count items and upload state read-only:
  `sqlite3 -readonly "file:<lib>/database/Photos.sqlite?mode=ro" "SELECT ZKIND, COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE=0 GROUP BY ZKIND;"`
  (0 = photos, 1 = videos) and `... GROUP BY ZCLOUDLOCALSTATE` (1 = already in iCloud).
- A `database/search` folder of several GB (notably `Spotlight/SpotlightKnowledgeEvents`)
  is a bloated search index. The supported fix is the repair tool: quit Photos, hold
  Option+Command while opening it, choose Repair. It can take hours for large
  libraries; keep the Mac plugged in. Results vary.
- Other options: move the library to an external APFS drive (Photos only opens with
  it connected), or empty Photos' "Recently Deleted".

### iCloud Drive

- `~/Library/Mobile Documents` holds downloaded copies. Turn on System Settings →
  Apple Account → iCloud → iCloud Drive → Optimize Mac Storage, or right-click a
  folder in Finder → Remove Download. Files stay in iCloud.
- Deleting files there deletes them from iCloud on every device. Only use Finder's
  "Remove Download" to free local space.

### Chrome and other browsers

- Each profile is a folder in `~/Library/Application Support/Google/Chrome`
  (`Profile N`). Map folders to people with the `profile.info_cache` key of the
  `Local State` JSON file. On a shared Mac, other people's profiles are theirs.
- Inside a profile, the big parts are usually `Extensions`, `Service Worker`
  (site caches), `File System` and `IndexedDB`. Site data is cleared from
  Chrome's settings (it logs the user out of sites), not by deleting folders.
- Ad blockers on Manifest V3 ship large rule sets (~300 MB per version). Chrome
  keeps the previous version until a full restart; quitting with Cmd+Q and
  reopening usually removes it.
- Flag extensions known as search hijackers or adware (e.g. "Trustnav Safesearch")
  and suggest removing them at `chrome://extensions`.

### Electron apps (Canva, Slack, Discord, Spotify, Teams, VS Code...)

- `Cache`, `Code Cache`, `GPUCache`, `Service Worker/CacheStorage` under the app's
  Application Support (or `Containers/<id>/Data/Library/Application Support/<App>`)
  are caches: safe to delete with the app closed.

### Microsoft Office

- Each app is 1–2 GB because it bundles its own frameworks and fonts. Do not strip
  language files from inside the bundle: it breaks the code signature and updates.

## Developer tools

| Item | Tier | How |
|---|---|---|
| npm cache `~/.npm` | A | `npm cache clean --force` |
| pnpm store | A | `pnpm store prune` (only unreferenced packages) |
| Yarn classic cache | A | `yarn cache clean` |
| pip cache | A | `python3 -m pip cache purge` |
| Homebrew | A/B | `brew cleanup --prune=all -s` is A. Removing formulae is B: check `brew uses --installed <f>` first, then `brew uninstall <f> && brew autoremove`. Big ones: `llvm` (usually pulled in by `rust`), `boost`/`folly` (by `watchman`, useful for React Native), `aspell` (by `php`). |
| `node_modules` | B | Recreated by `npm/pnpm/yarn install`, but it takes time and network. Good candidates: projects untouched for months. |
| Xcode DerivedData | A | `~/Library/Developer/Xcode/DerivedData`, with Xcode closed. |
| Xcode Archives | B | Needed to symbolicate crashes of shipped builds. |
| iOS/watchOS/macOS/visionOS DeviceSupport | A | One folder per OS version ever connected (several GB each). Xcode copies the symbols again the next time that device connects, which takes a few minutes. |
| Simulators | A/B | `~/Library/Developer/CoreSimulator/Caches` and `xcrun simctl delete unavailable` are A. Deleting runtimes or devices with data is B. |
| Docker Desktop | B | The disk image (`Containers/com.docker.docker`) only shrinks via `docker system prune` (add `-a` for unused images, `--volumes` deletes data volumes; ask) or Docker Desktop → Troubleshoot → Clean / Purge data. |
| Android | B | `~/Library/Android/sdk` system images and `~/.android/avd` emulators via Android Studio's SDK / Device Manager. |
| Gradle, CocoaPods, Cargo, Bun, Go caches | A | `~/.gradle/caches` (after `gradle --stop`), `~/Library/Caches/CocoaPods`, `~/.cargo/registry/cache`, `~/.bun/install/cache`, `go clean -modcache`. |
| `~/.cache` | B | Shared cache folder of command-line tools. Mostly disposable, but it may hold downloaded AI models (`huggingface`, `torch`, `whisper`, `lm-studio`) that take long to fetch again: list the subfolders and ask. Same for `~/.ollama/models`. |
| VS Code / Cursor extensions | A | The editor lists replaced or uninstalled extension folders in `extensions/.obsolete`; folders listed there and absent from `extensions.json` can go (`safe-clean.sh` moves them to the Trash). |
| Claude Code `~/.local/share/claude/versions` | leave | Claude Code manages its own versions; don't delete the running one. |

## Downloads, Desktop, Documents

- Tier B. Useful candidates to propose: archives that were already extracted
  (a sibling folder with the same name), installers (`.dmg`, `.pkg`) of apps
  already installed, duplicates of the same document in several formats, and items
  untouched for months.
- Before proposing that an archive is redundant, check the extracted folder exists.
- Interrupted downloads (`.download` from Safari, `.crdownload` from Chrome,
  `.part`/`.partial` from Firefox and others, `.opdownload` from Opera) are A once
  untouched for a day; a recent one may still be downloading.
- `scan.sh` lists the largest personal files outside `~/Library` with days since
  last use. A file marked "in iCloud only" frees nothing locally if deleted, and
  deleting it removes it from every device.
- External drives keep their own Trash (`/Volumes/<drive>/.Trashes/<uid>`);
  emptying the Trash in Finder clears them too while the drive is connected.

## System-wide locations

| Path | Tier | Notes |
|---|---|---|
| `/System`, `/usr` (except `/usr/local`) | C | Sealed, read-only system volume. Nothing to gain. |
| `/usr/local` | B | Old Homebrew (Intel) or manual installs. Look for broken links and wrappers of removed apps (`leftovers.sh`). Large single binaries are often standalone CLIs (e.g. `firebase`). |
| `/opt/homebrew` | B | Homebrew on Apple Silicon. Never delete it by hand: use the official uninstall script if the user really wants Homebrew gone, and remove `brew shellenv` from `~/.zprofile`. |
| `/Applications` | B | No caches live here. Gains come from uninstalling apps. Duplicate installs happen (e.g. website and App Store versions of the same app with different bundle ids). Spotlight's "last used" date is unreliable. |
| `/Library/Application Support` | B | Shared data of installed apps, often the biggest leftovers after an uninstall (Adobe, Logitech). |
| `/Library/Application Support/Logi/LogiOptionsPlus/depots` | A* | Logi Options+ keeps every downloaded update. Keep the depots referenced in `current.json` / `next.json` / `installation.json`; others can go (root-owned: user runs `sudo rm -rf`). |
| `/Library/Developer/CommandLineTools` | C | Needed by git, Homebrew and compilers. |
| `/Library/Updates` | C | macOS updates waiting to install; cleared by installing them. SIP-protected. |
| `/Library/Frameworks/Python.framework` | B | Python from python.org. Check nothing depends on it before removing. |
| `/Library/Java/JavaVirtualMachines` | B | JDKs; some apps and projects need them. |
| `/Library/Logs`, `~/Library/Logs` | A | Logs and crash reports; usually small. |
| Banking security modules (`/usr/local/bin/warsaw`, `/usr/local/lib/warsaw`) | C | Required by Brazilian internet banking in the browser. |
