"""Focused source and renderer checks for the Atlas Work graph.

These checks execute the real map renderer with deterministic DOM/canvas stubs.
Firefox interaction and visual checks belong to the integration owner.
"""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import re
import shutil
import subprocess

import pytest


VIEW = Path(__file__).resolve().parents[1] / "memory" / "brain" / "view"
NODE = shutil.which("node")


class GraphMarkup(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.ids = set()
        self.scripts = []
        self.links = []
        self.attrs = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.attrs.append((tag, attrs))
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        if tag == "link" and attrs.get("href"):
            self.links.append(attrs["href"])


def test_graph_shell_exposes_real_controls_and_keyboard_alternative():
    source = (VIEW / "graph.html").read_text()
    markup = GraphMarkup(source)
    assert {"map", "graph-search", "graph-type", "graph-zoom", "graph-browser-list",
            "graph-inspector", "inspector-body", "data-source-status"} <= markup.ids
    assert "atlas.css?v=20260907-a" in markup.links
    assert "atlas.js?v=20260907-a" in markup.scripts
    renderer_hash = hashlib.sha256((VIEW / "map.js").read_bytes()).hexdigest()
    assert f"map.js?v={renderer_hash}" in markup.scripts
    script_attrs = {attrs["src"]: attrs for tag, attrs in markup.attrs
                    if tag == "script" and attrs.get("src")}
    for src in ("summary_data.js", "map_data.js",
                next(item for item in markup.scripts if item.startswith("ui.js?")),
                f"map.js?v={renderer_hash}"):
        assert "defer" in script_attrs[src] and "async" not in script_attrs[src]
    assert "async" in script_attrs["atlas.js?v=20260907-a"]
    assert "defer" not in script_attrs["atlas.js?v=20260907-a"]
    assert [attrs.get("data-graph-mode") for tag, attrs in markup.attrs
            if tag == "button" and attrs.get("data-graph-mode")] == [
                "work", "governance", "usage"]
    assert any(tag == "button" and "data-graph-fit" in attrs for tag, attrs in markup.attrs)
    assert len([1 for tag, attrs in markup.attrs
                if tag == "button" and attrs.get("data-graph-zoom")]) == 2
    assert any(tag == "details" and attrs.get("class") == "graph-browser"
               for tag, attrs in markup.attrs)
    assert 'aria-hidden="true"' in source.split('<canvas id="map"', 1)[1].split(">", 1)[0]


def test_graph_copy_discloses_projection_limits_and_relation_meaning():
    source = (VIEW / "graph.html").read_text()
    assert "does not turn assignments into child execution" in source
    assert "does not call a cyclic projection a DAG" in source
    assert "Allowed contract skills do not prove observed use" in source
    assert "it is not a lifecycle enactment or verification count" in source
    assert "Neighborhoods are visual grouping only" in source
    assert "POST(" not in source
    assert ".post(" not in source.lower()


def test_recorded_work_controls_name_each_foundation_relation():
    source = (VIEW / "graph.html").read_text()
    for label in ("recorded parent", "recorded assignment", "explicit dependency",
                  "allowed skill", "caller-reported use"):
        assert label in source
    assert 'option value="work"' in source
    assert 'id="work-evidence"' in source


def test_normal_edge_colors_composite_above_three_to_one_on_white():
    source = (VIEW / "map.js").read_text()
    alpha = float(re.search(r"const NORMAL_EDGE_ALPHA = ([0-9.]+);", source).group(1))
    # Every light-theme edge hue reachable in _drawEdge, including the weakest
    # amber, is checked after canvas globalAlpha compositing over white.
    hues = ["#52617a", "#c27a10", "#238b92", "#5657d8",
            "#4f5fb8", "#6b479d", "#176c73", "#8a5200"]

    def luminance(rgb):
        channels = [value / 255 for value in rgb]
        linear = [value / 12.92 if value <= .04045
                  else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

    for hue in hues:
        assert hue in source
        foreground = [int(hue[index:index + 2], 16) for index in (1, 3, 5)]
        composited = [round(alpha * value + (1 - alpha) * 255)
                      for value in foreground]
        contrast = 1.05 / (luminance(composited) + .05)
        assert contrast >= 3, (hue, alpha, composited, contrast)


def test_inspector_action_cascade_contrast_and_fact_spacing():
    source = (VIEW / "graph.html").read_text()
    assert "html[data-atlas] .graph-inspector .source-action" in source
    assert 'html[data-atlas][data-theme="dark"] .graph-inspector .source-action' in source
    assert "grid-template-columns:minmax(92px,.42fr) minmax(0,1fr)" in source
    assert "gap:12px" in source

    def rgb(value):
        return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))

    def luminance(value):
        channels = [channel / 12.92 if channel <= .04045
                    else ((channel + .055) / 1.055) ** 2.4 for channel in rgb(value)]
        return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]

    def contrast(one, two):
        light, dark = sorted((luminance(one), luminance(two)), reverse=True)
        return (light + .05) / (dark + .05)

    assert contrast("#ffffff", "#5657d8") >= 4.5
    assert contrast("#172334", "#aa99ff") >= 4.5


RENDERER_CHECK = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function element(){
  return {style:{},children:[],listeners:{},textContent:'',className:'',attributes:{},
    appendChild(child){this.children.push(child);return child;},remove(){this.removed=true;},
    addEventListener(name,fn){this.listeners[name]=fn;},removeEventListener(name){delete this.listeners[name];},
    setAttribute(name,value){this.attributes[name]=String(value);},getAttribute(name){return this.attributes[name]||null;},
    getBoundingClientRect(){return {left:0,top:0,width:1000,height:620};}};
}
const windowEvents={},documentEvents={},frames=new Map();let frameId=0;
const root=element();root.setAttribute('data-theme','light');
const document={hidden:false,documentElement:root,head:element(),
  getElementById(){return null;},createElement(){return element();},
  addEventListener(name,fn){documentEvents[name]=fn;},removeEventListener(name){delete documentEvents[name];}};
const context={console,document,devicePixelRatio:1,UI:{agentHue(){return '#6677cc';}},
  getComputedStyle(){return {position:'relative',getPropertyValue(){return '';}};},
  requestAnimationFrame(fn){frames.set(++frameId,fn);return frameId;},cancelAnimationFrame(id){frames.delete(id);},
  addEventListener(name,fn){windowEvents[name]=fn;},removeEventListener(name){delete windowEvents[name];},
  setTimeout,clearTimeout};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const drawnText=[];
const draw=new Proxy({fillText(value){drawnText.push(String(value));}},
 {get(target,key){if(!(key in target))target[key]=()=>{};return target[key];}});
const wrap=element(),canvas=element();canvas.parentElement=wrap;canvas.clientWidth=1000;canvas.clientHeight=620;
canvas.getContext=()=>draw;
const nodes=[
 {id:'actor',type:'agent',label:'builder',date:'2026-09-01'},
 {id:'skill',type:'skill',label:'validate',pack:'core'},
 {id:'proposal',type:'proposal',label:'P-1',date:'2026-08-29'},
 {id:'rule',type:'rule',label:'R-1',date:'2026-08-30'},
];
for(let i=0;i<21;i++)nodes.push({id:'spawn-'+i,type:'spawn',label:'contract '+i,date:'2026-09-'+String(i+1).padStart(2,'0')});
const edges=[
 ...Array.from({length:8},(_,index)=>({src:'actor',dst:'spawn-'+(13+index),type:'launched',weight_e:1})),
 {src:'spawn-20',dst:'skill',type:'uses',weight_i:1},
 {src:'actor',dst:'skill',type:'used',weight_e:2,weight_i:1},
 {src:'proposal',dst:'rule',type:'enacts',weight_e:1},
];
let selected='';
const instance=context.BrainMap.mount(canvas,{map:{nodes,edges,cards:{}},summary:{matrix:{cells:[]}},
  windowDays:7,mode:'usage',onSelect:node=>{selected=node.id;}});
assert.equal(canvas.__brainmap,instance);
assert.equal(instance.skills.length,1);assert.equal(instance.agents.length,1);
assert.deepEqual(instance.getVisibleEdges().map(edge=>edge.type),['used']);
assert.ok(instance.getVisibleNodes().every(node=>['agent','skill'].includes(node.type)));
instance.selectById('actor');drawnText.length=0;instance._draw();
assert.equal(drawnText.filter(value=>value.includes('skill attribution')).length,1,
 'a selected actor gets one counted relation label instead of overlapping edge labels');
instance.setMode('governance');
assert.deepEqual([...new Set(instance.getVisibleEdges().map(edge=>edge.type))].sort(),['enacts','launched','uses']);
assert.ok(instance.getVisibleNodes().some(node=>node.id==='proposal'));
instance.setFilter({query:'P-1',type:'all'});
assert.ok(instance.getVisibleNodes().some(node=>node.id==='proposal'));
instance.setFilter({query:'',type:'skill'});
assert.ok(instance.getVisibleNodes().every(node=>node.type==='skill'));
instance.setMode('usage');
assert.deepEqual(instance.getVisibleEdges().map(edge=>edge.type),['used']);
assert.equal(instance.selectById('skill'),true);assert.equal(selected,'skill');
assert.ok(instance.getConnections('skill').some(row=>row.edge.type==='uses'));
canvas.clientWidth=808;canvas.clientHeight=650;instance.resize();instance.fit();
assert.ok(instance.getRenderMetrics().labelCssPixels>=12,'1440-class split layout keeps labels at least 12 CSS px');
canvas.clientWidth=812;canvas.clientHeight=500;instance.resize();instance.fit();
assert.ok(instance.getRenderMetrics().labelCssPixels>=12,'900px stacked layout keeps labels at least 12 CSS px');
const narrowIds=instance.getVisibleNodes().map(node=>node.id);
canvas.clientWidth=442;canvas.clientHeight=440;instance.resize();instance.fit();
assert.ok(instance.getRenderMetrics().labelCssPixels>=12,'500px viewport keeps canvas labels at least 12 CSS px');
assert.deepEqual(instance.getVisibleNodes().map(node=>node.id),narrowIds,'narrow sizing must not discard accessible records');
assert.equal(instance.selectById('actor'),true,'narrow canvas records remain programmatically selectable');
const actorItem=instance.visibleById.get('actor'),actorTransform=instance._transform();
const actorLeft=actorTransform.x+(actorItem.x-actorItem.width/2)*actorTransform.scale;
const actorRight=actorTransform.x+(actorItem.x+actorItem.width/2)*actorTransform.scale;
assert.ok(actorLeft>=11 && actorRight<=canvas.clientWidth-11,
 'keyboard selection pans an offscreen narrow-canvas node into view');
for(let i=0;i<30;i++)instance.zoomBy(.2);assert.equal(instance.getZoom(),2.1);
instance.fit();assert.ok(instance.getZoom()>1,'narrow fit preserves the minimum readable scale');
canvas.clientWidth=808;canvas.clientHeight=650;instance.resize();instance.fit();assert.equal(instance.getZoom(),1);
instance.update({map:{nodes:nodes.slice(0,4),edges,cards:{}},mode:'usage',query:'',type:'all'});
assert.equal(instance.skills.length,1);
instance.egoMode('skill',false);instance.hovered=instance.visible[0];
instance.update({map:{nodes:[nodes[0]],edges:[],cards:{}},mode:'usage',query:'',type:'all'});
assert.equal(instance.focusId,null);assert.equal(instance.selected,null);assert.equal(instance.hovered,null);
assert.equal(instance.back.style.display,'none');assert.equal(instance.getVisibleNodes().length,1);
assert.equal(instance.skills.length,0);
assert.equal(frames.size,1,'draw scheduling stays single-flight');
const [id,frame]=[...frames][0];frames.delete(id);frame();
assert.equal(frames.size,0,'static graph reaches idle after one paint');
instance.destroy();assert.equal(canvas.__brainmap,undefined);
assert.equal(windowEvents['atlas-theme-change'],undefined);
"""


def test_renderer_modes_search_selection_and_finite_lifecycle():
    if not NODE:
        pytest.fail("Node is required for the functional graph renderer check")
    result = subprocess.run(
        [NODE, "-e", RENDERER_CHECK, str(VIEW / "map.js")],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


WORK_RENDERER_CHECK = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function element(){
  return {style:{},children:[],listeners:{},textContent:'',className:'',attributes:{},
    appendChild(child){this.children.push(child);return child;},remove(){this.removed=true;},
    addEventListener(name,fn){this.listeners[name]=fn;},removeEventListener(name){delete this.listeners[name];},
    setAttribute(name,value){this.attributes[name]=String(value);},getAttribute(name){return this.attributes[name]||null;},
    getBoundingClientRect(){return {left:0,top:0,width:442,height:440};}};
}
const frames=new Map();let frameId=0;
const root=element();root.setAttribute('data-theme','light');
const document={hidden:false,documentElement:root,head:element(),getElementById(){return null;},
 createElement(){return element();},addEventListener(){},removeEventListener(){}};
const context={console,document,devicePixelRatio:1,UI:{agentHue(){return '#6677cc';}},
 getComputedStyle(){return {position:'relative',getPropertyValue(){return '';}};},
 requestAnimationFrame(fn){frames.set(++frameId,fn);return frameId;},cancelAnimationFrame(id){frames.delete(id);},
 addEventListener(){},removeEventListener(){},setTimeout,clearTimeout};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const draw=new Proxy({measureText(){return {width:10};}},
 {get(target,key){if(!(key in target))target[key]=()=>{};return target[key];}});
function mount(map){
 const wrap=element(),canvas=element();canvas.parentElement=wrap;canvas.clientWidth=442;canvas.clientHeight=440;
 canvas.getContext=()=>draw;return context.BrainMap.mount(canvas,{map,summary:{matrix:{cells:[]}},mode:'work'});
}
const capture={namespace:'agent_system/framework',locator:'framework:run-and-spawn',capture_basis:{
 captured_at:'2026-09-07T23:30:00Z',files:[
  {locator:'run_state/framework.run.jsonl',digest:'a'.repeat(64),size:120,availability:'available'},
  {locator:'run_state/spawn.jsonl',digest:'b'.repeat(64),size:80,availability:'available'}]}};
const review={id:'work:agent_system%2Fframework:task:review',type:'work',record_id:'review',kind:'task',
 role:false,raw_status:{state:'assigned',toString:7},source_locator:'run:review',source_metadata:capture};
const check={id:'work:agent_system%2Fframework:task:check',type:'work',record_id:'check',kind:'task',
 raw_status:0,source_locator:'run:check',source_metadata:capture};
const skill={id:'skill:agent_system%2Fframework:validate',type:'skill',skill_id:'validate',
 source_locator:{collection:capture.locator,skill_id:'validate'},source_metadata:capture};
const edge=(type,source,target,extra={})=>({id:'edge:'+type+':'+source+':'+target,type,source,target,
 source_locator:'edge:'+type,source_metadata:capture,...extra});
const work={schema_version:'work-graph/v1',source:capture,
 projection_state:{state:'partial',reason:'unresolved_references'},
 dependency_availability:{state:'available',reason:null},
 limits:{unit:'items',record_cap:2048,record_count:2,node_cap:256,edge_cap:1024,diagnostic_cap:256,
  node_candidates:3,edge_candidates:6,unresolved_candidates:1,cycle_candidates:1,nodes_omitted:0,
  edges_omitted:0,unresolved_omitted:0,cycles_omitted:0},
 nodes:[review,check,skill],edges:[
  edge('parent',review.id,check.id),edge('spawn_assignment',review.id,check.id),
  edge('dependency',check.id,review.id),edge('allowed_skill',review.id,skill.id),
  edge('observed_skill',check.id,skill.id,{assertion_basis:'caller_supplied'}),
  edge('spawn_assignment',review.id,review.id)],
 unresolved:[{reason:'duplicate_id',record_id:'held-duplicate',occurrences:2}],
 cycles:[{type:'dependency',node_ids:[review.id,check.id]}]};
const legacy={generated_at:'2026-09-07T23:30:01Z',
 nodes:[{id:'legacy-agent',type:'agent',label:'legacy actor'},
  {id:'legacy-spawn',type:'spawn',label:'legacy contract'},
  {id:'legacy-proposal',type:'proposal',label:'P-1'}],
 edges:[{src:'legacy-agent',dst:'legacy-spawn',type:'launched'},
  {src:'legacy-proposal',dst:'legacy-agent',type:'authored'}],cards:{},work};
const before=JSON.stringify(work),instance=mount(legacy);
assert.deepEqual(instance.getVisibleNodes().map(node=>node.id).sort(),work.nodes.map(node=>node.id).sort());
assert.deepEqual(instance.getVisibleEdges().map(item=>item.type).sort(),
 ['allowed_skill','dependency','observed_skill','parent','spawn_assignment','spawn_assignment']);
assert.equal(instance.getWorkState().state,'partial');
assert.equal(instance.getWorkState().reason,'unresolved_references');
assert.equal(instance.getNodeById(review.id).record_id,'review');
assert.equal(JSON.stringify(work),before,'renderer must not rewrite the qualified library output');
const related=instance.getConnections(review.id);
assert.deepEqual([...new Set(related.map(row=>row.edge.type))].sort(),
 ['allowed_skill','dependency','parent','spawn_assignment']);
assert.ok(related.some(row=>row.edge.type==='spawn_assignment'&&row.node.id===review.id),
 'self-assignment remains inspectable');
assert.equal(related.filter(row=>row.node.id===check.id).length,3,
 'parallel parent, assignment and dependency evidence stays separate');
const metrics=instance.getRenderMetrics();
assert.ok(metrics.labelCssPixels>=12);assert.ok(metrics.minimumNodeCssWidth>0);
assert.equal(metrics.selfLoopEdges,1);assert.equal(metrics.parallelRelationPairs,1);
assert.ok(metrics.visibleNodes<=36);instance.selectById(review.id,false);
assert.equal(instance.getRenderMetrics().selectedNodeInsideCanvas,true,
 'keyboard/pointer selection pans the selected narrow-canvas work node into view');
instance.setMode('governance');
assert.ok(instance.getVisibleNodes().some(node=>node.id==='legacy-proposal'));
assert.ok(instance.getVisibleNodes().every(node=>!node._workProjection));
instance.setMode('usage');assert.equal(instance.getVisibleNodes().length,1);
instance.destroy();

for(const [map,state] of [
 [{...legacy,work:undefined},'missing'],
 [{...legacy,work:{...work,projection_state:{state:'unavailable',reason:'capture_failed'},nodes:[],edges:[],
 limits:{...work.limits,node_candidates:0,edge_candidates:0}}},'unavailable'],
 [{...legacy,work:{...work,edges:[edge('dependency',check.id,'missing')]}},'malformed'],
 [{...legacy,work:{...work,schema_version:'work-graph/v0'}},'malformed'],
]){
 const item=mount(map);assert.equal(item.getWorkState().state,state);
 assert.equal(item.getVisibleNodes().length,0,'unavailable work must not fall back to legacy contracts');item.destroy();
}

const manyNodes=[];
for(let index=0;index<70;index++)manyNodes.push({id:'work:n:task:'+index,type:'work',record_id:String(index),kind:'task',
 source_locator:'record:'+index,source_metadata:capture});
const many={...legacy,work:{...work,projection_state:{state:'complete',reason:null},
 dependency_availability:{state:'unavailable',reason:'dependencies_not_supplied'},nodes:manyNodes,edges:[],unresolved:[],cycles:[],
 limits:{...work.limits,record_count:70,node_candidates:70,edge_candidates:0,unresolved_candidates:0,
  cycle_candidates:0,nodes_omitted:0}}};
const bounded=mount(many);assert.equal(bounded.getVisibleNodes().length,36);
assert.deepEqual(bounded.getWorkState().projection.dependency_availability,
 {state:'unavailable',reason:'dependencies_not_supplied'},
 'a real-shaped capture without dependency fields stays distinct from a synthetic dependency graph');
assert.equal(bounded.getHiddenCount(),34);bounded.setFilter({query:'record:69',type:'all'});
assert.equal(bounded.getVisibleNodes()[0].record_id,'69','search reaches an item beyond the initial neighborhood');
bounded.destroy();
"""


def test_recorded_work_renderer_admits_typed_projection_without_legacy_fallback():
    if not NODE:
        pytest.fail("Node is required for the functional recorded-work renderer check")
    result = subprocess.run(
        [NODE, "-e", WORK_RENDERER_CHECK, str(VIEW / "map.js")],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# Each probe executes the shipped renderer; the baseline prefix is a fully
# attributed v1 envelope, including parallel and self-assignment relations.
def run_work_probe(probe):
    if not NODE:
        pytest.fail("Node is required for work-graph admission and geometry")
    setup = WORK_RENDERER_CHECK.split("const before=JSON.stringify(work)", 1)[0]
    result = subprocess.run([NODE, "-e", setup + probe, str(VIEW / "map.js")],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mutation", [
    "candidate.source.capture_basis = {}",
    "delete candidate.nodes[0].source_locator",
    "candidate.nodes[0].source_locator = null",
    "delete candidate.nodes[0].source_metadata",
    "candidate.nodes[0].source_metadata.capture_basis = {}",
    "delete candidate.nodes[2].source_locator",
    "delete candidate.edges[0].id",
    "candidate.edges[1].id = candidate.edges[0].id",
    "delete candidate.edges[0].source_locator",
    "delete candidate.edges[0].source_metadata",
    "delete candidate.edges[4].assertion_basis",
    "candidate.edges[4].assertion_basis = 'verified'",
    "delete candidate.limits.record_cap",
    "candidate.limits.node_cap = 1",
    "candidate.limits.edge_cap = -1",
    "candidate.limits.diagnostic_cap = 0",
    "candidate.limits.unit = 'bytes'",
    "candidate.limits.node_candidates = 99",
    "candidate.projection_state.state = 'complete'",
    "candidate.projection_state.state = 'unavailable'",
    "delete candidate.unresolved[0].reason",
    "delete candidate.cycles[0].type",
    "candidate.cycles[0].node_ids = []",
    "candidate.edges[0].source = candidate.nodes[2].id",
    "candidate.edges[4].target = candidate.nodes[0].id",
])
def test_work_v1_rejects_missing_or_invalid_mandatory_evidence(mutation):
    run_work_probe("const candidate=JSON.parse(JSON.stringify(work));\n" + mutation + ";\n" + r"""
const item=mount({...legacy,work:candidate});
assert.equal(item.getWorkState().state,'malformed');
assert.equal(item.getVisibleNodes().length,0);
assert.equal(item.getVisibleEdges().length,0);
item.destroy();
""")


def test_legacy_spawn_remains_selectable_without_becoming_typed_work():
    run_work_probe(r"""
const item=mount(legacy);item.setMode('governance');
assert.ok(item.getVisibleNodes().some(node=>node.id==='legacy-spawn'));
assert.equal(item.selectById('legacy-spawn'),true);
assert.equal(item.selected.type,'spawn');
assert.equal(item.selected._workProjection,undefined);
assert.ok(item.getConnections('legacy-spawn').some(row=>row.edge.type==='launched'));
item.setMode('work');assert.ok(item.getVisibleNodes().every(row=>row.type!=='spawn'));
item.destroy();
""")


def test_directed_edge_tip_stays_outside_opaque_destination_card():
    run_work_probe(r"""
const item=mount(legacy), tips=[];
item._drawArrow=(x,y,angle)=>tips.push({x,y,angle});
for(const relation of item.visibleEdges.filter(edge=>edge.src!==edge.dst)){
 const target=item.visibleById.get(relation.dst);tips.length=0;item._drawEdge(relation);
 assert.equal(tips.length,1);const tip=tips[0];
 assert.ok(Math.abs(tip.x-target.x)>=target.width/2+1 ||
           Math.abs(tip.y-target.y)>=target.height/2+1,
           'arrow tip must remain visibly beyond the destination fill');
 const towardX=target.x-tip.x,towardY=target.y-tip.y;
 assert.ok(towardX*Math.cos(tip.angle)+towardY*Math.sin(tip.angle)>0,
           'arrow must point toward its actual destination');
}
assert.equal(item.getRenderMetrics().selfLoopEdges,1);
assert.equal(item.getRenderMetrics().parallelRelationPairs,1);item.destroy();
""")
