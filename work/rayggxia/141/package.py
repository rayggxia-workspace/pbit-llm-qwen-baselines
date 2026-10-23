"""Export exact committed blobs, not Windows checkout-normalized source."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
areas=['experiments/'+x for x in ['qwen_parallel_sampler_ppl_20261023','qwen_joint_stratified_attention_20261019','qwen_multiscale_stratified_20261019','qwen_fixedw_multiscale_20261019','qwen_dual_range_20261018','qwen_dual_iid_exact_20261018','attention_e01','pbit_sampler_qkv_20261021','qwen_ising_broadcast_20261021']]
names=subprocess.check_output(['git','ls-tree','-r','--name-only',sha,'--',*areas],cwd=root,text=True).splitlines()
out=root/'work/rayggxia/141'/('source-'+sha+'.tar')
if out.exists():raise FileExistsError(out)
manifest={'code_commit':sha,'files':{}}
with tarfile.open(out,'w') as tar:
    for name in names:
        blob=subprocess.check_output(['git','cat-file','blob',sha+':'+name],cwd=root)
        manifest['files'][name]=hashlib.sha256(blob).hexdigest()
        info=tarfile.TarInfo(name);info.size=len(blob);tar.addfile(info,io.BytesIO(blob))
    raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    info=tarfile.TarInfo('SOURCE_MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
receipt={'code_commit':sha,'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'files':len(names)}
(root/'work/rayggxia/141/PACKAGE.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
