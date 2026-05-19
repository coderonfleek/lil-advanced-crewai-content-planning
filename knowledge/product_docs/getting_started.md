# Getting Started with NimbusCloud

NimbusCloud is a cloud backup and sync service for individuals, teams, and enterprises. This guide covers account setup, the first backup, and the daily workflow.

## Account creation

You create a NimbusCloud account at https://app.nimbuscloud.example/signup. We require a valid email address and a password of at least 12 characters containing uppercase, lowercase, a digit, and a symbol. Accounts begin on the Free plan and can be upgraded at any time from the Billing tab in Settings.

When you sign up we send a verification email. You must click the verification link within 72 hours or the account is automatically deleted. If you did not receive the email, check your spam folder and then use the "Resend verification" link on the sign-in page.

## Plans and quotas

- **Free** — 5 GB of storage. One device. No version history. Community support only.
- **Pro** — 500 GB of storage. Up to 3 devices. 30-day version history. Email support with 48-hour SLA.
- **Business** — 2 TB of storage per seat, up to 25 seats. Unlimited devices. 90-day version history. Priority email + chat support with 8-hour SLA.
- **Enterprise** — Custom quota (starting at 10 TB). Unlimited seats. 365-day version history. 24/7 support with 1-hour SLA and a named account manager.

Quota is measured against your raw stored bytes, after client-side compression but before server-side deduplication. Deduplication savings are not passed back to your quota.

## Installing the client

NimbusCloud ships native clients for macOS 12+, Windows 10+, and Ubuntu 20.04+. Download installers from https://app.nimbuscloud.example/downloads. On all platforms the installer requires admin privileges and prompts you to choose a sync folder; the default is `~/NimbusCloud` on Unix-likes and `%USERPROFILE%\NimbusCloud` on Windows.

After installation, sign in once in the tray/menubar app. A first-time sign-in triggers a full directory scan, which for a fresh install takes under a minute. If you're migrating from another service and have a large local dataset, the initial upload can take hours — this is expected.

## Your first backup

Backups run automatically every four hours by default. You can force an immediate backup from the tray/menubar menu ("Back up now"), from the CLI with `nimbus backup run`, or by pressing ⌘⇧B (macOS) / Ctrl+Shift+B (Windows/Linux).

The first backup uploads the contents of your sync folder. Subsequent backups upload only changed blocks using content-defined chunking — typically a 4 GB file with a single small change uploads around 8 MB of deltas rather than the whole file.

## Sync vs. backup

It's worth being explicit about the distinction, because new users frequently conflate the two:

- **Sync** keeps your sync folder consistent across devices in near-real-time. Deleting a file from your sync folder on one machine propagates that deletion to other machines within seconds.
- **Backup** is a point-in-time snapshot retained according to your plan's version history. A file you delete from your sync folder can still be recovered from backup for the duration of your version-history window.

Backups are immutable and cannot be altered after they're written. You cannot "edit" a backup — only restore from it.
