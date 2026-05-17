"""Tests for the YAML curated source adapter."""

import textwrap

import pytest

from beacon.sources.base import SourceFetchError
from beacon.sources.yaml_curated import YamlCuratedAdapter


@pytest.fixture
def curated_dir(tmp_path):
    """A tmp curated dir with one YAML file holding 3 entries."""
    (tmp_path / "seed.yml").write_text(textwrap.dedent("""
        companies:
          - name: Example AI
            domain: example.ai
            careers_url: https://example.ai/careers
            hq_location: SF
            industry: Developer Tools
            signals:
              - signal_type: engineering_blog
                title: How we use Claude internally
                signal_strength: 4
          - name: Bare Minimum Co
          - name: Other AI
            source_ref: custom-ref
            domain: other.ai
    """))
    return tmp_path


def test_fetch_returns_all_entries(curated_dir):
    adapter = YamlCuratedAdapter(curated_dir=curated_dir)
    candidates = list(adapter.fetch())
    assert len(candidates) == 3
    names = {c.name for c in candidates}
    assert names == {"Example AI", "Bare Minimum Co", "Other AI"}


def test_fetch_attaches_signals(curated_dir):
    adapter = YamlCuratedAdapter(curated_dir=curated_dir)
    candidates = list(adapter.fetch())
    example = next(c for c in candidates if c.name == "Example AI")
    assert len(example.signals) == 1
    assert example.signals[0]["signal_type"] == "engineering_blog"
    assert example.signals[0]["signal_strength"] == 4


def test_source_ref_uses_explicit_value_when_present(curated_dir):
    adapter = YamlCuratedAdapter(curated_dir=curated_dir)
    candidates = list(adapter.fetch())
    other = next(c for c in candidates if c.name == "Other AI")
    assert other.source_ref == "seed/custom-ref"


def test_source_ref_falls_back_to_slug(curated_dir):
    adapter = YamlCuratedAdapter(curated_dir=curated_dir)
    candidates = list(adapter.fetch())
    bare = next(c for c in candidates if c.name == "Bare Minimum Co")
    assert bare.source_ref == "seed/bare-minimum-co"
    assert bare.signals == []
    assert bare.domain is None


def test_limit_truncates(curated_dir):
    adapter = YamlCuratedAdapter(curated_dir=curated_dir)
    candidates = list(adapter.fetch(limit=2))
    assert len(candidates) == 2


def test_missing_dir_raises(tmp_path):
    adapter = YamlCuratedAdapter(curated_dir=tmp_path / "nope")
    with pytest.raises(SourceFetchError, match="does not exist"):
        list(adapter.fetch())


def test_empty_dir_raises(tmp_path):
    adapter = YamlCuratedAdapter(curated_dir=tmp_path)
    with pytest.raises(SourceFetchError, match="No .yml"):
        list(adapter.fetch())


def test_entry_without_name_is_skipped(tmp_path):
    (tmp_path / "f.yml").write_text(textwrap.dedent("""
        companies:
          - domain: no-name.com
          - name: Has Name
    """))
    adapter = YamlCuratedAdapter(curated_dir=tmp_path)
    candidates = list(adapter.fetch())
    assert len(candidates) == 1
    assert candidates[0].name == "Has Name"


def test_committed_seed_file_loads():
    """Spec: `discover --source yaml` must return >=1 candidate against committed seed."""
    adapter = YamlCuratedAdapter()
    candidates = list(adapter.fetch())
    assert len(candidates) >= 1
    assert all(c.source == "yaml" for c in candidates)
