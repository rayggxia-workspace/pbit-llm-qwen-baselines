import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scalar_vcd import scalarize, verify_pt
from range_review import review
from reuse import checkpoint
from package import sha
import reuse


def waveform():
    return ('$timescale 1ns $end\n$scope module tb_ppa $end\n$scope module dut $end\n'
            '$var wire 1 ! clk $end\n$var reg 1 " out_valid $end\n'
            '$var wire 2048 # result [2047:0] $end\n'
            '$scope module resize_core $end\n$var wire 2048 # alias [0:2047] $end\n'
            '$upscope $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n'
            '#0\n$dumpvars\n0!\n0"\nb0 #\n$end\n#5\n1!\n1"\nb101 #\n'
            '#10\n0!\nb10 #\n#15\n1!\n#20\n')


class Tests(unittest.TestCase):
    def test_scalar_bits_aliases_and_short_vectors(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d);(p/'raw').write_text(waveform())
            a=scalarize(p/'raw',p/'scalar',21)
            text=(p/'scalar').read_text()
            self.assertNotIn('2048 #',text)
            self.assertIn('result [2047]',text)
            self.assertIn('alias [0]',text)
            self.assertEqual(a['scalar_ids'],2050)
            self.assertEqual(a['declarations'],4098)
            self.assertEqual(a['duration_ns'],20)
            r=a['expected_activity']
            self.assertEqual(r['result[0]']['toggle_count'],2)
            self.assertEqual(r['result[0]']['static_probability'],.25)
            self.assertEqual(r['result[1]']['static_probability'],.5)
            self.assertEqual(r['clk']['toggle_count'],3)
            self.assertEqual(r['clk']['static_probability'],.5)
            # Decode scalar events independently and compare every bit at every time.
            vals={};now=0; observed={}
            for line in text.split('$enddefinitions $end\n')[1].splitlines():
                if line.startswith('#'):
                    if vals: observed[now]=dict(vals)
                    now=int(line[1:])
                elif line and line[0] in '01': vals[line[1:]]=line[0]
            observed[now]=dict(vals)
            for t,n in [(0,0),(5,5),(10,2),(15,2),(20,2)]:
                bits=''.join(observed[t]['v2_'+str(j)] for j in range(2048))
                self.assertEqual(int(bits,2),n)

    def test_unknown_not_waived(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d);(p/'raw').write_text(waveform().replace('b101 #','bx #'))
            with self.assertRaisesRegex(ValueError,'X/Z'):
                scalarize(p/'raw',p/'out',21)

    def test_missing_functional_bit(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d);(p/'raw').write_text(waveform().replace('result [2047:0]','other [2047:0]'))
            with self.assertRaisesRegex(ValueError,'Missing functional'):
                scalarize(p/'raw',p/'out',21)

    def test_pt_binding_and_failure(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d);(p/'raw').write_text(waveform());a=scalarize(p/'raw',p/'out',21)
            h='name\ttoggle_rate\tstatic_probability\n'
            lines=['{}\t{}\t{}\n'.format(n,r['toggle_rate_per_ns'],r['static_probability']) for n,r in a['expected_activity'].items()]
            (p/'pt').write_text(h+''.join(lines))
            self.assertEqual(verify_pt(a,p/'pt')['checked_bits'],18)
            (p/'pt').write_text(h+''.join(lines).replace('clk\t0.15\t0.5','clk\t0\t0.5'))
            with self.assertRaisesRegex(ValueError,'mismatch'): verify_pt(a,p/'pt')
            (p/'pt').write_text(h)
            with self.assertRaisesRegex(ValueError,'unavailable'): verify_pt(a,p/'pt')

    def test_ranges_keep_warning_and_do_not_double_count(self):
        s=" load 0.0000001 at pin 'Y' of cell 'core/U1' is out of load range (0.000001, 0.02)\n"
        s+=" ramp 0.01 at pin 'A' of cell 'core/U1' is out of ramp range (0.02, 0.87)\n"
        r=review(s,{'core/U1':1e-6},10e-6)
        self.assertAlmostEqual(r['affected_cells_power_percent'],10)
        self.assertEqual(len(r['flagged_cells']['core/U1']),2)
        with self.assertRaises(ValueError): review(s,{},10e-6)
        with self.assertRaises(ValueError): review('changed format is out of range',{},10e-6)

    def test_checkpoint_tamper_and_path(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d);(p/'ok').write_text('ok')
            (p/'STAGE_COMPLETE.json').write_text(json.dumps({'ok':sha(p/'ok')}))
            checkpoint(p,['ok'])
            (p/'ok').write_text('changed')
            with self.assertRaises(ValueError):checkpoint(p,['ok'])
            (p/'STAGE_COMPLETE.json').write_text(json.dumps({'../escape':'bad'}))
            with self.assertRaises(ValueError):checkpoint(p,[])

    def test_reuse_config_source_and_parent_immutable(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            p=Path(d); old=p/'old'; new=p/'new'; src=p/'src'
            for q in (old/'dc', old/'gate/x', new, src): q.mkdir(parents=True)
            m=dict(name='x',mode='stream',inputs=1,outputs=1)
            cfg={k:'same' for k in ('kind','corner','clock_MHz','voltage_V','temperature_C','std_db_sha256',
                  'std_model_sha256','setup_uncertainty_ns','hold_uncertainty_ns','input_slew_ns','output_load_pF','method')}
            manifest=dict(files={'rtl/a.sv':'unchanged','pt.tcl':'old'})
            (old/'source_manifest.json').write_text(json.dumps(manifest))
            h=sha(old/'source_manifest.json');cfg['source_manifest_sha256']=h
            (old/'configuration.json').write_text(json.dumps(cfg));(old/'FLOW_COMPLETE').write_text('yes')
            manifest['files']['pt.tcl']='new'
            (src/'package_manifest.json').write_text(json.dumps(manifest))
            for n in ('mapped.v','mapped.sdc','mapped.ddc','SYNTH_COMPLETE'):(old/'dc'/n).write_text('ok')
            g=old/'gate/x'
            for n in ('FUNCTION_PASS','counts.txt','window.vcd','wave_audit.json'):(g/n).write_text('ok')
            (g/'workload.json').write_text(json.dumps(m))
            (g/'simulation.log').write_text('DIGITAL_PPA_PASS inputs=1 outputs=1')
            for q in (old/'dc',g):
                (q/'STAGE_COMPLETE.json').write_text(json.dumps({f.name:sha(f) for f in q.iterdir()}))
            before={f.relative_to(old).as_posix():sha(f) for f in old.rglob('*') if f.is_file()}
            with patch.object(reuse,'V1_MANIFEST',h):
                record=reuse.validate(old,cfg,src,[m]);reuse.copy_reports(old,new,[m],record)
                self.assertFalse((new/'dc/mapped.v').exists())
                self.assertEqual(before,{f.relative_to(old).as_posix():sha(f) for f in old.rglob('*') if f.is_file()})
                bad=dict(cfg,std_db_sha256='changed')
                with self.assertRaisesRegex(ValueError,'configuration/library'):reuse.validate(old,bad,src,[m])
                manifest['files']['rtl/a.sv']='changed'
                (src/'package_manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,'RTL/constraints'):reuse.validate(old,cfg,src,[m])

    def test_activity_tcl_port_and_net_fallback(self):
        import tkinter
        t=tkinter.Tcl()
        t.call('source',str(Path(__file__).resolve().parent/'activity_check.tcl'))
        t.eval('proc foreach_in_collection {v collection body} {uplevel 1 [list foreach $v $collection $body]}')
        t.eval('proc get_ports {args} {return {clk out_valid {result[0]} ignored}}')
        t.eval('proc get_object_name {x} {return $x}; proc sizeof_collection {x} {llength $x}')
        t.eval('proc get_nets {args} {return fallback_net}')
        t.eval('proc get_attribute {args} {set obj [lindex $args 1];set attr [lindex $args 2]; if {$obj eq "out_valid"} {return {}}; if {$attr eq "toggle_rate"} {return 0.2}; return 0.5}')
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as d:
            t.eval('rename open actual_open')
            t.setvar('test_dest',str(Path(d)/'activity.tsv'))
            t.eval('proc open {path mode} {actual_open $::test_dest $mode}; write_output_activity')
            text=(Path(d)/'activity.tsv').read_text()
            self.assertIn('out_valid\t0.2\t0.5\tnet',text)
            self.assertIn('result[0]\t0.2\t0.5\tport',text)
            self.assertNotIn('ignored',text)


if __name__=='__main__':
    unittest.main()
