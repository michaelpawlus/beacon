"""Tests for beacon.presence.crosspost — multi-platform content distribution."""

import pytest

from beacon.presence.crosspost import crosspost_blog, _make_linkedin_teaser


class TestCrosspostBlog:
    def test_returns_all_platforms(self):
        result = crosspost_blog("# Post\nThis is content.", title="Test Post")
        assert "astro" in result
        assert "linkedin" in result
        assert "medium" in result
        assert "devto" in result

    def test_astro_has_frontmatter(self):
        result = crosspost_blog("Content here", title="Test Post", tags=["ai"])
        assert result["astro"].startswith("---")
        assert 'title: "Test Post"' in result["astro"]
        assert "tags: [ai]" in result["astro"]

    def test_medium_strips_frontmatter(self):
        content = "---\ntitle: Old\n---\nBody content here"
        result = crosspost_blog(content, title="New")
        assert "---" not in result["medium"]
        assert "Body content here" in result["medium"]

    def test_devto_has_frontmatter(self):
        result = crosspost_blog("Content", title="Test", tags=["python", "ai"])
        assert "title: Test" in result["devto"]
        assert "tags: python, ai" in result["devto"]
        assert "published: false" in result["devto"]

    def test_linkedin_is_teaser(self):
        long_body = "# My Post\n\nThis is the hook paragraph with enough content.\n\nSecond paragraph with more detail.\n\nThird paragraph with even more detail.\n\nFourth paragraph wrapping up."
        result = crosspost_blog(long_body, title="My Post")
        assert "My Post" in result["linkedin"]
        assert "Fourth paragraph" not in result["linkedin"]

    def test_with_site_url(self):
        result = crosspost_blog("Content paragraph that is long enough to be used as hook content.", title="Post", site_url="https://example.com/post")
        assert "https://example.com/post" in result["linkedin"]

    def test_with_description(self):
        result = crosspost_blog("Content", title="Post", description="A great post", tags=["ai"])
        assert 'description: "A great post"' in result["astro"]
        assert "description: A great post" in result["devto"]

    def test_empty_tags(self):
        result = crosspost_blog("Content", title="Post")
        assert "devto" in result
        assert "astro" in result


class TestMakeLinkedInTeaser:
    def test_includes_title(self):
        result = _make_linkedin_teaser("Content that is long enough to be a paragraph hook.", title="My Post")
        assert "My Post" in result

    def test_strips_frontmatter(self):
        body = "---\ntitle: Test\n---\nActual content that is long enough to be a paragraph hook."
        result = _make_linkedin_teaser(body)
        assert "---" not in result
        assert "Actual content" in result

    def test_includes_site_url(self):
        result = _make_linkedin_teaser("Long enough content to form a valid paragraph hook for the LinkedIn post.", site_url="https://example.com")
        assert "https://example.com" in result

    def test_fallback_without_url(self):
        result = _make_linkedin_teaser("Content that is long enough to form a paragraph for testing purposes.")
        assert "Link to full post" in result

    def test_skips_headers(self):
        body = "# Title Header\n\nThis is the actual content paragraph that should be used as the teaser hook."
        result = _make_linkedin_teaser(body)
        # Should use the paragraph, not the header
        assert "actual content paragraph" in result

    def test_truncates_long_hooks(self):
        long_para = "word " * 200
        result = _make_linkedin_teaser(long_para)
        # Hook should be truncated to 500 chars
        assert len(result) < len(long_para)
