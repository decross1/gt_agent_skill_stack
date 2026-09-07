"""Drive the shipped Dashboard attention handlers offline, including detail routes."""
import pytest

from test_ui_data_provenance import run_js


SETUP = r"""
const item=(id,title,extra={})=>({id,title,kind:'proposal_review',severity:'high',
  detail:'Evidence '+title,surface:'framework',actionable:true,action_cmd:'COMMAND_'+title,...extra});
const framework=item('P-1','FRAMEWORK');
const external=item('P-2','EXTERNAL',{surface:'apparatus'});
const backlog=item('P-3','BACKLOG');
const unknown=item('P-4','UNKNOWN',{surface:null});
const malformed=item('P-5','MALFORMED',{actionable:'true'});
const candidate=item('P-6','CANDIDATE',{kind:'candidate_review'});
const fixture={inbox:[framework,external,backlog,unknown,malformed,candidate],
  attention:{framework_actions:[framework,unknown,malformed,candidate],
    external_acknowledgements:[external],backlog_history:[backlog],external_groups:[]}};
context.D=fixture;context.U=U;context.esc=U.esc;
context.$=id=>context.document.getElementById(id);
let panel='',title='';U.panel.open=(t,html)=>{title=t;panel=html;};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const section=html.slice(html.indexOf('/* ---------- needs-you inbox'),html.indexOf('/* ---------- embedded cluster map'));
vm.runInContext(section+';globalThis.drawInbox=renderInbox;globalThis.drawBlockers=renderBlockerSummary;globalThis.detail=openInboxKind;',context);
const viewOnly=()=>{assert.doesNotMatch(panel,/ui-copy|data-review-link|COMMAND_/);assert.match(panel,/view-only/);};
"""


def test_today_blocker_preview_is_descriptive_and_fail_closed():
    run_js(SETUP + r"""
context.drawBlockers();
const output=elements.get('blocker-summary').innerHTML;
assert.match(output,/1 source-reported blocker/);assert.match(output,/FRAMEWORK/);
assert.match(output,/do not grant decision authority/);
assert.doesNotMatch(output,/EXTERNAL|BACKLOG|UNKNOWN|MALFORMED|CANDIDATE/);
assert.doesNotMatch(output,/COMMAND_|ui-copy|data-review-link/);
""")


@pytest.mark.parametrize("lane", ["external", "backlog", "framework"])
def test_actual_cards_retain_partition_and_same_kind_detail(lane):
    run_js(SETUP + r"""
context.drawInbox();
const sections=elements.get('inbox').children;
const index={framework:0,external:1,backlog:2}[LANE];
sections[index].children[0].listeners.click();
assert.match(panel,new RegExp('Evidence '+LANE.toUpperCase()));
if(LANE==='framework'){
 assert.match(panel,/COMMAND_FRAMEWORK/);assert.match(panel,/data-review-link/);
 assert.doesNotMatch(panel,/COMMAND_UNKNOWN|COMMAND_MALFORMED|COMMAND_CANDIDATE/);
 assert.doesNotMatch(panel,/Evidence EXTERNAL|Evidence BACKLOG/);
}else{
 viewOnly();assert.doesNotMatch(panel,/Evidence FRAMEWORK/);
}
""".replace("LANE", repr(lane)))


def test_unqualified_or_unknown_detail_routes_never_grant_actions():
    run_js(SETUP + r"""
for(const key of [undefined,'unknown','__proto__']){
 context.detail('proposal_review',key);viewOnly();
 assert.match(panel,/Evidence FRAMEWORK/);assert.match(panel,/Evidence EXTERNAL/);
}
context.detail('candidate_review','framework_actions');viewOnly();
""")


@pytest.mark.parametrize("attention", ["undefined", "null", "{}", "{framework_actions:'bad'}"])
def test_missing_or_malformed_partitions_keep_evidence_view_only(attention):
    run_js(SETUP + "fixture.attention=" + attention + r""";
context.drawInbox();
context.detail('proposal_review','framework_actions');viewOnly();
assert.match(panel,/Evidence FRAMEWORK/);
""")


def test_malformed_authority_and_conflicting_membership_fail_closed():
    run_js(SETUP + r"""
for(const value of [undefined,null,false,0,1,'true',{},[]]){
 framework.actionable=value;context.detail('proposal_review','framework_actions');
 viewOnly();assert.match(panel,/Evidence FRAMEWORK/);
}
framework.actionable=true;
fixture.attention.external_acknowledgements.push({...framework,surface:'apparatus'});
context.detail('proposal_review','framework_actions');viewOnly();
""")
