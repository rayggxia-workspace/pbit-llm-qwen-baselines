"""Allocation-only text/tokenizer and new-article count gate; no LLM forward."""
from pathlib import Path
import argparse, json, os, time
from .capture_teacher import digest,parse_documents,select_documents
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));start=time.time()
 assert digest(cfg['text'])==cfg['expected_text_sha256']
 from transformers import AutoTokenizer
 tokenizer=AutoTokenizer.from_pretrained(cfg['model'],local_files_only=True)
 documents=parse_documents(Path(cfg['text']).read_text(encoding='utf-8'))
 selected,selection=select_documents(documents,lambda text:tokenizer.encode(text,add_special_tokens=False),context=cfg['context'],train_docs=cfg['train_docs'],val_docs=cfg['val_docs'],holdout_docs=cfg['holdout_docs'],seed=cfg['capture_seed'],exclude_document_sha256=cfg['exclude_document_sha256'],exclude_truncated_token_sha256=cfg['exclude_truncated_token_sha256'])
 out=Path(a.output).resolve();assert out.is_relative_to(Path('/home/Weican_Chen').resolve());out.mkdir(exist_ok=False,parents=True)
 result={'status':'passed','job':os.environ['SLURM_JOB_ID'],'selection':selection,'split_docs':{str(i):sum(d['split']==i for d in selected) for i in [0,1,2]},'config_sha256':digest(a.config),'seconds':time.time()-start,'no_model_loaded':True,'device':'cpu','source_commit':os.environ.get('GATE_SOURCE_COMMIT')}
 (out/'SELECTION_PREFLIGHT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result))
if __name__=='__main__':main()
