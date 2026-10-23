#!/usr/bin/env python3
"""Check uploaded Skills IL skills for newer versions and build verified upload zips.

Skills uploaded to claude.ai / Claude Desktop live outside the reach of
`npx skills-il update` and `gh skill update`, which only manage skills they
installed themselves. This script reads each installed skill's metadata.json,
compares its version with the skill's category repo on GitHub, and for every
outdated skill downloads the latest folder, verifies its Sigstore build
attestation with `gh attestation verify`, and packs a zip ready for
Customize -> Skills -> "+" -> Upload a skill.

Standard library only. Downloaded files are written and zipped, never executed.
"""

import argparse
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


def default_skill_roots():
    """Places where Claude Desktop and Claude Code keep installed skills."""
    home = os.path.expanduser('~')
    patterns = [
        # Claude Desktop on Windows: skills uploaded to claude.ai are synced here
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-Data', '*', 'local-agent-mode-sessions',
                     'skills-plugin', '*', '*', 'skills'),
        # Claude Desktop on macOS (best effort; pass --skills-dir if your path differs)
        os.path.join(home, 'Library', 'Application Support', 'Claude*', '*', 'local-agent-mode-sessions',
                     'skills-plugin', '*', '*', 'skills'),
        # Claude Code, user level
        os.path.join(home, '.claude', 'skills'),
    ]
    roots = []
    for pattern in patterns:
        roots.extend(p for p in glob.glob(pattern) if os.path.isdir(p))
    return roots


def find_installed(roots, author):
    found = {}
    for root in roots:
        for meta_path in glob.glob(os.path.join(root, '*', 'metadata.json')):
            try:
                with open(meta_path, encoding='utf-8') as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            if meta.get('author') != author:
                continue
            name = os.path.basename(os.path.dirname(meta_path))
            # The same skill can sit in two roots; keep the lowest version so an
            # outdated copy is never hidden by a current one.
            prev = found.get(name)
            if prev is None or parse_version(meta.get('version')) < parse_version(prev['version']):
                found[name] = {'name': name, 'version': meta.get('version', '0.0.0'),
                               'category': meta.get('category'), 'path': os.path.dirname(meta_path)}
    return sorted(found.values(), key=lambda s: s['name'])


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
    return sha


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--skills-dir', action='append', default=[],
                    help='extra folder that contains installed skill folders (repeatable)')
    ap.add_argument('--author', default='skills-il', help='metadata.json author to check (default: skills-il)')
    ap.add_argument('--owner', default='skills-il', help='GitHub org that hosts the category repos')
    ap.add_argument('--out', default=os.path.join(os.getcwd(), 'skill-updates'),
                    help='folder for the upload zips (default: ./skill-updates)')
    ap.add_argument('--check-only', action='store_true', help='report versions, download nothing')
    ap.add_argument('--allow-unverified', action='store_true',
                    help='build a zip even when the signature check fails or cannot run')
    ap.add_argument('--json', action='store_true', help='print a JSON report instead of a table')
    args = ap.parse_args()

    roots = default_skill_roots() + args.skills_dir
    installed = find_installed(roots, args.author)
    token = github_token()
    report = []
    for skill in installed:
        row = dict(skill, latest=None, status='', zip=None, verification=None)
        report.append(row)
        if not skill.get('category'):
            row['status'] = 'no category in metadata.json; cannot locate repo'
            continue
        try:
            row['latest'] = upstream_version(args.owner, skill, token)
        except (urllib.error.URLError, ValueError, KeyError) as e:
            row['status'] = f'lookup failed: {e}'
            continue
        if parse_version(row['latest']) <= parse_version(skill['version']):
            row['status'] = 'up to date'
            continue
        if args.check_only:
            row['status'] = 'update available'
            continue
        tmp = tempfile.mkdtemp(prefix='skill-update-')
        try:
            folder = os.path.join(tmp, skill['name'])
            download_skill(args.owner, skill, token, tmp)
            ok, detail = verify(folder, args.owner)
            row['verification'] = detail
            if ok or args.allow_unverified:
                row['zip'] = build_zip(folder, skill['name'], row['latest'], args.out)
                row['status'] = 'zip ready' if ok else 'zip ready (UNVERIFIED)'
            else:
                row['status'] = 'update available; zip withheld, signature not verified'
        except (urllib.error.URLError, ValueError, KeyError, OSError, subprocess.SubprocessError) as e:
            row['status'] = f'download failed: {e}'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    pending = sum(1 for r in report if r['latest'] and parse_version(r['latest']) > parse_version(r['version']))
    if args.json:
        print(json.dumps({'roots': roots, 'skills': report, 'updates': pending}, ensure_ascii=False, indent=2))
        return 0
    else:
        if not report:
            print(f'No installed skills by "{args.author}" found in: ' + ('; '.join(roots) or 'no skill folders'))
        for r in report:
            print(f'{r["name"]:<34} {r["version"]:>8} -> {str(r["latest"] or "?"):<8} {r["status"]}')
            if r['verification']:
                print(f'{"":<34} {r["verification"]}')
            if r['zip']:
                print(f'{"":<34} {r["zip"]}')
    print(f'UPDATES: {pending}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
