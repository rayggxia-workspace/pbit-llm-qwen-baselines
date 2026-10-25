from pathlib import Path
import importlib.util,subprocess,json
A=Path(__file__).resolve().parent;W=A.parent.parent/'tmp/pr55-review-round11-20261025'
p=W/'work/jieruiz/182/audit_cross_group_pipeline.py'
s=importlib.util.spec_from_file_location('review_audit',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
# Reapply the independent small-case assertions to PR190's current code,
# recording its actual commit instead of claiming to execute the old snapshot.
m.COMMIT=subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD']).decode().strip()
m.main()
