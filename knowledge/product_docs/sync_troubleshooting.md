# Sync Troubleshooting

This guide covers the most common sync issues reported to NimbusCloud support and the supported resolutions for each.

## Quota exceeded errors

The "quota exceeded" error appears when your raw stored bytes exceed your plan's quota. Note that quota is measured before server-side deduplication — if you see this error while your NimbusCloud dashboard shows a lower number, the dashboard is displaying deduplicated usage.

**Resolution steps:**

1. Check the actual stored bytes in Settings → Storage → "Raw upload size"
2. Empty the trash in the NimbusCloud web app (files in trash still count against quota for 30 days)
3. Prune old versions from Settings → Version History → "Prune versions older than..."
4. If still over quota, upgrade your plan or remove files from the sync folder

Business and Enterprise plans have overage protection: you can exceed your quota by up to 10% for up to 7 days before uploads are blocked. Pro plans block uploads immediately at 100% quota. Free plans block at 100% and also pause all ongoing backups.

**If the customer is on Business tier and reports a quota error while showing usage well below quota, this is almost certainly a dashboard display bug. Check Settings → Storage → Raw upload size for the authoritative number, and advise them to refresh.** This is a known issue tracked as NIMBUS-2341.

## "Sync paused" banner

The client pauses sync automatically when:

- The device is on a metered connection (cellular hotspot, airplane wifi marked as metered)
- Battery is below 15% and the device is not on AC power
- Disk space is below 2 GB free
- User has manually paused from the tray/menubar

To resume, click "Resume sync" from the tray/menubar, or run `nimbus sync resume` from the CLI.

## Files not syncing

If a specific file isn't syncing but others in the same folder are, check these in order:

1. **Filename contains forbidden characters.** NimbusCloud does not sync files with the following characters in their name: `< > : " | ? *` or any control characters.
2. **File size exceeds per-file limit.** Free: 2 GB per file. Pro: 50 GB per file. Business/Enterprise: 500 GB per file.
3. **File is open and locked.** On Windows, files opened by other applications with exclusive locks are skipped and retried on the next sync cycle.
4. **File is in an excluded path.** Check Settings → Sync Rules for any regex patterns excluding it.
5. **File is a symbolic link.** Symlinks are never followed.

If none of these apply, collect logs from Settings → Diagnostics → "Export last 24h logs" and open a support ticket.

## Sync loops (files keep re-uploading)

Sync loops are almost always caused by an application on your machine modifying files' timestamps or metadata on every open. The most common culprits are Adobe applications (especially older versions) and some antivirus software.

**Resolution:** Add the affected folder to Settings → Sync Rules → "Exclude metadata-only changes". This tells NimbusCloud to only upload when file *content* changes, not when timestamps or extended attributes change.

## Cross-device conflicts

When the same file is edited on two devices before sync catches up, NimbusCloud creates a conflict copy alongside the original. The conflict copy is named `<original>-conflict-<device-name>-<timestamp>.<ext>`. The original file retains the version from whichever device synced first.

**We never silently overwrite customer data.** If a customer reports "my file disappeared," the conflict copy almost always still exists. Ask them to search their sync folder for `-conflict-` in the filename.
