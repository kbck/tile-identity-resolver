# Tile Identity Resolver

A dependency-free Python library for identifying registered Tile trackers from
version-2 FEED service data. Requires Python 3.10 or newer.

## Install

From the repository root (not yet published on PyPI):

```sh
python -m pip install .
```

## Usage

```python
from tile_identity_resolver import Tile, TileResolver

# Replace these example credentials with your Tile's ID and auth key.
tile = Tile(
    tile_id="0011223344556677",
    auth_key="AAECAwQFBgcICQoLDA0ODw==",
)
resolver = TileResolver([tile])

# Pass the raw service-data value for UUID 0000feed-0000-1000-8000-00805f9b34fb.
def handle_feed_payload(payload: bytes) -> None:
    info = resolver.resolve(payload)
    if info is not None:
        print(info.tile.tile_id, info.counter, info.version, info.flags)
```

Tile IDs are eight-byte lowercase hex strings. Auth keys are sixteen-byte hex
or padded Base64 strings. Invalid credentials raise `ValueError`.

## API

| API | Behavior |
| --- | --- |
| `TileResolver(tiles=())` | Register one or more Tiles |
| `resolver.add(tile)` | Register a Tile; duplicate IDs raise `ValueError` |
| `resolver.remove(tile_id)` | Remove a Tile; missing IDs raise `KeyError` |
| `resolver.tiles` | Immutable snapshot of registered Tiles |
| `resolver.resolve(payload)` | Return `TileInfo` for an unambiguous match, otherwise `None` |

`TileInfo` contains the registered `tile`, `counter`, `version`, and `flags`.
Remove and re-add a Tile to replace its key.

Registration precomputes private IDs and uses memory per Tile. In async apps,
prepare the resolver in a worker thread and serialize access during mutations.
The library resolves identities only; it does not track Bluetooth addresses or
presence, and a match does not prove freshness or proximity.

## Development

```sh
python -m pip install -e '.[dev]'
python tools/check_package.py
```

Runs tests, code checks, and package validation.

## Acknowledgements

Based on [Security and Privacy Analysis of Tile's Location Tracking Protocol](https://www.usenix.org/conference/usenixsecurity26/presentation/kumar-akshaya)
by Akshaya Kumar, Anna Raymaker, and Michael A. Specter (USENIX Security 2026).

Unofficial; not affiliated with Tile or Life360.
Licensed under the [MIT License](LICENSE).
