"""Adapter registry — maps platform names to adapter instances."""

from beacon.scrapers.base import BaseAdapter


def get_adapter(platform: str) -> BaseAdapter | None:
    """Get the appropriate adapter for a careers platform.

    Args:
        platform: One of 'greenhouse', 'lever', 'ashby', 'custom'.

    Returns:
        An adapter instance, or None if no adapter available.
    """
    if platform == "greenhouse":
        from beacon.scrapers.greenhouse import GreenhouseAdapter
        return GreenhouseAdapter()
    elif platform == "lever":
        from beacon.scrapers.lever import LeverAdapter
        return LeverAdapter()
    elif platform == "ashby":
        from beacon.scrapers.ashby import AshbyAdapter
        return AshbyAdapter()
    elif platform == "custom":
        from beacon.scrapers.generic import GenericScraperAdapter
        return GenericScraperAdapter()
    return None
