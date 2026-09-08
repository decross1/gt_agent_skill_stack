"""Execute browser data-source logic with deterministic, offline Node fixtures.

These are functional checks, not screenshots or visual/performance assertions.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

VIEW = Path(__file__).resolve().parents[1] / "memory" / "brain" / "view"
NODE = shutil.which("node")

HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element() {
  return {textContent:'', innerHTML:'', dataset:{}, style:{}, children:[],listeners:{},
    addEventListener(k,fn){this.listeners[k]=fn;}, setAttribute(k,v){this[k]=v;},
    appendChild(e){this.children.push(e);}, querySelector(){return element();},
    classList:{add(){},remove(){},contains(){return false;}}};
}
const events = new Map(), documentEvents = new Map(), activeIntervals = new Map();
const context = {console, Date, Promise, JSON, setTimeout, clearTimeout, AbortController,
  addEventListener(k,fn){if(!events.has(k))events.set(k,[]);events.get(k).push(fn);},
  removeEventListener(k,fn){events.set(k,(events.get(k)||[]).filter(f=>f!==fn));},
  location:{protocol:'http:',hostname:'localhost'}, navigator:{},
  localStorage:{getItem(){return null;}},
  // This harness evaluates assets before the page; acquisition is tested separately.
  BrainMap:{mount(){return{demoCard(){}};}},
  document:{readyState:'complete',removeEventListener(k,fn){documentEvents.set(k,(documentEvents.get(k)||[]).filter(f=>f!==fn));},addEventListener(k,fn){if(!documentEvents.has(k))documentEvents.set(k,[]);documentEvents.get(k).push(fn);},createElement:element,head:element(),body:element(),
    getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},
    querySelector(){return element();},querySelectorAll(){return [];}},
  intervals:[], setInterval(fn){context.intervals.push(fn);const id=context.intervals.length;activeIntervals.set(id,fn);return id;},
  clearInterval(id){activeIntervals.delete(id);},
  fetch:async()=>{throw new Error('unexpected fetch');}};
context.window=context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1]+'/ui.js','utf8'),context);
const U=context.UI;
const stamp='2026-08-01T00:00:00Z';
const summary={status_strip:{},generated_at:stamp,matrix:{cells:[]},skills:[],agents:[]};
const map={nodes:[],edges:[],cards:{},generated_at:stamp};
const validSummary=d=>!!d.status_strip;
const validMap=d=>Array.isArray(d.nodes);
const ok=d=>({ok:true,status:200,json:async()=>d});
const failure={ok:false,status:500};
const host=element();
const announcement=element();
const show=(s,m)=>{U.renderDataStatus(host,s,m,announcement);return host.textContent;};
"""

CASES = {
    "offline": r"""
context.location.protocol='file:';
const s=U.dataSource(summary,validSummary), m=U.dataSource(map,validMap);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/Snapshot data/);
assert.match(host.textContent,/2026-08-01/);
assert.equal(s.data,summary);
assert.equal(s.source,'snapshot');
""",
    "mixed": r"""
context.fetch=async p=>p==='api/summary'?failure:ok(map);
const s=U.dataSource(summary,validSummary),m=U.dataSource(map,validMap);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/Mixed data/);
assert.match(host.textContent,/Summary: snapshot/);
assert.match(host.textContent,/Map: live response/);
assert.match(host.textContent,/HTTP 500/);
assert.equal(s.data,summary);
""",
    "cached_and_recovery": r"""
context.fetch=async p=>ok(p==='api/summary'?summary:map);
const s=U.dataSource(null,validSummary),m=U.dataSource(null,validMap);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/^Live responses/);
assert.match(host.textContent,/fetched separately/);
const success=s.receivedAt;
context.fetch=async()=>failure;
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/^Cached live data/);
assert.equal(s.receivedAt,success);
assert.equal(s.data,summary);
assert.match(host.textContent,/refresh failed/);
context.fetch=async p=>ok(p==='api/summary'?summary:map);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/^Live responses/);
assert.doesNotMatch(host.textContent,/refresh failed/);
""",
    "unavailable": r"""
context.fetch=async()=>failure;
const s=U.dataSource(null,validSummary),m=U.dataSource(null,validMap);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
assert.match(show(s,m),/^Data unavailable/);
context.fetch=async()=>ok(map);
await m.refresh('api/map');
assert.match(show(s,m),/^Data incomplete/);
assert.match(host.textContent,/Summary: unavailable/);
""",
    "invalid_response": r"""
const s=U.dataSource(summary,validSummary),m=U.dataSource(map,validMap);
for (const reply of [ok({}),ok(null),{ok:true,json:async()=>{throw new Error('bad JSON');}}]) {
 context.fetch=async()=>reply;
 await s.refresh('api/summary');
 assert.equal(s.data,summary);
 assert.equal(s.source,'snapshot');
 assert.match(show(s,m),/refresh failed/);
}
""",
    "timestamp_text_only": r"""
const unsafe={...summary,generated_at:'<img src=x onerror=alert(1)>'};
const s=U.dataSource(unsafe,validSummary),m=U.dataSource(map,validMap);
show(s,m);
assert.equal(host.innerHTML,'');
assert.match(host.textContent,/generation time unavailable/);
assert.doesNotMatch(host.textContent,/<img/);
""",
    "late_response": r"""
let finish;
context.fetch=()=>new Promise(resolve=>{finish=resolve;});
const s=U.dataSource(summary,validSummary);
const slow=s.refresh('api/summary');
s.cancel();await slow;
const newer={...summary,generated_at:'2026-08-02T00:00:00Z'};
context.fetch=async()=>ok(newer);
await s.refresh('api/summary');
finish(ok(summary));await slow;
assert.equal(s.data,newer);
""",
    "announcements_only_on_source_transitions": r"""
let spoken='',updates=0;
Object.defineProperty(announcement,'textContent',{get(){return spoken;},set(v){spoken=v;updates++;}});
const s=U.dataSource(null,validSummary),m=U.dataSource(null,validMap);
context.fetch=async p=>ok(p==='api/summary'?summary:map);
await Promise.all([s.refresh('api/summary'),m.refresh('api/map')]);
show(s,m);assert.equal(updates,1);
const previous=host.textContent;
s.receivedAt='2026-08-02T00:00:00Z';
show(s,m);assert.equal(updates,1);assert.notEqual(host.textContent,previous);
s.error='HTTP 500';show(s,m);assert.equal(updates,2);
assert.match(spoken,/Summary: cached live response/);
show(s,m);assert.equal(updates,2);
""",
}


def run_js(code):
    if not NODE:
        pytest.fail("Node is required for UI functional validation; no visual pass can substitute")
    result = subprocess.run(
        [NODE, "-e", HARNESS + "\n(async()=>{\n" + code +
         "\n})().catch(e=>{console.error(e);process.exitCode=1;});", str(VIEW)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr



CASES.update({
 "redirects_preserve_prior_projection_source": r"""
const s=U.dataSource(summary,validSummary);let options;
context.fetch=async(_path,opts)=>{options=opts;return {...ok(summary),redirected:true};};
assert.equal(await s.refresh('api/summary'),false);assert.equal(options.redirect,'error');
assert.equal(s.source,'snapshot');assert.equal(s.data,summary);assert.match(s.error,/redirect/i);
""",
 "impossible_generation_dates_are_not_normalized": r"""
for(const generated_at of ['2026-02-30T00:00:00Z','2026-08-01T24:00:00Z','2026-08-01T00:00:00+01:99']){
 const s=U.dataSource({...summary,generated_at},validSummary),m=U.dataSource(map,validMap);
 assert.match(show(s,m),/Summary: snapshot · generation time unavailable/);
}
""",
})

@pytest.mark.parametrize("case", CASES)
def test_source_provenance_transitions(case):
    run_js(CASES[case])


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
def test_actual_page_boot_exposes_missing_data(page):
    run_js(r"""
context.fetch=async()=>failure;
const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
assert.match(html,/id="data-source-announcement"[^>]*role="status"/);
assert.doesNotMatch(html,/id="data-source-status"[^>]*(?:role="status"|aria-live)/);
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInContext(script,context);
await new Promise(resolve=>setTimeout(resolve,0));
assert.match(elements.get('data-source-status').textContent,/^Data unavailable/);
""".replace("PAGE", json.dumps(page)))


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
def test_page_refresh_discloses_mixture_without_remounting_unchanged_map(page):
    run_js(r"""
const fixture={...summary,repo:'/fixture/framework',consumer:'/fixture/consumer',
  schema_version:2,window:{min_days:1,max_days:7,default_days:7,newest_event:stamp},
  status_strip:{system:'attention',needs_you:{high:0,med:0,low:0,total:0},
    drift:{skills:0},candidates:{total:0},loop:{state:'dormant',dormant_days:1},
    firewall:{status:'intact',violations:0},freshness:{recall_floor_age_days:1}},
  loop:{chains:[
    {proposal_id:'P-1',title:'Current rejection',final_verdict:'rejected',lane:'closed',filed_date:'2026-08-01'},
    {proposal_id:'P-2',title:'Undecided candidate',final_verdict:'open',lane:'draft',filed_date:'2026-08-02'},
    {proposal_id:'P-3',title:'Legacy decision',verdict:'accepted',date:'2026-07-30'}],
    stages:{harvest:{all:0},candidates:{total:0},proposals:{open:0},
    review:{accepted:0,auto_accept:0,rejected:2,auto_reject:1,human_review:0},
    enacted:{rules:0,skills_created:0,skills_healed:0}}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
const mounts=[];
context.BrainMap={mount(_,data){mounts.push(data);return{demoCard(){}};}};
const operations={read_only:true,server:{},proposals:{counts:{value:{accepted:1,enacted:1,verified:1},status:'observed',provenance:'synthetic structural receipts'}}};
context.fetch=async p=>p==='api/summary'?failure:p==='api/operations'?ok(operations):ok(map);
const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
await new Promise(resolve=>setTimeout(resolve,0));
const status=elements.get('data-source-status');
assert.match(status.textContent,/^Mixed data/);
assert.equal(mounts.length,1);
assert.equal(mounts[0].summary,fixture);
if (PAGE==='dashboard.html') {
 const ops=elements.get('operations').innerHTML;
 assert.match(ops,/reported verification receipts 1/);
 assert.match(ops,/<div class="k">reported verification receipts/);
 assert.match(ops,/not independently verified/);
 assert.doesNotMatch(ops,/ · V1|verified 1/);
 const review=elements.get('loopstrip').children.find(e=>(e.title||'').includes('auto-reject'));
 assert.match(review.innerHTML,/✗3/);
 assert.match(review.title,/2 rejected/);
 let panel='';U.panel.open=(_,html)=>{panel=html;};review.listeners.click();
 assert.match(panel,/>rejected<\/span>/);
 assert.match(panel,/>draft<\/span>/);
 assert.match(panel,/>accepted<\/span>/);
 for (const date of ['2026-08-01','2026-08-02','2026-07-30'])assert.ok(panel.includes(date));
}
assert.equal(context.intervals.length,1);
const changedTime={...fixture,generated_at:'2026-08-02T00:00:00Z'};
context.fetch=async p=>ok(p==='api/summary'?changedTime:map);
await context.intervals[0]();
assert.match(status.textContent,/^Live responses/);
assert.match(status.textContent,/2026-08-02/);
assert.equal(mounts.length,1,'generation metadata alone must preserve map interaction');
const changedMap={...map,nodes:[{id:'new-node'}]};
context.fetch=async p=>ok(p==='api/summary'?changedTime:changedMap);
await context.intervals[0]();
assert.equal(mounts.length,2,'map content changes must reach the renderer');
context.fetch=async()=>failure;
await context.intervals[0]();
assert.match(status.textContent,/^Cached live data/);
assert.match(status.textContent,/refresh failed/);
assert.equal(mounts.length,2);
""".replace("PAGE", json.dumps(page)))


def test_operations_request_rejects_redirected_local_facts():
    run_js(r"""
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const helper=html.slice(html.indexOf('const operationsSource ='),html.indexOf('// Render signature ='));
context.U=U;
vm.runInContext(helper+';globalThis.reviewFetchOperations=fetchLiveOperations;',context);
let options;context.fetch=async(_path,opts)=>{options=opts;return {...ok({read_only:true,server:{},proposals:{counts:{value:{verified:9}}}}),redirected:true};};
assert.equal(await context.reviewFetchOperations(),null);assert.equal(options.redirect,'error');
""")


FAKE_CLOCK = r"""
const timers=new Map();let timerId=0;
context.setTimeout=(fn,ms)=>{assert.ok(ms>0 && ms<=5000);timers.set(++timerId,fn);return timerId;};
context.clearTimeout=id=>timers.delete(id);
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
const expire=async()=>{for(const [id,fn] of [...timers]){timers.delete(id);fn();}await flush();};
const fire=async name=>{for(const fn of events.get(name)||[])fn({persisted:true});await flush();};
"""


@pytest.mark.parametrize("hang", ["fetch", "body"])
def test_source_deadline_singleflight_cancel_and_late_completion(hang):
    run_js(FAKE_CLOCK + r"""
let finish,signal,calls=0;
context.fetch=(_path,opts)=>{calls++;signal=opts.signal;
 const pending=new Promise(resolve=>{finish=resolve;});
 return HANG==='fetch'?pending:{ok:true,json:()=>pending};
};
const s=U.dataSource(summary,validSummary);
const pending=s.refresh('api/summary');let settled=false;pending.then(()=>{settled=true;});
const duplicate=s.refresh('api/summary');await flush();
assert.equal(duplicate,pending);
assert.equal(calls,1,'overlapping refresh must reuse one request');
assert.ok(timers.size>0,'whole fetch/body wait needs a finite deadline');
await expire();assert.equal(settled,true);assert.equal(await duplicate,false);
assert.equal(signal.aborted,true);assert.match(s.error,/timed out/i);
assert.equal(s.data,summary);assert.equal(s.receivedAt,null);
const snapshot=JSON.stringify(s);
finish(HANG==='fetch'?ok({...summary,stale:true}):{...summary,stale:true});await flush();
assert.equal(JSON.stringify(s),snapshot,'late response must not change data or provenance');
context.fetch=async()=>ok(summary);await s.refresh('api/summary');const success=s.receivedAt;
context.fetch=(_path,opts)=>{signal=opts.signal;return new Promise(resolve=>{finish=resolve;});};
const cancelled=s.refresh('api/summary');s.cancel();await cancelled;
assert.equal(signal.aborted,true);assert.equal(s.receivedAt,success);assert.match(s.error,/cancel/i);
const afterCancel=JSON.stringify(s);finish(ok({...summary,stale:true}));await flush();
assert.equal(JSON.stringify(s),afterCancel);
context.fetch=async()=>ok(summary);assert.equal(await s.refresh('api/summary'),true);
assert.equal(s.error,'');assert.equal(timers.size,0);
""".replace("HANG", json.dumps(hang)))


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
@pytest.mark.parametrize("hang", ["fetch", "body"])
def test_actual_page_hang_paints_snapshot_and_restores_one_loop(page, hang):
    run_js(FAKE_CLOCK + r"""
const fixture={...summary,repo:'/fixture/framework',consumer:'/fixture/consumer',
 window:{min_days:1,max_days:7,default_days:7,newest_event:stamp},
 status_strip:{system:'attention',needs_you:{high:0,med:0,low:0,total:0},drift:{skills:0},
 candidates:{total:0},loop:{state:'dormant',dormant_days:1},firewall:{status:'intact'},
 freshness:{recall_floor_age_days:1}},
 loop:{chains:[],stages:{harvest:{all:0},candidates:{total:0},proposals:{open:0},
 review:{accepted:0,auto_accept:0,rejected:0,auto_reject:0,human_review:0},
 enacted:{rules:0,skills_created:0,skills_healed:0}}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
const mounts=[];context.BrainMap={mount(_,data){mounts.push(data);return{demoCard(){}};}};
const requests=[];
context.fetch=(path,opts)=>{
 if(path==='proposal_review.html')return Promise.resolve({ok:true});
 let finish;const pending=new Promise(resolve=>{finish=resolve;});
 requests.push({path,signal:opts.signal,finish});
 return HANG==='fetch'?pending:{ok:true,json:()=>pending};
};
const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
assert.equal(mounts.length,1,'saved map must paint before network completion');
assert.equal(elements.get('asof').textContent,'2026-08-01');
await flush();const count=PAGE==='dashboard.html'?3:2;
assert.equal(requests.length,count);assert.equal(activeIntervals.size,1);
const tick=[...activeIntervals.values()][0];tick();tick();await flush();
assert.equal(requests.length,count,'a slow refresh must not overlap');
await expire();assert.match(elements.get('data-source-status').textContent,/refresh failed.*timed out/i);
if(PAGE==='dashboard.html')assert.match(elements.get('operations-source-status').textContent,/unavailable.*timed out/i);
assert.ok(requests.every(r=>r.signal.aborted));
const before=elements.get('data-source-status').textContent;
for(const r of requests)r.finish(HANG==='fetch'?ok(fixture):fixture);await flush();
assert.equal(elements.get('data-source-status').textContent,before);
tick();await flush();assert.equal(requests.length,count*2);
await fire('pagehide');assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
assert.ok(requests.every(r=>r.signal.aborted));
const hidden=elements.get('data-source-status').textContent;
for(const r of requests)r.finish(HANG==='fetch'?ok(fixture):fixture);await flush();
assert.equal(elements.get('data-source-status').textContent,hidden);
const operations={read_only:true,server:{},proposals:{counts:{value:{accepted:0}}}};
context.fetch=async path=>ok(path==='api/summary'?fixture:path==='api/map'?map:operations);
await fire('pageshow');await fire('pageshow');
assert.equal(activeIntervals.size,1);assert.equal(timers.size,0);
assert.match(elements.get('data-source-status').textContent,/^Live responses/);
assert.equal(mounts.length,1,'unchanged map keeps interaction after recovery');
if(PAGE==='dashboard.html'){
 assert.match(elements.get('operations-source-status').textContent,/live response.*last success/i);
 const success=elements.get('operations-source-status').textContent;
 context.fetch=async()=>failure;await [...activeIntervals.values()][0]();
 assert.match(elements.get('operations-source-status').textContent,/cached live response.*refresh failed/i);
 assert.ok(elements.get('operations-source-status').textContent.includes(success.split('last success ')[1]));
}
""".replace("PAGE", json.dumps(page)).replace("HANG", json.dumps(hang)))


def test_cancelled_flight_cannot_clear_its_replacement_without_abort_support():
    run_js(FAKE_CLOCK + r"""
delete context.AbortController;
const finishes=[];context.fetch=()=>new Promise(resolve=>finishes.push(resolve));
const s=U.dataSource(summary,validSummary);
const old=s.refresh('api/summary');await expire();assert.equal(await old,false);
const current=s.refresh('api/summary');
finishes[0](ok({...summary,stale:true}));await flush();
assert.equal(s.refresh('api/summary'),current);assert.equal(finishes.length,2);
finishes[1](ok({...summary,newer:true}));assert.equal(await current,true);
assert.equal(s.data.newer,true);assert.equal(timers.size,0);
""")


@pytest.mark.parametrize("dispose_before_start", [True, False])
def test_page_lifecycle_visibility_and_permanent_disposal(dispose_before_start):
    run_js(FAKE_CLOCK + r"""
let calls=0,painted=0;
const s=U.dataSource(summary,validSummary);
context.fetch=()=>{calls++;return new Promise(()=>{});};
U.pageRefresh(async current=>{await s.refresh('api/summary');if(current())painted++;},()=>s.cancel());
if(!EARLY)await flush();
for(const fn of events.get('pagehide'))fn({persisted:false});await flush();
assert.equal(calls,EARLY?0:1);assert.equal(timers.size,0);assert.equal(activeIntervals.size,0);assert.equal(painted,0);
await fire('pageshow');assert.equal(activeIntervals.size,0);assert.equal(calls,EARLY?0:1);
// A separate visible-page owner pauses and resumes, without duplicate loops.
U.pageRefresh(async current=>{await s.refresh('api/summary');if(current())painted++;},()=>s.cancel());
await flush();context.document.hidden=true;
for(const fn of documentEvents.get('visibilitychange'))fn();await flush();
assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
context.document.hidden=false;
for(const fn of documentEvents.get('visibilitychange'))fn();await flush();
assert.equal(activeIntervals.size,1);
await fire('pagehide');assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
""".replace("EARLY", json.dumps(dispose_before_start)))


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
def test_actual_page_file_mode_has_no_requests_or_polling(page):
    run_js(FAKE_CLOCK + r"""
context.location.protocol='file:';let calls=0;context.fetch=()=>{calls++;throw Error('offline');};
const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);await flush();
assert.equal(calls,0);assert.equal(timers.size,0);assert.equal(activeIntervals.size,0);
await fire('pageshow');assert.equal(calls,0);assert.equal(activeIntervals.size,0);
""".replace("PAGE", json.dumps(page)))


def test_operations_and_probe_hangs_do_not_delay_dashboard_projection():
    run_js(FAKE_CLOCK + r"""
const fixture={...summary,repo:'/fixture/framework',consumer:'/fixture/consumer',
 window:{min_days:1,max_days:7,default_days:7,newest_event:stamp},
 status_strip:{system:'attention',needs_you:{high:0,med:0,low:0,total:0},drift:{skills:0},
 candidates:{total:0},loop:{state:'dormant',dormant_days:1},firewall:{status:'intact'},
 freshness:{recall_floor_age_days:1}},
 loop:{chains:[],stages:{harvest:{all:0},candidates:{total:0},proposals:{open:0},
 review:{accepted:0,auto_accept:0,rejected:0,auto_reject:0,human_review:0},
 enacted:{rules:0,skills_created:0,skills_healed:0}}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
const fresh={...fixture,generated_at:'2026-08-02T00:00:00Z'};
const signals=[];context.fetch=(path,opts)=>{
 if(path==='api/summary')return Promise.resolve(ok(fresh));
 if(path==='api/map')return Promise.resolve(ok(map));
 signals.push(opts.signal);return new Promise(()=>{});
};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);await flush();
assert.equal(elements.get('asof').textContent,'2026-08-02');
assert.match(elements.get('data-source-status').textContent,/^Live responses/);
assert.match(elements.get('operations-source-status').textContent,/unavailable/);
assert.equal(signals.length,2);await fire('pagehide');
assert.ok(signals.every(signal=>signal.aborted));assert.equal(timers.size,0);
""")


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
def test_invalid_saved_payloads_are_not_painted_as_available_data(page):
    run_js(FAKE_CLOCK + r"""
context.location.protocol='file:';
context.BRAIN_SUMMARY={unexpected:'invalid summary'};
context.BRAIN_MAP={unexpected:'invalid map'};
const mounts=[];context.BrainMap={mount(_,data){mounts.push(data);return{demoCard(){}};}};
const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);await flush();
assert.match(elements.get('data-source-status').textContent,/^Data unavailable/);
assert.equal(mounts.length,0,'invalid saved map must not reach the renderer');
assert.equal(activeIntervals.size,0);
""".replace("PAGE", json.dumps(page)))


PAGE_DATA = r"""
const fixture={...summary,repo:'/fixture/framework',consumer:'/fixture/consumer',
 window:{min_days:1,max_days:7,default_days:7,newest_event:stamp},
 status_strip:{system:'attention',needs_you:{high:0,med:0,low:0,total:0},drift:{skills:0},
 candidates:{total:0},loop:{state:'dormant',dormant_days:1},firewall:{status:'intact'},
 freshness:{recall_floor_age_days:1}},
 loop:{chains:[],stages:{harvest:{all:0},candidates:{total:0},proposals:{open:0},
 review:{accepted:0,auto_accept:0,rejected:0,auto_reject:0,human_review:0},
 enacted:{rules:0,skills_created:0,skills_healed:0}}}};
const mounts=[];context.BrainMap={mount(_,data){mounts.push(data);return{demoCard(){}};}};
const boot=()=>{
 const html=fs.readFileSync(process.argv[1]+'/'+PAGE,'utf8');
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
};
"""


BAD_PAGE_PAYLOADS = {
    "summary_status_only": "badSummary={status_strip:{}};",
    "summary_window": "badSummary.window='bad';",
    "summary_window_type": "badSummary.window.max_days='7';",
    "summary_window_nonfinite": "badSummary.window.max_days=Infinity;",
    "summary_window_range": "badSummary.window.min_days=8;",
    "summary_status_child": "badSummary.status_strip.needs_you=null;",
    "summary_loop": "badSummary.loop.stages=[];",
    "summary_array": "badSummary.days={bad:true};",
    "summary_array_member": "badSummary.timeline=[null];",
    "summary_matrix": "badSummary.matrix.cells='bad';",
    "summary_date_type": "badSummary.generated_at={bad:true};",
    "map_nodes": "badMap.nodes={bad:true};",
    "map_node_member": "badMap.nodes=[null];",
    "map_edges": "badMap.edges='bad';",
    "map_cards": "badMap.cards=[];",
}


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
@pytest.mark.parametrize("delivery", ["saved", "live"])
@pytest.mark.parametrize("case", BAD_PAGE_PAYLOADS)
def test_actual_pages_reject_wrong_shapes_without_losing_last_success(page, delivery, case):
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", json.dumps(page)) + r"""
let badSummary=JSON.parse(JSON.stringify(fixture)),badMap=JSON.parse(JSON.stringify(map));
MUTATE
if(DELIVERY==='saved'){
 context.location.protocol='file:';context.BRAIN_SUMMARY=badSummary;context.BRAIN_MAP=badMap;
 boot();await flush();
 const status=elements.get('data-source-status').textContent;
 assert.match(status,/Data incomplete|Data unavailable/);
 assert.ok(mounts.every(m=>BAD_KIND==='summary'?m.summary!==badSummary:m.map!==badMap),
   'rejected source objects must never reach the renderer');
 // Missing summary must not leave keyboard window handlers dereferencing it.
 for(const fn of documentEvents.get('keydown')||[])fn({target:{tagName:'DIV'},key:'ArrowRight'});
}else{
 context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
 context.fetch=async p=>ok(p==='api/summary'?fixture:p==='api/map'?map:{read_only:true,server:{}});
 boot();await flush();
 const before=elements.get('data-source-status').textContent;
 assert.match(before,/^Live responses/);const mountCount=mounts.length;
 context.fetch=async p=>ok(p==='api/summary'?badSummary:p==='api/map'?badMap:{read_only:true,server:{}});
 await [...activeIntervals.values()][0]();
 const failed=elements.get('data-source-status').textContent;
 assert.match(failed,/refresh failed \(invalid response\)/);
 assert.equal(mounts.length,mountCount);
 assert.equal(elements.get('asof').textContent,'2026-08-01');
 context.fetch=async p=>ok(p==='api/summary'?fixture:p==='api/map'?map:{read_only:true,server:{}});
 await [...activeIntervals.values()][0]();
 assert.match(elements.get('data-source-status').textContent,/^Live responses/);
 assert.doesNotMatch(elements.get('data-source-status').textContent,/refresh failed/);
 assert.equal(mounts.length,mountCount);
 await fire('pagehide');
}
""".replace("MUTATE", BAD_PAGE_PAYLOADS[case]).replace("DELIVERY", json.dumps(delivery))
        .replace("BAD_KIND", json.dumps(case.split("_")[0])))


def test_renderer_admission_bounds_and_inner_map_shapes():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
const badSummary={...fixture,window:{...fixture.window,max_days:1000000000}};
assert.equal(U.usableSummary(badSummary),false,'finite request timeouts cannot bound a billion-step synchronous window');
for(const badMap of [
 {...map,nodes:[{id:'a',type:'agent'}]},
 {...map,nodes:[{id:'a',type:'agent',label:'a',date:7}]},
 {...map,cards:{a:{one_line:7}}},
 {...map,cards:{a:{page:7}}},
])assert.equal(U.usableMap(badMap),false);
assert.equal(U.usableSummary({...fixture,window:{...fixture.window,max_days:366}}),true);
""")


def test_actual_dashboard_keeps_malformed_attention_evidence_without_actions():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'dashboard.html'") + r"""
context.location.protocol='file:';
fixture.inbox=[{id:'P-90',kind:'proposal_review',title:'SAFE_HISTORY',detail:'source evidence',
 surface:'framework',actionable:true,action_cmd:'WITHHELD_COMMAND'},null];
fixture.attention={framework_actions:'malformed'};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
let panel='';U.panel.open=(_,html)=>{panel=html;};boot();await flush();
elements.get('inbox').children[0].children[0].listeners.click();
assert.match(panel,/SAFE_HISTORY/);assert.match(panel,/view-only/);
assert.doesNotMatch(panel,/ui-copy|data-review-link|WITHHELD_COMMAND/);
""")


def test_offline_graph_shim_retains_valid_saved_map_without_shared_ui():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.UI=undefined;context.location.protocol='file:';
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;boot();await flush();
assert.equal(mounts.length,1);assert.equal(mounts[0].summary,fixture);assert.equal(mounts[0].map,map);
assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
""")


def test_graph_inspector_keeps_hostile_source_text_inert_and_explains_enacts():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';
const hostile='<img src=x onerror=alert(1)>';
const proposal={id:'proposal-hostile',type:'proposal',label:hostile,date:'2026-08-01'};
const rule={id:'rule-safe',type:'rule',label:'R-safe',date:'2026-08-01'};
const graph={generated_at:stamp,nodes:[proposal,rule],
 edges:[{src:proposal.id,dst:rule.id,type:'enacts',weight_e:1}],
 cards:{[proposal.id]:{title:hostile,one_line:hostile,date:'2026-08-01',source:hostile,
   page:'javascript:alert(1)'},[rule.id]:{title:'R-safe',one_line:'source rule',date:'2026-08-01',source:'rules.md',page:''}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;
let choose;
context.BrainMap={mount(_canvas,options){choose=options.onSelect;return{
 getVisibleNodes(){return graph.nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getConnections(id){return id===proposal.id?[{edge:graph.edges[0],node:rule,direction:'out'}]:[];},
 selectById(){return false;},egoMode(){return true;}
};}};
boot();await flush();choose(proposal);
const body=elements.get('inspector-body');
const descendants=root=>[root,...root.children.flatMap(descendants)];
const rendered=descendants(body);
assert.equal(body.innerHTML,'','source values must be emitted through textContent, not HTML parsing');
assert.ok(rendered.some(node=>node.textContent===hostile));
assert.ok(rendered.every(node=>!String(node.href||'').startsWith('javascript:')));
assert.ok(rendered.some(node=>/not a lifecycle enactment or verification count/.test(node.textContent)));
""")


@pytest.mark.parametrize(("protocol", "linked"), [("file:", True), ("http:", False)])
def test_graph_recorded_page_path_links_only_in_file_view(protocol, linked):
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol=PROTOCOL;U.pageRefresh=()=>{};
const node={id:'agent-claude-code-main',type:'agent',label:'claude-code-main',date:'2026-08-01'};
const page='../pages/agent-claude-code-main.md';
const graph={generated_at:stamp,nodes:[node],edges:[],cards:{
 [node.id]:{title:'Claude Code',one_line:'recorded actor',date:'2026-08-01',source:'run logs',page}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;let choose;
context.BrainMap={mount(_canvas,options){choose=options.onSelect;return{
 getVisibleNodes(){return graph.nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getConnections(){return [];},selectById(){return false;},egoMode(){return true;}
};}};
boot();await flush();choose(node);
const walk=root=>[root,...root.children.flatMap(walk)];
const rendered=walk(elements.get('inspector-body'));
const action=rendered.find(item=>item.className==='source-action');
if(LINKED){assert.ok(action);assert.equal(action.href,page);}
else{
 assert.equal(action,undefined,'server view must not advertise its known 404 route as an action');
 assert.ok(rendered.some(item=>item.textContent.includes('Recorded source path: '+page)));
 assert.ok(rendered.some(item=>/unavailable in the server view/i.test(item.textContent)));
}
""".replace("PROTOCOL", json.dumps(protocol)).replace("LINKED", json.dumps(linked)))


def test_graph_runtime_safe_labels_require_exact_booleans():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';
const nodes=[{id:'skill-true',type:'skill',label:'true-skill',pack:'core'},
 {id:'skill-false',type:'skill',label:'false-skill',pack:'research'},
 {id:'skill-unknown',type:'skill',label:'unknown-skill',pack:'core'}];
fixture.skills=[{name:'true-skill',runtime_safe:true,governance:{}},
 {name:'false-skill',runtime_safe:false,governance:{}},
 {name:'unknown-skill',runtime_safe:'true',governance:{}}];
const graph={generated_at:stamp,nodes,edges:[],cards:{}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;let choose;
const inspector=elements.get('inspector-body')||context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){inspectorHtml=value;if(value==='')this.children=[];}});
context.BrainMap={mount(_canvas,options){choose=options.onSelect;return{
 getVisibleNodes(){return nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getConnections(){return [];},selectById(){return false;},egoMode(){return true;}
};}};
boot();await flush();
const text=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(elements.get('inspector-body')).map(node=>node.textContent).join(' ');};
choose(nodes[0]);assert.match(text(),/Runtime-safe core/);
choose(nodes[1]);assert.match(text(),/Development-time/);
choose(nodes[2]);assert.match(text(),/Unknown — not supplied as a boolean/);
assert.doesNotMatch(text(),/Runtime-safe core|Development-time/);
""")


def test_graph_refresh_revalidates_changed_and_removed_selection():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
const node={id:'skill-current',type:'skill',label:'validate',pack:'core'};
fixture.skills=[{name:'validate',runtime_safe:true,governance:{state:'recorded'}}];
let currentMap={generated_at:stamp,nodes:[node],edges:[],cards:{
 [node.id]:{title:'Validate',one_line:'OLD CARD',date:'2026-08-01',source:'old-source',page:''}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=currentMap;
const inspector=elements.get('inspector-body')||context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){inspectorHtml=value;if(value==='')this.children=[];}});
let active;
context.BrainMap={mount(_canvas,options){active={
 getVisibleNodes(){return options.map.nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getConnections(){return [];},egoMode(){return true;},
 selectById(id){const found=options.map.nodes.find(item=>item.id===id);if(!found)return false;
   options.onSelect(found);return true;}
};return active;}};
context.fetch=async path=>ok(path==='api/summary'?fixture:currentMap);
boot();await flush();active.selectById(node.id);
const text=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(elements.get('inspector-body')).map(item=>item.textContent).join(' ');};
assert.match(text(),/OLD CARD/);
currentMap={...currentMap,generated_at:'2026-08-02T00:00:00Z',cards:{
 [node.id]:{title:'Validate',one_line:'NEW CARD',date:'2026-08-02',source:'new-source',page:''}}};
await [...activeIntervals.values()][0]();
assert.match(text(),/NEW CARD/);assert.doesNotMatch(text(),/OLD CARD/);
currentMap={...currentMap,generated_at:'2026-08-03T00:00:00Z',nodes:[],cards:{}};
await [...activeIntervals.values()][0]();
assert.match(text(),/selected record is unavailable in the current map response/i);
assert.doesNotMatch(text(),/NEW CARD|old-source|new-source/);
""")


def test_graph_controls_clear_selection_excluded_from_visible_projection():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';context.location.pathname='/graph.html';
context.location.search='';context.location.hash='';
context.history={replaceState(_state,_title,url){
 const value=String(url),hash=value.indexOf('#');context.location.hash=hash<0?'':value.slice(hash);
}};
const spawn={id:'spawn-current',type:'spawn',label:'contract current',date:'2026-08-01'};
const skill={id:'skill-current',type:'skill',label:'validate',pack:'core'};
const proposal={id:'proposal-current',type:'proposal',label:'proposal alpha',date:'2026-08-01'};
const nodes=[spawn,skill,proposal];
const graph={generated_at:stamp,nodes,edges:[],cards:{
 [spawn.id]:{title:'Current contract',one_line:'spawn evidence',source:'spawn.jsonl',page:''},
 [skill.id]:{title:'Validate',one_line:'skill evidence',source:'SKILL.md',page:''},
 [proposal.id]:{title:'Proposal alpha',one_line:'proposal evidence',source:'proposals.jsonl',page:''}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;
const modeButtons=['work','governance','usage'].map(value=>{
 const button=element();button.attributes={};button.attributes['data-graph-mode']=value;
 button.getAttribute=name=>button.attributes[name]||null;return button;
});
const legendItems=['work','governance','usage'].map(value=>{
 const item=element();item.attributes={};item.attributes['data-legend-mode']=value;
 item.getAttribute=name=>item.attributes[name]||null;return item;
});
context.document.querySelectorAll=selector=>selector==='[data-graph-mode]'?modeButtons:
 selector==='[data-legend-mode]'?legendItems:[];
const inspector=context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){
 inspectorHtml=value;if(value==='')this.children=[];
}});
let activeMode='work',activeQuery='',activeType='all',active;const selectionRequests=[];
const allowed={work:new Set(['spawn','skill','agent']),
 governance:new Set(['proposal','skill','rule','harvest_finding','correction','anomaly','decision','agent']),
 usage:new Set(['skill','agent'])};
context.BrainMap={mount(_canvas,options){activeMode=options.mode;activeQuery=options.query||'';activeType=options.type||'all';
 const visible=()=>nodes.filter(node=>allowed[activeMode].has(node.type) &&
   (activeType==='all'||node.type===activeType) &&
   (!activeQuery||[node.id,node.label,node.type].join(' ').toLowerCase().includes(activeQuery.toLowerCase())));
 active={getVisibleNodes:visible,getHiddenCount(){return nodes.length-visible().length;},getZoom(){return 1;},
  getConnections(){return [];},egoMode(){return true;},fit(){},zoomBy(){},
  selectById(id){selectionRequests.push(id);const found=visible().find(node=>node.id===id);if(!found)return false;
   options.onSelect(found);return true;},
  setMode(next){activeMode=next;activeType='all';return this;},
  setFilter(filter){activeQuery=filter.query||'';activeType=filter.type||'all';return this;}};
 return active;}};
boot();await flush();
const text=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(inspector).map(item=>item.textContent).join(' ');};
const clickBrowser=id=>elements.get('graph-browser-list').children
 .find(button=>button['data-node-id']===id).listeners.click();
clickBrowser(spawn.id);assert.match(text(),/Current contract/);assert.match(context.location.hash,/spawn-current/);
modeButtons.find(button=>button.getAttribute('data-graph-mode')==='governance').listeners.click();
assert.match(text(),/unavailable in the current view/i);assert.equal(context.location.hash,'');
const requestsAfterClear=selectionRequests.length;
for(const handler of documentEvents.get('keydown')||[])handler({target:{tagName:'DIV'},key:'ArrowLeft'});
assert.equal(selectionRequests.length,requestsAfterClear,'a later remount must not refocus an excluded ID');

clickBrowser(proposal.id);assert.match(text(),/Proposal alpha/);assert.match(context.location.hash,/proposal-current/);
elements.get('graph-search').listeners.input({target:{value:'validate'}});
assert.match(text(),/unavailable in the current view/i);assert.equal(context.location.hash,'');

elements.get('graph-search').listeners.input({target:{value:''}});clickBrowser(skill.id);
elements.get('graph-type').listeners.change({target:{value:'proposal'}});
assert.match(text(),/unavailable in the current view/i);assert.equal(context.location.hash,'');

elements.get('graph-type').listeners.change({target:{value:'all'}});clickBrowser(skill.id);
modeButtons.find(button=>button.getAttribute('data-graph-mode')==='usage').listeners.click();
assert.match(text(),/Validate/);assert.match(context.location.hash,/skill-current/);
""")


def test_admitted_projection_mounts_the_actual_map_renderer():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
const frames=new Map();let frameId=0;
context.requestAnimationFrame=fn=>{frames.set(++frameId,fn);return frameId;};
context.cancelAnimationFrame=id=>frames.delete(id);
context.getComputedStyle=()=>({position:'relative',getPropertyValue(){return '';}});
context.removeEventListener=()=>{};context.document.removeEventListener=()=>{};
const drawing=new Proxy({measureText:()=>({width:10})},{get:(obj,key)=>key in obj?obj[key]:(()=>{})});
const canvas=element();canvas.getContext=()=>drawing;canvas.parentElement=element();
canvas.clientWidth=1000;canvas.clientHeight=600;canvas.removeEventListener=()=>{};
const originalElement=context.document.createElement;
context.document.createElement=()=>({...originalElement(),remove(){}});
const projected={...map,nodes:[{id:'agent-fixture',type:'agent',label:'fixture'},
 {id:'skill-gate-check',type:'skill',label:'gate-check',pack:'core'}],
 edges:[{src:'agent-fixture',dst:'skill-gate-check',type:'used',weight_e:1,weight_i:0}],cards:{}};
assert.equal(U.usableSummary(fixture),true);assert.equal(U.usableMap(projected),true);
vm.runInContext(fs.readFileSync(process.argv[1]+'/map.js','utf8'),context);
const instance=context.BrainMap.mount(canvas,{summary:fixture,map:projected,windowDays:7,embedded:true});
assert.equal(instance.agents.length,1);assert.equal(instance.skills.length,1);
const [id,frame]=[...frames][0];frames.delete(id);frame(0);
instance.destroy();assert.equal(frames.size,0);
""")


def test_graph_recorded_work_inspector_discloses_typed_raw_evidence_safely():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';context.location.pathname='/graph.html';context.location.search='';context.location.hash='';
context.history={replaceState(_state,_title,url){const value=String(url),at=value.indexOf('#');
 context.location.hash=at<0?'':value.slice(at);}};
const capture={namespace:'agent_system/framework',locator:'framework:run-and-spawn',capture_basis:{
 captured_at:'2026-09-07T23:30:00Z',atomic:false,limits:{file_bytes:1048576,file_rows:2048,row_bytes:65536},files:[
  {locator:'run_state/framework.run.jsonl',sha256:'a'.repeat(64),bytes:120,rows:2,availability:'available'},
  {locator:'run_state/spawn.jsonl',sha256:null,bytes:null,rows:0,availability:'unavailable',
   captured_prefix_sha256:'b'.repeat(64),captured_prefix_bytes:80}]}};
const source={id:'work:source',type:'work',label:'review',record_id:'review',kind:'task',role:false,
 raw_status:{state:'assigned',toString:7},source_locator:'run:review',source_metadata:capture,_workProjection:true};
const target={id:'work:target',type:'work',label:'check',record_id:'check',kind:'task',raw_status:0,
 source_locator:'run:check',source_metadata:capture,_workProjection:true};
const skill={id:'skill:validate',type:'skill',label:'validate',skill_id:'validate',source_metadata:capture,_workProjection:true};
const parallel=['parent','spawn_assignment'].map(type=>({type,source:source.id,target:target.id,
 source_locator:'edge:'+type,source_metadata:capture}));
parallel.push({type:'dependency',source:target.id,target:source.id,source_locator:'edge:dependency',source_metadata:capture});
parallel.push({type:'allowed_skill',source:source.id,target:skill.id,source_locator:'edge:allowed',source_metadata:capture,
 source_refs:['finding:one#ref='+'x'.repeat(80),'finding:two#ref='+'y'.repeat(80)]});
parallel.push({type:'observed_skill',source:source.id,target:skill.id,source_locator:'edge:observed',
 assertion_basis:'caller_supplied',source_metadata:capture});
parallel.push({type:'spawn_assignment',source:source.id,target:source.id,source_locator:'edge:self',source_metadata:capture});
const graph={...map,work:{schema_version:'work-graph/v1',source:capture,
 projection_state:{state:'partial',reason:'unresolved_references'},
 dependency_availability:{state:'available',reason:null},limits:{unit:'items',record_count:2,node_candidates:3,
 edge_candidates:6,unresolved_candidates:1,cycle_candidates:1,nodes_omitted:0,edges_omitted:0,
 unresolved_omitted:0,cycles_omitted:0},nodes:[source,target,skill],edges:parallel,
 unresolved:[{reason:'duplicate_id',record_id:'held-duplicate',occurrences:2}],cycles:[{node_ids:[source.id,target.id]}]}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;let choose;
context.BrainMap={mount(_canvas,options){choose=options.onSelect;return{
 getVisibleNodes(){return [source,target,skill];},getHiddenCount(){return 0;},getZoom(){return 1;},
 getWorkState(){return {state:'partial',reason:'unresolved_references',projection:graph.work};},
 getNodeById(id){return [source,target,skill].find(node=>node.id===id)||null;},
 getConnections(id){return parallel.filter(edge=>edge.source===id||edge.target===id).map(edge=>({edge,
  node:[source,target,skill].find(node=>node.id===(edge.source===id?edge.target:edge.source)),
  direction:edge.source===id?'out':'in'}));},selectById(){return false;},egoMode(){return true;}
};}};
boot();await flush();choose(source);
const descendants=root=>[root,...root.children.flatMap(descendants)];
const rendered=descendants(elements.get('inspector-body')).map(node=>node.textContent).join('\n');
assert.match(rendered,/\{"state":"assigned","toString":7\}/);assert.match(rendered,/Role\nfalse/);
assert.match(rendered,/Self-assignment/);assert.match(rendered,/Recorded parent/);
assert.match(rendered,/Recorded assignment/);assert.match(rendered,/Explicit dependency/);
assert.match(rendered,/Allowed skill/);assert.match(rendered,/caller-reported/);
assert.match(rendered,/finding:one#ref=/);assert.match(rendered,/finding:two#ref=/);
assert.ok(rendered.includes('x'.repeat(80)));assert.ok(rendered.includes('y'.repeat(80)),
 'complete exact source_refs remain available in disclosure');
const status=descendants(elements.get('work-evidence-body')).map(node=>node.textContent).join('\n');
assert.match(status,/unresolved_references/);assert.match(status,/duplicate_id/);assert.match(status,/cycle/i);
assert.match(status,/run_state\/framework\.run\.jsonl/);assert.match(status,/a{64}/);
assert.match(status,/run_state\/spawn\.jsonl/);assert.match(status,/unavailable/);
assert.match(status,/not authenticated/i);assert.match(status,/not an atomic/i);
assert.equal(elements.get('work-state')['data-work-state'],'partial');
assert.equal(elements.get('work-state')['data-dependency-state'],'available');
""")


@pytest.mark.parametrize(("edge", "related_id", "expected"), [
    ({"src": "selected", "dst": "other"}, "other", "outgoing"),
    ({"src": "other", "dst": "selected"}, "other", "incoming"),
    ({"src": "selected", "dst": "selected"}, "selected", "self"),
    ({"source": "selected", "target": "other"}, "other", "outgoing"),
    ({"source": "other", "target": "selected"}, "other", "incoming"),
    ({"source": "selected", "target": "selected"}, "selected", "self"),
    ({}, "other", "direction unavailable"),
    ({"src": "selected"}, "other", "direction unavailable"),
    ({"source": "selected"}, "other", "direction unavailable"),
    ({"src": None, "dst": None}, "selected", "direction unavailable"),
    ({"source": None, "target": None}, "selected", "direction unavailable"),
    ({"src": "", "dst": ""}, "selected", "direction unavailable"),
    ({"source": 0, "target": 0}, "selected", "direction unavailable"),
    ({"src": [], "dst": {}}, "other", "direction unavailable"),
    ({"source": "elsewhere", "target": "other"}, "other", "direction unavailable"),
    ({"src": "selected", "dst": "selected"}, "other", "direction unavailable"),
    ({"src": "selected", "dst": "other", "source": "selected"}, "other", "direction unavailable"),
    ({"src": "selected", "dst": "other", "source": "other", "target": "selected"}, "other", "direction unavailable"),
    ({"src": "selected", "dst": "other", "source": "selected", "target": "other"}, "other", "outgoing"),
])
def test_graph_inspector_qualifies_actual_relation_endpoints(edge, related_id, expected):
    """The shipped inspector must not infer a self-link from absent raw fields."""
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';
const selected={id:'selected',type:'agent',label:'Selected record'};
const other={id:'other',type:'skill',label:'Other record'};
const nodes=[selected,other], raw={type:'spawn_assignment',...EDGE};
const related=nodes.find(node=>node.id===RELATED_ID);
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP={...map,nodes,edges:[]};
let choose,clicked;
context.BrainMap={mount(_canvas,options){choose=options.onSelect;return{
 getVisibleNodes(){return nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getWorkState(){return {state:'missing',reason:'work_projection_missing',projection:null};},
 getNodeById(id){return nodes.find(node=>node.id===id)||null;},
 // A normalized row is not proof of valid raw endpoints: use deliberately
 // misleading direction to ensure the inspector checks its actual evidence.
 getConnections(){return [{edge:raw,node:related,direction:'out'}];},
 selectById(id){clicked=id;return true;},egoMode(){return true;}
};}};
boot();await flush();choose(selected);
const walk=root=>[root,...root.children.flatMap(walk)];
const rows=walk(elements.get('inspector-body')).filter(node=>node.className==='relation-row');
assert.equal(rows.length,1);
const row=rows[0], texts=row.children.map(child=>child.textContent);
assert.equal(texts[2],'recorded assignment · '+EXPECTED);
if(EXPECTED==='self') assert.match(texts[1],/Self-assignment/);
else assert.doesNotMatch(texts[1],/Self-assignment/);
if(EXPECTED==='direction unavailable') assert.match(texts[1],/endpoints.*unavailable|unavailable.*endpoints/i);
if(EXPECTED==='outgoing') assert.match(texts[1],/selected record names the related record/);
if(EXPECTED==='incoming') assert.match(texts[1],/related record names the selected record/);
row.listeners.click();assert.equal(clicked,RELATED_ID,'the related-record interaction remains available');
""".replace("EDGE", json.dumps(edge)).replace("RELATED_ID", json.dumps(related_id)).replace("EXPECTED", json.dumps(expected)))


def test_graph_current_malformed_work_refresh_clears_prior_selection():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
const capture={namespace:'agent_system/framework',locator:'framework:run-and-spawn',capture_basis:{captured_at:stamp,files:[]}};
const node={id:'work:current',type:'work',label:'current task',record_id:'current',kind:'task',
 source_locator:'run:current',source_metadata:capture,_workProjection:true};
const baseWork={schema_version:'work-graph/v1',source:capture,projection_state:{state:'complete',reason:null},
 dependency_availability:{state:'unavailable',reason:'dependencies_not_supplied'},limits:{unit:'items',record_count:1,
 node_candidates:1,edge_candidates:0,unresolved_candidates:0,cycle_candidates:0,nodes_omitted:0,edges_omitted:0,
 unresolved_omitted:0,cycles_omitted:0},nodes:[node],edges:[],unresolved:[],cycles:[]};
let currentMap={...map,work:baseWork};context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=currentMap;
const inspector=context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){inspectorHtml=value;if(value==='')this.children=[];}});
let active,failMap=false;
context.BrainMap={mount(_canvas,options){const valid=options.map.work&&options.map.work.schema_version==='work-graph/v1'&&
 Array.isArray(options.map.work.nodes)&&Array.isArray(options.map.work.edges);
 const nodes=valid?[node]:[];active={getVisibleNodes(){return nodes;},getHiddenCount(){return 0;},getZoom(){return 1;},
 getWorkState(){return valid?{state:'complete',reason:null,projection:options.map.work}:
  {state:'malformed',reason:'invalid_work_projection'};},getNodeById(id){return nodes.find(item=>item.id===id)||null;},
 getConnections(){return [];},egoMode(){return true;},selectById(id){const found=nodes.find(item=>item.id===id);if(!found)return false;
  options.onSelect(found);return true;}};return active;}};
context.fetch=async path=>path==='api/map'&&failMap?failure:ok(path==='api/summary'?fixture:currentMap);
boot();await flush();active.selectById(node.id);
const bodyText=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(elements.get('inspector-body')).map(item=>item.textContent).join(' ');};
assert.match(bodyText(),/current task/);
failMap=true;await [...activeIntervals.values()][0]();
assert.match(bodyText(),/current task/,'failed refresh retains the explicitly qualified last valid selection');
const staleState=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(elements.get('work-state')).map(item=>item.textContent).join(' ');};
assert.match(staleState(),/last valid map response/);assert.match(staleState(),/current refresh failed/);
failMap=false;
currentMap={...currentMap,generated_at:'2026-08-02T00:00:00Z',work:{schema_version:'work-graph/v1',nodes:'bad'}};
await [...activeIntervals.values()][0]();
assert.match(bodyText(),/selected record is unavailable in the current map response/i);
assert.doesNotMatch(bodyText(),/current task|run:current/);
const stateText=()=>{const walk=root=>[root,...root.children.flatMap(walk)];
 return walk(elements.get('work-state')).map(item=>item.textContent).join(' ');};
assert.match(stateText(),/Recorded work unavailable/);
""")


def test_graph_failed_capture_discloses_prefix_without_synthetic_zero_graph():
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
const prefix='c'.repeat(64);const capture={state:'unavailable',reason:'source_file_byte_limit_exceeded',source:{
 namespace:'agent_system/framework',locator:'framework:run-and-spawn',capture_basis:{captured_at:stamp,atomic:false,
 limits:{file_bytes:1048576,file_rows:2048,row_bytes:65536},files:[{locator:'run_state/framework.run.jsonl',
 sha256:null,bytes:null,rows:2048,availability:'byte_limit_exceeded',captured_prefix_sha256:prefix,
 captured_prefix_bytes:1048576}]}}};
const graph={...map,nodes:[{id:'legacy-spawn',type:'spawn',label:'legacy contract'}],work_capture:capture};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;
context.BrainMap={mount(){return{getVisibleNodes(){return [];},getHiddenCount(){return 0;},getZoom(){return 1;},
 getWorkState(){return {state:'unavailable',reason:capture.reason,projection:null,capture};},getConnections(){return [];},
 getNodeById(){return null;},selectById(){return false;},egoMode(){return false;}};}};
boot();await flush();
const walk=root=>[root,...root.children.flatMap(walk)];
const state=walk(elements.get('work-state')).map(item=>item.textContent).join(' ');
const evidence=walk(elements.get('work-evidence-body')).map(item=>item.textContent).join(' ');
assert.match(state,/explicitly unavailable/);assert.match(state,/source_file_byte_limit_exceeded/);
assert.doesNotMatch(state,/0 work|zero work/i);assert.equal(elements.get('graph-browser-list').children.length,1);
assert.match(evidence,/captured_prefix_bytes=1048576/);assert.ok(evidence.includes(prefix));
assert.equal(elements.get('work-state')['data-dependency-state'],'unavailable');
""")


@pytest.mark.parametrize(("node_type", "expected_mode"), [
    ("proposal", "governance"),
    ("agent", "usage"),
    ("spawn", "governance"),
])
def test_graph_legacy_deep_link_routes_to_existing_mode_and_preserves_query(node_type, expected_mode):
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.protocol='file:';context.location.pathname='/graph.html';context.location.search='?keep=1';
const id=NODE_TYPE+':legacy/source id';context.location.hash='#node='+encodeURIComponent(id);
let written='';context.history={replaceState(_state,_title,url){written=String(url);
 const at=written.indexOf('#');context.location.hash=at<0?'':written.slice(at);}};
const node={id,type:NODE_TYPE,label:'legacy linked record',date:'2026-08-01'};
const graph={...map,nodes:[node],cards:{[id]:{title:'Legacy linked record',one_line:'preserved source',source:'legacy',page:''}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph;let activeMode='work';
const allowed=()=>activeMode==='usage'?['agent','skill']:
 activeMode==='governance'?['proposal','rule','harvest_finding','correction','anomaly','decision','agent','skill','spawn']:['work'];
context.BrainMap={mount(_canvas,options){activeMode=options.mode;return{
 getVisibleNodes(){return allowed().includes(node.type)?[node]:[];},getHiddenCount(){return 0;},getZoom(){return 1;},
 getWorkState(){return {state:'missing',reason:'work_projection_missing',projection:null};},
 getNodeById(requested){return requested===id&&allowed().includes(node.type)?node:null;},getConnections(){return [];},
 egoMode(){return true;},setMode(next){activeMode=next;return this;},selectById(requested){if(requested!==id||!allowed().includes(node.type))return false;
  options.onSelect(node);return true;}};}};
boot();await flush();
assert.equal(activeMode,EXPECTED_MODE);assert.match(elements.get('inspector-body').children[1].textContent,/Legacy linked record/);
assert.ok(written.startsWith('/graph.html?keep=1#node='));assert.equal(decodeURIComponent(context.location.hash.slice(6)),id);
""".replace("NODE_TYPE", json.dumps(node_type)).replace("EXPECTED_MODE", json.dumps(expected_mode)))


@pytest.mark.parametrize(("node_id", "node_type"), [
    ("spawn-live-only", "spawn"),
    ("work:framework:run:live-only", "work"),
])
def test_graph_startup_retains_saved_missing_bookmark_until_live_map_resolves(node_id, node_type):
    run_js(FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.pathname='/graph.html';context.location.search='?keep=1';
context.location.hash='#node='+encodeURIComponent(NODE_ID);
context.history={replaceState(_state,_title,url){const value=String(url),at=value.indexOf('#');
 context.location.hash=at<0?'':value.slice(at);}};
const saved={...map,nodes:[],cards:{},generated_at:'2026-08-01T00:00:00Z'};
const target={id:NODE_ID,type:NODE_TYPE,label:'Live-only target',date:'2026-08-02',
 record_id:NODE_TYPE==='work'?'live-only':undefined,kind:NODE_TYPE==='work'?'run':undefined};
const work={projection_state:{state:'complete',reason:null},dependency_availability:{state:'available',reason:null},
 source:{namespace:'fixture',locator:'fixture',capture_basis:{captured_at:stamp}},limits:{},
 nodes:NODE_TYPE==='work'?[target]:[],edges:[],unresolved:[],cycles:[]};
const live={...saved,generated_at:'2026-08-02T00:00:00Z',
 nodes:NODE_TYPE==='work'?[]:[target],work,cards:{[NODE_ID]:{title:'LIVE TARGET',source:'live-map',page:''}}};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;
const inspector=context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){
 inspectorHtml=value;if(value==='')this.children=[];}});
let activeMode='work',active;
const workNodes=options=>(options.map.work&&Array.isArray(options.map.work.nodes)?options.map.work.nodes:[])
 .map(node=>({...node,label:node.record_id||node.skill_id||node.label,_workProjection:true}));
const baseAllowed=node=>activeMode==='governance'?
 ['proposal','rule','harvest_finding','correction','anomaly','decision','agent','skill','spawn'].includes(node.type):
 activeMode==='usage'?['agent','skill'].includes(node.type):false;
context.BrainMap={mount(_canvas,options){activeMode=options.mode;
 const nodes=()=>activeMode==='work'?workNodes(options):options.map.nodes.filter(baseAllowed);
 active={getVisibleNodes:nodes,getHiddenCount(){return 0;},getZoom(){return 1;},getConnections(){return [];},
  getWorkState(){const projection=options.map.work;return projection?
   {state:projection.projection_state.state,reason:projection.projection_state.reason,projection,capture:projection.source}:
   {state:'missing',reason:'work_projection_missing',projection:null,capture:null};},
  getNodeById(id){return nodes().find(node=>node.id===id)||null;},egoMode(){return true;},
  setMode(next){activeMode=next;return this;},
  selectById(id){const found=nodes().find(node=>node.id===id);if(!found)return false;options.onSelect(found);return true;}};
 return active;}};
let finishMap;context.fetch=path=>path==='api/summary'?Promise.resolve(ok(fixture)):
 new Promise(resolve=>{finishMap=resolve;});
boot();await flush();
assert.equal(decodeURIComponent(context.location.hash.slice(6)),NODE_ID,
 'the saved map cannot erase a newer requested ID while live map acquisition is pending');
finishMap(ok(live));await flush();
const walk=root=>[root,...root.children.flatMap(walk)];
const text=walk(inspector).map(item=>item.textContent).join(' ');
assert.match(text,/LIVE TARGET/);assert.doesNotMatch(text,/unavailable in the current map response/i);
assert.equal(decodeURIComponent(context.location.hash.slice(6)),NODE_ID);
""".replace("NODE_ID", json.dumps(node_id)).replace("NODE_TYPE", json.dumps(node_type)))


GRAPH_PENDING_PAGE = FAKE_CLOCK + PAGE_DATA.replace("PAGE", "'graph.html'") + r"""
context.location.pathname='/graph.html';context.location.search='?keep=1';
const requestedId=__REQUESTED_ID__;context.location.hash='#node='+encodeURIComponent(requestedId);
let written='';context.history={replaceState(_state,_title,url){written=String(url);
 const at=written.indexOf('#');context.location.hash=at<0?'':written.slice(at);}};
const source={namespace:'fixture',locator:'fixture:work',capture_basis:{captured_at:stamp,atomic:true}};
const limits=omitted=>({unit:'items',record_cap:20,node_cap:20,edge_cap:20,diagnostic_cap:20,
 record_count:0,node_candidates:omitted,edge_candidates:0,unresolved_candidates:0,cycle_candidates:0,
 nodes_omitted:omitted,edges_omitted:0,unresolved_omitted:0,cycles_omitted:0});
const workNode=(id,title='Requested work')=>({id,type:'work',record_id:title,kind:'run',source_locator:'fixture',source_metadata:source});
const legacyNode=(id,title='Requested contract')=>({id,type:'spawn',label:title,date:'2026-08-02'});
const workProjection=(nodes,state='complete')=>state==='malformed'?{unexpected:true}:{schema_version:'work-graph/v1',source,
 projection_state:{state,reason:state==='complete'?null:state==='partial'?'projection_truncated':'capture_unavailable'},
 dependency_availability:{state:'available',reason:null},limits:limits(state==='partial'?1:0),
 nodes:state==='unavailable'?[]:nodes,edges:[],unresolved:[],cycles:[]};
const graph=(workNodes=[],state='complete',baseNodes=[])=>({generated_at:'2026-08-01T00:00:00Z',
 nodes:baseNodes,edges:[],work:workProjection(workNodes,state),cards:Object.fromEntries([...workNodes,...baseNodes]
  .map(node=>[node.id,{title:node.record_id||node.label,one_line:'supplied evidence',source:'fixture',page:''}]))});
const requestedWork=workNode(requestedId,'REQUESTED TARGET');
const requestedLegacy=legacyNode(requestedId,'REQUESTED TARGET');
const otherWork=workNode('work:fixture:other','HUMAN CHOICE');
const inspector=context.document.getElementById('inspector-body');let inspectorHtml='';
Object.defineProperty(inspector,'innerHTML',{get(){return inspectorHtml;},set(value){inspectorHtml=value;if(value==='')this.children=[];}});
const modeButtons=['work','governance','usage'].map(value=>{const button=element();button['data-graph-mode']=value;
 button.getAttribute=name=>button[name]||null;return button;});
const legendItems=['work','governance','usage'].map(value=>{const item=element();item['data-legend-mode']=value;
 item.getAttribute=name=>item[name]||null;return item;});
context.document.querySelectorAll=selector=>selector==='[data-graph-mode]'?modeButtons:
 selector==='[data-legend-mode]'?legendItems:[];
let activeMode='work',activeQuery='',activeType='all',active;const selections=[];
const classify=projection=>!projection||!projection.projection_state?{state:'malformed',reason:'invalid_work_projection',projection:null}:
 {state:projection.projection_state.state,reason:projection.projection_state.reason,projection,capture:projection.source};
const projected=options=>{const state=classify(options.map.work);return state.projection&&state.state!=='unavailable'?
 state.projection.nodes.map(node=>({...node,label:node.record_id||node.skill_id,_workProjection:true})):[];};
const allowedBase=node=>activeMode==='governance'?
 ['proposal','rule','harvest_finding','correction','anomaly','decision','agent','skill','spawn'].includes(node.type):
 activeMode==='usage'?['agent','skill'].includes(node.type):false;
context.BrainMap={mount(_canvas,options){mounts.push(options);activeMode=options.mode;
 const modeNodes=()=>activeMode==='work'?projected(options):options.map.nodes.filter(allowedBase);
 const visible=()=>modeNodes().filter(node=>(activeType==='all'||node.type===activeType)&&
  (!activeQuery||[node.id,node.label,node.record_id].join(' ').toLowerCase().includes(activeQuery.toLowerCase())));
 active={getVisibleNodes:visible,getHiddenCount(){return modeNodes().length-visible().length;},getZoom(){return 1;},
  getConnections(){return [];},getWorkState(){const state=classify(options.map.work);return {...state,capture:state.capture||null};},
  getNodeById(id){return modeNodes().find(node=>node.id===id)||null;},egoMode(){return true;},fit(){},zoomBy(){},
  setMode(next){activeMode=next;activeType='all';return this;},
  setFilter(filter){activeQuery=filter.query||'';activeType=filter.type||'all';return this;},
  selectById(id,emit){selections.push(id);const found=modeNodes().find(node=>node.id===id);if(!found)return false;
   if(emit!==false)options.onSelect(found);return true;}};return active;}};
const walk=root=>[root,...root.children.flatMap(walk)];
const inspectorText=()=>walk(inspector).map(item=>item.textContent).join(' ');
"""


def run_graph_pending(code, requested_id="work:fixture:requested"):
    run_js(GRAPH_PENDING_PAGE.replace("__REQUESTED_ID__", json.dumps(requested_id)) + code)


@pytest.mark.parametrize("first", ["http", "invalid", "unavailable", "malformed", "partial"])
def test_graph_pending_typed_bookmark_survives_failure_or_incomplete_work_then_recovers(first):
    first_reply = {
        "http": "failure",
        "invalid": "ok({unexpected:'map shape'})",
        "unavailable": "ok(graph([], 'unavailable'))",
        "malformed": "ok(graph([], 'malformed'))",
        "partial": "ok(graph([], 'partial'))",
    }[first]
    run_graph_pending(r"""
const saved=graph([], 'complete');context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;
context.fetch=path=>Promise.resolve(path==='api/summary'?ok(fixture):FIRST_REPLY);
boot();await flush();
assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
assert.match(inspectorText(),/bookmark is retained for retry/i);assert.doesNotMatch(inspectorText(),/REQUESTED TARGET/);
if(['http','invalid'].includes(FIRST))assert.match(elements.get('data-source-status').textContent,/refresh failed/i);
context.fetch=async path=>ok(path==='api/summary'?fixture:graph([requestedWork], 'complete'));
await [...activeIntervals.values()][0]();
assert.match(inspectorText(),/REQUESTED TARGET/);assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
""".replace("FIRST_REPLY", first_reply).replace("FIRST", json.dumps(first)))


@pytest.mark.parametrize(("requested_id", "node_type"), [
    ("spawn-live-missing", "spawn"),
    ("work:fixture:live-missing", "work"),
])
def test_graph_qualified_complete_live_map_labels_requested_absence(requested_id, node_type):
    run_graph_pending(r"""
const saved=graph([], 'complete');const live=graph([], 'complete');
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;
context.fetch=async path=>ok(path==='api/summary'?fixture:live);boot();await flush();
assert.equal(context.location.hash,'');assert.match(inspectorText(),/requested record is unavailable in the current live map response/i);
assert.match(inspectorText(),new RegExp(requestedId.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
""", requested_id)


@pytest.mark.parametrize(("requested_id", "node_type"), [
    ("spawn-saved-present", "spawn"),
    ("work:fixture:saved-present", "work"),
])
def test_graph_saved_present_becomes_live_without_remount_then_later_disappearance_clears(requested_id, node_type):
    run_graph_pending(r"""
const target=NODE_TYPE==='work'?requestedWork:requestedLegacy;
const saved=NODE_TYPE==='work'?graph([target], 'complete'):graph([], 'complete',[target]);
const sameLive={...saved,generated_at:'2026-08-02T00:00:00Z'};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;
context.fetch=async path=>ok(path==='api/summary'?fixture:sameLive);boot();await flush();
assert.equal(mounts.length,1,'a source transition with the same map signature must not remount');
assert.match(inspectorText(),/REQUESTED TARGET/);assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
const removed=graph([], 'complete');removed.generated_at='2026-08-03T00:00:00Z';
context.fetch=async path=>ok(path==='api/summary'?fixture:removed);await [...activeIntervals.values()][0]();
assert.equal(context.location.hash,'');assert.match(inspectorText(),/selected record is unavailable in the current map response/i);
""".replace("NODE_TYPE", json.dumps(node_type)), requested_id)


@pytest.mark.parametrize(("requested_id", "node_type"), [
    ("spawn-map-first", "spawn"),
    ("work:fixture:map-first", "work"),
])
def test_graph_pending_bookmark_resolves_when_live_map_precedes_summary(requested_id, node_type):
    run_graph_pending(r"""
const target=NODE_TYPE==='work'?requestedWork:requestedLegacy;
const live=NODE_TYPE==='work'?graph([target], 'complete'):graph([], 'complete',[target]);
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=graph([], 'complete');let finishSummary;
context.fetch=path=>path==='api/map'?Promise.resolve(ok(live)):new Promise(resolve=>{finishSummary=resolve;});
boot();await flush();assert.match(inspectorText(),/REQUESTED TARGET/);
assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
finishSummary(ok(fixture));await flush();assert.match(inspectorText(),/REQUESTED TARGET/);
""".replace("NODE_TYPE", json.dumps(node_type)), requested_id)


@pytest.mark.parametrize("action", ["node", "mode", "filter", "url", "back"])
def test_graph_human_navigation_supersedes_older_pending_bookmark(action):
    run_graph_pending(r"""
const saved=ACTION==='back'?graph([requestedWork], 'complete'):graph([otherWork], 'complete');
const live=ACTION==='url'?graph([requestedWork,otherWork], 'complete'):
 ACTION==='back'?{...saved,generated_at:'2026-08-02T00:00:00Z'}:graph([requestedWork,otherWork], 'complete');
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;let finishMap;
context.fetch=path=>path==='api/summary'?Promise.resolve(ok(fixture)):new Promise(resolve=>{finishMap=resolve;});
boot();await flush();
if(ACTION==='node'){
 const button=elements.get('graph-browser-list').children.find(item=>item['data-node-id']===otherWork.id);button.listeners.click();
}else if(ACTION==='mode'){
 modeButtons.find(item=>item['data-graph-mode']==='governance').listeners.click();
}else if(ACTION==='filter'){
 elements.get('graph-search').listeners.input({target:{value:'human choice'}});
}else if(ACTION==='url'){
 context.location.hash='#node='+encodeURIComponent(otherWork.id);
 for(const handler of events.get('hashchange')||[])handler({});
}else{
 const before=selections.length;
 for(const handler of documentEvents.get('click')||[])handler({target:{classList:{contains:name=>name==='incidental'}}});
 assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId,'incidental clicks do not cancel the request');
 for(const handler of documentEvents.get('click')||[])handler({target:{classList:{contains:name=>name==='bm-back'}}});
 assert.equal(context.location.hash,'');finishMap(ok(live));await flush();assert.equal(selections.length,before);
}
if(ACTION!=='back'){finishMap(ok(live));await flush();}
if(['node','url'].includes(ACTION)){
 assert.equal(decodeURIComponent(context.location.hash.slice(6)),otherWork.id);assert.match(inspectorText(),/HUMAN CHOICE/);
 assert.notEqual(selections.at(-1),requestedId);
}else{
 assert.equal(context.location.hash,'');assert.ok(!selections.includes(requestedId)||ACTION==='back');
 if(ACTION==='mode')assert.equal(activeMode,'governance');
 if(ACTION==='filter')assert.equal(activeQuery,'human choice');
}
""".replace("ACTION", json.dumps(action)))


@pytest.mark.parametrize("requested_id", ["work:fixture:requested", "spawn-range"])
@pytest.mark.parametrize("action", ["button", "keyboard", "boundary", "input"])
def test_graph_activity_window_navigation_supersedes_pending_bookmark(requested_id, action):
    run_graph_pending(r"""
const saved=graph([otherWork], 'complete');
const target=requestedId.startsWith('work:')?requestedWork:requestedLegacy;
const live=requestedId.startsWith('work:')?graph([target,otherWork], 'complete'):
 graph([otherWork], 'complete',[target]);
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=saved;let finishMap;
context.fetch=path=>path==='api/summary'?Promise.resolve(ok(fixture)):new Promise(resolve=>{finishMap=resolve;});
boot();await flush();
assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
assert.equal(mounts.at(-1).windowDays,7);
if(ACTION==='button')elements.get('stepper').children[0].listeners.click();
else for(const handler of documentEvents.get('keydown')||[])handler({
 key:ACTION==='boundary'?'ArrowRight':'ArrowLeft',target:{tagName:ACTION==='input'?'INPUT':'BODY'}});
const changed=ACTION==='button'||ACTION==='keyboard';
assert.equal(mounts.at(-1).windowDays,changed?6:7,'execute the actual admitted window handler');
if(changed)assert.equal(context.location.hash,'','changing the window cancels older pending bookmark intent');
else assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId,'a no-op or input key leaves intent intact');
finishMap(ok(live));await flush();
if(changed){
 assert.equal(context.location.hash,'');assert.ok(!selections.includes(requestedId));
 assert.doesNotMatch(inspectorText(),/REQUESTED TARGET/);
}else{
 assert.equal(decodeURIComponent(context.location.hash.slice(6)),requestedId);
 assert.match(inspectorText(),/REQUESTED TARGET/);
}
""".replace("ACTION", json.dumps(action)), requested_id)
