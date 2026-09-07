"""Click shipped Dashboard contract rows with synthetic JSON receipt values."""
import json

import pytest

from test_ui_data_provenance import run_js


SETUP = r"""
context.U=U;context.esc=U.esc;
context.$=id=>context.document.getElementById(id);
let panel='',title='';U.panel.open=(t,html)=>{title=t;panel=html;};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const section=html.slice(html.indexOf('/* ---------- contracts'),html.indexOf('/* ---------- timeline'));
vm.runInContext(section+';globalThis.drawContracts=renderContracts;globalThis.showContract=openContract;',context);
const escaped=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
"""


@pytest.mark.parametrize("raw,display,verdict", [
    ({}, "{}", "unverified"), ([], "[]", "unverified"),
    (0, "0", "unverified"), (False, "false", "unverified"),
    ("", "", "unverified"), (None, "", "unverified"),
    (7, "7", "unverified"), (True, "true", "unverified"),
    ({"identity": "pass", "review": "pending"},
     '{"identity":"pass","review":"pending"}', "unverified"),
    (["pass", {"review": "pending"}], '["pass",{"review":"pending"}]', "unverified"),
    ({"toString": "not callable", "detail": "<script>&\"'"},
     '{"toString":"not callable","detail":"<script>&\\\"\'"}', "unverified"),
    ("<script>&\"'", "<script>&\"'", "freeform"),
    ("pass", "pass", "pass"), (" fail ", " fail ", "fail"),
    ("inconclusive", "inconclusive", "inconclusive"),
    ("a reported explanation", "a reported explanation", "freeform"),
])
@pytest.mark.parametrize("status", ["completed", "spawned"])
def test_contract_row_click_displays_raw_receipt_safely(raw, display, verdict, status):
    contract = {"spawn_id": "synthetic-receipt", "agent": "other", "surface": "framework",
                "date": "2026-09-05", "status": status, "done_check_raw": raw,
                "done_check": "pending" if status == "spawned" else verdict}
    run_js(SETUP + "\nconst receipt=" + json.dumps(contract) + ";\nconst expected=" + json.dumps(display) + r""";
const before=JSON.stringify(receipt);
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];
assert.match(row.innerHTML,new RegExp('>'+receipt.done_check+'</span>'));
row.listeners.click();
assert.equal(title,receipt.spawn_id);
assert.ok(panel.includes('<span>done-check</span><span>'+escaped(expected)+'</span>'),panel);
assert.doesNotMatch(panel,/\[object Object\]|<script>/);
assert.match(panel,new RegExp('>'+receipt.done_check+'</span>'));
if(receipt.done_check==='unverified'||receipt.done_check==='pending')
  assert.doesNotMatch(panel,/ui-pill ok/);
assert.equal(JSON.stringify(receipt),before);
""")


@pytest.mark.parametrize("status", ["aborted", "escalated", "budget_exceeded"])
def test_terminal_failure_with_pass_is_visible_as_a_non_green_contradiction(status):
    contract = {
        "spawn_id": "synthetic-contradiction",
        "agent": "other",
        "surface": "framework",
        "task": "contradictory receipt",
        "date": "2026-09-05",
        "started_at": "2026-09-05T00:00:00Z",
        "status_at": "2026-09-05T00:00:03Z",
        "status": status,
        "done_check_raw": "pass",
        "done_check": "pass",
        "evaluation_state": "contradiction",
        "verified_by": "parent-task",
        "verified_at": "2026-09-05T00:00:04Z",
        "state_basis": "HEAD@deadbeef",
        "child_summary": "child says done",
        "parent_observations": ["terminal state disagrees"],
        "budget": {"wall_time_seconds": 60},
        "actual_usage": None,
    }
    run_js(SETUP + "\nconst receipt=" + json.dumps(contract) + r""";
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];
assert.match(row.innerHTML,new RegExp(receipt.status));
assert.match(row.innerHTML,/status\/check conflict/);
assert.match(row.innerHTML,/>pass<\/span>/);
assert.doesNotMatch(row.innerHTML,/ui-pill ok/);
row.listeners.click();
assert.match(panel,/terminal state/);
assert.match(panel,new RegExp(receipt.status));
assert.match(panel,/reported done-check/);
assert.match(panel,/status\/check conflict/);
assert.match(panel,/parent-task/);
assert.match(panel,/source-reported/);
assert.match(panel,/unknown \(no receipt\)/);
assert.doesNotMatch(panel,/ui-pill ok/);
""")


@pytest.mark.parametrize("status,done_check,evaluation,green", [
    ("completed", "pass", "pass", True),
    (None, "pass", "unknown", False),
    ("unknown-terminal-state", "pass", "unknown", False),
    ("spawned", "pending", "pending", False),
])
def test_only_completed_reported_pass_can_render_green(
        status, done_check, evaluation, green):
    contract = {
        "spawn_id": "synthetic-state",
        "agent": "other",
        "surface": "framework",
        "date": "2026-09-05",
        "status": status,
        "done_check_raw": "pass",
        "done_check": done_check,
        "evaluation_state": evaluation,
        "budget": {},
    }
    run_js(SETUP + "\nconst receipt=" + json.dumps(contract) + ";\nconst green=" +
           json.dumps(green) + r""";
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];
assert.equal(/ui-pill ok/.test(row.innerHTML),green,row.innerHTML);
if(!green) assert.match(row.innerHTML,/pending|unknown/);
""")


@pytest.mark.parametrize("wall_time", [0, 75])
def test_contract_detail_preserves_provenance_escapes_poisoned_values_and_labels_budget(
        wall_time):
    run_js(SETUP + "\nconst wallTime=" + json.dumps(wall_time) + r""";
const poison={toString:'not callable',detail:'<script>&"\''};
const receipt={spawn_id:'synthetic-provenance',agent:'other',surface:'framework',
 task:'task <script>',date:'2026-09-05',started_at:'2026-09-05T00:00:00.123Z',
 status_at:'2026-09-05T00:00:09.987Z',status:'completed',done_check_raw:'pass',
 done_check:'pass',evaluation_state:'pass',verified_by:poison,
 verified_at:'2026-09-05T00:00:10.001Z',state_basis:poison,
 child_summary:{toString:'not callable',detail:'<child>'},
 parent_observations:[poison,'parent <evaluation>'],
 budget:{wall_time_seconds:wallTime,iterations:0,cost_usd:2.5},actual_usage:null};
const before=JSON.stringify(receipt);
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];
assert.ok(row.innerHTML.includes('planned '+wallTime+'s'),row.innerHTML);
assert.doesNotMatch(row.innerHTML,/<script>/);
row.listeners.click();
for(const label of ['launched (source timestamp)','terminal update (source timestamp)',
 'terminal state','reported done-check','evaluation','evaluator (source-reported)',
 'verification time (source-reported)','state basis (source-reported)',
 'child report','parent evaluation','planned budget','actual usage']) {
  assert.ok(panel.includes(label),label+' missing from '+panel);
}
assert.match(panel,/reported pass/);
assert.match(panel,/unknown \(no receipt\)/);
assert.match(panel,new RegExp('planned wall time.*'+wallTime+'s'));
assert.match(panel,/&lt;script&gt;/);
assert.match(panel,/&lt;child&gt;/);
assert.match(panel,/parent &lt;evaluation&gt;/);
assert.doesNotMatch(panel,/<script>|<child>|parent <evaluation>/);
assert.equal(JSON.stringify(receipt),before);
""")


@pytest.mark.parametrize("key", ["Enter", " "])
def test_contract_rows_support_keyboard_activation(key):
    contract = {
        "spawn_id": "synthetic-keyboard",
        "agent": "other",
        "surface": "framework",
        "date": "2026-09-05",
        "status": "completed",
        "done_check_raw": "pass",
        "done_check": "pass",
        "evaluation_state": "pass",
        "budget": {"wall_time_seconds": 1},
    }
    run_js(SETUP + "\nconst receipt=" + json.dumps(contract) +
           ";\nconst key=" + json.dumps(key) + r""";
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];let prevented=false;
assert.equal(row.role,'button');assert.equal(row.tabIndex,0);
row.listeners.keydown({key,preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(title,receipt.spawn_id);
""")


def test_show_all_contracts_control_is_keyboard_accessible_and_conservative():
    run_js(SETUP + r"""
const contracts=Array.from({length:10},(_,i)=>({spawn_id:'SP-'+i,agent:'other',
 surface:'framework',task:'task '+i,date:'2026-09-05',status:i===0?'aborted':'completed',
 done_check_raw:'pass',done_check:'pass',evaluation_state:i===0?'contradiction':'pass',budget:{}}));
context.D={contracts};context.drawContracts();
const more=elements.get('contracts').children[8];let prevented=false;
assert.equal(more.role,'button');assert.equal(more.tabIndex,0);
more.listeners.keydown({key:'Enter',preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(title,'contracts · 10');
assert.match(panel,/status\/check conflict/);
assert.doesNotMatch(panel,/ui-pill ok[^]*SP-0/);
""")


@pytest.mark.parametrize("status,check,label", [("completed", "fail", "reported fail"), ("completed", "inconclusive", "reported inconclusive")])
def test_completed_task_can_report_failed_or_inconclusive_validation(status, check, label):
    receipt = {"spawn_id": "SP-outcome", "status": status, "done_check": check, "done_check_raw": check,
               "agent": "other", "surface": "framework", "budget": {}}
    run_js(SETUP + "\nconst receipt=" + json.dumps(receipt) + ";const label=" + json.dumps(label) + r""";
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];row.listeners.click();
assert.match(panel,new RegExp(label));assert.doesNotMatch(panel,/status\/check conflict|ui-pill ok/);
""")


@pytest.mark.parametrize("duration", [False, -1, "75", {}, []])
def test_invalid_planned_duration_is_unknown(duration):
    run_js(SETUP + "\nconst duration=" + json.dumps(duration) + r""";
context.D={contracts:[{spawn_id:'SP-time',status:'completed',done_check:'pass',agent:'other',budget:{wall_time_seconds:duration}}]};
context.drawContracts();assert.match(elements.get('contracts').children[0].innerHTML,/planned unknown/);
""")


def test_all_contracts_have_disclosed_evaluator_context():
    run_js(SETUP + r"""
const contracts=Array.from({length:10},(_,i)=>({spawn_id:'SP-'+i,status:'completed',done_check:'pass',agent:'other',
 budget:{},verified_by:'reviewer-'+i,parent_observations:'evidence-'+i}));
context.D={contracts};context.drawContracts();elements.get('contracts').children[8].listeners.click();
assert.equal((panel.match(/<details class="ui-item">/g)||[]).length,10);
assert.match(panel,/reviewer-9/);assert.match(panel,/evidence-9/);assert.match(panel,/<summary/);
""")
