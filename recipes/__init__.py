"""Alert-recipe registry.

Each recipe is a module in this package that exposes:

    NAME: str                          # command name for `run-alert <NAME>`
    HELP: str                          # one-line description for --help
    add_arguments(parser)              # register recipe-specific CLI args
    build_blocks(args) -> list[dict]   # may fetch data; returns Block Kit blocks
    fallback_text(args) -> str         # notification/accessibility fallback

Optional:
    DEFAULT_CHANNEL: str | None        # used when --channel is omitted

Recipes are discovered lazily by module scan, so adding a new alert is just
dropping a new module in this directory — no registration boilerplate.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

_REGISTRY: dict[str, ModuleType] | None = None


def _discover() -> dict[str, ModuleType]:
    registry: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        name = getattr(module, "NAME", info.name)
        registry[name] = module
    return registry


def registry() -> dict[str, ModuleType]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _discover()
    return _REGISTRY


def get_recipe(name: str) -> ModuleType | None:
    return registry().get(name)


def recipe_names() -> list[str]:
    return sorted(registry().keys())
