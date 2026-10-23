# update_All_Skills

**skills-il-updater** keeps [Skills IL](https://agentskills.co.il) skills current when you installed them by uploading a zip to claude.ai or Claude Desktop.

`npx skills-il update` and `gh skill update` only update skills that they installed themselves. A skill you uploaded through Customize → Skills → "+" → Upload a skill is a copy, so nothing updates it and it falls behind its repo. This skill:

1. finds your installed Skills IL skills (`"author": "skills-il"` in `metadata.json`),
2. compares each with its repo, `skills-il/<category>`,
3. downloads each outdated skill and verifies its Sigstore build signature with `gh attestation verify`,
4. writes a zip that is ready to upload, but only if the signature verifies.

Downloaded files are zipped, never executed.

## Install

```bash
npx skills-il add TopSpeed0/update_All_Skills --skill skills-il-updater -g -a claude-code
```

Or copy the `skills-il-updater/` folder into `~/.claude/skills/`.

## Use

Ask your agent "are my skills up to date?" or "update my skills". You can also run the script yourself:

```bash
python skills-il-updater/scripts/check_updates.py --check-only      # report only
python skills-il-updater/scripts/check_updates.py --out ./skill-updates
```

Example run, 2026-10-23:

```
hebrew-document-generator             1.6.0 -> 1.8.0    zip ready
                                   Sigstore attestation verified for SKILL.md, metadata.json
israeli-bureaucracy-decoder           1.2.2 -> 1.3.3    zip ready
israeli-rental-agreements             1.2.0 -> 2.0.0    zip ready
UPDATES: 3
```

Then upload each zip: Customize → Skills → turn off or delete the old copy → "+" → Upload a skill.

## Requirements

- Python 3.9+ (standard library only)
- [GitHub CLI](https://cli.github.com) 2.49+, logged in, for signature checks and a higher API rate limit

## עברית

הסקיל מעדכן סקילים של Skills IL שהעליתם ידנית ל־claude.ai או לאפליקציה. אף כלי אחר לא מעדכן אותם, כי `npx skills-il update` ו־`gh skill update` מעדכנים רק סקילים שהם עצמם התקינו. הסקיל בודק אילו סקילים ישנים, מאמת את החתימה של כל עדכון, ומכין קובץ zip מוכן להעלאה. ההוראות המלאות בעברית נמצאות ב־`skills-il-updater/SKILL_HE.md`.

## License

MIT
