"""Focused offline regressions for Today decisions, blockers, and operations."""
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


CATALOG_SETUP = r"""
context.U=U;context.esc=U.esc;
context.$=id=>context.document.getElementById(id);
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const source=html.slice(html.indexOf('/* ---------- current decision catalog'),
  html.indexOf('/* ---------- status strip'));
vm.runInContext(source+`;globalThis.catalogValid=validCatalog;
  globalThis.setCatalog=(value,state={})=>{C=value;Object.assign(catalogView,state);};
  globalThis.drawCatalog=renderDecisionCatalog;`,context);
const record=(id,lifecycle,lane,eligible,verdict,extra={})=>({proposal_id:id,title:'Title '+id,
  target:'validate',target_type:'skill',scope:'framework',lifecycle,lane,eligible,verdict,
  decision:null,evidence:[],...extra});
const ready=record('P-100','open','ready',true,'open');
const held=record('P-101','draft','candidate',false,'open');
const history=record('P-102','closed','history',false,'rejected');
const catalog={proposals:[ready],records:[ready,held,history],
  counts:{ready:1,candidates:1,history:1,total:3}};
"""


def test_blocker_count_uses_only_qualified_framework_attention():
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


def test_recall_floor_is_age_labeled_and_never_called_fresh():
    run_js(STATUS_SETUP + r"""
fixture.status_strip.freshness={recall_floor:'2026-06-28',newest_event:'2026-09-07',recall_floor_age_days:71};
context.drawStatus();
const recall=elements.get('status').children[6];
assert.match(recall.innerHTML,/recall floor/);
assert.match(recall.innerHTML,/71d old/);
assert.doesNotMatch(recall.innerHTML,/fresh/i);
assert.match(recall.title,/source-reported recall floor/);
""")


def test_catalog_renders_actual_eligible_records_and_separate_held_history():
    run_js(CATALOG_SETUP + r"""
assert.equal(context.catalogValid(catalog),true);
context.setCatalog(catalog,{phase:'ready',receivedAt:'2026-09-07T19:40:00Z',error:''});
context.drawCatalog();
const output=elements.get('decision-catalog').innerHTML;
assert.match(output,/P-100/);assert.match(output,/Review/);
assert.match(output,/Held candidates · 1/);assert.match(output,/Decision history · 1/);
assert.match(output,/P-101/);assert.match(output,/P-102/);
assert.match(output,/does not report a generation timestamp/);
""")


def test_empty_catalog_is_truthful_and_never_indexes_a_missing_decision():
    run_js(CATALOG_SETUP + r"""
const empty={proposals:[],records:[],counts:{ready:0,candidates:0,history:0,total:0}};
assert.equal(context.catalogValid(empty),true);
context.setCatalog(empty,{phase:'ready',receivedAt:'2026-09-07T19:40:00Z',error:''});
context.drawCatalog();
const output=elements.get('decision-catalog').innerHTML;
assert.match(output,/No eligible decisions/);assert.match(output,/empty eligible list/);
assert.doesNotMatch(output,/decision-link/);
""")


def test_catalog_rejects_inconsistent_authority_and_counts():
    run_js(CATALOG_SETUP + r"""
for(const bad of [
 {...catalog,proposals:[]},
 {...catalog,counts:{...catalog.counts,ready:9}},
 {...catalog,records:[{...ready,eligible:'true'},held,history]},
 {...catalog,proposals:[{...ready,lifecycle:'closed'}]},
 {...catalog,records:[ready,ready]},
]) assert.equal(context.catalogValid(bad),false);
context.setCatalog(null,{phase:'error',error:'invalid response'});context.drawCatalog();
const output=elements.get('decision-catalog').innerHTML;
assert.match(output,/Decision catalog unavailable/);assert.match(output,/No decision is enabled/);
assert.doesNotMatch(output,/Review/);
""")


def test_atlas_page_fetches_catalog_with_get_and_never_posts_automatically():
    run_js(r"""
context.document.documentElement={hasAttribute(name){return name==='data-atlas';}};
const fixture={repo:'/fixture/framework',consumer:'/fixture/consumer',schema_version:2,
  generated_at:'2026-09-07T19:40:00Z',window:{min_days:1,max_days:7,default_days:7,newest_event:'2026-09-07'},
  status_strip:{system:'attention',needs_you:{high:0,med:0,low:0,total:0},
    drift:{skills:0,worst:null},candidates:{total:1},loop:{state:'dormant',dormant_days:71},
    firewall:{status:'intact',violations:0},freshness:{recall_floor:'2026-06-28',newest_event:'2026-09-07',recall_floor_age_days:71}},
  loop:{chains:[],stages:{harvest:{all:0,dormant_days:71,newest:'2026-06-28'},
    candidates:{total:1,newest:'2026-06-28'},proposals:{open:1,newest:'2026-09-07'},
    review:{accepted:0,auto_accept:0,rejected:0,auto_reject:0,human_review:0},
    enacted:{rules:0,skills_created:0,skills_healed:0}}},matrix:{cells:[]},skills:[],agents:[],
  incidents:[],contracts:[],timeline:[],rules:[],days:[],inbox:[],
  attention:{framework_actions:[],external_acknowledgements:[],backlog_history:[],external_groups:[]},
  attribution:{agent_rows:0,total_rows:0}};
const mapFixture={nodes:[],edges:[],cards:{},generated_at:'2026-09-07T19:40:00Z'};
const ready={proposal_id:'P-100',title:'Review the exact change',target:'validate',target_type:'skill',
  scope:'framework',lifecycle:'open',lane:'ready',eligible:true,verdict:'open',decision:null,evidence:[]};
const catalog={proposals:[ready],records:[ready],counts:{ready:1,candidates:0,history:0,total:1}};
const operations={read_only:true,server:{alive:{value:true,status:'observed'}},warnings:[]};
const calls=[];context.fetch=async(path,options={})=>{calls.push({path,method:options.method||'GET'});
  if(path==='api/summary')return ok(fixture);if(path==='api/map')return ok(mapFixture);
  if(path==='api/operations')return ok(operations);if(path==='api/proposals')return ok(catalog);
  if(path==='proposal_review.html')return {ok:true,status:200,redirected:false};throw new Error('unexpected '+path);};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=mapFixture;
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(calls.filter(call=>call.path==='api/proposals').length,1);
assert.ok(calls.every(call=>call.method==='GET' || call.method==='HEAD'));
assert.match(elements.get('decision-catalog').innerHTML,/P-100/);
assert.match(elements.get('decision-catalog').innerHTML,/Review/);
for(const fn of events.get('pagehide')||[])fn({persisted:false});
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


def test_observed_failure_timestamp_keeps_failure_tone():
    run_js(r"""
context.U=U;context.esc=U.esc;context.$=id=>context.document.getElementById(id);
context.operationsSource={error:''};
context.O={read_only:true,server:{alive:{value:true,status:'observed'}},
  pipeline:{last_success:{value:null,status:'unknown'},
    last_failure:{value:'2026-09-07T18:01:18Z',status:'observed'}},warnings:['fixture warning']};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const source=html.slice(html.indexOf('function renderOperations('),
  html.indexOf('/* ---------- needs-you inbox'));
vm.runInContext(source+';globalThis.drawOperations=renderOperations;',context);
context.drawOperations();
const output=elements.get('operations').innerHTML;
assert.match(output,/last pipeline failure · observed/);
assert.match(output,/class="v bad">2026-09-07T18:01:18Z/);
assert.match(output,/warnings: fixture warning/);
""")
