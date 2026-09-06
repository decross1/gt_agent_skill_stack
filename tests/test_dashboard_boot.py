"""Execute the shipped automatic bootstrap with absent and incompatible assets."""
import hashlib
import re

import pytest

from test_ui_data_provenance import FAKE_CLOCK, PAGE_DATA, VIEW, run_js

BOOT = FAKE_CLOCK + PAGE_DATA.replace('PAGE', "'dashboard.html'")


def test_dashboard_dependency_url_tracks_exact_ui_bytes():
    html = (VIEW / 'dashboard.html').read_text()
    digest = hashlib.sha256((VIEW / 'ui.js').read_bytes()).hexdigest()
    assert f'src="ui.js?v={digest}"' in html
    assert re.search(r'<noscript>[\s\S]*JavaScript[\s\S]*</noscript>', html)


@pytest.mark.parametrize('missing', ['all', 'dataSource', 'usableSummary', 'pageRefresh'])
def test_incompatible_dependency_shows_visible_failure_without_starting(missing):
    setup = 'context.UI=undefined;' if missing == 'all' else f'delete context.UI.{missing};'
    run_js(BOOT + setup + r"""
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
boot();await flush();
assert.match(elements.get('data-source-status').textContent,/Dashboard could not start/);
assert.match(elements.get('data-source-status').textContent,/interface files/);
assert.equal(activeIntervals.size,0);
assert.equal(mounts.length,0);
""")


def test_initial_render_exception_is_visible_and_not_html():
    run_js(BOOT + r"""
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
context.UI.esc=()=>{throw new Error('<img src=x onerror=alert(1)>');};
boot();await flush();
const status=elements.get('data-source-status');
assert.match(status.textContent,/Dashboard could not start/);
assert.equal(status.innerHTML,'');
assert.equal(activeIntervals.size,0);
""")


def test_current_dependency_automatically_boots_without_manual_render():
    run_js(BOOT + r"""
context.BRAIN_SUMMARY=fixture;context.BRAIN_MAP=map;
boot();await flush();
assert.doesNotMatch(elements.get('data-source-status').textContent,/not been checked|could not start/);
assert.match(elements.get('data-source-status').textContent,/snapshot/);
assert.equal(activeIntervals.size,1);
assert.equal(mounts.length,1);
""")
