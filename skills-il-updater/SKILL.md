---
name: skills-il-updater
description: Keeps installed Skills IL skills current. It finds outdated skills, verifies each update's Sigstore build signature, replaces local Claude Code copies in place (with a backup) and builds ready-to-upload zips for skills uploaded to claude.ai or Claude Desktop. Use when the user asks to "update my skills", "check for skill updates", "are my Skills IL skills up to date", "עדכן את הסקילים", or wants a weekly skill-update check. Not for skills installed with npx skills-il or gh skill; those have their own update commands.
license: MIT
compatibility: Python 3.9+ (standard library only). GitHub CLI (gh) 2.49+ for signature verification. Network access to api.github.com and raw.githubusercontent.com.
---

# Skills IL Updater

An installed Skills IL skill lives in one of two places, and each needs different handling:

| Where | Available in | Who can update it |
|---|---|---|
| **Uploaded** through Customize → Skills → "+" → Upload a skill | every Claude on the account: claude.ai, desktop app, phone | only the user, by uploading a new zip. claude.ai has no upload API |
| **Local**, a folder in `~/.claude/skills` | Claude Code on this computer | this skill, automatically |

`npx skills-il update` and `gh skill update` only manage skills they installed themselves, so uploaded skills and hand-copied local skills fall behind unnoticed. This skill closes that gap. It updates local copies by itself, and for uploaded skills it does everything except the final click.

## Instructions

### Step 1: Run the check

```bash
python scripts/check_updates.py --check-only
```

The script looks for installed skills whose `metadata.json` has `"author": "skills-il"`:

- **uploaded:** the Claude Desktop cache of claude.ai skills (`%LOCALAPPDATA%\Claude-Data\...\skills-plugin\...\skills` on Windows; the macOS equivalent under `~/Library/Application Support` is best effort). The script only reads this folder. The app re-syncs it from the account, so it never writes there.
- **local:** `~/.claude/skills`, plus any folder passed with `--skills-dir PATH` (repeatable).

Each skill's repo is `skills-il/<category>`, from the `category` field of its `metadata.json`. Expected output, one line per installed copy, then a summary line:

```
hebrew-document-generator   local      1.6.0 -> 1.8.0   update available
hebrew-document-generator   uploaded   1.6.0 -> 1.8.0   update available
UPDATES: 2  INSTALLED: 0  MANUAL: 1
```

### Step 2: Update

```bash
python scripts/check_updates.py --install-local --out ./skill-updates
```

For each outdated copy, the script downloads the skill folder at its latest commit and runs `gh attestation verify` on `SKILL.md` and `metadata.json` against the `skills-il` org. Verification proves that the files were built by the Skills IL release workflow and not changed on the way. Downloaded files are never executed. Then:

- **Local copy:** the verified folder replaces the old one. The old folder moves to `~/.claude/skill-backups/<name>-v<old>-<time>` first, so the update can be undone by moving it back. Without `--install-local`, a local copy gets a zip like an uploaded one.
- **Uploaded copy:** the script writes `<name>-v<version>.zip` to `--out`.
- **Linked folder** (symlink or Windows junction, as the skills-il CLI creates): left alone. Tell the user to run `npx skills-il update`.

If a signature does not verify, nothing is installed, and no zip is built. Tell the user. Suggest `--allow-unverified` (zips only, it never installs) only if they ask. The usual cause is a skill changed after its last signed release, and the safe option is to wait for the next release.

### Step 3: Hand over the manual part

Report what was updated automatically, then the zips. Each zip needs these steps, because no agent can upload to claude.ai on the user's behalf:

1. Sidebar → Customize → Skills.
2. Open the old skill → "..." → Delete, so two skills with the same name are not active.
3. "+" → Create skill → Upload a skill → choose the zip.
4. Make sure the new skill is turned on, then fully quit and reopen the desktop app.

### Step 4 (optional): Make it a weekly routine

Schedule `python scripts/check_updates.py --install-local --out <folder>` once a week with the agent's scheduler or the OS (cron, Task Scheduler). Read the last line. Notify the user only when `MANUAL` is not 0, and mention any `INSTALLED` updates in one line. A week with nothing to do stays quiet.

## Examples

### Example 1: Status check
User says: "Are my Skills IL skills up to date?"
Actions:
1. Run `python scripts/check_updates.py --check-only`.
2. Report the table as a short list, grouped into local and uploaded.
Result: "3 uploaded skills have updates; your local copies are current."

### Example 2: Update everything
User says: "Update my skills."
Actions:
1. Run `python scripts/check_updates.py --install-local --out ./skill-updates`.
2. Say what was replaced locally, with the backup paths.
3. List each zip with its verification result and the four upload steps.
Result: local skills current; verified zips in `./skill-updates` for the uploaded ones.

## Troubleshooting

### Error: "No installed skills by "skills-il" found"
**Cause:** the skills are somewhere the script does not look, or come from another author.
**Solution:** pass the folder with `--skills-dir`, or use `--author` for another publisher whose repos follow the same `<org>/<category>/<skill>` layout (set `--owner` too).

### Error: "lookup failed: HTTP Error 403"
**Cause:** GitHub's anonymous API limit (60 requests an hour).
**Solution:** log in with `gh auth login`, or set `GITHUB_TOKEN`. The script picks either up automatically.

### Status: "not installed: signature not verified" or "zip withheld"
**Cause:** the skill's files changed after its last signed release, or `gh` could not reach Sigstore.
**Solution:** retry later; if it persists, report it to the skill's repo. The installed version stays untouched.

### Undo a local update
Move the folder from `~/.claude/skill-backups/` back to `~/.claude/skills/<name>`. Delete or rename the new one first.

### Status: "gh CLI not found"
**Cause:** GitHub CLI is not installed, so signatures cannot be checked.
**Solution:** install gh from https://cli.github.com and run `gh auth login`.
