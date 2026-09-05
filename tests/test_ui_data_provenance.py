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
const context = {console, Date, Promise, JSON, setTimeout, clearTimeout,
  addEventListener(){},
  location:{protocol:'http:',hostname:'localhost'}, navigator:{},
  localStorage:{getItem(){return null;}},
  document:{addEventListener(){},createElement:element,head:element(),body:element(),
    getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},
    querySelector(){return element();}},
  intervals:[], setInterval(fn){context.intervals.push(fn);},
  fetch:async()=>{throw new Error('unexpected fetch');}};
context.window=context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1]+'/ui.js','utf8'),context);
const U=context.UI;
const stamp='2026-08-01T00:00:00Z';
const summary={status_strip:{},generated_at:stamp};
const map={nodes:[],edges:[],cards:[],generated_at:stamp};
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
