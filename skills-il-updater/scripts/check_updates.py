#!/usr/bin/env python3
"""Keep Skills IL skills current: auto-update local installs, build verified zips for uploaded ones.

Skills uploaded to claude.ai / Claude Desktop are copies that nothing updates:
`npx skills-il update` and `gh skill update` only manage skills they installed
themselves. This script reads each installed skill's metadata.json, compares
its version with the skill's category repo on GitHub, downloads every outdated
skill and verifies its Sigstore build attestation with `gh attestation verify`.

  * Uploaded skills (the Claude Desktop cache of claude.ai skills): a zip ready
    for Customize -> Skills -> "+" -> Upload a skill. Uploading stays manual,
    because claude.ai has no API for it.
  * Local skills (~/.claude/skills, or --skills-dir): with --install-local the
    verified folder replaces the old one, after a backup to ~/.claude/skill-backups.
  * Skills installed by `npx skills-il add -g` (listed in ~/.agents/.skill-lock.json):
    checked read-only, by commits since install and by SKILL.md content, and the
    exact npx command to update them is printed. Their folders are never touched.

Standard library only. Downloaded files are written and zipped, never executed.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API = 'https://api.github.com'
RAW = 'https://raw.githubusercontent.com'
SKIP_NAMES = {'__pycache__', '.DS_Store', 'Thumbs.db', 'desktop.ini'}
VERIFY_FILES = ('SKILL.md', 'metadata.json')
HOME = os.path.expanduser('~')
BACKUP_ROOT = os.path.join(HOME, '.claude', 'skill-backups')
# Written by `npx skills-il add -g`. The CLI drops metadata.json, and when it cannot
# reach the GitHub API during install (an expired GITHUB_TOKEN is enough) it records
# an empty skillFolderHash without a warning; `npx skills-il check` then reports
# "No version hash available" and never updates that skill.
CLI_LOCK = os.path.join(HOME, '.agents', '.skill-lock.json')


def default_skill_roots():
    """(path, kind) for every place Claude Desktop and Claude Code keep installed skills."""
    uploaded = [
        # Claude Desktop on Windows: skills uploaded to claude.ai are synced here
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-Data', '*', 'local-agent-mode-sessions',
                     'skills-plugin', '*', '*', 'skills'),
        # Claude Desktop on macOS (best effort; pass --skills-dir if your path differs)
        os.path.join(HOME, 'Library', 'Application Support', 'Claude*', '*', 'local-agent-mode-sessions',
                     'skills-plugin', '*', '*', 'skills'),
    ]
    roots = [(p, 'uploaded') for pattern in uploaded for p in glob.glob(pattern) if os.path.isdir(p)]
    local = os.path.join(HOME, '.claude', 'skills')
    if os.path.isdir(local):
        roots.append((local, 'local'))
    return roots


def kind_of(path):
    # The app re-syncs its skill cache from the account and would overwrite any
    # local edit, so a folder inside it is always treated as uploaded.
    return 'uploaded' if 'skills-plugin' in path.replace('\\', '/').split('/') else 'local'


def find_installed(roots, author):
    installs = []
    for root, kind in roots:
        for meta_path in glob.glob(os.path.join(root, '*', 'metadata.json')):
            try:
                with open(meta_path, encoding='utf-8') as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            if meta.get('author') != author:
                continue
            path = os.path.dirname(meta_path)
            installs.append({'name': os.path.basename(path), 'version': meta.get('version', '0.0.0'),
                             'category': meta.get('category'), 'path': path, 'kind': kind})
    return sorted(installs, key=lambda s: (s['name'], s['kind']))


def read_cli_lock(path=CLI_LOCK):
    try:
        with open(path, encoding='utf-8') as f:
            skills = json.load(f).get('skills', {})
    except (OSError, ValueError):
        return []
    entries = []
    for name, e in skills.items():
        if e.get('sourceType') != 'github' or not e.get('source') or not e.get('skillPath'):
            continue
        folder = next((p for p in (os.path.join(HOME, '.claude', 'skills', name), os.path.join(HOME, '.agents', 'skills', name))
                       if os.path.isdir(p)), None)
        entries.append({'name': name, 'source': e['source'], 'dir': os.path.dirname(e['skillPath']).replace('\\', '/'),
                        'since': e.get('updatedAt') or e.get('installedAt'), 'path': folder})
    return entries


def changelog_version(folder):
    """The CLI drops metadata.json, so read the installed version from CHANGELOG.md when there is one."""
    try:
        with open(os.path.join(folder, 'CHANGELOG.md'), encoding='utf-8') as f:
            m = re.search(r'^##\s*\[?v?(\d+\.\d+\.\d+)', f.read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def check_cli(entry, token):
    """Read-only check of a CLI-installed skill. Returns (latest_version, outdated, reason)."""
    repo, d = entry['source'], entry['dir']
    reasons = []
    if entry['since']:
        since = urllib.parse.quote(entry['since'])
        commits = fetch(f'{API}/repos/{repo}/commits?path={urllib.parse.quote(d)}&since={since}&per_page=20', token)
        if commits:
            reasons.append(f'{len(commits)} commit(s) since install')
    try:
        latest = fetch(f'{RAW}/{repo}/HEAD/{urllib.parse.quote(d)}/metadata.json', token).get('version')
    except (urllib.error.URLError, ValueError):
        latest = None
    # A skill installed from an older tag has no newer commits after its install
    # date, so compare the instructions too. The CLI writes CRLF on Windows.
    if entry['path'] and os.path.exists(os.path.join(entry['path'], 'SKILL.md')):
        upstream = fetch(f'{RAW}/{repo}/HEAD/{urllib.parse.quote(d)}/SKILL.md', token, raw=True)
        with open(os.path.join(entry['path'], 'SKILL.md'), 'rb') as f:
            local = f.read()
        if local.replace(b'\r\n', b'\n') != upstream.replace(b'\r\n', b'\n'):
            reasons.append('SKILL.md differs from the latest version')
    return latest, bool(reasons), '; '.join(reasons)


def npx_update_command(entry):
    return f'npx skills-il add {entry["source"]} --skill {entry["name"]} -g -a claude-code -y'


def parse_version(v):
    nums = [int(x) for x in re.findall(r'\d+', str(v or '0'))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def github_token():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token or not shutil.which('gh'):
        return token
    try:
        out = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def fetch(url, token, raw=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'skills-il-updater'})
    if token and url.startswith(API):
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data if raw else json.loads(data.decode('utf-8'))


def upstream_version(owner, skill, token):
    url = f'{RAW}/{owner}/{skill["category"]}/HEAD/{urllib.parse.quote(skill["name"])}/metadata.json'
    return fetch(url, token).get('version')


def download_skill(owner, skill, token, dest):
    repo = f'{owner}/{skill["category"]}'
    name = skill['name']
    commits = fetch(f'{API}/repos/{repo}/commits?path={urllib.parse.quote(name)}&per_page=1', token)
    sha = commits[0]['sha']
    tree = fetch(f'{API}/repos/{repo}/git/trees/{sha}?recursive=1', token)
    prefix = name + '/'
    for entry in tree.get('tree', []):
        path = entry['path']
        if entry['type'] != 'blob' or not path.startswith(prefix):
            continue
        if any(part in SKIP_NAMES for part in path.split('/')):
            continue
        target = os.path.join(dest, *path.split('/'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as f:
            f.write(fetch(f'{RAW}/{repo}/{sha}/{urllib.parse.quote(path)}', token, raw=True))
    return os.path.join(dest, name)


def verify(folder, owner):
    """Return (ok, detail). ok is None when verification could not run."""
    if not shutil.which('gh'):
        return None, 'gh CLI not found; install gh 2.49+ to verify signatures'
    for fname in VERIFY_FILES:
        path = os.path.join(folder, fname)
        if not os.path.exists(path):
            return False, f'{fname} missing'
        res = subprocess.run(['gh', 'attestation', 'verify', path, '--owner', owner],
                             capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            out = (res.stderr or res.stdout).strip()
            if '404' in out:
                return False, f'{fname}: no signed {owner} release contains this exact file'
            lines = out.splitlines()
            return False, f'{fname}: {lines[-1] if lines else "verification failed"}'
    return True, 'Sigstore attestation verified for ' + ', '.join(VERIFY_FILES)


def build_zip(folder, name, version, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f'{name}-v{version}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, dns, fns in os.walk(folder):
            dns[:] = [d for d in dns if d not in SKIP_NAMES]
            for fn in sorted(fns):
                if fn in SKIP_NAMES or fn.endswith('.pyc'):
                    continue
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, folder).replace(os.sep, '/')
                z.write(full, f'{name}/{rel}')
    return zip_path


def install_local(folder, install, backup_root):
    """Replace a local skill folder with the verified one; the old folder moves to a backup."""
    target = install['path']
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(backup_root, f'{install["name"]}-v{install["version"]}-{stamp}')
    staged = target + '.new'
    shutil.rmtree(staged, ignore_errors=True)
    shutil.copytree(folder, staged, ignore=shutil.ignore_patterns(*SKIP_NAMES, '*.pyc'))
    os.makedirs(backup_root, exist_ok=True)
    shutil.move(target, backup)
    try:
        os.replace(staged, target)
    except OSError:
        shutil.move(backup, target)  # put the old version back rather than leave a gap
        raise
    return backup


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--skills-dir', action='append', default=[],
                    help='extra folder that contains installed skill folders (repeatable)')
    ap.add_argument('--author', default='skills-il', help='metadata.json author to check (default: skills-il)')
    ap.add_argument('--owner', default='skills-il', help='GitHub org that hosts the category repos')
    ap.add_argument('--out', default=os.path.join(os.getcwd(), 'skill-updates'),
                    help='folder for the upload zips (default: ./skill-updates)')
    ap.add_argument('--check-only', action='store_true', help='report versions, download nothing')
    ap.add_argument('--install-local', action='store_true',
                    help='replace outdated local skills in place (after verification and a backup)')
    ap.add_argument('--backup-dir', default=BACKUP_ROOT,
                    help=f'where replaced local skills are kept (default: {BACKUP_ROOT})')
    ap.add_argument('--allow-unverified', action='store_true',
                    help='build a zip even when the signature check fails or cannot run (never installs)')
    ap.add_argument('--json', action='store_true', help='print a JSON report instead of a table')
    args = ap.parse_args()

    roots = default_skill_roots() + [(d, kind_of(os.path.abspath(d))) for d in args.skills_dir]
    cli_entries = read_cli_lock()
    cli_names = {e['name'] for e in cli_entries}
    # A folder the skills-il CLI owns is never replaced by this script, even if it kept metadata.json.
    installs = [i for i in find_installed(roots, args.author) if not (i['kind'] == 'local' and i['name'] in cli_names)]
    token = github_token()
    latest_cache = {}
    report = []
    for entry in cli_entries:
        row = {'name': entry['name'], 'kind': 'cli', 'path': entry['path'], 'category': None,
               'version': (changelog_version(entry['path']) if entry['path'] else None) or '?',
               'latest': None, 'status': '', 'zip': None, 'backup': None, 'verification': None,
               'action': None, 'command': None}
        report.append(row)
        try:
            row['latest'], outdated, reason = check_cli(entry, token)
        except (urllib.error.URLError, ValueError, KeyError, OSError) as e:
            row['status'] = f'lookup failed: {e}'
            continue
        if outdated:
            row['command'] = npx_update_command(entry)
            row['status'] = f'update available ({reason}); folder left to the skills-il CLI'
            row['action'] = 'cli'
        else:
            row['status'] = 'up to date'
    for inst in installs:
        row = dict(inst, latest=None, status='', zip=None, backup=None, verification=None, action=None, command=None)
        report.append(row)
        if not inst.get('category'):
            row['status'] = 'no category in metadata.json; cannot locate repo'
            continue
        try:
            if inst['name'] not in latest_cache:
                latest_cache[inst['name']] = upstream_version(args.owner, inst, token)
            row['latest'] = latest_cache[inst['name']]
        except (urllib.error.URLError, ValueError, KeyError) as e:
            row['status'] = f'lookup failed: {e}'
            continue
        if parse_version(row['latest']) <= parse_version(inst['version']):
            row['status'] = 'up to date'
            continue
        # The skills-il CLI links each agent folder to one canonical copy: a symlink,
        # or on Windows often a directory junction, which os.path.islink does not see.
        linked = os.path.islink(inst['path']) or getattr(os.path, 'isjunction', lambda p: False)(inst['path'])
        cli_managed = inst['kind'] == 'local' and linked
        if cli_managed:
            row['status'] = 'linked folder, left alone; if the skills-il CLI installed it, run npx skills-il update'
            row['action'] = 'cli'
            continue
        if args.check_only:
            row['status'] = 'update available'
            row['action'] = 'manual' if inst['kind'] == 'uploaded' or not args.install_local else 'auto'
            continue
        tmp = tempfile.mkdtemp(prefix='skill-update-')
        try:
            folder = download_skill(args.owner, inst, token, tmp)
            ok, detail = verify(folder, args.owner)
            row['verification'] = detail
            if inst['kind'] == 'local' and args.install_local:
                if ok:
                    row['backup'] = install_local(folder, inst, args.backup_dir)
                    row['status'] = 'updated in place'
                    row['action'] = 'done'
                else:
                    row['status'] = 'not installed: signature not verified'
                    row['action'] = 'blocked'
            elif ok or args.allow_unverified:
                row['zip'] = build_zip(folder, inst['name'], row['latest'], args.out)
                row['status'] = 'zip ready, upload it' if ok else 'zip ready (UNVERIFIED), upload it'
                row['action'] = 'manual'
            else:
                row['status'] = 'update available; zip withheld, signature not verified'
                row['action'] = 'blocked'
        except (urllib.error.URLError, ValueError, KeyError, OSError, subprocess.SubprocessError) as e:
            row['status'] = f'failed: {e}'
            row['action'] = 'blocked'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    outdated = [r for r in report if r['action'] == 'cli' or
                (r['latest'] and r['kind'] != 'cli' and parse_version(r['latest']) > parse_version(r['version']))]
    summary = {
        'updates': len(outdated),
        'installed': sum(1 for r in outdated if r['action'] == 'done'),
        'manual': sum(1 for r in outdated if r['action'] in ('manual', 'cli', 'blocked')),
    }
    if args.json:
        print(json.dumps({'roots': [r for r, _ in roots], 'skills': report, **summary}, ensure_ascii=False, indent=2))
        return 0
    if not report:
        print(f'No installed skills by "{args.author}" found in: ' + ('; '.join(r for r, _ in roots) or 'no skill folders'))
    for r in report:
        print(f'{r["name"]:<32} {r["kind"]:<8} {r["version"]:>8} -> {str(r["latest"] or "?"):<8} {r["status"]}')
        for extra in ('verification', 'zip', 'backup', 'command'):
            if r[extra]:
                label = {'backup': 'backup: ', 'command': 'run: '}.get(extra, '')
                print(f'{"":<41} {label}{r[extra]}')
    print(f'UPDATES: {summary["updates"]}  INSTALLED: {summary["installed"]}  MANUAL: {summary["manual"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
