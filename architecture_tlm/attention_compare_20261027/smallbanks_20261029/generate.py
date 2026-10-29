"""Generate small real SRAMs; retain rejected configurations. Run under Slurm.

Vendor libraries remain on the authorized EDA host. This is library extraction,
not transistor simulation or measured post-layout array power.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'extractor'))
from extract import extract

def save(p, obj):
    p.write_bytes((json.dumps(obj, indent=2) + '\n').encode('utf-8'))

def main():
    root = Path(os.environ['SB_RESULTS'])
    root.mkdir(exist_ok=False)
    results = []
    for depth, width in [(128, 1), (64, 2), (32, 4), (128, 2), (128, 128)]:
        name = 'SB_D%d_W%d' % (depth, width)
        req = dict(id=name, macro_name=name, requested_depth=depth,
                   requested_word_bits=width, compiler_corner='SS1P08V125CCMAX',
                   voltage_V=1.08, temperature_C=125, role='small_bank_candidate')
        for mux in [4, 8]:
            d = root / (name + '_M%d' % mux)
            d.mkdir()
            cmd = ['minder', '-ip', 'TMHDSPZ055ABA', '-ipver', '0.1.0',
                   '-word', str(depth), '-bits', str(width), '-mux', str(mux),
                   '-vt', '0', '-lpwr', '0', '-red', '0', '-wordwrite', '0',
                   '-busmode', '1', '-ringtype', 'ringless', '-corner', req['compiler_corner'],
                   '-rename', name, '-ds', '-ver', '-lib', '-lef']
            save(d / 'request.json', req)
            save(d / 'command.json', cmd)
            with (d / 'generation.log').open('w') as f:
                p = subprocess.run(cmd, cwd=str(d), stdout=f, stderr=subprocess.STDOUT)
            result = dict(request=req, mux=mux, returncode=p.returncode, directory=d.name)
            try:
                if p.returncode != 0:
                    raise RuntimeError('compiler returned nonzero')
                manifest, summaries = extract(d, req)
                assert manifest['mux'] == mux
                result.update(status='EXTRACTED_NOT_SIMULATED', manifest=manifest, summaries=summaries)
            except Exception as e:
                result.update(status='REJECTED_OR_EXTRACTION_FAILED', error=str(e))
            result['generation_log_sha256'] = hashlib.sha256((d / 'generation.log').read_bytes()).hexdigest()
            results.append(result)
            save(root / 'RESULTS.json', results)
            print(name, mux, result['status'], flush=True)
            if result['status'] == 'EXTRACTED_NOT_SIMULATED':
                break
    save(root / 'COMPLETE.json', dict(attempts=len(results), successful=sum(r['status']=='EXTRACTED_NOT_SIMULATED' for r in results)))

if __name__ == '__main__':
    main()
