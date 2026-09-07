"""Focused source and renderer checks for the Atlas Work graph.

These checks execute the real map renderer with deterministic DOM/canvas stubs.
Firefox interaction and visual checks belong to the integration owner.
"""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
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
    assert "does not supply dependency records or exact parent/child source IDs" in source
    assert "they are not a task DAG" in source
    assert "Allowed contract skills do not prove observed use" in source
    assert "it is not a lifecycle enactment or verification count" in source
    assert "Neighborhoods are visual grouping only" in source
    assert "POST(" not in source
    assert ".post(" not in source.lower()


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
const draw=new Proxy({}, {get(target,key){if(!(key in target))target[key]=()=>{};return target[key];}});
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
 {src:'actor',dst:'spawn-20',type:'launched',weight_e:1},
 {src:'spawn-20',dst:'skill',type:'uses',weight_i:1},
 {src:'actor',dst:'skill',type:'used',weight_e:2,weight_i:1},
 {src:'proposal',dst:'rule',type:'enacts',weight_e:1},
];
let selected='';
const instance=context.BrainMap.mount(canvas,{map:{nodes,edges,cards:{}},summary:{matrix:{cells:[]}},
  windowDays:7,onSelect:node=>{selected=node.id;}});
assert.equal(canvas.__brainmap,instance);
assert.equal(instance.skills.length,1);assert.equal(instance.agents.length,1);
assert.deepEqual([...new Set(instance.getVisibleEdges().map(edge=>edge.type))].sort(),['launched','uses']);
assert.ok(instance.getVisibleNodes().every(node=>['agent','spawn','skill'].includes(node.type)));
assert.equal(instance.getVisibleNodes().filter(node=>node.type==='spawn').length,8);
assert.ok(instance.getHiddenCount()>0,'bounded work view discloses omitted source records');
instance.setFilter({query:'contract 0',type:'all'});
assert.ok(instance.getVisibleNodes().some(node=>node.id==='spawn-0'),'search reaches a record outside the initial recent slice');
instance.setFilter({query:'',type:'skill'});
assert.ok(instance.getVisibleNodes().every(node=>node.type==='skill'));
instance.setMode('governance');
assert.deepEqual(instance.getVisibleEdges().map(edge=>edge.type),['enacts']);
assert.ok(instance.getVisibleNodes().some(node=>node.id==='proposal'));
instance.setMode('usage');
assert.deepEqual(instance.getVisibleEdges().map(edge=>edge.type),['used']);
assert.equal(instance.selectById('skill'),true);assert.equal(selected,'skill');
assert.ok(instance.getConnections('skill').some(row=>row.edge.type==='uses'));
canvas.clientWidth=808;canvas.clientHeight=650;instance.resize();instance.fit();
assert.ok(instance.getRenderMetrics().labelCssPixels>=12,'1440-class split layout keeps labels at least 12 CSS px');
canvas.clientWidth=812;canvas.clientHeight=500;instance.resize();instance.fit();
assert.ok(instance.getRenderMetrics().labelCssPixels>=12,'900px stacked layout keeps labels at least 12 CSS px');
for(let i=0;i<30;i++)instance.zoomBy(.2);assert.equal(instance.getZoom(),2.1);
instance.fit();assert.equal(instance.getZoom(),1);
instance.update({map:{nodes:nodes.slice(0,4),edges,cards:{}},mode:'usage',query:'',type:'all'});
assert.equal(instance.skills.length,1);
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
