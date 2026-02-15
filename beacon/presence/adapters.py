"""Platform format adapters for content output.

Adapts generated content for platform-specific constraints:
- LinkedIn: character limits, no markdown
- GitHub: full markdown
- Blog: YAML frontmatter + markdown
- Medium: markdown (no frontmatter)
- Dev.to: markdown with liquid tags frontmatter
"""

import re
from datetime import datetime


def adapt_for_linkedin(content: str, max_chars: int = 3000) -> str:
    """Adapt content for LinkedIn posting.

    - Strips markdown formatting (bold, italic, links, headers)
    - Preserves line breaks
    - Truncates to character limit
    """
    text = content

    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)

    # Convert markdown links to plain text with URL
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", text)

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)

    # Remove images
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Clean up extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[: max_chars - 3].rsplit(" ", 1)[0] + "..."

    return text


def adapt_for_github_markdown(content: str) -> str:
    """Adapt content for GitHub markdown rendering.

    Ensures proper GitHub-flavored markdown formatting.
    """
    text = content.strip()

    # Ensure proper spacing around headers
    text = re.sub(r"(\S)\n(#{1,6}\s)", r"\1\n\n\2", text)

    # Ensure blank line before lists
    text = re.sub(r"(\S)\n([-*+]\s)", r"\1\n\n\2", text)

    return text


def adapt_for_blog_markdown(content: str, title: str = "", tags: list[str] | None = None,
                             description: str = "", date: str | None = None) -> str:
    """Adapt content for blog publishing with YAML frontmatter.

    If frontmatter already exists in content, returns as-is.
    Otherwise, adds YAML frontmatter.
    """
    if content.strip().startswith("---"):
        return content.strip()

    date = date or datetime.now().strftime("%Y-%m-%d")
    tags = tags or []

    frontmatter_parts = [
        "---",
        f'title: "{title}"',
        f"date: {date}",
    ]
    if description:
        frontmatter_parts.append(f'description: "{description}"')
    if tags:
        frontmatter_parts.append(f"tags: [{', '.join(tags)}]")
    frontmatter_parts.append("draft: true")
    frontmatter_parts.append("---")

    frontmatter = "\n".join(frontmatter_parts)
    return f"{frontmatter}\n\n{content.strip()}"


def adapt_for_medium(content: str) -> str:
    """Adapt content for Medium publishing.

    - Removes YAML frontmatter
    - Keeps standard markdown (Medium supports it)
    - Ensures proper heading hierarchy
    """
    text = content.strip()

    # Remove YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    # Medium doesn't support H1 well — convert to H2
    text = re.sub(r"^# ", "## ", text, flags=re.MULTILINE)

    return text


def adapt_for_devto(content: str, title: str = "", tags: list[str] | None = None,
                     description: str = "", published: bool = False) -> str:
    """Adapt content for Dev.to publishing with liquid tags frontmatter.

    Dev.to uses a specific frontmatter format.
    """
    tags = tags or []

    # Remove existing frontmatter if present
    text = content.strip()
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    # Build Dev.to frontmatter
    tag_str = ", ".join(tags[:4])  # Dev.to max 4 tags
    frontmatter_parts = [
        "---",
        f"title: {title}",
        f"published: {'true' if published else 'false'}",
        f"description: {description}",
        f"tags: {tag_str}",
        "---",
    ]

    frontmatter = "\n".join(frontmatter_parts)
    return f"{frontmatter}\n\n{text}"
