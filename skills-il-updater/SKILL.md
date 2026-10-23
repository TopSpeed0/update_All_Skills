---
name: skills-il-updater
description: Keeps every installed Skills IL skill current with one command. It runs npx skills-il update, repairs CLI installs that update silently skips, replaces hand-copied Claude Code skills (with a backup) and builds signature-verified zips for skills uploaded to claude.ai. Use when the user asks to "update my skills", "check for skill updates", "are my Skills IL skills up to date", "עדכן את הסקילים", or wants a weekly skill-update schedule.
license: MIT
compatibility: Python 3.9+ (standard library only). GitHub CLI (gh) 2.49+ for signature verification. Node.js (npx) only if skills were installed with the skills-il CLI. Network access to api.github.com and raw.githubusercontent.com.
---

# Skills IL Updater

One command keeps every Skills IL skill on the machine current:

```bash
python scripts/check_updates.py --update
```

The user only has to remember two things:

1. **Schedule** that command once a week, if they want it to run by itself (Step 3).
2. **Upload the zips** from `~/skill-updates` for skills that should live in claude.ai (Step 2). claude.ai has no upload API, so this one step stays manual.

Everything else is automatic.

## Where skills live, and what happens to each

| Installed as | Found by | What `--update` does | User action |
|---|---|---|---|
| **CLI**: `npx skills-il add -g` | `~/.agents/.skill-lock.json` | runs `npx skills-il update`, then re-installs (this one skill only) any that update skipped | none |
| **Local copy**: a folder in `~/.claude/skills` with `metadata.json` (unzipped from the site, cloned, copied) | `metadata.json` with `"author": "skills-il"` | downloads the latest version, verifies the Sigstore signature, backs up the old folder to `~/.claude/skill-backups`, replaces it | none |
| **Uploaded** to claude.ai / Claude Desktop | the desktop app's skill cache (read only) | downloads, verifies, writes `<name>-v<version>.zip` to `~/skill-updates` | upload the zip |
| **Linked folder** (symlink or Windows junction) | `~/.claude/skills` | left alone | none |

Rules that always hold:

- Nothing is installed or zipped unless its signature verifies.
- Downloaded files are never executed.
- The desktop app's cache is only read, never written.
- CLI folders are only changed by the CLI itself.

## Known issues this skill works around

These came out of real testing on Windows 11 with skills-il CLI installs and claude.ai uploads.

| Problem | Effect | How the skill handles it |
|---|---|---|
| No tool updates uploaded skills | `npx skills-il update` and `gh skill update` only manage their own installs. Uploaded skills fall behind silently | compares each with GitHub and builds a verified zip |
| The CLI records an empty `skillFolderHash` when its GitHub calls fail during install (an expired `GITHUB_TOKEN` is enough), and does not warn | `npx skills-il check`/`update` report "No version hash available" and never update that skill again | detects staleness by commits since install and by `SKILL.md` content, then re-installs that one skill, which records a fresh hash |
| The CLI's suggested fix is `npx skills add <repo> -g -y` | wrong package (`skills`, not `skills-il`), and with no `--skill` it installs every skill in the repo | never runs it; re-installs with `--skill <name>` |
| npx with a bad token causes the empty hash above | running the CLI with an expired token creates the problem | checks the token first; npx runs only with a working token, otherwise it is skipped with a note |
| The CLI does not copy `metadata.json` | the installed version is not on disk | reads the version from `CHANGELOG.md` |
| Files arrive with CRLF line endings (git `autocrlf`) | a byte comparison says every file changed | compares with line endings normalized |
| The desktop app keeps the `GITHUB_TOKEN` it started with | after a token rotation, tools launched from the app use the expired one until the app restarts | uses `GITHUB_TOKEN`/`GH_TOKEN`, else `gh auth token`, and reports an invalid token instead of failing |
| On Windows, links are often junctions, which `os.path.islink` misses | a linked folder could be mistaken for a plain copy | detects junctions too and leaves them alone |
| The same skill can be both uploaded and local | Claude Code then shows two skills with the same name | reports each copy separately. Keep one per skill |
| The zip from the Skills IL site is generated on click and unsigned | no way to know it matches the signed release | zips only files whose Sigstore attestation verifies |

## Instructions

### Step 1: Run it

```bash
python scripts/check_updates.py --update
```

Use `--check-only` to see the state without changing anything. Each line shows the skill, how it is installed (`cli`, `local`, `uploaded`), the installed and latest versions, and what happened. The last line summarizes:

```
UPDATES: 2  INSTALLED: 1  MANUAL: 1  BLOCKED: 0
```

- `INSTALLED`: updated automatically.
- `MANUAL`: zips waiting in `~/skill-updates`.
- `BLOCKED`: could not be updated. Read the `NOTE:` lines, which name the cause (no npx, invalid token, signature not verified).

Options: `--out DIR` for another zip folder, `--skills-dir DIR` for extra skill folders, `--json` for machine-readable output. `--allow-unverified` builds zips that failed verification; never use it unless the user explicitly asks.

### Step 2: Hand over the zips

If `MANUAL` is not 0, tell the user the zips are in `~/skill-updates` (the `ZIPS TO UPLOAD:` line gives the full path). For each zip:

1. Sidebar → Customize → Skills.
2. Open the old skill → "..." → Delete, so two skills with the same name are not active.
3. "+" → Create skill → Upload a skill → choose the zip.
4. Make sure it is turned on, then fully quit and reopen the desktop app.

Do not list the `BLOCKED` items as tasks. Explain their cause once.

### Step 3: Schedule it (optional)

Run the same command weekly. Pick one:

- **The agent's scheduler**, for example a scheduled task with the prompt "Run `python <path>/scripts/check_updates.py --update` and tell me only if `MANUAL` or `BLOCKED` is not 0".
- **Windows**: `schtasks /Create /SC WEEKLY /D SUN /ST 09:00 /TN skills-il-updater /TR "python <path>\scripts\check_updates.py --update"`
- **macOS/Linux** (cron): `0 9 * * 0 python3 <path>/scripts/check_updates.py --update`

The schedule needs a working GitHub login (`gh auth login`, or a `GITHUB_TOKEN` in the user's environment), so that npx never runs with an expired token.

## Examples

### Example 1: "Are my skills up to date?"
Run `python scripts/check_updates.py --check-only` and summarize in one short list.

### Example 2: "Update my skills"
Run `python scripts/check_updates.py --update`. Report what updated automatically in one line, then the zip folder and the four upload steps if `MANUAL` > 0.

### Example 3: "Set up weekly updates"
Explain the two things to remember, create the schedule (Step 3) and run it once now.

## Troubleshooting

### `NOTE: npx not found`
Node.js is missing, so CLI installs cannot be updated. Install Node.js LTS (for example `winget install OpenJS.NodeJS.LTS`), then run again.

### `NOTE: GITHUB_TOKEN missing or invalid`
Run `gh auth login`, or renew the token and set it again. Restart the desktop app afterwards, because it keeps the token it started with.

### `still outdated after re-install`
The latest files changed after the newest release, or GitHub was briefly unreachable. Run again later.

### `not installed: signature not verified` or `zip withheld`
The skill changed after its last signed release, or Sigstore was unreachable. The installed version is untouched. Wait for the next release.

### Undo a local update
Move the folder from `~/.claude/skill-backups/` back to `~/.claude/skills/<name>`. Delete or rename the new one first.

### `No installed skills by "skills-il" found`
Pass extra folders with `--skills-dir`, or use `--author`/`--owner` for another publisher that uses the same `<org>/<category>/<skill>` layout.
