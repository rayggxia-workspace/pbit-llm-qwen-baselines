"""Use the packaged rasterizer with a native Word PDF, since soffice is absent."""
from pathlib import Path
import importlib.util,shutil,tempfile
P=Path(__file__).resolve().parent
ROOT=P.parents[2]
skill=Path('C:/Users/86134/.codex/plugins/cache/openai-primary-runtime/documents/26.1020.11618/skills/documents/render_docx.py')
s=importlib.util.spec_from_file_location('renderer',skill);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
td=P/'render_tmp';td.mkdir(exist_ok=True);tempfile.tempdir=str(td)
def native(doc_path,user_profile,convert_tmp_dir,stem,verbose=False):
    target=Path(convert_tmp_dir)/(stem+'.pdf')
    shutil.copyfile(P/'render/word_export.pdf',target)
    return str(target),'Native Microsoft Word PDF; LibreOffice unavailable; document unchanged.'
m.convert_to_pdf=native
pages=m.rasterize(str(ROOT/'architecture_tlm/memory_savings_20261023/概率计算架构的SRAM与DRAM节省总结.docx'),str(P/'render'),150,verbose=False,emit_pdf=False)
print('Rasterized pages',len(pages))
