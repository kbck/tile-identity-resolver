"""Register Tile identities and resolve version-2 FEED payloads."""

import hashlib
import hmac
from collections.abc import Iterable

from .models import Tile, TileInfo, _to_bytes


def _generate_private_ids(tile: Tile) -> dict[bytes, int]:
    tile_id = bytes.fromhex(tile.tile_id)
    auth_key = _to_bytes(tile.auth_key)
    identity_message = tile_id + b"identity" + bytes(16)
    identity_key = hmac.digest(auth_key, identity_message, hashlib.sha256)[:16]

    private_ids = {}
    for counter in range(8640):
        counter_message = counter.to_bytes(4, "little") + bytes(28)
        private_id = hmac.digest(
            identity_key, counter_message, hashlib.sha256
        )[:8]
        private_ids[private_id] = counter
    return private_ids


class TileResolver:
    """Resolve payloads against any number of registered Tiles.

    Each resolver prepares and owns candidates for its registered Tiles.
    Calls are synchronous; callers must serialize concurrent mutations.
    """

    def __init__(self, tiles: Iterable[Tile] = ()) -> None:
        self._tiles: dict[str, Tile] = {}
        self._private_ids: dict[str, list[bytes]] = {}
        self._index: dict[
            bytes, tuple[Tile, int] | dict[str, tuple[Tile, int]]
        ] = {}
        for tile in tiles:
            self.add(tile)

    @property
    def tiles(self) -> tuple[Tile, ...]:
        """Return a snapshot of Tiles in registration order."""
        return tuple(self._tiles.values())

    def add(self, tile: Tile) -> None:
        """Register a Tile and prepare its candidate IDs.

        Duplicate stable IDs raise ValueError. To change a key, remove
        the existing Tile and add its replacement.
        """
        if not isinstance(tile, Tile):
            raise TypeError("Expected a Tile")
        if tile.tile_id in self._tiles:
            raise ValueError("Tile ID is already registered")
        private_ids = _generate_private_ids(tile)
        self._tiles[tile.tile_id] = tile
        self._private_ids[tile.tile_id] = list(private_ids)
        for private_id, counter in private_ids.items():
            match = (tile, counter)
            owners = self._index.get(private_id)
            if owners is None:
                self._index[private_id] = match
            elif isinstance(owners, tuple):
                # Allocate an owners dictionary only for collisions.
                self._index[private_id] = {
                    owners[0].tile_id: owners,
                    tile.tile_id: match,
                }
            else:
                owners[tile.tile_id] = match

    def remove(self, tile_id: str) -> None:
        """Remove a Tile by hex ID; raise KeyError if it is unknown."""
        del self._tiles[tile_id]
        private_ids = self._private_ids.pop(tile_id)
        for private_id in private_ids:
            owners = self._index[private_id]
            if isinstance(owners, tuple):
                del self._index[private_id]
            else:
                del owners[tile_id]
                if len(owners) == 1:
                    self._index[private_id] = next(iter(owners.values()))

    def resolve(
        self, payload: bytes | bytearray | memoryview
    ) -> TileInfo | None:
        """Resolve FEED data without UUID or advertising headers.

        Return None for short, unsupported, unknown, or ambiguous data.
        Allow trailing bytes. Other input types raise TypeError.
        No state is updated by resolving a payload.
        """
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("Payload must be bytes, bytearray, or memoryview")
        payload = bytes(payload)
        if len(payload) < 10 or payload[0] != 2:
            return None
        match = self._index.get(payload[2:10])
        if not isinstance(match, tuple):
            return None
        tile, counter = match
        return TileInfo(
            tile=tile,
            counter=counter,
            version=payload[0],
            flags=payload[1],
        )
