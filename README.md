# update_All_Skills

**skills-il-updater** keeps your [Skills IL](https://agentskills.co.il) skills current, whether you uploaded them to claude.ai or keep them as local Claude Code folders.

| Where the skill is installed | Find the update | Download and verify the signature | Replace the old version |
|---|---|---|---|
| Local: `~/.claude/skills` (Claude Code) | automatic | automatic | **automatic**, after a backup |
| Uploaded: claude.ai / Claude Desktop | automatic | automatic, as a ready zip | **manual**: Customize → Skills → Upload. claude.ai has no upload API |

`npx skills-il update` and `gh skill update` only update skills that they installed themselves. The skills-il site can also notify you about skills you've saved there, but updating uploaded skills is still manual, one at a time. This skill:

1. finds your installed Skills IL skills (`"author": "skills-il"` in `metadata.json`),
2. compares each with its repo, `skills-il/<category>`,
3. downloads each outdated skill and verifies its Sigstore build signature with `gh attestation verify`,
4. replaces local copies in place (old version kept in `~/.claude/skill-backups/`) and writes upload zips for uploaded ones.

Nothing is installed or zipped unless the signature verifies. Downloaded files are never executed. The app's own skill cache and skills-il CLI links are only read, never changed.

## Install

```bash
npx skills-il add TopSpeed0/update_All_Skills --skill skills-il-updater -g -a claude-code
```

Or copy the `skills-il-updater/` folder into `~/.claude/skills/`.

## Use

Ask your agent "are my skills up to date?" or "update my skills". You can also run the script yourself:

```bash
python skills-il-updater/scripts/check_updates.py --check-only                        # report only
python skills-il-updater/scripts/check_updates.py --install-local --out ./skill-updates
```

Example run, 2026-10-24:

```
hebrew-document-generator        local       1.6.0 -> 1.8.0    updated in place
                                          Sigstore attestation verified for SKILL.md, metadata.json
                                          backup: ~/.claude/skill-backups/hebrew-document-generator-v1.6.0-20261024-001654
hebrew-document-generator        uploaded    1.6.0 -> 1.8.0    zip ready, upload it
israeli-bureaucracy-decoder      uploaded    1.2.2 -> 1.3.3    zip ready, upload it
israeli-rental-agreements        uploaded    1.2.0 -> 2.0.0    zip ready, upload it
UPDATES: 4  INSTALLED: 1  MANUAL: 3
```

To run it every week, schedule the second command. Then look at `MANUAL` in the last line: only that count needs you.

## Verify this skill's own release

Releases are built by the Skills IL reusable workflow, so pass it as the signer:

```bash
gh attestation verify skills-il-updater/SKILL.md --repo TopSpeed0/update_All_Skills --signer-repo skills-il/release-workflow
```

## Requirements

- Python 3.9+ (standard library only)
- [GitHub CLI](https://cli.github.com) 2.49+, logged in, for signature checks and a higher API rate limit

## עברית

הסקיל שומר על הסקילים של Skills IL מעודכנים:
- **סקילים מקומיים** ב־Claude Code מתעדכנים לבד, אחרי אימות חתימה ועם גיבוי של הגרסה הקודמת.
- **לסקילים שהועלו** ל־claude.ai הוא מכין zip מאומת. ההעלאה עצמה נשארת ידנית, כי ל־claude.ai אין API להעלאה.

ההוראות המלאות בעברית נמצאות ב־`skills-il-updater/SKILL_HE.md`.

## License

MIT
