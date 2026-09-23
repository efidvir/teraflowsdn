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

"""
Telemetry callbacks for writing SIMAP telemetry to InfluxDB.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Union

from .....common.tools.rest_conf.server.restconf_server.Callbacks import _Callback
from .influxdb_client import SimapInfluxDBClient


LOGGER = logging.getLogger(__name__)


def _extract_telemetry_from_nested(data: Dict, link_id: str = None, node_id: str = None) -> Optional[Dict]:
    """
    Extract simap-telemetry data from various nested JSON structures returned by YangHandler.
    
    The YangHandler.update() returns different structures depending on context:
    - {"ietf-network:network": [{"network-id": "te", "ietf-network-topology:link": [{"link-id": "L1", "simap-telemetry:simap-telemetry": {...}}]}]}
    - {"ietf-network-topology:link": [{"link-id": "L1", "simap-telemetry:simap-telemetry": {...}}]}
    - {"simap-telemetry:simap-telemetry": {...}}
    - {"ietf-network:node": [...]} for nodes
    
    Args:
        data: The JSON dict to search
        link_id: If searching for link telemetry, the link ID to match
        node_id: If searching for node telemetry, the node ID to match
    
    Returns:
        The telemetry dict or None if not found
    """
    if not isinstance(data, dict):
        return None
    
    # Direct telemetry at top level
    if 'simap-telemetry:simap-telemetry' in data:
        return data['simap-telemetry:simap-telemetry']
    
    # Check for direct telemetry fields (already unwrapped)
    if 'bandwidth-utilization' in data or 'latency' in data or 'cpu-utilization' in data:
        return data
    
    # Search in ietf-network:network array
    if 'ietf-network:network' in data:
        for network in data['ietf-network:network']:
            if isinstance(network, dict):
                # Look for links
                if link_id and 'ietf-network-topology:link' in network:
                    for link in network['ietf-network-topology:link']:
                        if isinstance(link, dict) and link.get('link-id') == link_id:
                            if 'simap-telemetry:simap-telemetry' in link:
                                return link['simap-telemetry:simap-telemetry']
                # Look for nodes
                if node_id and 'node' in network:
                    for node in network['node']:
                        if isinstance(node, dict) and node.get('node-id') == node_id:
                            if 'simap-telemetry:simap-telemetry' in node:
                                return node['simap-telemetry:simap-telemetry']
    
    # Search in ietf-network-topology:link array
    if 'ietf-network-topology:link' in data:
        for link in data['ietf-network-topology:link']:
            if isinstance(link, dict):
                if link_id is None or link.get('link-id') == link_id:
                    if 'simap-telemetry:simap-telemetry' in link:
                        return link['simap-telemetry:simap-telemetry']
    
    # Search in ietf-network:node or node array
    for node_key in ['ietf-network:node', 'node']:
        if node_key in data:
            for node in data[node_key]:
                if isinstance(node, dict):
                    if node_id is None or node.get('node-id') == node_id:
                        if 'simap-telemetry:simap-telemetry' in node:
                            return node['simap-telemetry:simap-telemetry']
    
    return None


class CallbackOnLinkTelemetry(_Callback):
    """
    Callback triggered when link telemetry data is updated via RESTCONF.
    Writes telemetry data to InfluxDB.
    """

    # Pattern matches:
    # /restconf/data/ietf-network:networks/network=<network_id>/ietf-network-topology:link=<link_id>
    PATTERN = (
        r'/restconf/data/ietf-network:networks'
        r'/network=(?P<network_id>[^/]+)'
        r'/ietf-network-topology:link=(?P<link_id>[^/]+)'
    )

    def __init__(self, influx_client: SimapInfluxDBClient) -> None:
        """
        Initialize the callback with an InfluxDB client.

        Args:
            influx_client: SimapInfluxDBClient instance for writing telemetry
        """
        super().__init__(self.PATTERN)
        self._influx_client = influx_client

    def execute_data_update(
        self,
        match: re.Match,
        path: str,
        old_data: Optional[Union[Dict, str]],
        new_data: Optional[Union[Dict, str]]
    ) -> bool:
        """
        Execute the callback to write link telemetry to InfluxDB.

        Args:
            match: Regex match object containing network_id and link_id
            path: Original RESTCONF path
            old_data: Previous telemetry data (unused)
            new_data: New telemetry data to write (can be dict or JSON string)

        Returns:
            True to continue executing other callbacks
        """
        if new_data is None:
            LOGGER.debug("Link telemetry deletion, skipping InfluxDB write")
            return True

        # Handle case where new_data is a JSON string instead of a dict
        if isinstance(new_data, str):
            try:
                new_data = json.loads(new_data)
            except json.JSONDecodeError:
                LOGGER.error("Failed to parse new_data as JSON: %s", new_data)
                return True

        network_id = match.group('network_id')
        link_id = match.group('link_id')

        # Extract telemetry fields from nested JSON structure
        # YangHandler returns various nested formats depending on context
        telemetry = _extract_telemetry_from_nested(new_data, link_id=link_id)
        if telemetry is None:
            LOGGER.warning(
                "Could not extract telemetry from data for link=%s: %s",
                link_id, new_data
            )
            return True

        bandwidth_utilization = telemetry.get('bandwidth-utilization', 0)
        latency = telemetry.get('latency', 0)
        related_service_ids = telemetry.get('related-service-ids', None)

        LOGGER.info(
            "Link telemetry callback: network=%s, link=%s, bw=%s, lat=%s",
            network_id, link_id, bandwidth_utilization, latency
        )

        self._influx_client.write_link_telemetry(
            network_id=network_id,
            link_id=link_id,
            bandwidth_utilization=float(bandwidth_utilization),
            latency=float(latency),
            related_service_ids=related_service_ids
        )

        return True  # Continue to other callbacks


class CallbackOnNodeTelemetry(_Callback):
    """
    Callback triggered when node telemetry data is updated via RESTCONF.
    Writes telemetry data to InfluxDB.
    """

    # Pattern matches:
    # /restconf/data/ietf-network:networks/network=<network_id>/node=<node_id>
    PATTERN = (
        r'/restconf/data/ietf-network:networks'
        r'/network=(?P<network_id>[^/]+)'
        r'/node=(?P<node_id>[^/]+)'
    )

    def __init__(self, influx_client: SimapInfluxDBClient) -> None:
        """
        Initialize the callback with an InfluxDB client.

        Args:
            influx_client: SimapInfluxDBClient instance for writing telemetry
        """
        super().__init__(self.PATTERN)
        self._influx_client = influx_client

    def execute_data_update(
        self,
        match: re.Match,
        path: str,
        old_data: Optional[Union[Dict, str]],
        new_data: Optional[Union[Dict, str]]
    ) -> bool:
        """
        Execute the callback to write node telemetry to InfluxDB.

        Args:
            match: Regex match object containing network_id and node_id
            path: Original RESTCONF path
            old_data: Previous telemetry data (unused)
            new_data: New telemetry data to write (can be dict or JSON string)

        Returns:
            True to continue executing other callbacks
        """
        if new_data is None:
            LOGGER.debug("Node telemetry deletion, skipping InfluxDB write")
            return True

        # Handle case where new_data is a JSON string instead of a dict
        if isinstance(new_data, str):
            try:
                new_data = json.loads(new_data)
            except json.JSONDecodeError:
                LOGGER.error("Failed to parse new_data as JSON: %s", new_data)
                return True

        network_id = match.group('network_id')
        node_id = match.group('node_id')

        # Extract telemetry fields from nested JSON structure
        # YangHandler returns various nested formats depending on context
        telemetry = _extract_telemetry_from_nested(new_data, node_id=node_id)
        if telemetry is None:
            LOGGER.warning(
                "Could not extract telemetry from data for node=%s: %s",
                node_id, new_data
            )
            return True

        cpu_utilization = telemetry.get('cpu-utilization', 0)
        related_service_ids = telemetry.get('related-service-ids', None)

        LOGGER.info(
            "Node telemetry callback: network=%s, node=%s, cpu=%s",
            network_id, node_id, cpu_utilization
        )

        self._influx_client.write_node_telemetry(
            network_id=network_id,
            node_id=node_id,
            cpu_utilization=float(cpu_utilization),
            related_service_ids=related_service_ids
        )

        return True  # Continue to other callbacks
