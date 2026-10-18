"""Test protocol derivation, matching, and registration lifecycle."""

import base64
import hashlib
import hmac
from dataclasses import FrozenInstanceError

import pytest

from tile_identity_resolver import Tile, TileInfo, TileResolver
from tile_identity_resolver import resolver as implementation

TILE_ID = "0011223344556677"
OTHER_ID = "8899aabbccddeeff"
KEY = base64.b64encode(bytes(range(16))).decode()
OTHER_KEY = base64.b64encode(bytes(reversed(range(16)))).decode()


def payload_for(tile: Tile, counter: int, flags: int = 0) -> bytes:
    """Construct a payload using explicit protocol message layouts."""
    key = base64.b64decode(tile.auth_key)
    seed = hmac.new(
        key,
        bytes.fromhex(tile.tile_id) + b"identity" + bytes(16),
        hashlib.sha256,
    ).digest()[:16]
    identity = hmac.new(
        seed, counter.to_bytes(4, "little") + bytes(28), hashlib.sha256
    ).digest()[:8]
    return bytes([2, flags]) + identity


@pytest.fixture
def tiles():
    return (
        Tile(TILE_ID, KEY),
        Tile(OTHER_ID, OTHER_KEY),
    )


@pytest.mark.parametrize(
    "tile_id",
    [
        None, bytes(8), bytearray(8), "", "xyz", "00", "00" * 9,
        OTHER_ID.upper(), " " + TILE_ID,
    ],
)
def test_invalid_tile_id(tile_id):
    with pytest.raises(ValueError):
        Tile(tile_id, KEY)


@pytest.mark.parametrize(
    "auth_key",
    [
        None, bytes(16), bytearray(16), "bad-key", "", "\u2603", "====",
        base64.b64encode(bytes(15)).decode(),
        base64.b64encode(bytes(17)).decode(),
    ],
)
def test_invalid_key_is_not_echoed(auth_key):
    with pytest.raises(ValueError) as caught:
        Tile(TILE_ID, auth_key)
    if isinstance(auth_key, str) and auth_key:
        assert auth_key not in str(caught.value)


@pytest.mark.parametrize(
    "auth_key",
    [KEY, " " + KEY + " ", KEY[:-3] + "x==", bytes(range(16)).hex()],
)
def test_supported_key_formats(auth_key):
    tile = Tile(TILE_ID, auth_key)
    assert tile.auth_key == auth_key
    reference = Tile(TILE_ID, KEY)
    result = TileResolver([tile]).resolve(payload_for(reference, 1))
    assert result == TileInfo(tile, 1, 2, 0)


def test_multiple_tiles_return_registered_objects_and_metadata(tiles):
    keys, wallet = tiles
    resolver = TileResolver(tiles)
    assert resolver.tiles == tiles
    keys_info = resolver.resolve(payload_for(keys, 1093, flags=255))
    wallet_info = resolver.resolve(payload_for(wallet, 256, flags=7))
    assert keys_info == TileInfo(keys, 1093, 2, 255)
    assert wallet_info == TileInfo(wallet, 256, 2, 7)
    assert keys_info.tile is keys
    assert wallet_info.tile is wallet


def test_results_are_immutable_snapshots(tiles):
    tile = tiles[0]
    resolver = TileResolver([tile])
    info = resolver.resolve(payload_for(tile, 1))
    resolver.resolve(payload_for(tile, 2))
    assert info.counter == 1
    with pytest.raises(FrozenInstanceError):
        info.counter = 5


def test_tiles_are_immutable(tiles):
    tile = tiles[0]
    with pytest.raises(FrozenInstanceError):
        tile.auth_key = OTHER_KEY
    with pytest.raises(FrozenInstanceError):
        tile.tile_id = OTHER_ID


def test_auth_key_is_hidden_from_repr(tiles):
    tile = tiles[0]
    assert KEY not in repr(tile)
    assert KEY not in repr(TileInfo(tile, 1, 2, 0))


@pytest.mark.parametrize("counter", [0, 1, 255, 256, 8639, 8640])
def test_counter_boundaries(tiles, counter):
    tile = tiles[0]
    result = TileResolver([tile]).resolve(payload_for(tile, counter))
    if counter == 8640:
        assert result is None
    else:
        assert result.counter == counter


@pytest.mark.parametrize("factory", [bytes, bytearray, memoryview])
def test_bytes_like_input_and_trailing_data(tiles, factory):
    tile = tiles[0]
    payload = factory(payload_for(tile, 1) + b"extra")
    result = TileResolver([tile]).resolve(payload)
    assert result == TileInfo(tile, 1, 2, 0)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x02",
        b"\x02\xff1234567",
        b"\x01\x0012345678",
        b"\x02\x00unknown!",
    ],
)
def test_malformed_unsupported_and_unknown_payloads(tiles, payload):
    assert TileResolver(tiles).resolve(payload) is None


@pytest.mark.parametrize("payload", [None, "0200", 123, [2, 0]])
def test_non_bytes_input_raises_type_error(payload):
    with pytest.raises(TypeError, match="Payload must be"):
        TileResolver().resolve(payload)


def test_duplicate_ids(tiles):
    resolver = TileResolver(tiles)
    with pytest.raises(ValueError, match="already registered"):
        resolver.add(Tile(OTHER_ID, KEY))
    assert resolver.tiles == tiles
    with pytest.raises(TypeError, match="Expected a Tile"):
        resolver.add(TILE_ID)
    with pytest.raises(ValueError, match="already registered"):
        TileResolver([tiles[0], tiles[0]])


def test_remove_and_replace_key(tiles):
    tile, other = tiles
    resolver = TileResolver(tiles)
    old_payload = payload_for(tile, 1)
    resolver.remove(TILE_ID)
    assert resolver.resolve(old_payload) is None
    assert resolver.resolve(payload_for(other, 1)).tile is other
    replacement = Tile(TILE_ID, OTHER_KEY)
    resolver.add(replacement)
    assert resolver.resolve(old_payload) is None
    assert resolver.resolve(payload_for(replacement, 1)).tile is replacement
    resolver.remove(OTHER_ID)
    resolver.remove(TILE_ID)
    assert resolver.tiles == ()
    assert resolver.resolve(payload_for(replacement, 1)) is None
    with pytest.raises(KeyError):
        resolver.remove(TILE_ID)
    with pytest.raises(KeyError):
        resolver.remove("invalid")


def test_collisions_fail_closed_and_removal_restores_unique_match(monkeypatch):
    def shared_candidates(tile):
        counter = 1 if tile.tile_id == TILE_ID else 2
        return {b"sharedid": counter}

    monkeypatch.setattr(
        implementation, "_generate_private_ids", shared_candidates
    )
    keys = Tile(TILE_ID, KEY)
    wallet = Tile(OTHER_ID, OTHER_KEY)
    resolver = TileResolver([keys])
    payload = b"\x02\xffsharedid"
    assert resolver.resolve(payload) == TileInfo(keys, 1, 2, 255)
    resolver.add(wallet)
    assert resolver.resolve(payload) is None
    resolver.remove(TILE_ID)
    assert resolver.resolve(payload) == TileInfo(wallet, 2, 2, 255)
    resolver.remove(OTHER_ID)
    assert resolver.resolve(payload) is None


def test_tile_construction_does_not_prepare_candidates(monkeypatch):
    def fail(tile):
        pytest.fail("Tile construction must not generate private IDs")

    monkeypatch.setattr(implementation, "_generate_private_ids", fail)
    tile = Tile(TILE_ID, KEY)
    assert tile.tile_id == TILE_ID


def test_resolve_does_not_repeat_preparation(tiles, monkeypatch):
    tile = tiles[0]
    resolver = TileResolver([tile])

    def fail(tile):
        pytest.fail("Resolving should use prepared IDs")

    monkeypatch.setattr(implementation, "_generate_private_ids", fail)
    assert resolver.resolve(payload_for(tile, 1)) == TileInfo(tile, 1, 2, 0)


def test_preparation_failure_leaves_registration_unchanged(tiles, monkeypatch):
    tile, other = tiles
    resolver = TileResolver([tile])

    def fail(tile):
        raise RuntimeError("Preparation failed")

    monkeypatch.setattr(implementation, "_generate_private_ids", fail)
    with pytest.raises(RuntimeError, match="Preparation failed"):
        resolver.add(other)
    assert resolver.tiles == (tile,)
    assert resolver.resolve(payload_for(tile, 1)).tile is tile
    assert resolver.resolve(payload_for(other, 1)) is None
