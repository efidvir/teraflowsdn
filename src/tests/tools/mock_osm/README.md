# Mock OSM (tests.tools.mock_osm)

This package provides a small interactive shell for testing WIM connectivity
through the MockOSM connector.

## Run

```bash
python -m tests.tools.mock_osm example_connection.json example_mapping.json
```

## Commands

- `create <service_type> <endpoint...> [vlan <vlan-id>]`
  - `ELINE` requires exactly 2 endpoints
  - `ELAN` requires at least 2 endpoints
- `status`
- `delete`
- `exit`

Endpoints are provided as a list of strings (service endpoint IDs), for example:

```text
(mock-osm) create ELINE ep-R1-1/2 ep-R4-1/3
```

Optional VLAN tagging for all endpoints:

```text
(mock-osm) create ELINE ep-R1-1/2 ep-R4-1/3 vlan 1234
```

## Example configs

See:
- `src/tests/tools/mock_osm/example_connection.json`
- `src/tests/tools/mock_osm/example_mapping.json`

The mapping file is a JSON list where each entry includes the
`service_endpoint_id`, `device-id`, and `service_mapping_info` with `bearer`
and `site-id`.
