"""Atlas shell and safe-bootstrap regressions for Skills & healing and Review."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import hashlib
import shutil
import subprocess

import pytest


VIEW = Path(__file__).resolve().parents[1] / "memory" / "brain" / "view"
NODE = shutil.which("node")


class Shell(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html = {}
        self.primary_depth = 0
        self.primary_links = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "html":
            self.html = attrs
        if tag == "nav" and attrs.get("aria-label") == "Primary":
            self.primary_depth += 1
        elif tag == "a" and self.primary_depth:
            self.primary_links.append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav" and self.primary_depth:
            self.primary_depth -= 1


@pytest.mark.parametrize(
    ("page", "current"),
    [("activity.html", "page"), ("proposal_review.html", "location")],
)
def test_atlas_shell_has_exact_primary_navigation_and_local_theme_assets(page, current):
    source = (VIEW / page).read_text()
    shell = Shell()
    shell.feed(source)
    assert "data-atlas" in shell.html
    assert shell.html["data-theme"] == "light"
    assert [link.get("href") for link in shell.primary_links] == [
        "dashboard.html", "graph.html", "activity.html"
    ]
    assert shell.primary_links[-1].get("aria-current") == current
    assert all(link.get("href") != "proposal_review.html" for link in shell.primary_links)
    assert source.index("atlas.css?v=20260907-a") < source.index("atlas.js?v=20260907-a")
    assert any(tag == "script" and attrs.get("src") == "atlas.js?v=20260907-a" and
               "async" in attrs and "defer" not in attrs for tag, attrs in shell.tags)


def test_activity_initial_panels_use_native_hidden_and_contextual_review_link():
    shell = Shell()
    shell.feed((VIEW / "activity.html").read_text())
    tags = {attrs.get("id"): (tag, attrs) for tag, attrs in shell.tags if attrs.get("id")}
    for name in ("activity", "actors", "skills", "proposals", "candidates", "blockers"):
        _, tab = tags[f"{name}-tab"]
        _, panel = tags[f"{name}-section"]
        assert tab["role"] == "tab"
        assert tab["aria-controls"] == f"{name}-section"
        assert ("hidden" in panel) is (name != "activity")
    contextual = [attrs for tag, attrs in shell.tags
                  if tag == "a" and attrs.get("href") == "proposal_review.html"]
    assert contextual, "Review remains reachable contextually from Skills & healing"


REVIEW_BOOT = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(process.argv[1],'utf8');
const script=html.slice(html.lastIndexOf('<script>')+8,html.lastIndexOf('</script>'));
const calls=[],listeners={},nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{id,value:'',hidden:id==='detailbody',disabled:false,
 textContent:'',innerHTML:'',addEventListener(type,fn){listeners[id+':'+type]=fn;},querySelectorAll(){return [];}});return nodes.get(id);}
for(const id of ['proposal-search','refresh-review','detailbody','placeholder','catalog-counts','listbody','gerr'])node(id);
const document={getElementById:node,body:{appendChild(){}},createElement(){return {remove(){}};}};
const context={console,document,URLSearchParams,AbortController,location:{search:''},
 setTimeout,clearTimeout,fetch:async(path,options={})=>{calls.push({path,method:options.method||'GET'});
  return {ok:true,redirected:false,json:async()=>({proposals:[],records:[],counts:{ready:0,candidates:0,history:0,total:0}})};}};
vm.createContext(context);vm.runInContext(script,context);
setImmediate(()=>setImmediate(()=>{
 try{
  assert.deepEqual(calls,[{path:'/api/proposals',method:'GET'}]);
  assert.equal(node('placeholder').hidden,false);
  assert.match(node('placeholder').textContent,/Catalog loaded: no framework review records/);
  assert.doesNotMatch(node('placeholder').textContent,/Refreshing/);
  assert.match(node('catalog-counts').textContent,/0 ready · 0 held · 0 history/);
  assert.equal(node('refresh-review').disabled,false);
  console.log('REVIEW BOOT EMPTY CATALOG QUALIFIED');
 }catch(error){console.error(error.stack||error);process.exitCode=1;}
}));
"""


def test_review_boot_is_get_only_and_loaded_empty_catalog_settles():
    assert NODE is not None, "node is required to execute the shipped Review bootstrap"
    result = subprocess.run(
        [NODE, "-e", REVIEW_BOOT, str(VIEW / "proposal_review.html")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REVIEW BOOT EMPTY CATALOG QUALIFIED" in result.stdout


def test_activity_changed_renderer_uses_its_exact_content_revision():
    shell = Shell()
    shell.feed((VIEW / "activity.html").read_text())
    digest = hashlib.sha256((VIEW / "activity.js").read_bytes()).hexdigest()
    scripts = [attrs["src"] for tag, attrs in shell.tags
               if tag == "script" and attrs.get("src", "").split("?")[0] == "activity.js"]
    assert scripts == [f"activity.js?v={digest}"]
