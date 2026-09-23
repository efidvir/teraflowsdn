# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import cmd
import json
import logging
import shlex
import sys
from typing import Any, Dict, List, Tuple

from .MockOSM import MockOSM

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

SUPPORTED_SERVICE_TYPES = {"ELINE", "ELAN"}


def _load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _first_present(data: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _parse_connection_config(config: Dict[str, Any]) -> Tuple[str, str, str]:
    if not isinstance(config, dict):
        raise ValueError("Connection config must be a JSON object.")

    wim_ip = _first_present(config, ("wim_ip", "ip", "host", "address"))
    wim_port = _first_present(config, ("wim_port", "port"))
    wim_user = _first_present(config, ("wim_user", "user", "username"))
    wim_pass = _first_present(config, ("wim_pass", "wim_password", "pass", "password"))

    missing = []
    if not wim_ip:
        missing.append("wim_ip")
    if wim_port is None:
        missing.append("wim_port")
    if not wim_user:
        missing.append("wim_user")
    if wim_pass is None:
        missing.append("wim_pass")

    if missing:
        raise ValueError(
            "Connection config missing required fields: {}".format(", ".join(missing))
        )

    try:
        wim_port = int(wim_port)
    except (TypeError, ValueError) as exc:
        raise ValueError("wim_port must be an integer") from exc

    wim_url = "http://{:s}:{:d}".format(str(wim_ip), wim_port)
    return wim_url, str(wim_user), str(wim_pass)


def _parse_mapping_config(mapping: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(mapping, list):
        raise ValueError("Mapping config must be a JSON list.")

    mapping_by_id = {}
    for index, entry in enumerate(mapping):
        if not isinstance(entry, dict):
            raise ValueError("Mapping entry {:d} must be a JSON object".format(index))
        service_endpoint_id = entry.get("service_endpoint_id")
        if not service_endpoint_id or not isinstance(service_endpoint_id, str):
            raise ValueError(
                "Mapping entry {:d} missing service_endpoint_id".format(index)
            )
        if service_endpoint_id in mapping_by_id:
            LOGGER.warning(
                "Duplicate service_endpoint_id in mapping: %s", service_endpoint_id
            )
        mapping_by_id[service_endpoint_id] = entry

    return mapping_by_id


class MockOSMShell(cmd.Cmd):
    intro = "Welcome to the MockOSM shell.\nType help or ? to list commands.\n"
    prompt = "(mock-osm) "

    def __init__(self, mock_osm: MockOSM, mapping_by_id: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.mock_osm = mock_osm
        self.mapping_by_id = mapping_by_id

    def do_create(self, arg: str) -> None:
        "Create a connectivity service: create <service_type> <endpoint...> [vlan <vlan-id>]"
        try:
            service_type, endpoints = self._parse_create_args(arg)
            service_uuid = self.mock_osm.create_connectivity_service(
                service_type, endpoints
            )
            print("Service {:s} created".format(service_uuid))
        except Exception as exc:
            print("Error: {:s}".format(str(exc)))

    def do_status(self, arg: str) -> None:
        "Retrieve status of services"
        service_uuids = list(self.mock_osm.conn_info.keys())
        for service_uuid in service_uuids:
            status = self.mock_osm.get_connectivity_service_status(service_uuid)
            print("Status of Service {:s} is {:s}".format(service_uuid, str(status)))

    def do_delete(self, arg: str) -> None:
        "Delete all services"
        service_uuids = list(self.mock_osm.conn_info.keys())
        for service_uuid in service_uuids:
            self.mock_osm.delete_connectivity_service(service_uuid)
            print("Service {:s} deleted".format(service_uuid))

    def do_exit(self, arg: str) -> bool:
        "Exit MockOSM"
        print("Bye!")
        return True

    def _parse_create_args(self, arg: str) -> Tuple[str, List[Dict[str, Any]]]:
        tokens = shlex.split(arg)
        if len(tokens) < 2:
            raise ValueError(
                "Usage: create <service_type> <endpoint...> [vlan <vlan-id>]"
            )

        service_type = tokens[0]
        endpoints_tokens = tokens[1:]
        vlan_id = None
        if "vlan" in endpoints_tokens:
            vlan_index = endpoints_tokens.index("vlan")
            if vlan_index == len(endpoints_tokens) - 1:
                raise ValueError("vlan requires <vlan-id>")
            if vlan_index + 2 != len(endpoints_tokens):
                raise ValueError("vlan must be the last argument")
            vlan_token = endpoints_tokens[vlan_index + 1]
            try:
                vlan_id = int(vlan_token)
            except (TypeError, ValueError) as exc:
                raise ValueError("vlan-id must be an integer") from exc
            endpoints_tokens = endpoints_tokens[:vlan_index]

        endpoints = self._load_endpoints(endpoints_tokens)
        self._validate_service_request(service_type, endpoints)
        connection_points = [
            {
                "service_endpoint_id": endpoint,
                "service_endpoint_encapsulation_type": (
                    "dot1q" if vlan_id is not None else "none"
                ),
                **(
                    {"service_endpoint_encapsulation_info": {"vlan": vlan_id}}
                    if vlan_id is not None
                    else {}
                ),
            }
            for endpoint in endpoints
        ]
        return service_type, connection_points

    def _load_endpoints(self, tokens: List[str]) -> List[str]:
        endpoints = []
        for token in tokens:
            if "," in token:
                endpoints.extend([item for item in token.split(",") if item])
            else:
                endpoints.append(token)
        return endpoints

    def _validate_service_request(
        self, service_type: str, endpoints: List[str]
    ) -> None:
        if not isinstance(service_type, str) or not service_type:
            raise ValueError("Service type must be a non-empty string.")

        if service_type not in SUPPORTED_SERVICE_TYPES:
            raise ValueError(
                "Unsupported service type. Supported: {}".format(
                    ", ".join(sorted(SUPPORTED_SERVICE_TYPES))
                )
            )

        if not endpoints:
            raise ValueError("Endpoints list must not be empty.")

        if service_type == "ELINE" and len(endpoints) != 2:
            raise ValueError("ELINE requires exactly 2 endpoints.")

        if service_type == "ELAN" and len(endpoints) < 2:
            raise ValueError("ELAN requires at least 2 endpoints.")

        for index, endpoint in enumerate(endpoints):
            if not isinstance(endpoint, str) or not endpoint:
                raise ValueError(
                    "Endpoint {:d} must be a non-empty string".format(index)
                )
            if endpoint not in self.mapping_by_id:
                raise ValueError(
                    "Endpoint {:s} not found in WIM port mapping".format(endpoint)
                )


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MockOSM shell")
    parser.add_argument(
        "connection_config",
        help="JSON with WIM IP, port, user, and password",
    )
    parser.add_argument(
        "mapping_config",
        help="JSON with pre-generated WIM port mapping",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)

    try:
        connection_config = _load_json_file(args.connection_config)
        mapping_config = _load_json_file(args.mapping_config)
        wim_url, wim_user, wim_pass = _parse_connection_config(connection_config)
        mapping_by_id = _parse_mapping_config(mapping_config)
    except Exception as exc:
        print("Configuration error: {:s}".format(str(exc)), file=sys.stderr)
        return 2

    mock_osm = MockOSM(wim_url, mapping_config, wim_user, wim_pass)
    MockOSMShell(mock_osm, mapping_by_id).cmdloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
