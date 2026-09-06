"""Click shipped Dashboard contract rows with synthetic JSON receipt values."""
import json

import pytest

from test_ui_data_provenance import run_js


SETUP = r"""
context.U=U;context.esc=U.esc;
context.$=id=>context.document.getElementById(id);
let panel='',title='';U.panel.open=(t,html)=>{title=t;panel=html;};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const section=html.slice(html.indexOf('/* ---------- contracts'),html.indexOf('/* ---------- timeline'));
vm.runInContext(section+';globalThis.drawContracts=renderContracts;',context);
const escaped=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
"""


@pytest.mark.parametrize("raw,display,verdict", [
    ({}, "{}", "unverified"), ([], "[]", "unverified"),
    (0, "0", "unverified"), (False, "false", "unverified"),
    ("", "", "unverified"), (None, "", "unverified"),
    (7, "7", "unverified"), (True, "true", "unverified"),
    ({"identity": "pass", "review": "pending"},
     '{"identity":"pass","review":"pending"}', "unverified"),
    (["pass", {"review": "pending"}], '["pass",{"review":"pending"}]', "unverified"),
    ({"toString": "not callable", "detail": "<script>&\"'"},
     '{"toString":"not callable","detail":"<script>&\\\"\'"}', "unverified"),
    ("<script>&\"'", "<script>&\"'", "freeform"),
    ("pass", "pass", "pass"), (" fail ", " fail ", "fail"),
    ("inconclusive", "inconclusive", "inconclusive"),
    ("a reported explanation", "a reported explanation", "freeform"),
])
@pytest.mark.parametrize("status", ["completed", "spawned"])
def test_contract_row_click_displays_raw_receipt_safely(raw, display, verdict, status):
    contract = {"spawn_id": "synthetic-receipt", "agent": "other", "surface": "framework",
                "date": "2026-09-05", "status": status, "done_check_raw": raw,
                "done_check": "pending" if status == "spawned" else verdict}
    run_js(SETUP + "\nconst receipt=" + json.dumps(contract) + ";\nconst expected=" + json.dumps(display) + r""";
const before=JSON.stringify(receipt);
context.D={contracts:[receipt]};context.drawContracts();
const row=elements.get('contracts').children[0];
assert.match(row.innerHTML,new RegExp('>'+receipt.done_check+'</span>'));
row.listeners.click();
assert.equal(title,receipt.spawn_id);
assert.ok(panel.includes('<span>done-check</span><span>'+escaped(expected)+'</span>'),panel);
assert.doesNotMatch(panel,/\[object Object\]|<script>/);
assert.match(panel,new RegExp('>'+receipt.done_check+'</span>'));
if(receipt.done_check==='unverified'||receipt.done_check==='pending')
  assert.doesNotMatch(panel,/ui-pill ok/);
assert.equal(JSON.stringify(receipt),before);
""")
