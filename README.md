# Tile Identity Resolver

A dependency-free Python library that identifies registered Tile trackers from
raw FEED service-data payloads. Supports multiple Tiles and version-2 private IDs.

## Install

Requires Python 3.10 or newer. From the repository root:

```sh
python -m pip install .
```

For an editable development installation:

```sh
python -m pip install -e '.[dev]'
```

The distribution name is `tile-identity-resolver`; imports use
`tile_identity_resolver`. The package is not yet published on PyPI.

## Usage

```python
from tile_identity_resolver import Tile, TileResolver

# Illustrative credentials; replace with the IDs and keys for your own Tiles.
keys = Tile(
    tile_id="0011223344556677",
    auth_key="AAECAwQFBgcICQoLDA0ODw==",
)
wallet = Tile(
    tile_id="8899aabbccddeeff",
    auth_key="Dw4NDAsKCQgHBgUEAwIBAA==",
)
resolver = TileResolver([keys, wallet])

# Your scanner supplies the service-data value for UUID
# 0000feed-0000-1000-8000-00805f9b34fb. Exclude the UUID and AD headers.
def handle_feed_payload(payload: bytes) -> None:
    info = resolver.resolve(payload)
    if info is not None:
        print(info.tile.tile_id, info.counter, info.version, info.flags)
        if info.tile is keys:
            print("Identified the keys Tile")
```

The library returns a frozen `TileInfo` containing the exact registered `Tile`
object and metadata for that payload. It never writes received metadata into the
shared Tile, so later calls cannot change earlier results.

## API

| API | Behavior |
| --- | --- |
| `Tile(tile_id, auth_key)` | Accept a lowercase hex ID and a hex or padded Base64 key; invalid credentials raise `ValueError` |
| `TileResolver(tiles=())` | Register the supplied Tiles and build the resolver's candidate index |
| `resolver.add(tile)` | Prepare candidate IDs and register a Tile; duplicate stable IDs raise `ValueError` |
| `resolver.remove(tile_id)` | Remove by exact registered ID string; missing IDs raise `KeyError` |
| `resolver.tiles` | Immutable snapshot of registered Tiles |
| `resolver.resolve(payload)` | Return `TileInfo` for one unambiguous match, otherwise `None` |

`TileInfo` exposes `tile`, `counter`, `version`, and `flags`. Flags are returned
as an integer without interpretation. Payloads can be `bytes`, `bytearray`, or
`memoryview`; incorrect input types raise `TypeError`. Short payloads,
unsupported versions, unknown IDs, and matches shared by multiple Tiles return
`None`. Extra trailing bytes are accepted.

`Tile` is a frozen dataclass storing `tile_id` as a lowercase hexadecimal string
and `auth_key` as hexadecimal or padded Base64 text. The ID represents eight
bytes and the key sixteen bytes. The constructor validates them without changing
the stored strings.

Pass strings directly to `Tile(tile_id, auth_key)`. Key strings ending in `=`
are decoded as Base64 for validation; other key strings are decoded as hex.
For display, use `tile.tile_id` directly; `tile.auth_key` stays out of repr.

Constructing a `Tile` only validates its credentials. Registration decodes the
strings to bytes and precomputes its 8,640 private IDs in the resolver.
Each resolver owns its prepared IDs; removing a Tile discards them.
`resolve()` uses a dictionary lookup without repeating preparation.

In async applications, construct and populate a resolver in a worker thread
before using it on your event loop. Adding new credentials also performs
synchronous preparation. Serialize access while mutating a resolver across
threads. Memory use grows with the number of registered Tiles.

Remove and re-add a Tile to replace its key. Resolving does not track addresses,
RSSI, time, availability, or connections. A valid payload may be replayed, so a
match does not prove freshness or physical proximity. Credentials are omitted
from object repr but remain accessible through `Tile.auth_key`.

## Protocol Scope

Version-2 FEED service data starts with one version byte (`2`), one flags byte,
and an eight-byte private ID. Identity derivation uses:

```text
identity_key = HMAC-SHA256(auth_key, tile_id || "identity" || 16 zero bytes)[:16]
private_id = HMAC-SHA256(identity_key, LE32(counter) || 28 zero bytes)[:8]
```

Counters 0 through 8639 are indexed. This scheme has been checked against
captures from one owned Tile; other hardware, firmware, full-cycle behavior,
and key resets need validation. This is Tile-specific identity resolution,
not Bluetooth RPA resolution using an IRK.

## Development

```sh
python -m pytest -q
python -m ruff check src tests
python -m build
```

This project is unofficial and is not affiliated with Tile or Life360.

## Acknowledgements

This implementation is based on the protocol analysis in
[*Security and Privacy Analysis of Tile's Location Tracking Protocol*](https://www.usenix.org/conference/usenixsecurity26/presentation/kumar-akshaya)
by Akshaya Kumar, Anna Raymaker, and Michael A. Specter, published at
USENIX Security 2026. Thanks to the authors for documenting Tile’s protocol and making their research publicly available.

## License

Licensed under the [MIT License](LICENSE).
