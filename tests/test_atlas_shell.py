"""Static and executable checks for the shared Atlas presentation shell."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest


VIEW = Path(__file__).resolve().parents[1] / "memory" / "brain" / "view"
NODE = shutil.which("node")


def _luminance(value: str) -> float:
    channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045
              else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(left: str, right: str) -> float:
    bright, dark = sorted((_luminance(left), _luminance(right)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def test_today_uses_the_shared_light_shell_and_progressive_evidence():
    html = (VIEW / "dashboard.html").read_text()
    assert '<html lang="en" data-atlas data-theme="light">' in html
    assert html.index("</style>") < html.index('atlas.css?v=20260907-a')
    assert '<script async src="atlas.js?v=20260907-a"></script>' in html
    map_digest = hashlib.sha256((VIEW / "map.js").read_bytes()).hexdigest()
    assert f'<script defer src="map.js?v={map_digest}"></script>' in html
    assert '<script defer src="map.js"></script>' not in html
    assert 'window.addEventListener("atlas-theme-change", mountMap)' not in html
    assert '<aside class="atlas-nav" aria-label="Agent System navigation">' in html
    assert 'href="dashboard.html" aria-current="page">Today</a>' in html
    assert '>Work graph</a>' in html and '>Skills &amp; healing</a>' in html
    assert 'nav class="views"' not in html
    evidence = html[html.index('<details class="evidence-vault"'):
                    html.index('</details>', html.index('<details class="evidence-vault"'))]
    for section_id in ("operationsband", "inbox", "mapband", "loopband",
                       "contractsband", "timelineband", "rulesband", "daysband"):
        assert f'id="{section_id}"' in evidence


def test_shared_css_preserves_hidden_and_meets_small_text_contrast():
    css = (VIEW / "atlas.css").read_text()
    assert "html[data-atlas] [hidden] { display: none !important; }" in css
    assert "@media (max-width: 900px)" in css
    assert "position: relative" in css[css.index("@media (max-width: 900px)"):]
    assert "html[data-atlas] #ui-panel" in css
    assert 'html[data-atlas] [role="tooltip"]' in css
    dark_start = css.index('html[data-atlas][data-theme="dark"]')
    palettes = {
        "light": dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", css[:dark_start])),
        "dark": dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})",
                                css[dark_start:css.index("html[data-atlas] *,", dark_start)])),
    }
    assert palettes["light"]["--accent"] != palettes["dark"]["--accent"]
    for mode, values in palettes.items():
        for foreground in ("--text", "--text-dim", "--text-faint", "--text-ghost", "--warn", "--accent"):
            for background in ("--surface", "--surface-2", "--bg"):
                assert _contrast(values[foreground], values[background]) >= 4.5, (mode, foreground, background)


def test_status_cells_wrap_internally_and_focus_outline_has_actual_contrast():
    css = (VIEW / "atlas.css").read_text()
    status = re.search(r"html\[data-atlas\] #status\s*\{([^}]+)\}", css)
    segment = re.search(r"html\[data-atlas\] #status \.seg\s*\{([^}]+)\}", css)
    label = re.search(r"html\[data-atlas\] #status \.seg \.k\s*\{([^}]+)\}", css)
    assert status and segment and label
    assert re.search(r"display:\s*grid", status.group(1))
    assert re.search(r"grid-template-columns:\s*repeat\(7,\s*minmax\(0,\s*1fr\)\)", status.group(1))
    assert re.search(r"min-width:\s*0", segment.group(1))
    assert re.search(r"flex-wrap:\s*wrap", segment.group(1))
    assert re.search(r"overflow:\s*hidden", segment.group(1))
    assert re.search(r"white-space:\s*normal", label.group(1))
    assert re.search(r"overflow-wrap:\s*anywhere", label.group(1))

    focus = re.search(r"html\[data-atlas\] :focus-visible\s*\{([^}]+)\}", css)
    assert focus
    outline = re.search(r"outline:\s*\d+px solid var\((--[\w-]+)\)", focus.group(1))
    assert outline, "focus outline must resolve to a palette token, not an untested color mix"
    dark_start = css.index('html[data-atlas][data-theme="dark"]')
    modes = {
        "light": css[:dark_start],
        "dark": css[dark_start:css.index("html[data-atlas] *,", dark_start)],
    }
    for mode, block in modes.items():
        values = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block))
        outline_color = values[outline.group(1)]
        for background in ("--surface", "--surface-2", "--bg"):
            assert _contrast(outline_color, values[background]) >= 3.0, (mode, background)


@pytest.mark.parametrize("phase", ["early", "late"])
def test_theme_helper_persists_target_mode_and_emits_graph_event(phase):
    if not NODE:
        pytest.fail("Node is required to exercise the shared theme helper")
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const attributes={},button={textContent:'',setAttribute(k,v){attributes[k]=v;}};
const listeners={},events=[];
const early=process.argv[2]==='early';let parsed=!early;
const root={dataset:{theme:'light'},hasAttribute(k){return k==='data-atlas';}};
global.document={documentElement:root,readyState:early?'loading':'complete',
 querySelectorAll(){return parsed?[button]:[];},
 addEventListener(k,fn){listeners[k]=fn;}};
global.localStorage={value:'dark',getItem(k){assert.equal(k,'brain.atlas.theme');return this.value;},
 setItem(k,v){assert.equal(k,'brain.atlas.theme');this.value=v;}};
global.window={CustomEvent:function(name,opts){this.type=name;this.detail=opts.detail;},
 dispatchEvent(event){events.push(event);}};
eval(fs.readFileSync(process.argv[1],'utf8'));
assert.equal(root.dataset.theme,'dark');assert.equal(events.length,1);
assert.equal(events[0].type,'atlas-theme-change');assert.equal(events[0].detail.theme,'dark');
if(early){assert.equal(button.textContent,'');parsed=true;listeners.DOMContentLoaded();}
assert.equal(button.textContent,'Light theme');
assert.equal(attributes['aria-label'],'Switch to light theme');assert.equal(attributes['aria-pressed'],'true');
listeners.click({target:{closest(){return button;}}});
assert.equal(root.dataset.theme,'light');assert.equal(localStorage.value,'light');
assert.equal(button.textContent,'Dark theme');assert.equal(events.length,2);
assert.equal(events[1].type,'atlas-theme-change');assert.equal(events[1].detail.theme,'light');
"""
    result = subprocess.run(
        [NODE, "-e", script, str(VIEW / "atlas.js"), phase],
        text=True, capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_theme_helper_has_no_data_or_action_authority():
    source = (VIEW / "atlas.js").read_text()
    assert "brain.atlas.theme" in source
    assert not re.search(r"\bfetch\s*\(|XMLHttpRequest|/api/|\bPOST\b", source)
