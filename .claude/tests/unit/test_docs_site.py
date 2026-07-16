from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
BUILD_DOCS = REPO / "docs-site" / "scripts" / "build_docs.py"


def _load_build_docs():
    spec = importlib.util.spec_from_file_location("build_docs", BUILD_DOCS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_matrix_is_generated_from_manifest():
    build_docs = _load_build_docs()

    names = {row["name"] for row in build_docs.hook_matrix()}

    assert "search-first" in names
    assert "budget-observer" in names
    assert "terse-output" in names


def test_installer_flags_are_parsed_from_argparse_metadata():
    build_docs = _load_build_docs()

    flags = {flag for row in build_docs.installer_flags() for flag in row["flags"]}

    assert "--agent" in flags
    assert "--codex-savings" in flags
    assert "--no-compact" in flags


def test_strategy_matrix_links_to_strategy_pages():
    build_docs = _load_build_docs()

    slugs = {row["slug"] for row in build_docs.strategy_matrix()}

    assert "search-first" in slugs
    assert "budget-control-plane" in slugs
    assert "lean-output-truncation" in slugs


def test_every_slide_has_a_visual_definition():
    build_docs = _load_build_docs()

    slide_anchors = [anchor for anchor, _title, _text in build_docs.SLIDES]

    assert len(slide_anchors) == 26
    assert set(slide_anchors) == set(build_docs.SLIDE_VISUALS)


def test_presentation_renders_one_image_per_slide():
    build_docs = _load_build_docs()

    html = build_docs.presentation_page("presentation.html")
    slide_count = len(build_docs.SLIDES)
    image_slide_count = sum(
        anchor not in {"telemetry", "maintenance-skills"}
        for anchor, _title, _text in build_docs.SLIDES
    )

    assert html.count('<section class="slide"') == slide_count
    assert html.count('<figure class="slide-visual">') == slide_count
    assert html.count('assets/slides/') == image_slide_count + 5


def test_overview_uses_representative_report_instead_of_slider():
    build_docs = _load_build_docs()

    html = build_docs.overview_page("index.html")

    assert 'class="overview-stats"' in html
    assert "Measured before model" in html
    assert "Sanitized example data" in html
    assert 'type="range"' not in html


def test_strategy_detail_marks_strategy_navigation_current():
    build_docs = _load_build_docs()

    html = build_docs.strategy_page(
        "strategies/search-first.html",
        "search-first",
        build_docs.STRATEGY_DETAILS["search-first"],
    )

    assert 'href="../strategy-map.html" aria-current="page">Strategies</a>' in html


def test_repo_link_uses_github_blob_when_publish_env_is_set(monkeypatch):
    build_docs = _load_build_docs()
    monkeypatch.setenv("LESS_TOKENS_DOCS_REPO_URL", "https://github.com/hofmockel/less_tokens")
    monkeypatch.setenv("LESS_TOKENS_DOCS_COMMIT", "abc123")

    assert build_docs.repo_link("strategies/search-first.html", "README.md") == (
        "https://github.com/hofmockel/less_tokens/blob/abc123/README.md"
    )


def test_repo_link_stays_local_without_publish_env(monkeypatch):
    build_docs = _load_build_docs()
    monkeypatch.delenv("LESS_TOKENS_DOCS_REPO_URL", raising=False)
    monkeypatch.delenv("LESS_TOKENS_DOCS_COMMIT", raising=False)

    assert build_docs.repo_link("strategies/search-first.html", "README.md") == "../../../README.md"
