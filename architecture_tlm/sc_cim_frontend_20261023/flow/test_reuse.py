import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import run


class ReuseTests(unittest.TestCase):
    def test_hash_bound_reuse_and_mismatch_rejection(self):
        with tempfile.TemporaryDirectory(dir=str(run.ROOT.parent)) as directory:
            base=Path(directory);old=base/'old';out=base/'new';src=base/'src'
            old.mkdir();out.mkdir();(src/'rtl').mkdir(parents=True);(old/'net').mkdir()
            (src/'rtl/core.sv').write_bytes(b'module core; endmodule\n')
            lib=base/'lib.db';model=base/'model.v';lib.write_bytes(b'lib');model.write_bytes(b'model')
            env={k:'1' for k in ['CIM_KIND','CIM_N','CIM_M','CIM_T','CIM_K','CIM_EXT','PPA_CORNER','LOAD_PF','INPUT_SLEW_NS','BUF_REF']}
            env.update(STD_DB=str(lib),STD_MODEL=str(model))
            (old/'CONFIG.json').write_text(json.dumps(env))
            (old/'SOURCE.json').write_text(json.dumps({'rtl/core.sv':run.digest(src/'rtl/core.sv')}))
            (old/'INPUT_BINDING.json').write_text(json.dumps({'libraries':{k:{'sha256':run.digest(Path(env[k]))} for k in ['STD_DB','STD_MODEL']}}))
            (old/'COMMANDS.json').write_text(json.dumps([{'command':['dc_shell'],'exit_code':0}]))
            for name in ['SYNTH_COMPLETE','mapped.v','mapped.sdc']:(old/'net'/name).write_bytes(b'evidence\n')
            with patch.object(run,'ROOT',src):
                net=run.reuse_synthesis(old,out,env)
                self.assertEqual((net/'mapped.v').read_bytes(),b'evidence\n')
                self.assertTrue((out/'REUSE_SYNTHESIS.json').is_file())
                bad=dict(env,CIM_M='64')
                with self.assertRaisesRegex(ValueError,'config mismatch'):run.reuse_synthesis(old,out,bad)
                lib.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'library mismatch'):run.reuse_synthesis(old,out,env)

    def test_vcs_default_timescale(self):
        self.assertIn("'-timescale=1ns/1ps'",(run.ROOT/'flow/run.py').read_text())


if __name__=='__main__':unittest.main()
