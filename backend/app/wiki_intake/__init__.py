"""KFC-owned Wiki intake module.

The module owns repo-local sidecar state for Clippings -> Wiki intake. The
external Clippings directory is read-only input; processing state is stored
under ``backend/data/wiki_intake``.
"""

from .store import WikiIntakeStore, WikiIntakeStoreError

__all__ = ["WikiIntakeStore", "WikiIntakeStoreError"]
