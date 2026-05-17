"""Source adapter registry for `beacon companies discover`.

Each adapter is registered by short name. The CLI looks adapters up here so
adding a new source is a one-line change in `_REGISTRY`.
"""

from beacon.sources.base import (
    Candidate,
    SourceAdapter,
    SourceAuthError,
    SourceError,
    SourceFetchError,
)

__all__ = [
    "Candidate",
    "SourceAdapter",
    "SourceAuthError",
    "SourceError",
    "SourceFetchError",
    "get_adapter",
    "list_sources",
]


_REGISTRY: dict[str, str] = {
    "yaml": "beacon.sources.yaml_curated:YamlCuratedAdapter",
    "crunchbase": "beacon.sources.crunchbase:CrunchbaseAdapter",
}


def list_sources() -> list[str]:
    """Return registered source names in stable order."""
    return sorted(_REGISTRY)


def get_adapter(name: str, **kwargs) -> SourceAdapter:
    """Instantiate an adapter by name.

    Raises:
        KeyError: If `name` is not registered.
    """
    if name not in _REGISTRY:
        raise KeyError(f"Unknown source '{name}'. Registered: {sorted(_REGISTRY)}")

    module_path, class_name = _REGISTRY[name].split(":")
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)
