"""Tile credentials and metadata decoded from a matching payload."""

import base64
from dataclasses import dataclass, field


def _to_bytes(value: str | bytes) -> bytes:
    """Accept raw bytes or decode hexadecimal or padded Base64 text."""
    if isinstance(value, bytes):
        return value
    if not isinstance(value, str):
        raise ValueError("Expected raw bytes, hexadecimal, or Base64 text")
    value = value.strip()
    if value.endswith("="):
        return base64.b64decode(value, validate=True)
    return bytes.fromhex(value)


@dataclass(frozen=True, slots=True)
class Tile:
    """Immutable Tile credentials stored as text.

    The ID is lowercase hex; the key is hex or padded Base64.
    """

    tile_id: str
    auth_key: str = field(repr=False)

    def __post_init__(self) -> None:
        tile_id = _to_bytes(self.tile_id)
        if len(tile_id) != 8 or tile_id.hex() != self.tile_id:
            raise ValueError("Tile ID must be 16 lowercase hexadecimal digits")
        if (
            not isinstance(self.auth_key, str)
            or len(_to_bytes(self.auth_key)) != 16
        ):
            raise ValueError("Auth key must decode to sixteen bytes")

@dataclass(frozen=True, slots=True)
class TileInfo:
    """A registered Tile and metadata from one matching FEED payload.

    A match does not establish freshness, proximity, or availability.
    Flags are exposed verbatim; their meaning is not interpreted here.
    """

    tile: Tile
    counter: int
    version: int
    flags: int
