"""Exercise real Tcl control flow with mock EDA commands; not a tool run."""
import ast
import json
from pathlib import Path
import tkinter

root = Path(__file__).resolve().parent
for p in root.glob('*.py'):
    ast.parse(p.read_text(), filename=p.name, feature_version=(3, 6))
t = tkinter.Tcl()
t.setvar('env(PPA_SOURCE)', root.as_posix())
t.call('source', str(root/'common.tcl'))
t.eval('proc redirect {opt name body} {upvar 1 $name result; set result "report"; uplevel 1 $body}')
t.eval('rename save_text actual_save_text; proc save_text {path text} {}')
assert t.eval('proc wrapper {} {set x 19; capture fixture {expr {$x+4}}}; wrapper') == 'report'
assert t.eval('catch {capture fixture {error sentinel}}') == '1'
for cmd in ('create_clock', 'set_clock_transition', 'set_clock_uncertainty', 'set_input_transition',
            'set_input_delay', 'set_output_delay', 'set_false_path', 'set_load'):
    t.eval('proc '+cmd+' {args} {lappend ::record [linsert $args 0 [lindex [info level 0] 0]]}')
for cmd in ('get_ports', 'get_clocks', 'remove_from_collection'):
    t.eval('proc '+cmd+' {args} {return fixture}')
t.eval('proc all_inputs {} {return fixture}; proc all_outputs {} {return fixture}')
t.eval('set ::record {}; constraints')
commands = [list(t.splitlist(x)) for x in t.splitlist(t.eval('set record'))]
for name, key, value in [('create_clock', '-period', 10), ('set_clock_uncertainty', '-setup', 2),
                         ('set_clock_uncertainty', '-hold', .1), ('set_input_delay', '-max', 1)]:
    c = next(c for c in commands if c[0] == name and key in c)
    assert float(c[c.index(key)+1]) == value
# Both documented report_lib formats and PVT rejection.
t.eval('rename lib_for_ref actual_lib_for_ref; proc lib_for_ref {r} {return fixture}')
t.eval('rename capture actual_capture; proc capture {path body} {return $::fixture}')
t.eval('proc set_operating_conditions {args} {set ::applied $args}')
for corner, v, temp in [('ss', 1.08, 125), ('tt', 1.2, 25)]:
    for block in (True, False):
        name = corner+'_test'
        text = ('Operating Conditions:\nOperating Condition Name : {}\nProcess : 1\nTemperature : {}\nVoltage : {}\n\n'.format(name, temp, v)
                if block else 'Operating Conditions:\nName Process Temp Volt\n{} 1 {} {}\n'.format(name, temp, v))
        t.setvar('fixture', text)
        t.setvar('env(PPA_CORNER)', corner)
        t.eval('conditions')
        assert name in t.eval('set ::applied')
        t.setvar('env(PPA_CORNER)', 'tt' if corner == 'ss' else 'ss')
        assert t.eval('catch {conditions}') == '1'
print(json.dumps(dict(python36_syntax='PASS', capture_scope_errors='PASS', constraints='PASS',
                     pvt_report_formats_and_wrong_corner_guard='PASS', eda_execution='NOT_RUN'), indent=2))
