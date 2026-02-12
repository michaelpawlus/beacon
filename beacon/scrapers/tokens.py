"""Board token mappings for Greenhouse and other ATS platforms.

Greenhouse board tokens are extracted from company career page URLs.
Format: boards-api.greenhouse.io/v1/boards/{token}/jobs
"""

# Maps company domain -> Greenhouse board token
# Tokens are the URL slug used in the Greenhouse boards API
GREENHOUSE_TOKENS: dict[str, str] = {
    "anthropic.com": "anthropic",
    "openai.com": "openai",
    "vercel.com": "vercel",
    "databricks.com": "databricks",
    "cohere.com": "cohere",
    "duolingo.com": "duolingo",
    "block.xyz": "block",
    "notion.so": "notion",
    "ramp.com": "ramp",
    "gitlab.com": "gitlab",
    "scale.com": "scaleai",
    "wandb.ai": "wandb",
    "getdbt.com": "daboraio",
    "figma.com": "figma",
    "canva.com": "canva",
    "doordash.com": "doordash",
    "brex.com": "brex",
    "together.ai": "togetherai",
    "hex.tech": "hex",
}


def get_board_token(platform: str, domain: str) -> str | None:
    """Look up the board token for a company by platform and domain."""
    if platform == "greenhouse":
        return GREENHOUSE_TOKENS.get(domain)
    return None
