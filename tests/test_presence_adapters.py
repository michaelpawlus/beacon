"""Tests for beacon.presence.adapters — platform format adapters."""

import pytest

from beacon.presence.adapters import (
    adapt_for_blog_markdown,
    adapt_for_devto,
    adapt_for_github_markdown,
    adapt_for_linkedin,
    adapt_for_medium,
)


class TestAdaptForLinkedIn:
    def test_strips_bold_markdown(self):
        result = adapt_for_linkedin("This is **bold** text")
        assert result == "This is bold text"

    def test_strips_italic_markdown(self):
        result = adapt_for_linkedin("This is *italic* text")
        assert result == "This is italic text"

    def test_strips_headers(self):
        result = adapt_for_linkedin("## Header\nContent")
        assert result == "Header\nContent"

    def test_converts_links(self):
        result = adapt_for_linkedin("Visit [Google](https://google.com)")
        assert result == "Visit Google (https://google.com)"

    def test_strips_code_blocks(self):
        result = adapt_for_linkedin("Before\n```python\ncode\n```\nAfter")
        assert "```" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_inline_code(self):
        result = adapt_for_linkedin("Use `pip install` to install")
        assert result == "Use pip install to install"

    def test_strips_images(self):
        result = adapt_for_linkedin("![alt](image.png)")
        assert "![" not in result

    def test_truncates_to_limit(self):
        long_text = "word " * 1000
        result = adapt_for_linkedin(long_text, max_chars=100)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_preserves_line_breaks(self):
        result = adapt_for_linkedin("Line 1\n\nLine 2")
        assert "Line 1\n\nLine 2" in result

    def test_collapses_excess_newlines(self):
        result = adapt_for_linkedin("Line 1\n\n\n\n\nLine 2")
        assert "\n\n\n" not in result

    def test_default_limit_is_3000(self):
        short_text = "Hello world"
        result = adapt_for_linkedin(short_text)
        assert result == "Hello world"

    def test_strips_underscore_formatting(self):
        result = adapt_for_linkedin("This is __bold__ and _italic_")
        assert result == "This is bold and italic"


class TestAdaptForGitHubMarkdown:
    def test_adds_spacing_before_headers(self):
        result = adapt_for_github_markdown("Content\n## Header")
        assert "\n\n## Header" in result

    def test_adds_spacing_before_lists(self):
        result = adapt_for_github_markdown("Content\n- Item 1")
        assert "\n\n- Item 1" in result

    def test_preserves_existing_spacing(self):
        result = adapt_for_github_markdown("Content\n\n## Header")
        assert result == "Content\n\n## Header"

    def test_strips_surrounding_whitespace(self):
        result = adapt_for_github_markdown("  \n\nContent\n\n  ")
        assert result == "Content"

    def test_handles_multiple_header_levels(self):
        content = "Text\n# H1\nMore\n### H3"
        result = adapt_for_github_markdown(content)
        assert "\n\n# H1" in result
        assert "\n\n### H3" in result


class TestAdaptForBlogMarkdown:
    def test_adds_frontmatter(self):
        result = adapt_for_blog_markdown("Content here", title="My Post")
        assert result.startswith("---")
        assert 'title: "My Post"' in result
        assert "Content here" in result

    def test_includes_date(self):
        result = adapt_for_blog_markdown("Content", date="2025-01-15")
        assert "date: 2025-01-15" in result

    def test_includes_tags(self):
        result = adapt_for_blog_markdown("Content", tags=["python", "ai"])
        assert "tags: [python, ai]" in result

    def test_includes_description(self):
        result = adapt_for_blog_markdown("Content", description="A blog post")
        assert 'description: "A blog post"' in result

    def test_includes_draft_flag(self):
        result = adapt_for_blog_markdown("Content")
        assert "draft: true" in result

    def test_preserves_existing_frontmatter(self):
        content = "---\ntitle: Existing\n---\nBody"
        result = adapt_for_blog_markdown(content, title="Ignored")
        assert "Existing" in result
        assert "Ignored" not in result

    def test_uses_current_date_as_default(self):
        from datetime import datetime
        result = adapt_for_blog_markdown("Content")
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"date: {today}" in result


class TestAdaptForMedium:
    def test_removes_frontmatter(self):
        content = "---\ntitle: Test\ntags: [ai]\n---\nBody content"
        result = adapt_for_medium(content)
        assert "---" not in result
        assert "Body content" in result

    def test_converts_h1_to_h2(self):
        result = adapt_for_medium("# Title\nContent")
        assert result.startswith("## Title")

    def test_preserves_h2_and_below(self):
        result = adapt_for_medium("## Subtitle\n### Sub")
        assert "## Subtitle" in result
        assert "### Sub" in result

    def test_handles_no_frontmatter(self):
        result = adapt_for_medium("Just content")
        assert result == "Just content"


class TestAdaptForDevTo:
    def test_adds_devto_frontmatter(self):
        result = adapt_for_devto("Content", title="My Post", tags=["python", "ai"])
        assert "title: My Post" in result
        assert "published: false" in result
        assert "tags: python, ai" in result

    def test_limits_to_four_tags(self):
        result = adapt_for_devto("Content", tags=["alpha", "beta", "gamma", "delta", "epsilon"])
        assert "tags: alpha, beta, gamma, delta" in result
        assert "epsilon" not in result

    def test_replaces_existing_frontmatter(self):
        content = "---\ntitle: Old\n---\nBody"
        result = adapt_for_devto(content, title="New")
        assert "title: New" in result
        assert "title: Old" not in result
        assert "Body" in result

    def test_published_flag(self):
        result = adapt_for_devto("Content", published=True)
        assert "published: true" in result

    def test_includes_description(self):
        result = adapt_for_devto("Content", description="A great post")
        assert "description: A great post" in result
