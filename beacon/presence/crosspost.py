"""Cross-posting pipeline for multi-platform content distribution.

Generates platform-specific versions of blog posts for:
- Astro (YAML frontmatter + markdown)
- LinkedIn (teaser post with link)
- Medium (markdown, no frontmatter)
- Dev.to (liquid tags frontmatter)
"""

import sqlite3

from beacon.presence.adapters import (
    adapt_for_blog_markdown,
    adapt_for_devto,
    adapt_for_linkedin,
    adapt_for_medium,
)


def crosspost_blog(
    body: str,
    title: str = "",
    tags: list[str] | None = None,
    description: str = "",
    site_url: str = "",
) -> dict[str, str]:
    """Generate platform-specific versions of a blog post.

    Returns a dict with keys: astro, linkedin, medium, devto.
    """
    tags = tags or []

    versions = {
        "astro": adapt_for_blog_markdown(
            body, title=title, tags=tags, description=description,
        ),
        "linkedin": _make_linkedin_teaser(body, title=title, site_url=site_url),
        "medium": adapt_for_medium(body),
        "devto": adapt_for_devto(
            body, title=title, tags=tags, description=description,
        ),
    }

    return versions


def _make_linkedin_teaser(body: str, title: str = "", site_url: str = "") -> str:
    """Create a LinkedIn teaser post that links to the full blog post.

    Extracts the first paragraph as a hook and adds a call to action.
    """
    # Strip frontmatter if present
    text = body.strip()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    # Find first substantial paragraph (skip headers)
    paragraphs = text.split("\n\n")
    hook = ""
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("#") and len(p) > 50:
            hook = p
            break

    if not hook:
        hook = paragraphs[0] if paragraphs else ""

    parts = []
    if title:
        parts.append(f"New post: {title}")
        parts.append("")
    parts.append(hook[:500])
    parts.append("")
    if site_url:
        parts.append(f"Read the full post: {site_url}")
    else:
        parts.append("Link to full post in comments.")

    teaser = "\n".join(parts)
    return adapt_for_linkedin(teaser)
