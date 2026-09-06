"""Focused offline regressions for Dashboard action counts and operations states."""
import pytest

from test_ui_data_provenance import run_js


STATUS_SETUP = r"""
const item=(id,severity,extra={})=>({id,title:id,kind:'proposal_review',severity,
  detail:'Evidence '+id,surface:'framework',actionable:true,action_cmd:'COMMAND_'+id,...extra});
const valid=[item('F-high','high'),item('F-med','med'),item('F-low','low')];
const conflict=item('F-conflict','high');
const unknown=item('F-unknown','high',{surface:null});
const malformed=item('F-malformed','high',{actionable:'true'});
const candidate=item('F-candidate','high',{kind:'candidate_review'});
const external=Array.from({length:511},(_,i)=>item('E-'+i,'high',{surface:'apparatus'}));
external[0]={...conflict,surface:'apparatus'};
const backlog=Array.from({length:11},(_,i)=>item('B-'+i,'high',{kind:'candidate_review'}));
const fixture={
  status_strip:{system:'attention',needs_you:{high:525,med:0,low:0,total:525},
    drift:{skills:0,worst:null},candidates:{total:11},loop:{state:'dormant',dormant_days:1},
    firewall:{status:'intact',violations:0},freshness:{recall_floor:'2026-09-06',newest_event:'2026-09-06',recall_floor_age_days:0}},
  inbox:[...valid,conflict,unknown,malformed,candidate,...external,...backlog],
  attention:{framework_actions:[...valid,conflict,unknown,malformed,candidate],
    external_acknowledgements:external,backlog_history:backlog,external_groups:[]}};
context.D=fixture;context.U=U;context.esc=U.esc;
context.$=id=>context.document.getElementById(id);
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const statusSection=html.slice(html.indexOf('/* ---------- status strip'),html.indexOf('/* ---------- bounded operations truth'));
const attentionHelpers=html.slice(html.indexOf('const RANK ='),html.indexOf('function renderInbox()'));
vm.runInContext(statusSection+attentionHelpers+';globalThis.drawStatus=renderStatus;',context);
"""


def test_headline_counts_only_current_eligible_framework_actions():
    run_js(STATUS_SETUP + r"""
const before=JSON.stringify(fixture.attention);
context.drawStatus();
const needs=elements.get('status').children[1];
assert.match(needs.innerHTML,/<span class="v">3<\/span>/);
assert.doesNotMatch(needs.innerHTML,/>525</);
assert.match(needs.title,/1 high · 1 med · 1 low/);
assert.equal(JSON.stringify(fixture.attention),before,'counting must not remove descriptive evidence');
assert.equal(fixture.attention.external_acknowledgements.length,511);
assert.equal(fixture.attention.backlog_history.length,11);
""")


@pytest.mark.parametrize("attention", ["undefined", "null", "{}", "{framework_actions:'bad'}"])
def test_headline_fails_closed_when_attention_authority_is_unknown(attention):
    run_js(STATUS_SETUP + "fixture.attention=" + attention + r""";
context.drawStatus();
const needs=elements.get('status').children[1];
assert.match(needs.innerHTML,/<span class="v">0<\/span>/);
assert.doesNotMatch(needs.innerHTML,/>525</);
""")


def test_operations_initial_http_state_is_loading():
    run_js(r"""
context.fetch=()=>new Promise(()=>{});
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const ops=elements.get('operations').innerHTML;
assert.match(ops,/data-state="loading"/);
assert.match(ops,/loading operations data/i);
assert.doesNotMatch(ops,/offline|start the brain server/i);
for(const fn of events.get('pagehide')||[])fn({persisted:false});
""")


def test_operations_offline_file_state_explains_the_transport_limit():
    run_js(r"""
context.location.protocol='file:';
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const ops=elements.get('operations').innerHTML;
assert.match(ops,/data-state="offline"/);
assert.match(ops,/offline file view/i);
assert.match(ops,/brain server/i);
""")


@pytest.mark.parametrize("status", [404, 500])
def test_operations_http_failure_is_not_called_offline(status):
    run_js(r"""
context.fetch=async path=>({ok:false,status:STATUS});
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
await new Promise(resolve=>setTimeout(resolve,0));
const ops=elements.get('operations').innerHTML;
assert.match(ops,/data-state="error"/);
assert.match(ops,new RegExp('request failed \\(HTTP '+STATUS+'\\)','i'));
assert.doesNotMatch(ops,/offline|start the brain server/i);
assert.match(elements.get('operations-source-status').textContent,new RegExp('unavailable.*HTTP '+STATUS,'i'));
""".replace("STATUS", str(status)))
