"""Use existing endpoint-bound local client; never log or relocate credentials."""
from pathlib import Path
import hashlib,json,shutil,stat,sys,time
ROOT=Path(__file__).resolve().parents[5]
TASK=ROOT/'tmp/normal-readout-issue184-20261025'
SRC=TASK/'architecture_tlm/physical_rng_sampled_readout/src'
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'local_tools/paracloud_client'))
import client
REMOTE='/public3/home/t6s011227/analog_pbit_20261016/sampled_readout_v1'
COMMIT='be26000c2c401befa13eb7b2b1bde2e11e52a9e2'
def sha(data):return hashlib.sha256(data).hexdigest()
def remote(ssh,command,timeout=120):
    channel=ssh.get_transport().open_session(timeout=30)
    try:
        channel.settimeout(30);channel.exec_command(command);channel.shutdown_write()
        stdout,stderr=bytearray(),bytearray();deadline=time.monotonic()+timeout
        while True:
            if channel.recv_ready():stdout.extend(channel.recv(32768))
            if channel.recv_stderr_ready():stderr.extend(channel.recv_stderr(32768))
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                return channel.recv_exit_status(),bytes(stdout),bytes(stderr)
            if time.monotonic()>deadline:raise TimeoutError('Remote command timed out; inspect queue/logs before retrying')
            time.sleep(.02)
    finally:channel.close()

manifest=json.loads((SRC/'package_manifest.json').read_text(encoding='utf-8'))
assert sha((SRC/'package_manifest.json').read_bytes())=='9df7309709ebe6748479b0c66b19756c6198247508b544c503983d57a8f5ca27'
upload=ROOT/'远端上传/sampled_readout_v1'
if not upload.exists():
    upload.mkdir()
    for name in list(manifest)+['package_manifest.json']:shutil.copyfile(SRC/name,upload/name)
for name,h in manifest.items():assert sha((upload/name).read_bytes())==h
receipt=WORK/'SUBMISSION_SAMPLED_20261025.json'
if receipt.exists():raise FileExistsError('Original submission receipt exists; inspect existing job')
password=client.load_password()
try:
    with client.connect(password) as ssh:
        code,stdout,stderr=remote(ssh,"hostname; squeue -u t6s011227 -o '%.18i %.12j %.8T %.10M %R'",30)
        if code:raise RuntimeError('Read-only queue check failed')
        (WORK/'sampled_queue_before_submission.txt').write_bytes(stdout+stderr)
        with ssh.open_sftp() as sftp:
            sftp.get_channel().settimeout(30)
            try:info=sftp.lstat(REMOTE)
            except FileNotFoundError:sftp.mkdir(REMOTE);info=sftp.lstat(REMOTE)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=23785:raise RuntimeError('Unexpected upload directory type/owner')
            for name in list(manifest)+['package_manifest.json']:
                data=(upload/name).read_bytes();destination=REMOTE+'/'+name
                try:
                    with sftp.open(destination,'rb') as f:existing=f.read()
                except FileNotFoundError:existing=None
                if existing is not None:
                    if existing!=data:raise RuntimeError('Existing remote file differs; no overwrite: '+name)
                else:
                    with sftp.open(destination,'wx') as f:f.write(data)
            print('UPLOADED25FILES_NO_ARCHIVE',flush=True)
        command="cd "+REMOTE+"\nexport STUDY_PYTHON=/usr/bin/python3\nexport SAMPLED_SOURCE_COMMIT="+COMMIT+"\nbash submit.sh"
        code,stdout,stderr=remote(ssh,command,150)
        (WORK/'sampled_submission_stdout.txt').write_bytes(stdout);(WORK/'sampled_submission_stderr.txt').write_bytes(stderr)
        print(stdout.decode('utf-8','replace'));print(stderr.decode('utf-8','replace'),file=sys.stderr)
        if code:raise RuntimeError('Submission command failed; inspect logs before retrying')
        text=stdout.decode('utf-8');line=next(line for line in text.splitlines() if line.startswith('JOB='));job=int(line.split('=')[1])
        info=dict(job=job,remote_root=REMOTE,source_commit=COMMIT,source_manifest_sha256=sha((SRC/'package_manifest.json').read_bytes()),
            config_sha256=sha((SRC/'config.json').read_bytes()),allocated_CPUs=8,threads_per_case=1,workers=8,
            compute_budget_hours=6,walltime='06:15:00',local_upload=str(upload),source_files=25,submission_exit=code)
        receipt.write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8',newline='\n')
        print('SUBMISSION_RECEIPT_SAVED',job,flush=True)
finally:
    del password
