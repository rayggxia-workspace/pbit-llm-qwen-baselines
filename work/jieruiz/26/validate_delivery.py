"""Document-only checks. Does not download sources or run model/hardware tests."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user-copy', type=Path)
    ap.add_argument('--verify-local-sources', action='store_true')
    ap.add_argument('--git-ref', help='HEAD, commit, or : for staged blob bytes')
    args = ap.parse_args()
    manifest = json.loads((WORK / 'MANIFEST.json').read_text(encoding='utf-8'))
    evidence = json.loads((WORK / 'SOURCE_EVIDENCE.json').read_text(encoding='utf-8'))
    records = [manifest['document'], manifest['evidence']]
    for record in records:
        data = (ROOT / record['path']).read_bytes()
        assert sha(data) == record['sha256'], record['path']
        assert b'\r' not in data and data.endswith(b'\n')
        data.decode('utf-8')
        if args.git_ref:
            ref = ':' if args.git_ref == ':' else args.git_ref + ':'
            saved = subprocess.check_output(['git', 'show', ref + record['path']], cwd=ROOT)
            assert saved == data, 'Git bytes differ: ' + record['path']
    body = (ROOT / manifest['document']['path']).read_text(encoding='utf-8')
    table = re.search(r'\| # \| 文献/资料.*?(?=\n\n)', body, re.S).group(0)
    assert [int(n) for n in re.findall(r'^\| (\d+) \|', table, re.M)] == list(range(1, 18))
    assert len(re.findall(r'^### (?:2\.[1-6]|3\.\d+) ', body, re.M)) == 17
    assert len(evidence['coverage']) == 17
    assert evidence['no_full_text'] == [], 'All17 full sources are now available'
    assert evidence['devices_three']['current_digitizers']['main_text_status'].startswith('FULL')
    assert '17项现在均已取得全文' in body
    assert all(link.startswith('https://') for link in re.findall(r'\]\(([^\n)]+)\)', body))
    checked = 0
    if args.verify_local_sources:
        for item in evidence['all_checked_local_source_bytes']:
            assert sha(Path(item['local_path']).read_bytes()) == item['sha256'], item['local_path']
            checked += 1
        source = Path(evidence['original_list']['path'])
        assert sha(source.read_bytes()) == evidence['original_list']['sha256']
    if args.user_copy:
        assert args.user_copy.read_bytes() == (ROOT / manifest['document']['path']).read_bytes()
    print(json.dumps({'status': 'PASS', 'individual_reviews': 17,
                      'abstract_only': [], 'source_byte_checks': checked,
                      'same_byte_copy_checked': bool(args.user_copy),
                      'git_blob_ref': args.git_ref,
                      'document_sha256': manifest['document']['sha256']}))


if __name__ == '__main__':
    main()
