"""The apply ladder: exact verbatim, indentation-tolerant fallback, hard fail on
content drift. Both backends (local and the in-sandbox script) share semantics —
a patch that passes on one must pass on the other."""

import subprocess
import sys
import tempfile
from pathlib import Path

from blindrun.adapters.sandbox_contree import _APPLY_PY
from blindrun.adapters.sandbox_local import _apply_edits

_FILE = "index.html"
_CONTENT = """<main>
  <div id="size-picker">
    <div class="size" onclick="pick(this)">S</div>
  </div>
</main>
"""

_VERBATIM = "<<<SEARCH\n  <div id=\"size-picker\">\n===\n  <div id=\"size-picker\" role=\"radiogroup\">\n>>>"
_REINDENTED = "<<<SEARCH\n<div id=\"size-picker\">\n===\n<div id=\"size-picker\" role=\"radiogroup\">\n>>>"
_DRIFTED = "<<<SEARCH\n<div id='size-picker' class='picker'>\n===\n<div>\n>>>"


def _run_local(content: str, edits: str) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        (site / _FILE).write_text(content)
        rc, err = _apply_edits(site, _FILE, edits)
        return rc, err, (site / _FILE).read_text() if rc == 0 else ""


def _run_contree(content: str, edits: str) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        page, patch = Path(tmp) / "p.html", Path(tmp) / "e.txt"
        page.write_text(content)
        patch.write_text(edits)
        r = subprocess.run(
            [sys.executable, "-c", _APPLY_PY, str(page), str(patch)],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode, r.stderr.strip(), page.read_text() if r.returncode == 0 else ""


def test_verbatim_applies_on_both_backends():
    for rc, _, out in (_run_local(_CONTENT, _VERBATIM), _run_contree(_CONTENT, _VERBATIM)):
        assert rc == 0
        assert 'role="radiogroup"' in out
        assert 'onclick="pick(this)">S' in out  # untouched tail survives


def test_indentation_drift_tolerated_and_reindented_on_both():
    # model quoted the picker with NO indentation; file has 2 spaces
    for rc, _, out in (_run_local(_CONTENT, _REINDENTED), _run_contree(_CONTENT, _REINDENTED)):
        assert rc == 0
        assert '  <div id="size-picker" role="radiogroup">' in out


def test_content_drift_still_fails_on_both():
    assert _run_local(_CONTENT, _DRIFTED)[0] == 1
    assert _run_contree(_CONTENT, _DRIFTED)[0] != 0


def test_mega_block_splits_into_independent_candidates():
    """Models emit all alternatives inside one unclosed block; the extractor must
    return each <<<SEARCH/===/>>> pair as its own candidate, not one mega-patch
    whose later pairs poison the branch after pair 1 mutated the file."""
    from blindrun.pipeline.orchestrator import _extract_edit_blocks

    mega = (
        "```fix\n"
        "<<<SEARCH\n  <div id=\"a\">\n===\n  <div id=\"a\" fixed>\n"
        "<<<SEARCH\n  <div id=\"b\">\n===\n  <div id=\"b\" fixed>\n"
        "<<<SEARCH\n  <div id=\"c\">\n===\n  <div id=\"c\" fixed>\n>>>\n```"
    )
    edits = _extract_edit_blocks(mega)
    assert len(edits) == 3
    assert edits[0] == '<<<SEARCH\n  <div id="a">\n===\n  <div id="a" fixed>\n>>>'
