# update_All_Skills

**skills-il-updater** keeps every [Skills IL](https://agentskills.co.il) skill on your machine current with one command, however you installed it:

```bash
python skills-il-updater/scripts/check_updates.py --update
```

You only need to remember two things:

1. **Schedule** that command weekly, if you want it to run by itself.
2. **Upload the zips** from `~/skill-updates` for skills you keep in claude.ai. claude.ai has no upload API, so this is the one manual step.

| Installed as | What `--update` does | You |
|---|---|---|
| CLI: `npx skills-il add -g` | runs `npx skills-il update`, and re-installs (that skill only) any it silently skips | nothing |
| Local copy in `~/.claude/skills` | downloads, verifies the Sigstore signature, backs up, replaces | nothing |
| Uploaded to claude.ai / Claude Desktop | downloads, verifies, writes a zip to `~/skill-updates` | upload it |

Nothing is installed or zipped unless the signature verifies. Downloaded files are never executed. The desktop app's skill cache is only read, and CLI folders are changed only by the CLI.

## Why it exists

Found while testing on Windows 11 (full list in [`SKILL.md`](skills-il-updater/SKILL.md#known-issues-this-skill-works-around)):

- `npx skills-il update` and `gh skill update` only update their own installs. Uploaded skills fall behind silently.
- If the skills-il CLI can't reach GitHub during install (an expired `GITHUB_TOKEN` is enough), it records an empty hash without a warning. From then on `npx skills-il check` and `update` skip that skill for good.
- The CLI's suggested fix (`npx skills add <repo> -g -y`) uses the wrong package and has no `--skill`, so it installs every skill in the repo.
- The CLI doesn't copy `metadata.json`. Its files arrive with CRLF, Windows junctions hide from `islink`, and the desktop app keeps a stale token until it restarts.

The updater detects all of these, checks the token before letting npx run, and repairs a skipped skill by re-installing just that skill.

## Install

```bash
npx skills-il add TopSpeed0/update_All_Skills --skill skills-il-updater -g -a claude-code
```

Or copy the `skills-il-updater/` folder into `~/.claude/skills/`.

## Use

```bash
python skills-il-updater/scripts/check_updates.py --check-only   # look, change nothing
python skills-il-updater/scripts/check_updates.py --update       # update everything that can be automatic
```

Example run, 2026-10-24, after an npx install had been left with an empty hash:

```
israel-gov-api                   cli         1.4.0 -> 1.4.0    updated: re-installed with npx (update had skipped it)
israeli-bureaucracy-decoder      uploaded    1.3.3 -> 1.3.3    up to date
israeli-rental-agreements        uploaded    2.0.0 -> 2.0.0    up to date
UPDATES: 1  INSTALLED: 1  MANUAL: 0  BLOCKED: 0
```

To schedule it weekly, on Windows:

```
schtasks /Create /SC WEEKLY /D SUN /ST 09:00 /TN skills-il-updater /TR "python <path>\skills-il-updater\scripts\check_updates.py --update"
```

With cron: `0 9 * * 0 python3 <path>/skills-il-updater/scripts/check_updates.py --update`. Either way, you need a working GitHub login (`gh auth login` or `GITHUB_TOKEN`).

## Verify this skill's own release

Releases are built by the Skills IL reusable workflow, so pass it as the signer:

```bash
gh attestation verify skills-il-updater/SKILL.md --repo TopSpeed0/update_All_Skills --signer-repo skills-il/release-workflow
```

## Requirements

- Python 3.9+ (standard library only)
- [GitHub CLI](https://cli.github.com) 2.49+, logged in
- Node.js LTS, only if you install skills with `npx skills-il`

## עברית

פקודה אחת, `--update`, מעדכנת את כל הסקילים של Skills IL במחשב:
- **סקילים מ־npx:** מתעדכנים אוטומטית. אם ה־CLI מדלג על סקיל בגלל hash ריק, הסקיל מתקין אותו מחדש לבד.
- **עותקים מקומיים:** מוחלפים אוטומטית, אחרי אימות חתימה ועם גיבוי.
- **סקילים שהועלו ל־claude.ai:** מקבלים zip מאומת ב־`~/skill-updates`.

צריך לזכור רק שני דברים: לתזמן את הפקודה, ולהעלות את קובצי ה־zip. ההוראות המלאות בעברית נמצאות ב־`skills-il-updater/SKILL_HE.md`.

## License

MIT
