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
