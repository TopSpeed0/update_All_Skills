# עדכון סקילים של Skills IL

סקיל שהעליתם דרך Customize ← Skills ← "+" ← Upload a skill הוא עותק, ואף אחד לא מעדכן אותו. `npx skills-il update` ו־`gh skill update` מנהלים רק סקילים שהם עצמם התקינו, וסקיל שהועלה ל־claude.ai לא מסונכרן ל־Claude Code (וגם לא להפך). כך סקילים שהועלו נשארים מאחור בלי שאף אחד שם לב. הסקיל הזה מוצא אותם, משווה אותם לגרסה ב־GitHub, ומכין קובצי zip מאומתים להעלאה.

## הוראות

### שלב 1: מריצים את הבדיקה

```bash
python scripts/check_updates.py --check-only
```

הסקריפט מחפש סקילים מותקנים שב־`metadata.json` שלהם כתוב `"author": "skills-il"`, בשלושה מקומות:

- המטמון של Claude Desktop ב־Windows (`%LOCALAPPDATA%\Claude-Data\...\skills-plugin\...\skills`). לשם מסונכרנים הסקילים שהועלו ל־claude.ai.
- המקביל ב־macOS, תחת `~/Library/Application Support` (ניסיון בלבד).
- `~/.claude/skills` (Claude Code).

תיקייה נוספת מוסיפים עם `--skills-dir PATH` (אפשר כמה פעמים). הריפו של כל סקיל הוא `skills-il/<category>`, לפי השדה `category` ב־`metadata.json` שלו.

פלט צפוי: שורה לכל סקיל, ובסוף שורת סיכום:

```
hebrew-document-generator   1.6.0 -> 1.8.0   update available
UPDATES: 1
```

### שלב 2: בונים את קובצי ההעלאה

```bash
python scripts/check_updates.py --out ./skill-updates
```

לכל סקיל שלא מעודכן, הסקריפט מוריד את תיקיית הסקיל ב־commit האחרון שלה, ומריץ `gh attestation verify` על `SKILL.md` ועל `metadata.json` מול הארגון `skills-il`. הקובץ `<name>-v<version>.zip` נכתב רק אם החתימה מאומתת. האימות מוכיח שהקבצים הם אלה שנבנו ב־workflow השחרור של Skills IL, ולא עותק ששונה בדרך. הקבצים שירדו נארזים ב־zip ואף פעם לא מורצים.

אם החתימה לא מאומתת, אומרים את זה למשתמש, ולא מציעים `--allow-unverified` אלא אם הוא ביקש. הסיבה הנפוצה היא סקיל ששונה אחרי ה־release החתום האחרון שלו, והאפשרות הבטוחה היא לחכות ל־release הבא.

### שלב 3: מסבירים למשתמש איך להחליף כל סקיל

מציגים את הטבלה ואת הנתיבים לקבצים, ואז את השלבים. ההעלאה ידנית, כי אף סוכן לא יכול להעלות ל־claude.ai בשם המשתמש:

1. סרגל הצד ← Customize ← Skills.
2. מוחקים או מכבים את העותק הישן של הסקיל, כדי שלא יהיו פעילים שני סקילים באותו שם.
3. "+" ← Upload a skill ← בוחרים את קובץ ה־zip.
4. מוודאים שהסקיל החדש מופעל.

### שלב 4 (רשות): הופכים את זה לשגרה שבועית

מתזמנים את `python scripts/check_updates.py --check-only` פעם בשבוע, דרך המתזמן של הסוכן או של מערכת ההפעלה (cron, Task Scheduler). מודיעים למשתמש רק כשהשורה האחרונה היא לא `UPDATES: 0`, כדי ששבוע בלי עדכונים יעבור בשקט.

## דוגמאות

### דוגמה 1: סידור חודשי
המשתמש אומר: "הסקילים של Skills IL שלי מעודכנים?"
פעולות:
1. מריצים `python scripts/check_updates.py --check-only`.
2. מציגים את הטבלה כרשימה קצרה.
תוצאה: "ל־2 מתוך 3 יש עדכון: hebrew-document-generator 1.6.0 ← 1.8.0, israeli-rental-agreements 1.2.0 ← 2.0.0."

### דוגמה 2: לעדכן הכול
המשתמש אומר: "תעדכן את הסקילים שלי."
פעולות:
1. מריצים `python scripts/check_updates.py --out ./skill-updates`.
2. מציגים כל קובץ zip עם תוצאת האימות שלו.
3. נותנים את ארבעת שלבי ההעלאה.
תוצאה: קובצי zip מאומתים ב־`./skill-updates`, מוכנים להעלאה.

## פתרון בעיות

### שגיאה: "No installed skills by "skills-il" found"
**סיבה:** מטמון הסקילים נמצא במקום שהסקריפט לא בודק, או שהסקילים ממפרסם אחר.
**פתרון:** מעבירים את התיקייה עם `--skills-dir`, או משתמשים ב־`--author` למפרסם אחר שהריפו שלו בנוי באותו מבנה `<org>/<category>/<skill>` (ומגדירים גם `--owner`).

### שגיאה: "lookup failed: HTTP Error 403"
**סיבה:** המגבלה של GitHub לבקשות אנונימיות (60 בשעה).
**פתרון:** מתחברים עם `gh auth login`, או מגדירים `GITHUB_TOKEN`. הסקריפט מזהה את שניהם לבד.

### סטטוס: "zip withheld, signature not verified"
**סיבה:** קבצי הסקיל השתנו אחרי ה־release החתום האחרון, או ש־`gh` לא הצליח להגיע ל־Sigstore.
**פתרון:** מנסים שוב מאוחר יותר. אם זה נמשך, מדווחים לריפו של הסקיל. בונים zip לא מאומת רק אם המשתמש אישר במפורש שהוא לוקח את הסיכון.

### סטטוס: "gh CLI not found"
**סיבה:** GitHub CLI לא מותקן, ולכן אי אפשר לבדוק חתימות.
**פתרון:** מתקינים gh מ־https://cli.github.com ומריצים `gh auth login`.
