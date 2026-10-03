# Running the safe cleanup automatically

Only tier A (`scripts/safe-clean.sh --apply`) belongs in an unattended job. It
deletes caches that rebuild themselves and moves obsolete editor extensions to the
Trash; it skips browser and Xcode caches while those apps are open. Everything that
needs judgment stays manual.

`launchd` is the right scheduler on macOS: it runs without any agent or terminal
open, and a `StartCalendarInterval` job that was missed while the Mac slept runs
at the next wake. Cloud schedulers cannot reach the local disk.

## Install (monthly, day 1 at 10:00)

Replace `SKILL_DIR` with the absolute path of this skill (the folder that contains
`SKILL.md`) and write the file to `~/Library/LaunchAgents/com.mac-cleanup.monthly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mac-cleanup.monthly</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>out=$(/bin/bash "SKILL_DIR/scripts/safe-clean.sh" --apply 2>&amp;1); printf '%s\n%s\n' "$(date)" "$out" >> "$HOME/Library/Logs/mac-cleanup.log"; msg=$(printf '%s' "$out" | grep 'Total freed' | head -1); /usr/bin/osascript -e "display notification \"${msg:-done}\" with title \"Mac cleanup\""</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Day</key><integer>1</integer>
    <key>Hour</key><integer>10</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>ProcessType</key>
  <string>Background</string>
  <key>LowPriorityIO</key>
  <true/>
</dict>
</plist>
```

Then load it and check it:

```bash
plutil -lint ~/Library/LaunchAgents/com.mac-cleanup.monthly.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mac-cleanup.monthly.plist
launchctl print gui/$(id -u)/com.mac-cleanup.monthly | head -20
```

Test a run right away with `launchctl kickstart gui/$(id -u)/com.mac-cleanup.monthly`
and read `~/Library/Logs/mac-cleanup.log`.

For a weekly run, replace `Day` with `<key>Weekday</key><integer>1</integer>` (Monday).

## Low-space alert (optional)

To be warned before the disk fills up, add a second agent that runs daily and
notifies below a threshold (here 20 GB):

```bash
free_gb=$(df -g /System/Volumes/Data | awk 'NR==2 {print $4}')
[ "$free_gb" -lt 20 ] && osascript -e "display notification \"Only ${free_gb} GB free — ask your agent to run mac-cleanup\" with title \"Low disk space\""
```

Use the same plist shape with `StartCalendarInterval` `Hour` only (daily).

## Remove

```bash
launchctl bootout gui/$(id -u)/com.mac-cleanup.monthly
rm ~/Library/LaunchAgents/com.mac-cleanup.monthly.plist
```
