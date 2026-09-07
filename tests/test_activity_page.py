"""Functional DOM and request tests for the read-only Activity page.

The local DOM harness executes the actual HTML/JS, without a browser, network,
packages or source ledgers. It does not establish visual or screenreader quality.
"""
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

VIEW = Path(__file__).resolve().parents[1] / "memory/brain/view"
NODE = shutil.which("node")


class PageTree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = {"tag": "document", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in {"meta", "link", "input", "br", "hr", "img"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        self.stack[-1]["children"].append(value)


HARNESS = r"""
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const crypto=require('node:crypto').webcrypto;
const elements=new Map(), timers=new Map(), intervals=new Map(), globalEvents={};
let timerId=0, focused=null;
class Element {
 constructor(tag,attrs={}) {this.tagName=tag.toUpperCase();this.attrs={...attrs};this.children=[];
  this.listeners={};this.value=attrs.value||'';this.checked=Object.hasOwn(attrs,'checked');this.disabled=false;
  this._text='';this.className=attrs.class||'';this.dataset={};this.hidden=Object.hasOwn(attrs,'hidden');}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 set textContent(v){this._text=String(v);this.children=[];}
 set innerHTML(_){throw new Error('Dynamic HTML is forbidden in this view');}
 appendChild(child){this.children.push(child);return child;}
 replaceChildren(...nodes){this._text='';this.children=nodes;}
 setAttribute(k,v){this.attrs[k]=String(v);}
 getAttribute(k){return this.attrs[k]??null;}
 querySelectorAll(selector){assert.equal(selector,'details[data-evidence-key]');return descendants(this,e=>e.tagName==='DETAILS'&&e.dataset.evidenceKey!==undefined);}
 addEventListener(k,fn){(this.listeners[k]??=[]).push(fn);}
 async dispatch(k,extra={}){if(this.disabled)return;const event={defaultPrevented:false,target:this,
  preventDefault(){this.defaultPrevented=true;},...extra};for(const fn of this.listeners[k]||[])await fn(event);return event;}
 focus(){focused=this;}
}
function build(node){if(typeof node==='string'){const e=new Element('#text');e.textContent=node;return e;}
 const e=new Element(node.tag,node.attrs);if(node.attrs.id)elements.set(node.attrs.id,e);
 for(const child of node.children)e.appendChild(build(child));return e;}
const page=build(PAGE_TREE);
const document={hidden:false,createElement:tag=>new Element(tag),getElementById:id=>elements.get(id)||null};
const $=id=>elements.get(id), content=id=>$(id).textContent;
function descendants(node,predicate){return [node,...node.children.flatMap(c=>descendants(c,predicate))].filter(predicate);}
function fixture(){const data = {
 schema_version:2,generated_at:'2026-09-05T04:37:00Z',repo:'synthetic-repo',consumer:null,
 window:{oldest_event:'2026-06-01',newest_event:'2026-09-05'},days:[],
 agents:[{id:'builder',evidence:'mixed',first_seen:'2026-08-01',last_seen:'2026-09-05',runs_by_day:{'2026-09-05':1}},
         {id:'historical',evidence:'inferred',first_seen:null,last_seen:null,runs_by_day:{}}],
 skills:[{name:'validate',layer:'A',pack:'core',runtime_safe:true,purpose:'Check independent signals',
          governance:{conformance:{confirmed:3,friction:2,gap:1,diverged:0,status:'recorded'},drift:{active:false}},usage:{explicit:1,inferred:10}},
         {name:'review',layer:'B',pack:'research',runtime_safe:false,purpose:'Review evidence',
          governance:{conformance:{confirmed:0,friction:1,gap:0,diverged:0},drift:{active:true,open_note:'Unresolved friction'}},usage:{explicit:0,inferred:1}}],
 matrix:{cells:[{agent:'builder',skill:'validate',explicit:1,inferred:10,last:'2026-09-05',methods:{skill_used:1,contract:10}},
                {agent:'historical',skill:'review',explicit:0,inferred:1,last:'2026-06-01',methods:{harvest:1}}]},
 timeline:[{id:'failure-1',date:'2026-09-05',ts:'2026-09-05T04:29:32.722209+00:00',kind:'run_flag',title:'Fixture validation',agent:'builder',skill:'validate',verdict:'failed'},
           {id:'annotation-1',ts:'2026-09-04T00:00:00Z',kind:'proposal_evidence_reported',title:'Fixture annotation',agent:'reported-label',skill:null,verdict:null}],
 loop:{chains:[{proposal_id:'P-FIXTURE-A',title:'Tighten validation',target:'validate',target_type:'skill',final_verdict:'accepted',lane:'closed',
                lifecycle:[{ts:'2026-09-01T00:00:00Z',actor:'human:reported-label',verdict:'accepted'}],
                healing:{accepted:{state:'accepted',at:'2026-09-01'},enacted:{state:'enacted',at:null,evidence:{commit:'a'.repeat(40),paths:['.agents/skills/validate/SKILL.md']}},verified:{state:'pending',reported:{at:null,result:'pass',output_sha256:'b'.repeat(64)}}}},
               {proposal_id:'P-FIXTURE-D',title:'Draft skill change',target:'review',target_type:'skill',final_verdict:'open',lane:'draft',healing:{}},
               {proposal_id:'P-FIXTURE-R',title:'Rejected change',target:'validate',target_type:'skill',final_verdict:'auto-reject',lane:'rejected',decided_at:null,
                lifecycle:[{ts:'2026-08-01T00:00:00Z',actor:'reported-reviewer',verdict:'auto-reject'}],healing:{}}]},
 inbox:[{id:'needs-1',title:'Missing independent verification',kind:'verification',severity:'high',detail:'Output receipt has not been checked',
         surface:'framework',actionable:true,action_cmd:'review fixture evidence; do not execute this text',source:'synthetic-source.jsonl:2',link:{skill:'validate'}}]
};data.attention={framework_actions:data.inbox,external_acknowledgements:[],backlog_history:[]};return data;}
const context={console,Date,Promise,JSON,Uint8Array,TextEncoder,AbortController,crypto,document,
 location:{protocol:'file:'},BRAIN_SUMMARY:fixture(),
 setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
 setInterval(fn,ms){const id=++timerId;intervals.set(id,{fn,ms});return id;},clearInterval:id=>intervals.delete(id),
 addEventListener(k,fn){globalEvents[k]=fn;},fetch:async()=>{throw new Error('Unexpected network request');}};
context.window=context;vm.createContext(context);
const boot=()=>vm.runInContext(fs.readFileSync(process.argv[1]+'/activity.js','utf8'),context);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const tab=async name=>{await $(name+'-tab').dispatch('click');await settle();};
const response=data=>({ok:true,status:200,text:async()=>JSON.stringify(data)});
"""

CASES = {
    "initial_tab_state_hides_every_inactive_panel_natively": r"""
const names=['activity','actors','skills','proposals','candidates','blockers'];
for(const name of names){
 assert.equal($(name+'-tab').getAttribute('aria-selected'),String(name==='activity'));
 assert.equal($(name+'-section').hidden,name!=='activity');
}
boot();await settle();
for(const name of names)assert.equal($(name+'-section').hidden,name!=='activity');
""",
    "tab_keyboard_navigation_tracks_focus_selection_and_panels": r"""
boot();await settle();
const names=['activity','actors','skills','proposals','candidates','blockers'];
const state=selected=>{for(const name of names){
 assert.equal($(name+'-tab').getAttribute('aria-selected'),String(name===selected));
 assert.equal($(name+'-tab').getAttribute('tabindex'),name===selected?'0':'-1');
 assert.equal($(name+'-section').hidden,name!==selected);
}assert.equal(focused,$(selected+'-tab'));};
$('activity-tab').focus();
let event=await $('activity-tab').dispatch('keydown',{key:'ArrowLeft'});state('blockers');assert.equal(event.defaultPrevented,true);
event=await $('blockers-tab').dispatch('keydown',{key:'ArrowRight'});state('activity');assert.equal(event.defaultPrevented,true);
event=await $('activity-tab').dispatch('keydown',{key:'ArrowRight'});state('actors');assert.equal(event.defaultPrevented,true);
event=await $('actors-tab').dispatch('keydown',{key:'End'});state('blockers');assert.equal(event.defaultPrevented,true);
event=await $('blockers-tab').dispatch('keydown',{key:'Home'});state('activity');assert.equal(event.defaultPrevented,true);
""",
    "actual_html_and_snapshot": r"""
boot(); await settle();
assert.match(content('data-state'),/Snapshot data/);
assert.match(content('source-metadata'),/2026-09-05T04:37:00Z/);
assert.match(content('source-metadata'),/Not supplied/);
assert.match(content('activity-list'),/failure-1/);
assert.match(content('activity-list'),/2026-09-05T04:29:32.722209\+00:00/);
assert.match(content('activity-list'),/failed/);
assert.equal(descendants($('skills-list'),e=>e.className.includes('skill-card')).length,0);
assert.equal(descendants($('proposals-list'),e=>e.tagName==='ARTICLE').length,0);
assert.equal($('refresh-data').disabled,true);
assert.equal(descendants(page,e=>e.tagName==='H1').length,1);
assert.equal(descendants(page,e=>e.attrs['aria-current']==='page')[0].attrs.href,'activity.html');
assert.equal($('activity-search').tagName,'INPUT');
assert.equal($('actor-filter').tagName,'SELECT');
assert.equal($('data-announcement').attrs['aria-live'],'polite');
""",
    "historical_and_mixed_actor": r"""
boot();await settle();
assert.match(content('activity-list'),/registry: mixed; event attribution provenance not supplied/);
assert.match(content('activity-list'),/reported-label · not resolved/);
await tab('actors');
assert.match(content('actors-list'),/Reference only · no recorded run presence; observation time unavailable/);
assert.match(content('actors-list'),/mixed/);
assert.doesNotMatch(content('actors-list'),/active session|running now/);
assert.match(content('usage-list'),/contract: 10/);
assert.match(content('usage-list'),/Explicit usage labels/);
assert.match(content('usage-list'),/Inferred references/);
assert.doesNotMatch(content('usage-list'),/11 uses/);
""",
    "independent_lifecycle_and_candidates": r"""
boot();await settle();
await tab('proposals');
assert.match(content('proposals-list'),/Recorded acceptance/);
assert.match(content('proposals-list'),/Projector-reported Git\/path evidence · date unknown/);
assert.match(content('proposals-list'),/Reported verification · pending/);
assert.match(content('proposals-list'),/human:reported-label/);
assert.match(content('proposals-list'),/Rejected verdict/);
assert.match(content('proposals-list'),/reported-reviewer/);
await tab('candidates');
assert.match(content('candidates-list'),/P-FIXTURE-D/);
assert.doesNotMatch(content('candidates-list'),/P-FIXTURE-A|P-FIXTURE-R/);
assert.match(content('candidates-list'),/recorded gaps/);
assert.doesNotMatch(content('proposals-list'),/verified badge|healed/);
""",
    "contradiction_is_visible": r"""
context.BRAIN_SUMMARY.loop.chains[0].final_verdict='rejected';
boot();await settle();
await tab('proposals');
assert.match(content('proposals-list'),/Contradictory supplied lifecycle evidence/);
assert.match(content('proposals-list'),/reconcile the contradictory verdict/);
assert.match(content('proposals-list'),/Projector-reported Git\/path evidence/);
""",
    "friction_is_not_automatically_active_drift": r"""
boot();await settle();
await tab('skills');
const cards=descendants($('skills-list'),e=>e.className.includes('skill-card'));
assert.match(cards[0].textContent,/Confirmed \/ friction3 \/ 2/);
assert.doesNotMatch(cards[0].textContent,/Friction or gap remains/);
assert.match(cards[1].textContent,/Friction or gap remains: Unresolved friction/);
""",
    "filters_and_clear_are_functional": r"""
boot();await settle();
$('actor-filter').value='historical';await $('actor-filter').dispatch('change');
assert.match(content('activity-list'),/No recorded activity matches/);
await tab('actors');
assert.match(content('usage-list'),/historical \/ review/);
assert.doesNotMatch(content('usage-list'),/builder \/ validate/);
$('clear-filters').dispatch('click');
assert.equal(focused,$('activity-search'));
$('skill-filter').value='review';await $('skill-filter').dispatch('change');
await tab('skills');
assert.doesNotMatch(content('skills-list'),/Check independent signals/);
await tab('proposals');
assert.match(content('proposals-list'),/P-FIXTURE-D/);
await $('clear-filters').dispatch('click');
$('activity-search').value='P-FIXTURE-R';await $('activity-search').dispatch('input');
await tab('proposals');
assert.match(content('proposals-list'),/P-FIXTURE-R/);
assert.doesNotMatch(content('proposals-list'),/P-FIXTURE-A/);
""",
    "hostile_source_values_are_text_only": r"""
const bad='<img src=x onerror=alert(1)>';
context.BRAIN_SUMMARY.skills[0].purpose=bad;
context.BRAIN_SUMMARY.loop.chains[0].title=bad;
context.BRAIN_SUMMARY.inbox[0].action_cmd=bad;
boot();await settle();
await tab('skills');
assert.match(content('skills-list'),/<img src=x onerror=alert\(1\)>/);
await tab('proposals');
assert.match(content('proposals-list'),/<img src=x onerror=alert\(1\)>/);
assert.equal(descendants($('skills-list'),e=>e.tagName==='IMG').length,0);
await tab('blockers');
assert.equal(descendants($('blockers-list'),e=>e.tagName==='BUTTON').length,0);
assert.match(content('blockers-list'),/text only; not executed/);
""",
    "qualified_times_without_future_ban": r"""
boot();const A=context.Activity;
for(const bad of [null,7,{},'bad','2026-02-30','2026-09-05T25:00:00Z','2026-09-05T01:00:00+01:99'])assert.equal(A.recordedTime(bad),null);
for(const good of ['2024-02-29','2040-01-02T00:15:00+05:30','2026-09-05T00:00:00'])assert.equal(A.recordedTime(good),good);
assert.equal(A.recordedTime('2026-09-05T00:00:00',true),null);
context.BRAIN_SUMMARY.timeline[0].ts=7;
context.BRAIN_SUMMARY.timeline[1].ts='2040-01-02T00:15:00+05:30';
$('activity-search').dispatch('input');
assert.match(content('activity-list'),/Unknown \/ invalid recorded time/);
assert.match(content('activity-list'),/2040-01-02T00:15:00\+05:30/);
""",
    "missing_initial_data_can_recover": r"""
context.BRAIN_SUMMARY=null;boot();await settle();
assert.match(content('data-state'),/Data unavailable/);
assert.match(content('activity-list'),/absence is not a successful outcome/);
context.location.protocol='http:';context.fetch=async()=>response(fixture());
assert.equal(await context.activityStore.refresh(),true);
assert.match(content('data-state'),/Live response received/);
await tab('skills');
assert.match(content('skills-list'),/validate/);
assert.match(content('source-metadata'),/response bytes/);
""",
    "live_failure_cache_and_recovery": r"""
context.location.protocol='http:';context.fetch=async()=>response(fixture());boot();
await context.activityStore.refresh();
assert.match(content('data-state'),/Live response received/);
const received=context.activityStore.receivedAt, hash=context.activityStore.hash;
context.fetch=async()=>({ok:false,status:503});await context.activityStore.refresh();
assert.match(content('data-state'),/Cached response · refresh failed/);
assert.equal(context.activityStore.receivedAt,received);assert.equal(context.activityStore.hash,hash);
assert.match(content('data-warning'),/HTTP 503/);
context.fetch=async()=>response(fixture());await context.activityStore.refresh();
assert.doesNotMatch(content('data-state'),/Cached/);assert.equal(content('data-warning'),'');
""",
    "invalid_response_preserves_snapshot": r"""
boot();context.location.protocol='http:';context.fetch=async()=>response({schema_version:999});
await context.activityStore.refresh();
assert.match(content('data-state'),/Snapshot data/);
assert.match(content('data-warning'),/Unsupported or incomplete/);
await tab('skills');
assert.match(content('skills-list'),/validate/);
context.fetch=async()=>({ok:true,text:async()=>'{bad'});await context.activityStore.refresh();
assert.match(content('data-state'),/Snapshot data/);
""",
    "timeout_is_bounded": r"""
boot();context.location.protocol='http:';context.fetch=()=>new Promise(()=>{});
const waiting=context.activityStore.refresh();
assert.equal(timers.size,1);const timer=[...timers.values()][0];assert.equal(timer.ms,5000);timer.fn();
assert.equal(await waiting,false);assert.equal(context.activityStore.loading,false);
assert.match(content('data-warning'),/timed out/);assert.match(content('data-state'),/Snapshot data/);
""",
    "older_response_cannot_overwrite_newer": r"""
boot();context.location.protocol='http:';let release;
context.fetch=()=>new Promise(resolve=>{release=resolve;});const old=context.activityStore.refresh();
const fresh=fixture();fresh.repo='newer-response';context.fetch=async()=>response(fresh);
await context.activityStore.refresh();release(response(fixture()));await old;
assert.equal(context.activityStore.data.repo,'newer-response');assert.match(content('source-metadata'),/newer-response/);
""",
    "payload_digest_binds_actual_response_text": r"""
boot();context.location.protocol='http:';const raw=JSON.stringify(fixture(),null,2)+'\n';
context.fetch=async()=>({ok:true,text:async()=>raw});await context.activityStore.refresh();
assert.equal(context.activityStore.hash,require('node:crypto').createHash('sha256').update(raw).digest('hex'));
assert.match(content('source-metadata'),/does not identify a Git revision or an exact source-ledger prefix/);
""",
    "digest_unavailable_remains_unknown": r"""
context.crypto=null;boot();await settle();
assert.match(content('source-metadata'),/Unavailable; payload identity not established/);
assert.match(content('data-state'),/Snapshot data/);
""",
    "visibility_toggle_and_page_disposal": r"""
context.location.protocol='http:';context.fetch=async()=>response(fixture());boot();await context.activityStore.refresh();let requests=0;
context.fetch=async()=>{requests++;return response(fixture());};
const interval=[...intervals.values()][0];assert.equal(interval.ms,30000);
document.hidden=true;interval.fn();assert.equal(requests,0);
document.hidden=false;$('auto-refresh').checked=false;interval.fn();assert.equal(requests,0);
$('auto-refresh').checked=true;interval.fn();await context.activityStore.refresh();assert.equal(requests,2);
globalEvents.pagehide();assert.equal(intervals.size,0);assert.equal(await context.activityStore.refresh(),false);
""",
    "malformed_rows_are_disclosed": r"""
context.BRAIN_SUMMARY.timeline.push(null,7);context.BRAIN_SUMMARY.skills.push('bad');boot();await settle();
assert.match(content('data-warning'),/3 malformed rows could not be displayed/);
assert.match(content('activity-list'),/failure-1/);
""",
    "generation_refresh_preserves_open_evidence": r"""
boot();await settle();
await tab('proposals');
const original=descendants($('proposals-list'),e=>e.tagName==='DETAILS')[0];original.open=true;
context.location.protocol='http:';const updated=fixture();updated.generated_at='2026-09-05T06:00:00Z';
context.fetch=async()=>response(updated);await context.activityStore.refresh();
const current=descendants($('proposals-list'),e=>e.tagName==='DETAILS')[0];
assert.equal(current,original,'metadata-only refresh must keep existing evidence controls');
assert.equal(current.open,true);assert.match(content('source-metadata'),/2026-09-05T06:00:00Z/);
""",
    "changed_content_preserves_expansion_and_filter": r"""
boot();await settle();
$('skill-filter').value='validate';await $('skill-filter').dispatch('change');
await tab('proposals');
const original=descendants($('proposals-list'),e=>e.tagName==='DETAILS')[0];original.open=true;
$('activity-search').focus();context.location.protocol='http:';
const updated=fixture();updated.loop.chains[0].title='Updated evidence';
context.fetch=async()=>response(updated);await context.activityStore.refresh();
assert.match(content('proposals-list'),/Updated evidence/);
assert.equal(descendants($('proposals-list'),e=>e.tagName==='DETAILS')[0].open,true);
assert.equal($('skill-filter').value,'validate');assert.equal(focused,$('activity-search'));
""",
    "bare_enactment_claim_is_not_structural_evidence": r"""
context.BRAIN_SUMMARY.loop.chains[0].healing.enacted={state:'enacted'};boot();await settle();
await tab('proposals');
assert.match(content('proposals-list'),/Incomplete enactment claim/);
assert.doesNotMatch(content('proposals-list'),/Projector-reported Git\/path evidence|Structural Git\/path evidence/);
assert.match(content('proposals-list'),/provide the implementation commit and paths/);
""",
    "canonical_enactment_receipt_is_visible_but_reported": r"""
boot();await settle();
await tab('proposals');
assert.match(content('proposals-list'),/Reported commit/);
assert.match(content('proposals-list'),new RegExp('a'.repeat(40)));
assert.match(content('proposals-list'),/Reported paths/);
assert.match(content('proposals-list'),/Projector-reported/);
""",
    "bfcache_keeps_refresh_usable": r"""
context.location.protocol='http:';context.fetch=async()=>response(fixture());boot();await context.activityStore.refresh();
globalEvents.pagehide({persisted:true});let requests=0;context.fetch=async()=>{requests++;return response(fixture());};
assert.equal(await context.activityStore.refresh(),true);assert.equal(requests,1);
await globalEvents.pageshow({persisted:true});assert.equal(requests,2);
assert.match(content('data-state'),/Live response received/);
globalEvents.pagehide({persisted:false});assert.equal(intervals.size,0);
""",
    "file_snapshot_absence_has_actionable_diagnostic": r"""
context.BRAIN_SUMMARY=undefined;boot();await settle();
assert.match(content('data-warning'),/Snapshot unavailable/);
assert.match(content('activity-list'),/existing brain UI|valid generated snapshot/);
assert.doesNotMatch(content('activity-list'),/Refresh to try again/);
assert.equal($('auto-refresh').checked,false);assert.equal($('auto-refresh').disabled,true);
assert.equal(intervals.size,0);
""",
    "invalid_snapshot_is_distinct_from_absent": r"""
context.BRAIN_SUMMARY={schema_version:999};boot();await settle();
assert.match(content('data-warning'),/unsupported or incomplete/);
assert.doesNotMatch(content('data-warning'),/Snapshot unavailable/);
""",
    "uninstalled_skill_and_lifecycle_actor_are_searchable": r"""
const draft=context.BRAIN_SUMMARY.loop.chains[1];draft.target='future-fixture-skill';
boot();await settle();
assert.ok($('skill-filter').children.some(option=>option.value==='future-fixture-skill'));
$('skill-filter').value='future-fixture-skill';await $('skill-filter').dispatch('change');
await tab('candidates');
assert.match(content('candidates-list'),/P-FIXTURE-D/);
await $('clear-filters').dispatch('click');$('activity-search').value='human:reported-label';await $('activity-search').dispatch('input');
await tab('proposals');
assert.match(content('proposals-list'),/P-FIXTURE-A/);
""",
    "file_snapshot_does_not_start_a_refresh_timer": r"""
boot();await settle();assert.equal(intervals.size,0);assert.equal($('auto-refresh').disabled,true);
assert.equal(content('data-warning'),'');
""",
    "refresh_transition_and_incomplete_rows_are_announced": r"""
context.location.protocol='http:';context.fetch=async()=>response(fixture());boot();await context.activityStore.refresh();
let release;context.fetch=()=>new Promise(resolve=>{release=resolve;});const waiting=context.activityStore.refresh();
assert.match(content('data-announcement'),/Checking/);
const updated=fixture();updated.timeline.push(null);release(response(updated));await waiting;
assert.match(content('data-announcement'),/checked|received/);
assert.match(content('data-announcement'),/malformed row/);
""",
    "redirects_are_not_mislabeled_as_same_origin": r"""
boot();context.location.protocol='http:';let options;
context.fetch=async(_url,opts)=>{options=opts;return {...response(fixture()),redirected:true,url:'https://other.invalid/summary'};};
assert.equal(await context.activityStore.refresh(),false);
assert.equal(options.redirect,'error');assert.match(content('data-warning'),/redirect/i);
assert.match(content('data-state'),/Snapshot data/);
""",
    "malformed_or_wrong_target_paths_do_not_advance_enactment": r"""
boot();const A=context.Activity;
for(const paths of [[],['/absolute'],['../outside'],['nested/../outside'],['.agents/skills/other/SKILL.md']]){
 const chain=fixture().loop.chains[0];chain.healing.enacted.evidence.paths=paths;
 const result=A.lifecycle(chain);assert.match(result.enactment,/Incomplete enactment claim/);
 assert.match(result.next,/provide the implementation commit and paths/);
}
const valid=A.lifecycle(fixture().loop.chains[0]);assert.equal(valid.completeEnactment,true);
""",
    "open_verdict_cannot_silently_pair_with_acceptance": r"""
context.BRAIN_SUMMARY.loop.chains[0].final_verdict='open';boot();await settle();
await tab('proposals');
assert.match(content('proposals-list'),/Contradictory supplied lifecycle evidence/);
assert.match(content('proposals-list'),/reconcile the contradictory verdict/);
""",
}



CASES.update({
    "published_attention_partitions_override_raw_commands": r"""
const d=context.BRAIN_SUMMARY;
const external={id:'external-1',title:'External retained history',kind:'gate',surface:'apparatus',actionable:true,
 action_cmd:'EXTERNAL_COMMAND_MUST_NOT_RENDER',detail:'Recorded owner acknowledgement',link:{skill:'external-only'}};
d.inbox.push(external);
d.attention={framework_actions:[d.inbox[0]],external_acknowledgements:[{...external,actionable:false,action_cmd:null}],backlog_history:[]};
boot();await settle();
await tab('blockers');
assert.match(content('blockers-list'),/External retained history/);
assert.match(content('blockers-list'),/external acknowledgements.*view-only/i);
assert.doesNotMatch(content('blockers-list'),/EXTERNAL_COMMAND_MUST_NOT_RENDER/);
assert.match(content('blockers-list'),/review fixture evidence; do not execute this text/);
assert.ok($('skill-filter').children.some(e=>e.value==='external-only'));
""",
    "legacy_attention_stays_visible_without_commands": r"""
const d=fixture();delete d.attention;context.BRAIN_SUMMARY=d;
boot();await settle();
await tab('blockers');
assert.match(content('blockers-list'),/Legacy inbox.*view-only/);
assert.match(content('blockers-list'),/Missing independent verification/);
assert.doesNotMatch(content('blockers-list'),/review fixture evidence; do not execute this text/);
""",
    "malformed_attention_does_not_fall_back_to_raw_inbox": r"""
context.BRAIN_SUMMARY.attention={framework_actions:[]};
boot();await settle();
await tab('blockers');
assert.match(content('blockers-list'),/Attention unavailable.*malformed/);
assert.doesNotMatch(content('blockers-list'),/Missing independent verification/);
assert.match(content('data-warning'),/Malformed attention partitions/);
""",
    "malformed_partition_rows_are_disclosed": r"""
context.BRAIN_SUMMARY.attention={framework_actions:[null,9],external_acknowledgements:[],backlog_history:[]};
boot();await settle();assert.match(content('data-warning'),/2 malformed rows/);
""",
    "published_actor_metadata_stays_asserted_not_authenticated": r"""
context.BRAIN_SUMMARY.agents=[
 {id:'oracle',evidence:'explicit',actor_source:'structured_actor',actor_type:'agent',authentication:'ui-asserted',cryptographically_authenticated:false},
 {id:'legacy-unverified:derrick',evidence:'inferred',actor_source:'legacy_scalar',actor_type:'unknown',authentication:'unverified'},
 {id:'malformed-claim',authentication:'claimed-proof',cryptographically_authenticated:true}];
boot();await settle();
await tab('actors');
assert.match(content('actors-list'),/Reported actor metadata/);
assert.match(content('actors-list'),/structured_actor.*agent.*ui-asserted.*no \(assertion only\)/);
assert.match(content('actors-list'),/legacy-unverified:derrick.*legacy_scalar/);
assert.match(content('actors-list'),/unsupported claim/);
assert.doesNotMatch(content('actors-list'),/cryptographic authentication: true/);
""",
    "external_partition_cannot_regain_command_from_malformed_copy": r"""
context.BRAIN_SUMMARY.attention={framework_actions:[],external_acknowledgements:[{id:'bad-copy',title:'Still external',actionable:true,action_cmd:'EXTERNAL_COMMAND_MUST_NOT_RENDER'}],backlog_history:[]};
boot();await settle();await tab('blockers');assert.match(content('blockers-list'),/Still external/);
assert.doesNotMatch(content('blockers-list'),/EXTERNAL_COMMAND_MUST_NOT_RENDER/);
""",
})


CASES.update({
 "compact_record_titles_keep_full_source_in_disclosure": r"""
const longTitle='Full source title '+ 'detailed evidence '.repeat(20);
context.BRAIN_SUMMARY.loop.chains[1].title=longTitle;
boot();await settle();
for(const panel of ['proposals','candidates']){
 await tab(panel);
 const cards=descendants($(panel+'-list'),e=>e.tagName==='ARTICLE');
 const card=cards.find(e=>e.textContent.includes('P-FIXTURE-D'));
 const heading=descendants(card,e=>e.tagName==='H3')[0];
 assert.ok(heading.textContent.length<=110,'compact heading retains ID, not full title wall');
 const disclosure=descendants(card,e=>e.tagName==='DETAILS')[0];
 assert.equal(disclosure.open,false);
 assert.ok(disclosure.textContent.includes(longTitle),'full title preserved as disclosed source');
 assert.match(card.textContent,/Graduation|graduation/);
}
""",
 "required_activity_host_is_not_silently_skipped": r"""
elements.delete('activity-list');
assert.throws(boot);
""",
 "legacy_html_without_overview_still_boots_activity": r"""
elements.delete('lifecycle-overview');
boot();await settle();
assert.match(content('activity-list'),/Fixture validation/);
await tab('proposals');
assert.match(content('proposals-list'),/P-FIXTURE-A/);
assert.equal($('activity-section').hidden,true);
assert.equal($('proposals-section').hidden,false);
""",
 "proposal_overview_is_counted_without_funnel_claims": r"""
context.BRAIN_SUMMARY.loop.chains.push(null);
boot();await settle();await tab('proposals');
assert.match(content('lifecycle-overview'),/3 readable supplied records · 1 malformed/);
assert.match(content('lifecycle-overview'),/1 recorded acceptance/);
assert.match(content('lifecycle-overview'),/2 unknown, pending, rejected, or other/);
assert.match(content('lifecycle-overview'),/1 recorded enactment claim/);
assert.match(content('lifecycle-overview'),/1 structurally complete reported Git\/path receipt/);
assert.match(content('lifecycle-overview'),/1 reported verification record/);
assert.match(content('lifecycle-overview'),/Counts can overlap/);
assert.doesNotMatch(content('lifecycle-overview'),/success rate|conversion|healed/);
assert.match(content('proposal-gate'),/Draft graduation is closed/);
assert.match(content('proposal-gate'),/open or human-review/);
""",
 "unavailable_lifecycle_counts_stay_unknown": r"""
context.BRAIN_SUMMARY.loop.chains=[null];
boot();await settle();await tab('proposals');
assert.match(content('lifecycle-overview'),/No readable supplied records · 1 malformed/);
assert.match(content('lifecycle-overview'),/Lifecycle counts are unknown/);
assert.doesNotMatch(content('lifecycle-overview'),/0 recorded acceptance|0 recorded enactment|0 reported verification/);
assert.match(content('data-warning'),/malformed row/);
""",
 "canonical_records_get_inspect_only_relative_links": r"""
context.BRAIN_SUMMARY.loop.chains[0].proposal_id='P-104';
context.BRAIN_SUMMARY.loop.chains[1].proposal_id='P-205';
boot();await settle();await tab('proposals');
const proposalLinks=descendants($('proposals-list'),e=>e.tagName==='A');
assert.equal(proposalLinks.length,2);
assert.equal(proposalLinks[0].textContent,'Inspect record');
assert.equal(proposalLinks[0].getAttribute('href'),'proposal_review.html?id=P-104');
assert.equal(proposalLinks[1].getAttribute('href'),'proposal_review.html?id=P-205');
assert.doesNotMatch(content('proposals-list'),/Approve|Accept record/);
await tab('candidates');
const candidateLinks=descendants($('candidates-list'),e=>e.tagName==='A');
assert.equal(candidateLinks.length,1);
assert.equal(candidateLinks[0].textContent,'Inspect record');
assert.equal(candidateLinks[0].getAttribute('href'),'proposal_review.html?id=P-205');
assert.match(content('candidates-list'),/Next evidence · Graduation record required/);
assert.doesNotMatch(content('candidates-list'),/separately governed graduation record/);
""",
 "malformed_test_and_source_urls_never_become_links": r"""
const original=context.BRAIN_SUMMARY.loop.chains[1];
const ids=['P-FIXTURE-D','P-12?next=https://evil.invalid','javascript:alert(1)','https://evil.invalid/P-9','P-7/../../review'];
context.BRAIN_SUMMARY.loop.chains=ids.map((proposal_id,index)=>({...original,proposal_id,
 title:'Unsafe '+index,lane:'draft',proposal_review_url:'https://evil.invalid/approve',url:'javascript:alert(1)'}));
boot();await settle();await tab('proposals');
assert.equal(descendants($('proposals-list'),e=>e.tagName==='A').length,0);
assert.match(content('proposals-list'),/Unsafe 0/);
await tab('candidates');
assert.equal(descendants($('candidates-list'),e=>e.tagName==='A').length,0);
assert.match(content('candidates-list'),/Unsafe 4/);
""",
 "proposal_cards_keep_full_evidence_in_closed_disclosures": r"""
context.BRAIN_SUMMARY.loop.chains[0].proposal_id='P-104';
boot();await settle();await tab('proposals');
const card=descendants($('proposals-list'),e=>e.tagName==='ARTICLE')[0];
assert.match(card.textContent,/Current stage/);
assert.match(card.textContent,/Required next evidence/);
const disclosure=descendants(card,e=>e.tagName==='DETAILS')[0];
assert.equal(disclosure.open,false);
assert.match(disclosure.textContent,/Full lifecycle evidence and source/);
assert.match(disclosure.textContent,/Acceptance.*Recorded acceptance.*2026-09-01/);
assert.match(disclosure.textContent,/Enactment.*Projector-reported Git\/path evidence/);
assert.match(disclosure.textContent,/Verification.*Reported verification · pending/);
assert.match(disclosure.textContent,/human:reported-label/);
assert.match(disclosure.textContent,new RegExp('a'.repeat(40)));
assert.match(disclosure.textContent,/memory\/brain\/proposals.jsonl/);
disclosure.open=true;
assert.equal(disclosure.open,true);
""",
 "large_projection_mounts_one_compact_page_with_paging_and_details": r"""
context.BRAIN_SUMMARY.timeline=Array.from({length:30},(_,index)=>({id:'large-'+index,ts:'2026-08-'+String(index+1).padStart(2,'0')+'T00:00:00Z',kind:'run_flag',title:'Large record '+index,agent:'builder',skill:'validate',verdict:index===29?null:'failed'}));
boot();await settle();
assert.equal(descendants($('activity-list'),e=>e.tagName==='TR').length,13);
assert.match(content('activity-list'),/Large record 29/);assert.match(content('activity-list'),/Unknown/);
assert.doesNotMatch(content('activity-list'),/Large record 0/);
assert.equal(descendants($('actors-list'),e=>e.tagName==='TR').length,0);
assert.equal(descendants($('skills-list'),e=>e.tagName==='ARTICLE').length,0);
const evidence=descendants($('activity-list'),e=>e.tagName==='DETAILS')[0];assert.equal(evidence.open,false);evidence.open=true;
assert.match(evidence.textContent,/summary.timeline — supplied row cursor unavailable/);
const next=descendants($('activity-list'),e=>e.tagName==='BUTTON'&&e.textContent==='Next')[0];await next.dispatch('click');
assert.match(content('activity-list'),/Showing 13–24 of 30/);
const previous=descendants($('activity-list'),e=>e.tagName==='BUTTON'&&e.textContent==='Previous')[0];assert.equal(previous.disabled,false);await previous.dispatch('click');
assert.match(content('activity-list'),/Showing 1–12 of 30/);
await descendants($('activity-list'),e=>e.tagName==='BUTTON'&&e.textContent==='Next')[0].dispatch('click');
$('activity-search').value='Large record 29';await $('activity-search').dispatch('input');
assert.match(content('activity-list'),/Large record 29/);assert.doesNotMatch(content('activity-list'),/Showing 13–24/);
await $('clear-filters').dispatch('click');assert.match(content('activity-list'),/Showing 1–12 of 30/);
""",
 "backlog_commands_remain_withheld": r"""
context.BRAIN_SUMMARY.attention={framework_actions:[],external_acknowledgements:[],backlog_history:[{id:'backlog-1',surface:'framework',title:'Held candidate',actionable:true,action_cmd:'BACKLOG_COMMAND_MUST_NOT_RENDER'}]};
boot();await settle();await tab('blockers');assert.match(content('blockers-list'),/Held candidate/);
assert.match(content('blockers-list'),/backlog history.*view-only/);
assert.doesNotMatch(content('blockers-list'),/BACKLOG_COMMAND_MUST_NOT_RENDER/);
""",
 "failed_initial_refresh_retains_snapshot_digest": r"""
let finishDigest;const snapshot=context.BRAIN_SUMMARY;
const expected=require('node:crypto').createHash('sha256').update(JSON.stringify(snapshot)).digest();
context.crypto={subtle:{digest:()=>new Promise(resolve=>{finishDigest=resolve;})}};
context.location.protocol='http:';context.fetch=async()=>({ok:false,status:503});boot();
await context.activityStore.refresh();finishDigest(Uint8Array.from(expected).buffer);await settle();
assert.equal(context.activityStore.source,'snapshot');assert.equal(context.activityStore.data,snapshot);
assert.equal(context.activityStore.hash,expected.toString('hex'));
assert.equal(context.activityStore.hashKind,'snapshot JSON value');
""",
})

@pytest.mark.parametrize("case", CASES)
def test_activity_functional_dom(case):
    assert NODE, "Functional DOM verification requires the existing Node executable"
    page = PageTree()
    page.feed((VIEW / "activity.html").read_text())
    program = HARNESS.replace("PAGE_TREE", json.dumps(page.root))
    program += "\n(async()=>{\n" + CASES[case] + "\n})().catch(error=>{console.error(error);process.exitCode=1;});"
    result = subprocess.run([NODE, "-e", program, str(VIEW)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mode", ["emitted", "missing", "malformed_script"])
def test_generated_snapshot_script_bootstrap(tmp_path, mode):
    """Execute the real emitted data asset before the page, including failures."""
    assert NODE, "Functional DOM verification requires the existing Node executable"
    sys.path.insert(0, str(VIEW.parents[2] / "scripts"))
    from project_summary import emit

    data = {"schema_version": 2, "generated_at": "2026-09-05T00:00:00Z",
            "window": {"oldest_event": "2026-09-01", "newest_event": "2026-09-05"},
            "agents": [], "skills": [{"name": "emitted-fixture-skill", "purpose": "Synthetic emitted evidence"}],
            "timeline": [], "inbox": [], "matrix": {"cells": []}, "loop": {"chains": []}}
    script = tmp_path / "summary_data.js"
    if mode != "missing":
        emit(data, tmp_path)
    if mode == "malformed_script":
        script.write_text("window.BRAIN_SUMMARY = {broken;")
    page = PageTree()
    page.feed((VIEW / "activity.html").read_text())
    program = HARNESS.replace("PAGE_TREE", json.dumps(page.root))
    program += "\n(async()=>{context.BRAIN_SUMMARY=undefined;\n"
    program += "try{vm.runInContext(fs.readFileSync(" + json.dumps(str(script)) + ",'utf8'),context);}catch(_){/* Browser continues to the next script after a failed data asset. */}\n"
    program += "boot();await settle();\n"
    if mode == "emitted":
        program += "await tab('skills');assert.match(content('skills-list'),/Synthetic emitted evidence/);assert.match(content('data-state'),/Snapshot data/);"
    else:
        program += "assert.match(content('data-warning'),/Snapshot unavailable/);assert.match(content('data-state'),/Data unavailable/);assert.equal($('auto-refresh').disabled,true);"
    program += "\n})().catch(error=>{console.error(error);process.exitCode=1;});"
    result = subprocess.run([NODE, "-e", program, str(VIEW)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
