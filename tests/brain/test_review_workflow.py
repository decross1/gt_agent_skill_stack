"""Functional source-level regressions for the shipped Review page handlers.

The Node harness executes the exact function bodies from proposal_review.html
with inert DOM/fetch doubles. It opens no browser, socket, service, or ledger.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
UI = REPO / "memory" / "brain" / "view" / "proposal_review.html"
NODE = shutil.which("node")


HARNESS = r"""
(async()=>{
const assert=require('node:assert/strict'), fs=require('node:fs');
const html=fs.readFileSync(process.argv[1],'utf8'), which=process.argv[2];
const between=(start,end)=>{const a=html.indexOf(start),b=html.indexOf(end,a);
  assert.ok(a>=0&&b>a,`missing shipped source slice: ${start}`);return html.slice(a,b);};
const optional=(start,end,fallback)=>html.includes(start)?between(start,end):fallback;
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const identity=optional('/* request identity */','/* ---------------- list ---------------- */',`
function captureSelection(){return {pid:current,epoch:selectionEpoch};}
function selectionIsCurrent(request){return !!request&&request.pid===current&&request.epoch===selectionEpoch;}
`);

if(which==='rule-check'){
  const source=between('function renderRuleCheck(rc)','function renderThread(disc)');
  const renderRuleCheck=new Function('esc',source+';return renderRuleCheck;')(esc);
  for(const value of [null,{}, {conflict:false,rule:null,why:'parse-fallback'},
                       {conflict:'false',why:'malformed'}]){
    const markup=renderRuleCheck(value);
    assert.match(markup,/unknown|unavailable/i);
    assert.match(markup,/non-authoritative/i);
    assert.doesNotMatch(markup,/rulecheck ok|no active-rule conflict/i);
  }
}

if(which==='synthesis'){
  const sync=between('function syncAcceptAmended()','function currentRow()');
  const synth=between('async function synthesize()','/* ---------------- verdict');
  let resolveRequest; const calls=[];
  const elements={
    synthesize:{textContent:'Draft updated proposal',innerHTML:'',disabled:false},
    'synth-err':{textContent:''},'amended-wrap':{hidden:true},
    'amended-draft':{value:''},'accept-amended':{disabled:true},
    'card-amended':{classList:{toggle(){}}},send:{disabled:false,innerHTML:''}
  };
  const factory=new Function('env',`
    let current='P-ONE',selectionEpoch=1,busy=false,amendedDraft=null;
    let currentDetail={proposal:{proposal_id:'P-ONE'},review:{eligible:true}};
    const $=env.$,api=env.api,toast=env.toast;
    function setBusy(state){busy=state;}
    ${identity}${sync}${synth}
    return {synthesize,setCurrent(value){current=value;selectionEpoch+=1;busy=false;
      currentDetail={proposal:{proposal_id:value},review:{eligible:true}};},
      state(){return {current,busy,amendedDraft};}};
  `);
  const ui=factory({$:id=>elements[id]||null,toast(){},api(path){calls.push(path);
    return new Promise(resolve=>{resolveRequest=resolve;});}});
  const pending=ui.synthesize();
  assert.deepEqual(calls,['/api/proposal/P-ONE/synthesize']);
  ui.setCurrent('P-TWO');
  resolveRequest({amended_change:'draft generated for P-ONE'});
  await pending;
  assert.deepEqual(ui.state(),{current:'P-TWO',busy:false,amendedDraft:null});
  assert.equal(elements['amended-wrap'].hidden,true);
  assert.equal(elements['amended-draft'].value,'');
  assert.equal(elements['accept-amended'].disabled,true);
}

if(which==='discussion'){
  const threadSource=between('function renderThread(disc)','function actorLabel(actor)');
  const send=between('async function sendMessage()','/* ---------------- synthesize');
  let resolveRequest;const calls=[],markers={replace:0};
  const thread={classList:{contains(){return false;},remove(){}},innerHTML:'',scrollTop:0,
    scrollHeight:1,insertAdjacentHTML(){},replaceWith(){markers.replace+=1;}};
  const elements={msg:{value:'question for A'},'discuss-err':{textContent:''},thread,
    send:{disabled:false,innerHTML:''},synthesize:{disabled:false},thinking:null,'optimistic-user':null};
  const document={createElement(){return {firstElementChild:{},set innerHTML(_value){}};}};
  const factory=new Function('env',`
    let current='P-ONE',selectionEpoch=1,busy=false;
    let currentDetail={proposal:{proposal_id:'P-ONE'},review:{eligible:true}};
    const $=env.$,api=env.api,toast=env.toast,document=env.document,esc=env.esc;
    function setBusy(state){busy=state;}function scrollThread(){}
    ${identity}${threadSource}${send}
    return {sendMessage,setCurrent(value){current=value;selectionEpoch+=1;busy=false;
      currentDetail={proposal:{proposal_id:value},review:{eligible:true}};},state(){return {current,busy};}};
  `);
  const ui=factory({esc,document,$:id=>elements[id]||null,toast(){},api(path){calls.push(path);
    return new Promise(resolve=>{resolveRequest=resolve;});}});
  const pending=ui.sendMessage();assert.deepEqual(calls,['/api/proposal/P-ONE/discuss']);
  ui.setCurrent('P-TWO');resolveRequest({discussion:[{role:'assistant',content:'answer for A'}]});
  await pending;
  assert.deepEqual(ui.state(),{current:'P-TWO',busy:false});
  assert.equal(markers.replace,0);
}

if(which==='eligibility'){
  const render=between('function renderDecide()','/* "Accept amended"');
  const sync=between('function syncAcceptAmended()','function scrollThread()');
  const invoke=(proposals,currentDetail)=>{
    const nodes=new Map();
    const generic=()=>({innerHTML:'',disabled:false,classList:{toggle(){}},addEventListener(){}});
    const host=generic();nodes.set('decide-body',host);
    const factory=new Function('env',`
      let current='P-X',amendedDraft=null;let proposals=env.proposals,currentDetail=env.currentDetail;
      const $=id=>env.node(id),esc=env.esc;function promptVerdict(){}
      ${sync}${render};return ()=>{renderDecide();return $('decide-body').innerHTML;};
    `);
    return factory({proposals,currentDetail,esc,node:id=>{if(!nodes.has(id))nodes.set(id,generic());return nodes.get(id);}})();
  };
  const draft=invoke([{proposal_id:'P-X',verdict:'open',lifecycle:'draft',eligible:false}],
    {proposal:{proposal_id:'P-X'},review:{lifecycle:'draft',eligible:false,eligibility_reason:'candidate graduation is closed'}});
  const closed=invoke([],{proposal:{proposal_id:'P-X'},review:{lifecycle:'closed',eligible:false,eligibility_reason:'decision already recorded'}});
  const loading=invoke([{proposal_id:'P-X',verdict:'open',eligible:true}],null);
  for(const markup of [draft,closed,loading]){
    assert.doesNotMatch(markup,/id="accept-original"|id="accept-amended"|id="reject"/);
    assert.match(markup,/unavailable|closed|recorded|loading/i);
  }
}

if(which==='modal-response'){
  const submit=between('async function submitVerdict','/* ---------------- busy lock');
  let resolveRequest;const calls=[],markers={removed:0,toasts:[],loads:0,selected:[]};
  const generic={textContent:'',innerHTML:'',disabled:false,hidden:false};
  const scrim={_reviewContext:{selection:{pid:'P-101',epoch:1},pid:'P-101',
      proposal:{proposal_id:'P-101',change:'exact A',target:'validate',target_type:'skill'},proposalBasis:JSON.stringify(['P-101','skill','validate','exact A']),amendedChange:null},
    querySelector(sel){return sel==='#note-err'?generic:generic;},remove(){markers.removed+=1;}};
  const factory=new Function('env',`
    let current='P-101',selectionEpoch=1,busy=false,amendedDraft=null;
    let currentDetail={proposal:{proposal_id:'P-101',change:'exact A',target:'validate',target_type:'skill'},review:{proposal_id:'P-101',scope:'framework',lifecycle:'open',lane:'ready',eligible:true,verdict:'open',decision:null,evidence:[]}};
    let proposals=[currentDetail.review];
    const $=env.$,api=env.api,toast=env.toast,esc=env.esc;
    function setBusy(state){busy=state;}
    async function loadList(){env.markers.loads+=1;proposals=[];}
    function selectProposal(pid){env.markers.selected.push(pid);}
    ${identity}${submit}
    return {submitVerdict,setCurrent(value){current=value;selectionEpoch+=1;busy=false;
      currentDetail={proposal:{proposal_id:value,change:'exact B'},review:{eligible:true}};},
      state(){return {current,busy};}};
  `);
  const ui=factory({markers,esc,$:()=>generic,toast:m=>markers.toasts.push(m),
    api(path){calls.push(path);return new Promise(resolve=>{resolveRequest=resolve;});}});
  const pending=ui.submitVerdict('accept','original','ok','derrick',scrim);
  assert.deepEqual(calls,['/api/proposal/P-101/verdict']);
  ui.setCurrent('P-102');
  resolveRequest({ok:true,recorded:'accepted'});
  await pending;
  assert.deepEqual(ui.state(),{current:'P-102',busy:false});
  assert.equal(markers.removed,0);
  assert.deepEqual(markers.toasts,[]);
  assert.equal(markers.loads,0);
  assert.deepEqual(markers.selected,[]);
}
})().catch(error=>{console.error(error&&error.stack||error);process.exitCode=1;});
"""


@pytest.mark.parametrize("case", ["rule-check", "synthesis", "discussion", "eligibility", "modal-response"])
def test_shipped_review_handlers_fail_closed_across_selection_and_lifecycle(case):
    assert NODE is not None, "node is required to execute the shipped Review handlers"
    proc = subprocess.run(
        [NODE, "-e", HARNESS, str(UI), case],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


QUALIFICATION_HARNESS = r"""
(async()=>{
const assert=require('node:assert/strict'),fs=require('node:fs');
const html=fs.readFileSync(process.argv[1],'utf8'),which=process.argv[2];
const slice=(a,b)=>{const start=html.indexOf(a),end=html.indexOf(b,start);assert.ok(start>=0&&end>start,`missing source ${a}`);return html.slice(start,end);};
if(which==='deadline'){
 let aborts=0;
 const source=slice('async function api(', 'function toast(');
 for(const fetch of [()=>new Promise(()=>{}),async()=>({ok:true,json:()=>new Promise(()=>{})})]){
  const api=new Function('fetch','setTimeout','clearTimeout','AbortController',source+';return api;')(
   fetch,fn=>{queueMicrotask(fn);return 1;},()=>{},class{constructor(){this.signal={};}abort(){aborts++;}});
  await assert.rejects(api('/api/proposals'),/timed out/i);
 }
 assert.equal(aborts,2);
}
if(which==='detail-shape'){
 const identity=slice('/* request identity */','/* ---------------- list ---------------- */');
 const render=slice('function renderDetail(d)','/* Decide zone');
 const invoke=new Function(`let current='P-100',currentDetail=null;let proposals=[{proposal_id:'P-100',scope:'framework',lifecycle:'open',lane:'ready',verdict:'open',eligible:true,decision:null,evidence:[]}];${identity}${render};return {renderDetail,validateDetail};`)();
 const review={proposal_id:'P-100',scope:'framework',lifecycle:'open',lane:'ready',verdict:'open',eligible:true,decision:null,evidence:[]};
 const valid={proposal:{proposal_id:'P-100',change:'exact body',target:'validate',target_type:'skill'},review};
 assert.equal(invoke.validateDetail(valid,'P-100'),valid);
 for(const bad of [null,[],{...valid,proposal:{...valid.proposal,proposal_id:'P-101'}},
   {...valid,review:{...review,scope:'research'}},{...valid,review:{...review,lifecycle:'draft'}},
   {...valid,review:{...review,eligible:'true'}},{...valid,review:{...review,proposal_id:'P-101'}}])
  assert.throws(()=>invoke.renderDetail(bad),/unsupported|inconsistent|mismatch|invalid/i);
}
if(which==='advisory-shapes'){
 const escSource=slice('const esc =','let proposals =');
 const functions=slice('function bullets(','function renderDetail(d)');
 const api=new Function(escSource+functions+';return {modelNotes,recordedEvidence};')();
 const poison={toString:'not callable',payload:'<script>&'};
 const rendered=api.modelNotes({model:poison,means:poison,pros_accept:poison,cons_accept:[poison],
  pros_reject:[],cons_reject:[],rule_check:{conflict:false,why:'parse-fallback'}});
 assert.match(rendered,/non-authoritative/);assert.match(rendered,/unknown|unavailable/i);
 assert.match(rendered,/&lt;script&gt;&amp;/);assert.doesNotMatch(rendered,/<script>|rulecheck ok/);
 const evidence=api.recordedEvidence([{kind:'verification',result:false,output_sha256:'b'.repeat(64),source:'fixture'},null]);
 assert.match(evidence,/false/);assert.match(evidence,new RegExp('b'.repeat(64)));
}
console.log('QUALIFIED '+which);
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
"""


@pytest.mark.parametrize("case", ["deadline", "detail-shape", "advisory-shapes"])
def test_review_qualifies_loading_payload_and_advisory_evidence(case):
    assert NODE is not None, "node is required for shipped Review handler regressions"
    proc = subprocess.run([NODE, "-e", QUALIFICATION_HARNESS, str(UI), case],
                          capture_output=True, text=True, timeout=10, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "QUALIFIED " + case in proc.stdout, "handler did not finish its assertions"


CONSISTENCY_HARNESS = r"""
(async()=>{
const assert=require('node:assert/strict'),fs=require('node:fs');
const html=fs.readFileSync(process.argv[1],'utf8'),which=process.argv[2];
const source=html.split('<script>')[1].split('/* ---------------- init ---------------- */')[0];
const clone=x=>JSON.parse(JSON.stringify(x));
const ready={proposal_id:'P-100',scope:'framework',lifecycle:'open',lane:'ready',eligible:true,
 verdict:'open',decision:null,evidence:[],target:'validate',target_type:'skill'};
const closed={...ready,lifecycle:'closed',lane:'history',eligible:false,verdict:'accepted',
 decision:{verdict:'accepted'}};
const detail=review=>({proposal:{proposal_id:'P-100',change:'exact governed body',target:'validate',target_type:'skill'},review:clone(review)});
function create(){
 const calls=[],nodes=new Map();let request;
 function node(id){if(!nodes.has(id))nodes.set(id,{id,hidden:false,disabled:false,value:'',textContent:'',innerHTML:'',
   classList:{toggle(){},contains(){return false;},remove(){}},addEventListener(){},focus(){},remove(){this.removed=true;},
   querySelector(selector){return node(id+selector);},querySelectorAll(){return [];},appendChild(){},setAttribute(){}});return nodes.get(id);}
 const document={getElementById:node,activeElement:node('initial-focus'),body:node('body'),
   createElement(){return node('created-'+nodes.size);}};
 const fetch=async(path,options={})=>{calls.push({path,method:options.method||'GET'});
   if(request)return request(path,options);
   return {ok:true,json:async()=>path==='/api/proposals'?{records:[closed]}:
     options.method==='POST'?{ok:true,recorded:'accepted'}:detail(closed)};};
 const exports=`return {validateDetail,renderDetail,renderDecide,loadList,reloadRecords,selectProposal,openModal,submitVerdict,sendMessage,synthesize,
 set(rows,d){proposals=rows;current='P-100';currentDetail=d;selectionEpoch=1;listEpoch=0;busy=false;},
 catalog(rows){proposals=rows;},detail(d){currentDetail=d;},state(){return {currentDetail,activeModal,selectionEpoch,listEpoch};}};})();`;
 const ui=new Function('document','fetch',source.replace('(function () {','return (function () {')+exports)(document,fetch);
 ui.set([clone(ready)],detail(ready));return {ui,calls,node,request(fn){request=fn;}};
}
if(which.startsWith('catalog-')){
 const {ui}=create();const field=which.slice(8);let row=clone(ready),d=detail(ready);
 if(field==='closed')row=clone(closed);
 else if(field==='inverse')d=detail(closed);
 else if(field==='missing')row=null;
 else if(field==='lifecycle')row.lifecycle='human-review';
 else if(field==='lane')row.lane='history';
 else if(field==='eligible')row.eligible='true';
 else if(field==='scope')row.scope='apparatus';
 else if(field==='verdict')row.verdict='rejected';
 else if(field==='id')row.proposal_id='P-101';
 ui.set(row?[row]:[],d);
 assert.throws(()=>ui.validateDetail(d,'P-100'),/stale|inconsistent|refresh|mismatch|invalid/i);
}
if(which.startsWith('contradiction-')){
 const {ui}=create();const d=detail(ready);
 if(which==='contradiction-decision')d.review.decision={verdict:'accepted'};
 else if(which==='contradiction-evidence')d.review.evidence=[{kind:'verification',result:'pass'}];
 else d.review.evidence={result:'pass'};
 ui.set([clone(ready)],d);assert.throws(()=>ui.validateDetail(d,'P-100'),/inconsistent|invalid|refresh/i);
}
if(which.startsWith('submit-')){
 const {ui,calls}=create();ui.openModal('accept','original');const modal=ui.state().activeModal;assert.ok(modal);
 if(which==='submit-catalog')ui.catalog([clone(closed)]);
 else if(which==='submit-basis')ui.detail({...detail(ready),proposal:{...detail(ready).proposal,change:'different body'}});
 else if(which==='submit-same-object')ui.state().currentDetail.proposal.change='changed in place';
 else if(which==='submit-detail')ui.detail(detail(closed));
 await ui.submitVerdict('accept','original','accepted','oracle',modal);
 assert.equal(calls.filter(c=>c.method==='POST').length,0);
 assert.match(modal.querySelector('#note-err').textContent,/changed|stale|refresh|unavailable/i);
}
if(which==='refresh-open-modal'){
 const {ui,request}=create();ui.openModal('accept','original');let finish;
 request(()=>new Promise(resolve=>{finish=resolve;}));const pending=ui.loadList();
 assert.equal(ui.state().currentDetail,null);assert.equal(ui.state().activeModal,null);
 finish({ok:true,json:async()=>({records:[ready]})});await pending;
}
if(which==='selection-during-refresh'){
 const {ui,calls,request,node}=create();let finish;
 request(()=>new Promise(resolve=>{finish=resolve;}));const pending=ui.loadList();
 // Start the actual selection handler while the catalog is unresolved.
 const selection=ui.selectProposal('P-100');
 assert.equal(calls.length,1,'selection must not fetch detail against an unchecked catalog');
 assert.match(node('gerr').textContent,/refresh|checking/i);
 finish({ok:true,json:async()=>({records:[ready]})});await pending;await selection;
 assert.equal(ui.state().currentDetail,null);
}
if(which==='empty-catalog'){
 const {ui,calls,request,node}=create();
 request(async()=>({ok:true,json:async()=>({proposals:[],records:[],counts:{ready:0,candidates:0,history:0,total:0}})}));
 assert.equal(await ui.loadList(),true);
 assert.deepEqual(calls,[{path:'/api/proposals',method:'GET'}]);
 assert.equal(node('placeholder').hidden,false);
 assert.match(node('placeholder').textContent,/Catalog loaded: no framework review records/);
 assert.doesNotMatch(node('placeholder').textContent,/Refreshing/);
 assert.match(node('catalog-counts').textContent,/0 ready · 0 held · 0 history/);
 assert.equal(node('refresh-review').disabled,false);
 assert.equal(ui.state().currentDetail,null);
}
if(which==='malformed-catalog-load'){
 const {ui,calls,request,node}=create();
 request(async()=>({ok:true,json:async()=>({records:[{proposal_id:'P-100',scope:'framework',lifecycle:'draft',lane:'ready',eligible:true,verdict:'open'}]})}));
 assert.equal(await ui.loadList(),false);
 assert.deepEqual(calls,[{path:'/api/proposals',method:'GET'}]);
 assert.match(node('placeholder').textContent,/Records unavailable/);
 assert.match(node('catalog-counts').textContent,/Counts unavailable/);
 assert.equal(node('refresh-review').disabled,false);
 assert.equal(ui.state().currentDetail,null);
}
if(which==='matched-flow'){
 for(const review of [ready,{...ready,lifecycle:'human-review',verdict:'human-review',decision:{verdict:'human-review'}}]){
  const {ui,calls}=create();const d=detail(review);ui.set([clone(review)],d);
  assert.equal(ui.validateDetail(d,'P-100'),d);ui.openModal('accept','original');const modal=ui.state().activeModal;assert.ok(modal);
  await ui.submitVerdict('accept','original','accepted','oracle',modal);
  assert.deepEqual(calls.filter(c=>c.method==='POST'),[{path:'/api/proposal/P-100/verdict',method:'POST'}]);
 }
}
console.log('CONSISTENT '+which);
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
"""


@pytest.mark.parametrize("case", [
    "catalog-closed", "catalog-inverse", "catalog-missing", "catalog-lifecycle",
    "catalog-lane", "catalog-eligible", "catalog-scope", "catalog-verdict", "catalog-id",
    "contradiction-decision", "contradiction-evidence", "contradiction-shape",
    "submit-catalog", "submit-basis", "submit-same-object", "submit-detail",
    "refresh-open-modal", "selection-during-refresh", "empty-catalog",
    "malformed-catalog-load", "matched-flow",
])
def test_catalog_detail_and_confirmation_stay_consistent(case):
    assert NODE is not None, "node is required for the actual shipped-handler check"
    result = subprocess.run([NODE, "-e", CONSISTENCY_HARNESS, str(UI), case],
                            text=True, capture_output=True, timeout=12, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSISTENT " + case in result.stdout
