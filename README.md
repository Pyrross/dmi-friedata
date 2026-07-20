# DMI Frie Data Python Library

A lightweight, Pythonic client for the public DMI Frie Data APIs.

## Goals

- Provide a single, easy-to-use `DMIClient` entrypoint.
- Support the STAC-style binary download APIs and the JSON/OGC-style APIs.
- Keep the code well documented and small enough to extend incrementally.

## Installation

```bash
pip install .
```

## Quick start

```python
from dmi_frie_data import DMIClient

client = DMIClient()

# List radar collections
print(client.radar.list_collections())

# List forecast STAC items for a collection
items = client.forecast_stac.list_items(
    collection="harmonie_dini_sf",
    limit=5,
)
print(items)
```

## Status

This initial implementation provides the package scaffold, shared HTTP transport, and a public client facade.
The service modules are intentionally small and open for extension.
