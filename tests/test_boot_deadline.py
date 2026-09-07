"""Execute the actual inline readiness handlers; Firefox covers resource loading."""
import hashlib
import json
import threading
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

import browser_boot_probe as probe

from test_ui_data_provenance import FAKE_CLOCK, PAGE_DATA, VIEW, run_js

PAGES = ['dashboard.html', 'graph.html']


def test_browser_fixture_rejects_paths_outside_its_source(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (tmp_path / 'private.txt').write_text('PRIVATE')
    fixture = object.__new__(probe.Fixture)
    fixture.source_view = source
    case = probe.ProbeCase('graph.html', 'normal')
    for asset in ('../private.txt', str(tmp_path / 'private.txt'), 'sub/../../private.txt'):
        status, _, body = fixture.bytes_for(case, asset)
        assert status == 404 and b'PRIVATE' not in body


@pytest.mark.parametrize('mode,asset', [('missing', 'ui.js'), ('stale-ui', None)])
def test_browser_graph_dependency_check_rejects_a_generic_data_label(mode, asset):
    case = probe.ProbeCase('graph.html', mode, asset)
    fixture = type('Fixture', (), {'lock': __import__('threading').Lock(), 'events': []})()
    passed, _, _ = probe.verdict_for(case, 'candidate', {'final': {
        'status': 'Snapshot data', 'readyState': 'complete'}}, fixture)
    assert not passed


@pytest.mark.parametrize('page', PAGES)
def test_browser_normal_check_requires_rendered_structure_without_js_errors(page):
    case = probe.ProbeCase(page, 'normal')
    fixture = type('Fixture', (), {'lock': __import__('threading').Lock(), 'events': []})()
    data = {'status': 'Snapshot data', 'readyState': 'complete', 'probe': {'errors': []}}
    assert not probe.verdict_for(case, 'candidate', {'final': data}, fixture)[0]
    data.update(statusRows=7, canvas={'width': 100, 'height': 100, 'rendererMounted': True}, mapNoteHidden=True)
    assert probe.verdict_for(case, 'candidate', {'final': data}, fixture)[0]
    data['probe']['errors'] = [{'type': 'error', 'message': 'initialization broke'}]
    assert not probe.verdict_for(case, 'candidate', {'final': data}, fixture)[0]


@pytest.mark.parametrize('mode', ['normal', 'file', 'file-missing-ui'])
def test_graph_probe_rejects_blank_default_canvas_without_renderer_marker(mode):
    case = probe.ProbeCase('graph.html', mode)
    fixture = SimpleNamespace(lock=threading.Lock(), events=[])
    data = {'status': 'Snapshot data', 'readyState': 'complete', 'probe': {'errors': []},
            'canvas': {'width': 300, 'height': 150}, 'mapNoteHidden': True,
            'hasSummary': True, 'hasMap': True, 'url': 'file:///graph.html'}
    if mode == 'normal':
        data['url'] = 'http://127.0.0.1/graph.html'
    if mode == 'file-missing-ui':
        data['status'] = 'Saved data only. Live refresh and source checks are disabled.'
    for marker in (None, False, 'true', 1):
        data['canvas']['rendererMounted'] = marker
        assert not probe.verdict_for(case, 'candidate', {'final': data}, fixture)[0]
    data['canvas']['rendererMounted'] = True
    assert probe.verdict_for(case, 'candidate', {'final': data}, fixture)[0]


def test_actual_capture_reads_renderer_owned_marker_without_modifying_canvas():
    run_js("context.performance={getEntriesByType:()=>[]};" +
           "context.document.title='Map';context.document.readyState='complete';" +
           "context.document.getElementById('data-source-status').getAttribute=()=>null;" +
           "const canvas=context.document.getElementById('map');" +
           "canvas.width=300;canvas.height=150;" +
           "const capture=()=>vm.runInContext(" + json.dumps('(function(){' + probe.CAPTURE_SCRIPT + '})()') + ",context);" +
           "assert.equal(capture().canvas.rendererMounted,false);" +
           "assert.equal(canvas.__brainmap,undefined);" +
           "canvas.__brainmap={};assert.equal(capture().canvas.rendererMounted,true);")


@pytest.fixture
def offline_probe_receipt(tmp_path, monkeypatch):
    """Execute main's receipt path with inert browser/process adapters."""
    source = tmp_path / 'source'
    view = source / 'memory/brain/view'
    view.mkdir(parents=True)
    for name in (*probe.PAGES, 'ui.js', 'map.js'):
        (view / name).write_text('fixture source')
    saved = tmp_path / 'saved'
    saved.mkdir()
    for name in ('summary_data.js', 'map_data.js'):
        (saved / name).write_text('window.DATA = {};')
    process = SimpleNamespace(pid=1, poll=lambda: 0)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *_a, **_k: process)
    monkeypatch.setattr(probe.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(stdout='checkout-only-sha\n'))
    server = SimpleNamespace(server_port=1, shutdown=lambda: None, server_close=lambda: None)
    monkeypatch.setattr(probe, 'start_fixture_server', lambda _f: (server, SimpleNamespace(join=lambda **_k: None)))
    def command(_method, path, *_args, **_kwargs):
        if path == '/session':
            return {'sessionId': 'private', 'capabilities': {'webSocketUrl': 'ws://unused', 'browserVersion': 'inert'}}
        return {}
    monkeypatch.setattr(probe, 'WebDriver', lambda *_a: SimpleNamespace(command=command))
    monkeypatch.setattr(probe, 'BidiBridge', lambda *_a: SimpleNamespace(
        process=process, events=[], command=lambda *_a: {}, flush=lambda: None, close=lambda: None))
    def invoke(specs, released='Snapshot data', fatal=False):
        def case_result(case, phase, _origin, fixture, *_args):
            if fatal:
                raise RuntimeError('inert transport failed')
            captures = {'final': {'status': 'Snapshot data', 'readyState': 'complete'}}
            if case.mode in {'hold', 'pagehide'}:
                captures = {'after-pagehide' if case.mode == 'pagehide' else 'deadline': {
                    'status': 'Data sources have not been checked.', 'readyState': 'loading'},
                    'released': {'status': released, 'readyState': 'complete'}}
            passed, reason, details = probe.verdict_for(case, phase, captures, fixture)
            return {'case_id': case.case_id, 'mode': case.mode, 'probe_pass': passed,
                    'reason': reason, 'details': details}
        monkeypatch.setattr(probe, 'run_case', case_result)
        output = tmp_path / ('result-' + str(len(list(tmp_path.glob('result-*')))))
        args = ['--source', str(source), '--fixture-view', str(saved), '--output', str(output),
                '--profile-root', str(tmp_path), '--phase', 'baseline', '--page', 'graph.html']
        for spec in specs:
            args.extend(['--case', spec])
        code = probe.main(args)
        return code, json.loads((output / 'result.json').read_text()), json.loads((output / 'metadata.json').read_text())
    return invoke


def test_receipt_records_executing_probe_identity_separate_from_product_source(offline_probe_receipt):
    _, _, metadata = offline_probe_receipt(['normal'])
    assert metadata['source_head'] == 'checkout-only-sha'
    assert metadata['runner']['path'] == str(Path(probe.__file__).resolve())
    assert metadata['runner']['sha256'] == hashlib.sha256(Path(probe.__file__).read_bytes()).hexdigest()
    assert metadata['source_assets']['graph.html'] == hashlib.sha256(b'fixture source').hexdigest()


@pytest.mark.parametrize('specs,release,expected,exit_code', [
    (['normal'], 'Snapshot data', 'baseline-observed', 0),
    (['normal', 'hold:ui.js'], 'Snapshot data', 'baseline-red-reproduced', 0),
    (['hold:ui.js'], 'Snapshot data', 'baseline-red-reproduced', 0),
    (['pagehide:ui.js'], 'Snapshot data', 'baseline-observed', 0),
    (['normal', 'hold:ui.js'], 'Data sources have not been checked.', 'not-established', 1),
    (['hold:ui.js'], 'Loading interface files', 'not-established', 1),
])
def test_baseline_receipt_distinguishes_observation_from_reproduced_hold(
        offline_probe_receipt, specs, release, expected, exit_code):
    code, result, _ = offline_probe_receipt(specs, released=release)
    assert code == exit_code
    assert result['product_state'] == expected


def test_failed_probe_does_not_certify_baseline_observation(offline_probe_receipt):
    code, result, _ = offline_probe_receipt(['normal'], fatal=True)
    assert code == 1 and result['fatal']['type'] == 'RuntimeError'
    assert result['product_state'] == 'not-established'


@pytest.mark.parametrize('value', ['inf', 'nan', '-1'])
def test_browser_probe_rejects_unbounded_or_negative_delay_before_start(value):
    with pytest.raises(SystemExit, match='finite positive'):
        probe.main(['--source', '/unused', '--fixture-view', '/unused', '--output', '/unused',
                    '--hold-seconds', value])


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.external = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and 'src' in attrs:
            self.external.append(attrs)


@pytest.mark.parametrize('page', PAGES)
def test_ordered_dependencies_do_not_block_the_inline_deadline(page):
    scripts = Scripts((VIEW / page).read_text()).external
    presentation = [s for s in scripts if s['src'].split('?')[0] == 'atlas.js']
    critical = [s for s in scripts if s['src'].split('?')[0] != 'atlas.js']
    assert len(presentation) == 1
    assert presentation[0]['src'] == 'atlas.js?v=20260907-a'
    assert [s['src'].split('?')[0] for s in critical] == [
        'summary_data.js', 'map_data.js', 'ui.js', 'map.js']
    assert 'async' in presentation[0] and 'defer' not in presentation[0]
    assert all('defer' in s and 'async' not in s for s in critical)
    digest = hashlib.sha256((VIEW / 'ui.js').read_bytes()).hexdigest()
    assert critical[2]['src'] == f'ui.js?v={digest}'


LIFECYCLE = r"""
context.document.readyState='loading';
let monotonic=0;context.performance={now:()=>monotonic};
const remove=(registry,k,fn)=>registry.set(k,(registry.get(k)||[]).filter(f=>f!==fn));
context.removeEventListener=(k,fn)=>remove(events,k,fn);
context.document.removeEventListener=(k,fn)=>remove(documentEvents,k,fn);
const ready=async()=>{
 context.document.readyState='interactive';
 for(const fn of [...(documentEvents.get('DOMContentLoaded')||[])])fn();
 await flush();
};
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
"""


def page_js(page, code):
    run_js(FAKE_CLOCK + PAGE_DATA.replace('PAGE', repr(page)) + LIFECYCLE + code)


@pytest.mark.parametrize('page', PAGES)
def test_waits_for_scripts_then_boots_once_and_releases_startup_hooks(page):
    page_js(page, r"""
boot();await flush();
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);
assert.match(elements.get('data-source-status').textContent,/Loading interface files/);
assert.equal(timers.size,1);
await ready();
assert.equal(mounts.length,1);assert.equal(activeIntervals.size,1);
assert.equal((documentEvents.get('DOMContentLoaded')||[]).length,0);
assert.equal((events.get('pagehide')||[]).length,1,'only normal refresh owns pagehide');
assert.equal((documentEvents.get('visibilitychange')||[]).length,1,'only normal page refresh owns visibility now');
await ready();assert.equal(mounts.length,1);assert.equal(activeIntervals.size,1);
""")


@pytest.mark.parametrize('page', PAGES)
def test_deadline_fails_without_boot_and_late_completion_cannot_replace_it(page):
    page_js(page, r"""
boot();await expire();
const status=elements.get('data-source-status');
assert.match(status.textContent,/could not start.*5 seconds.*Reload/i);
assert.equal(status.role,'alert');const failed=status.textContent;
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
assert.equal((events.get('pagehide')||[]).length,0);
assert.equal((documentEvents.get('DOMContentLoaded')||[]).length,0);
assert.equal((documentEvents.get('visibilitychange')||[]).length,0);
await ready();await fire('pageshow');
assert.equal(status.textContent,failed);assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);
""")


@pytest.mark.parametrize('page', PAGES)
def test_late_ready_or_visible_event_checks_elapsed_deadline_before_timer_runs(page):
    for event in ['ready', 'visible']:
        page_js(page, r"""
boot();monotonic=5001;
if(EVENT==='ready')await ready();
else {context.document.hidden=false;for(const fn of [...(documentEvents.get('visibilitychange')||[])])fn();await flush();}
assert.match(elements.get('data-source-status').textContent,/could not start.*5 seconds/i);
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
""".replace('EVENT', repr(event)))


@pytest.mark.parametrize('page', PAGES)
def test_pagehide_during_startup_cancels_and_cannot_resume_late(page):
    page_js(page, r"""
boot();await fire('pagehide');
assert.match(elements.get('data-source-status').textContent,/startup was interrupted.*Reload/i);
assert.equal(timers.size,0);assert.equal(mounts.length,0);
assert.equal((events.get('pagehide')||[]).length,0);
assert.equal((documentEvents.get('DOMContentLoaded')||[]).length,0);
assert.equal((documentEvents.get('visibilitychange')||[]).length,0);
await ready();await fire('pageshow');
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);
""")


@pytest.mark.parametrize('page', PAGES)
def test_file_mode_boots_saved_data_without_background_refresh(page):
    page_js(page, r"""
context.location.protocol='file:';boot();await ready();
assert.equal(mounts.length,1);assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
assert.match(elements.get('data-source-status').textContent,/Snapshot data/);
""")


def test_offline_graph_missing_ui_keeps_valid_saved_map_with_truthful_label():
    page_js('graph.html', r"""
context.location.protocol='file:';context.UI=undefined;
boot();await ready();
assert.equal(mounts.length,1);assert.equal(activeIntervals.size,0);
assert.match(elements.get('data-source-status').textContent,/Saved data only.*interface.*unavailable/i);
""")


def test_graph_missing_renderer_is_a_visible_failure():
    page_js('graph.html', r"""
context.BrainMap=undefined;boot();await ready();
assert.match(elements.get('data-source-status').textContent,/could not start.*map interface/i);
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);
""")


@pytest.mark.parametrize('page', PAGES)
def test_dependency_values_are_captured_after_ready_not_when_gate_is_installed(page):
    page_js(page, r"""
const renderer=context.BrainMap;
context.UI=undefined;context.BrainMap=undefined;
context.BRAIN_SUMMARY=undefined;context.BRAIN_MAP=undefined;
boot();await flush();
assert.match(elements.get('data-source-status').textContent,/Loading interface files/);
assert.equal(mounts.length,0);
context.UI=U;context.BrainMap=renderer;context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
await ready();assert.equal(mounts.length,1);assert.equal(activeIntervals.size,1);
assert.equal(mounts[0].summary,fixture);assert.equal(mounts[0].map,map);
""")


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('elapsed,expected_mounts', [(4999, 1), (5000, 0)])
def test_exact_readiness_deadline_boundary(page, elapsed, expected_mounts):
    page_js(page, f"boot();monotonic={elapsed};await ready();" +
            f"assert.equal(mounts.length,{expected_mounts});")


def test_http_graph_missing_ui_fails_without_using_offline_shim():
    page_js('graph.html', r"""
context.UI=undefined;boot();await ready();
assert.match(elements.get('data-source-status').textContent,/could not start.*interface files/i);
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);
""")


def test_offline_graph_invalid_saved_map_is_labeled_unavailable():
    page_js('graph.html', r"""
context.location.protocol='file:';context.UI=undefined;context.BRAIN_MAP={nodes:'bad'};
boot();await ready();
assert.equal(mounts.length,0);assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
assert.match(elements.get('data-source-status').textContent,/Data unavailable.*interface files are unavailable/i);
""")


def test_graph_thrown_initialization_is_contained_and_releases_startup_hooks():
    page_js('graph.html', r"""
context.BrainMap.mount=()=>{throw new Error('<img src=x onerror=alert(1)>');};
boot();await ready();
const status=elements.get('data-source-status');
assert.match(status.textContent,/could not start.*initialization error/i);
assert.doesNotMatch(status.textContent,/<img/);
assert.equal(activeIntervals.size,0);assert.equal(timers.size,0);
assert.equal((events.get('pagehide')||[]).length,0);
assert.equal((documentEvents.get('DOMContentLoaded')||[]).length,0);
assert.equal((documentEvents.get('visibilitychange')||[]).length,0);
""")
