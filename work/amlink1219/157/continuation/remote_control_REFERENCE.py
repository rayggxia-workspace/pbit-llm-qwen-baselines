"""Small SSH staging/monitoring helpers. No credentials or heavyweight login work."""
from pathlib import Path
import json
import os
import re
import shlex
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
attempt = os.environ.get('PDNN_ATTEMPT', '')
if attempt and not re.fullmatch('[a-zA-Z0-9_-]+', attempt):
    raise ValueError('unsafe attempt name')
OUT = BASE/attempt if attempt else BASE
OUT.mkdir(exist_ok=True)
SSH = 'C:/Windows/System32/OpenSSH/ssh.exe'
SCP = 'C:/Windows/System32/OpenSSH/scp.exe'
KEY = 'C:/Users/A/.ssh/id_ed25519_lerobot_gpu'
OPTIONS = ['-i', KEY, '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
           '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=10',
           '-o', 'ServerAliveCountMax=2']
HOST = 'Weican_Chen@10.129.164.156'
PERSONAL = '/home/Weican_Chen'
PROJECT = PERSONAL + '/projects/pbit-pdnn-task-accuracy-issue145'
PYTHON = PERSONAL + '/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python'
GUARD = '''set -euo pipefail
test "$(id -un)" = Weican_Chen
test "$(getent passwd Weican_Chen | cut -d: -f6)" = /home/Weican_Chen
test "$(readlink -f /home/Weican_Chen)" = /home/Weican_Chen
test "$(stat -c %U /home/Weican_Chen)" = Weican_Chen
test "$(realpath -e /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145)" = /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145
test "$(stat -c %U /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145)" = Weican_Chen
'''


def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def ssh(script, timeout=45):
    result = subprocess.run([SSH, *OPTIONS, '-p', '21570', HOST,
                             'bash -lc '+shlex.quote(script)],
                            capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'SSH exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def transfer(local, remote, download=False):
    args = [SCP, *OPTIONS, '-P', '21570']
    args += [HOST+':'+remote, str(local)] if download else [str(local), HOST+':'+remote]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        raise RuntimeError(f'SCP exit {result.returncode}\n{result.stdout}\n{result.stderr}')


def queues():
    from concurrent.futures import ThreadPoolExecutor
    known = ROOT/'.agents/skills/slurm-ssh-compute/references/known_hosts'
    profiles = [('primary', HOST, '21570', 'Weican_Chen', '/opt/slurm/21.08.8/bin/squeue'),
                ('fallback144', 'pwmat@162.105.201.144', '22', 'pwmat', '/usr/bin/squeue'),
                ('fallback155', 'pwmat@162.105.201.155', '22', 'pwmat', '/usr/bin/squeue')]
    def check(item):
        name, host, port, user, queue = item
        opts = [] if name == 'primary' else ['-o', 'UserKnownHostsFile='+str(known), '-o', 'StrictHostKeyChecking=yes']
        command = 'set -eu\ntest "$(id -un)" = '+user+'\nhostname\n'+queue+' -u '+user+" -o '%i %P %j %T %R %b'"
        result = subprocess.run([SSH, *OPTIONS, *opts, '-p', port, host,
                                 'bash -lc '+shlex.quote(command)], capture_output=True,
                                text=True, encoding='utf-8', timeout=40)
        return dict(profile=name, host=host, returncode=result.returncode,
                    stdout=result.stdout, stderr=result.stderr)
    with ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(check, profiles))
    save('queues_latest.json', result)
    if any(row['returncode'] for row in result):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'queues':
        print(json.dumps(queues(), ensure_ascii=False))
    elif sys.argv[1] == 'inventory':
        result = ssh(GUARD+'''find /home/Weican_Chen/projects -mindepth 1 -maxdepth 1 -user Weican_Chen -type d -iname '*pbit*' -printf '%f\n'
''')
        (OUT/'personal_pbit_projects.txt').write_text(result, encoding='utf-8', newline='\n')
        print(result)
    else:
        raise ValueError('unknown action')
