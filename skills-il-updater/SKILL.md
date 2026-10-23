---
name: skills-il-updater
description: Checks Skills IL skills that were uploaded to claude.ai or Claude Desktop for newer versions, verifies each update's Sigstore build signature, and builds zips ready to re-upload. Use when the user asks to "update my skills", "check for skill updates", "are my Skills IL skills up to date", "עדכן את הסקילים", or wants a weekly skill-update check. Not for skills installed with npx skills-il or gh skill; those have their own update commands.
license: MIT
compatibility: Python 3.9+ (standard library only). GitHub CLI (gh) 2.49+ for signature verification. Network access to api.github.com and raw.githubusercontent.com.
---

# Skills IL Updater

Skills uploaded through Customize → Skills → "+" → Upload a skill are copies. Nothing updates them: `npx skills-il update` and `gh skill update` only manage skills they installed themselves, and a skill uploaded to claude.ai is not synced to Claude Code (or the other way round). So uploaded skills quietly fall behind their repo. This skill finds them, compares them with GitHub, and prepares verified zips for the user to upload.

## Instructions

### Step 1: Run the check

```bash
python scripts/check_updates.py --check-only
```

The script looks for installed skills whose `metadata.json` has `"author": "skills-il"`, in:

- the Claude Desktop skill cache on Windows (`%LOCALAPPDATA%\Claude-Data\...\skills-plugin\...\skills`), where skills uploaded to claude.ai are synced,
- the macOS equivalent under `~/Library/Application Support` (best effort),
- `~/.claude/skills` (Claude Code).

Add another folder with `--skills-dir PATH` (repeatable). Each skill's repo is `skills-il/<category>`, taken from the `category` field of its `metadata.json`.

Expected output, one line per skill, then a summary line:

```
hebrew-document-generator   1.6.0 -> 1.8.0   update available
UPDATES: 1
```

### Step 2: Build the upload zips

```bash
python scripts/check_updates.py --out ./skill-updates
```

For each outdated skill the script downloads the skill folder at its latest commit and runs `gh attestation verify` on `SKILL.md` and `metadata.json` against the `skills-il` org. It writes `<name>-v<version>.zip` only when the signature verifies. Verification proves the files are the ones built by the Skills IL release workflow, not a copy changed on the way. Downloaded files are zipped, never executed.

If the signature does not verify, tell the user and do not suggest `--allow-unverified` unless they ask for it. The usual cause is a skill changed after its last signed release; waiting for the next release is the safe option.

### Step 3: Tell the user how to replace each skill

Show the table and the zip paths, then the steps. Uploading is manual, because no agent can upload to claude.ai on the user's behalf:

1. Sidebar → Customize → Skills.
2. Delete or turn off the old copy of the skill, so two skills with the same name are not active.
3. "+" → Upload a skill → choose the zip.
4. Make sure the new skill is turned on.

### Step 4 (optional): Make it a weekly routine

Schedule `python scripts/check_updates.py --check-only` once a week with the agent's scheduler or the OS (cron, Task Scheduler). Notify the user only when the last line is not `UPDATES: 0`, so a quiet week stays quiet.

## Examples

### Example 1: Monthly tidy-up
User says: "Are my Skills IL skills up to date?"
Actions:
1. Run `python scripts/check_updates.py --check-only`.
2. Report the table in one short list.
Result: "2 of 3 have updates: hebrew-document-generator 1.6.0 → 1.8.0, israeli-rental-agreements 1.2.0 → 2.0.0."

### Example 2: Update everything
User says: "Update my skills."
Actions:
1. Run `python scripts/check_updates.py --out ./skill-updates`.
2. List each zip with its verification result.
3. Give the four upload steps.
Result: verified zips in `./skill-updates`, ready to upload.

## Troubleshooting

### Error: "No installed skills by "skills-il" found"
**Cause:** the skill cache is somewhere the script does not look, or the skills come from another author.
**Solution:** pass the folder with `--skills-dir`, or use `--author` for another publisher whose repos follow the same `<org>/<category>/<skill>` layout (set `--owner` too).

### Error: "lookup failed: HTTP Error 403"
**Cause:** GitHub's anonymous API limit (60 requests an hour).
**Solution:** log in with `gh auth login`, or set `GITHUB_TOKEN`. The script picks either up automatically.

### Status: "zip withheld, signature not verified"
**Cause:** the skill's files changed after the last signed release, or `gh` could not reach Sigstore.
**Solution:** retry later; if it persists, report it to the skill's repo. Only build an unverified zip when the user explicitly accepts the risk.

### Status: "gh CLI not found"
**Cause:** GitHub CLI is not installed, so signatures cannot be checked.
**Solution:** install gh from https://cli.github.com and run `gh auth login`.
