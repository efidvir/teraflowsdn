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

import libyang, logging, os, json, struct
from typing import Any
from common.proto.context_pb2 import TopologyDetails, Device, Link
from .NameMapping import NameMappings
from context.client.ContextClient import ContextClient
from common.tools.object_factory.Device import json_device_id
from common.proto.context_pb2 import DeviceId

LOGGER = logging.getLogger(__name__)

YANG_DIR = os.path.join(os.path.dirname(__file__), 'yang')
YANG_MODULES = [
    'ietf-network', 'ietf-network-topology', 'ietf-l3-unicast-topology',
    'ietf-te-types', 'ietf-te-packet-types',
    'ietf-te-topology', 'ietf-l3-te-topology', 'ietf-te-topology-packet',
    'ietf-l3-isis-topology', 'ietf-isis-sr-mpls'
]

class YangHandler:
    def __init__(self) -> None:
        self._yang_context = libyang.Context(YANG_DIR)
        for yang_module_name in YANG_MODULES:
            LOGGER.info('Loading module: {:s}'.format(str(yang_module_name)))
            self._yang_context.load_module(yang_module_name).feature_enable_all()

    def _load_te_data(self) -> dict:
        te_data_path = os.path.join(os.path.dirname(__file__), 'te_data.json')
        if not os.path.exists(te_data_path):
            LOGGER.warning('TE data file not found: {:s}'.format(te_data_path))
            return {}
        try:
            with open(te_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error('Failed to load TE data: {:s}'.format(str(e)))
            return {}

    def _to_te_bandwidth(self, val: Any) -> str:
        """
        Converts a bandwidth value to the format required by ietf-te-types (hex float).
        If the value is already a string starting with '0x', it is assumed to be correct.
        Otherwise, it is treated as a decimal (int/float/string) and converted.
        Enforces IEEE 754 single precision (float32) and cleans up trailing zeros to match YANG regex.
        """
        if isinstance(val, str) and val.strip().lower().startswith('0x'):
            return val

        try:
            # Enforce 32-bit float precision
            f_val = float(val)
            f32 = struct.unpack('f', struct.pack('f', f_val))[0]

            # Convert to hex
            hex_val = float(f32).hex()

            # Format: 0x1.xxxxxp+yy
            # Strip trailing zeros from the mantissa to satisfy the YANG regex (max 5+1 hex digits)
            if 'p' in hex_val:
                mantissa, exp = hex_val.split('p')
                mantissa = mantissa.rstrip('0')
                return f"{mantissa}p{exp}"
            return hex_val

        except ValueError:
            # Fallback to string if conversion fails, though it might error later in libyang
            return str(val)

    def get_te_link_key(self, link_name: str) -> str:
        """
        Resolves the te_data key for a link.
        Supports the new format: entries starting with 'link:' in te_data are matched
        against the link name directly or as a suffix.
        Falls back to simple substring matching for legacy entries.
        """
        te_data = self._load_te_data()
        direct_key = f'link:{link_name}'
        if direct_key in te_data:
            return direct_key
        for key in te_data:
            if not key.startswith('link:'):
                continue
            key_name = key[len('link:'):]
            if key_name == link_name or key_name in link_name or link_name in key_name:
                return key
        return link_name

    def _to_uri(self, value: str, type_name: str) -> str:
        if ':' in value and value.split(':')[0].lower() in ['urn', 'http', 'https', 'ftp', 'file']:
             return value
        return f'urn:tfs:{type_name}:{value}'

    def _to_isis_system_id(self, ip_address: str) -> str:
        try:
             parts = ip_address.split('.')
             if len(parts) != 4: return ip_address
             padded = ''.join([p.zfill(3) for p in parts])
             return '.'.join([padded[i:i+4] for i in range(0, 12, 4)])
        except:
             return ip_address

    def compose_network(self, te_topology_name: str, topology_details: TopologyDetails, include_te: bool = False, include_isis: bool = True) -> dict:
        networks = self._yang_context.create_data_path('/ietf-network:networks')
        network_id = self._to_uri(te_topology_name, 'network')
        network = networks.create_path(f'network[network-id="{network_id}"]')
        network.create_path('network-id', network_id)

        network_types = network.create_path('network-types')
        network_types.create_path('ietf-l3-unicast-topology:l3-unicast-topology')
        if include_isis:
            network_types.create_path('ietf-l3-isis-topology:isis-topology')

        name_mappings = NameMappings()

        for device in topology_details.devices:
            self.compose_node(device, name_mappings, network, include_isis)

        for link in topology_details.links:
            self.compose_link(link, name_mappings, network, include_te)

        result = json.loads(networks.print_mem('json'))
        if include_isis:
            te_data = self._load_te_data()
            self._inject_isis_tlv_extensions(result, topology_details, te_data)
        return result

    def _inject_isis_tlv_extensions(self, result: dict, topology_details: TopologyDetails, te_data: dict) -> None:
        """
        Post-processes the YANG JSON dict to inject a custom 'isis-tlv-areas' block
        into each node that has TLV data in te_data.json.
        This block is outside the YANG schema and provides per-area detail:
            loopback, area-address, pfx-sid-index.
        """
        device_tlvs = {}
        for dev in topology_details.devices:
            device_name = dev.name
            isis_data, use_tlvs = self._find_node_isis_data(te_data, device_name)
            if use_tlvs and isis_data:
                tlvs = isis_data.get('TLVs', {})
                if tlvs:
                    device_tlvs[device_name] = tlvs

        if not device_tlvs:
            return

        for network in result.get('ietf-network:networks', {}).get('network', []):
            for node in network.get('node', []):
                node_id = node.get('node-id', '')
                device_name = node_id.split('urn:tfs:node:')[-1] if 'urn:tfs:node:' in node_id else None
                if device_name and device_name in device_tlvs:
                    node['isis-tlv-areas'] = device_tlvs[device_name]


    def compose_node(self, dev: Device, name_mappings: NameMappings, network: Any, include_isis: bool = False) -> None:
        device_name = dev.name
        name_mappings.store_device_name(dev)

        node_id = self._to_uri(device_name, 'node')
        node = network.create_path(f'node[node-id="{node_id}"]')
        node.create_path('node-id', node_id)
        node_attributes = node.create_path('ietf-l3-unicast-topology:l3-node-attributes')
        node_attributes.create_path('name', device_name)

        context_client = ContextClient()
        device = context_client.GetDevice(DeviceId(**json_device_id(device_name)))

        for endpoint in device.device_endpoints:
            name_mappings.store_endpoint_name(dev, endpoint)

        self._process_device_config(device, node)

        if include_isis:
             self._add_isis_attributes(node_attributes, device_name)

    def _find_node_isis_data(self, te_data: dict, device_name: str):
        """
        Finds ISIS node attributes in te_data for a given device name.
        Supports two formats:

        Format A (old): keyed by device name
            "node:Phoenix-4": { "isis_node_attributes": { "node-name": ..., "router-id": [...], ... } }

        Format B (new): keyed by router-id
            "node:1.1.1.1": { "isis_node_attributes": { "node-name": "Phoenix-4", "TLVs": { "18201": {...}, ... } } }

        TLV format (B) takes priority over old format (A).
        Returns (isis_data, use_tlvs) where use_tlvs is True for Format B.
        """
        node_key_suffix = device_name
        for key, val in te_data.items():
            if not key.startswith('node:'):
                continue
            isis_data = val.get('isis_node_attributes', {})
            if 'TLVs' not in isis_data:
                continue
            node_name = isis_data.get('node-name', '')
            key_name = key[len('node:'):]
            if node_name == device_name or key_name == device_name:
                return isis_data, True

        node_key = f'node:{device_name}'
        if node_key in te_data:
            isis_data = te_data[node_key].get('isis_node_attributes', {})
            return isis_data, False

        return None, False

    def _add_isis_attributes(self, node_attributes: Any, device_name: str) -> None:
        te_data = self._load_te_data()
        isis_data, use_tlvs = self._find_node_isis_data(te_data, device_name)
        if not isis_data:
            return

        isis_attrs = node_attributes.create_path('ietf-l3-isis-topology:isis-node-attributes')

        if 'node-name' in isis_data:
            isis_attrs.create_path('node-name', isis_data['node-name'])

        if use_tlvs:
            tlvs = isis_data.get('TLVs', {})
            first_tlv = True
            added_routers = set()
            added_areas = set()
            for _tlv_key, tlv_val in tlvs.items():
                if 'loopback' in tlv_val:
                    rid = tlv_val['loopback']
                    if rid not in added_routers:
                        isis_attrs.create_path('router-id', rid)
                        added_routers.add(rid)
                if 'area-address' in tlv_val:
                    for area in tlv_val['area-address']:
                        if area not in added_areas:
                            isis_attrs.create_path('area-address', area)
                            added_areas.add(area)
                if first_tlv and 'pfx-sid-index' in tlv_val:
                    isis_attrs.create_path(
                        'ietf-isis-sr-mpls:segment-routing-mpls/pfx-sid-index',
                        tlv_val['pfx-sid-index']
                    )
                    first_tlv = False
        else:
            if 'router-id' in isis_data:
                for rid in isis_data['router-id']:
                    isis_attrs.create_path('router-id', rid)
            if 'area-address' in isis_data:
                for area in isis_data['area-address']:
                    isis_attrs.create_path('area-address', area)
            if 'pfx-sid-index' in isis_data:
                isis_attrs.create_path(
                    'ietf-isis-sr-mpls:segment-routing-mpls/pfx-sid-index',
                    isis_data['pfx-sid-index']
                )

    def _process_device_config(self, device: Device, node: Any) -> None:
        for config in device.device_config.config_rules:
            if config.WhichOneof('config_rule') != 'custom' or '/interface[' not in config.custom.resource_key:
                continue

            for endpoint in device.device_endpoints:
                endpoint_name = endpoint.name
                if f'/interface[{endpoint_name}]' in config.custom.resource_key or f'/interface[{endpoint_name}.' in config.custom.resource_key:
                    interface_name = config.custom.resource_key.split('interface[')[1].split(']')[0]
                    self._create_termination_point(node, interface_name, endpoint_name, config.custom.resource_value)

    def _create_termination_point(self, node: Any, interface_name: str, endpoint_name: str, resource_value: str) -> None:
        ip_addresses = self._extract_ip_addresses(json.loads(resource_value))
        if ip_addresses:
            tp_id = self._to_uri(interface_name, 'tp')
            tp = node.create_path(f'ietf-network-topology:termination-point[tp-id="{tp_id}"]')
            tp.create_path('tp-id', tp_id)
            tp_attributes = tp.create_path('ietf-l3-unicast-topology:l3-termination-point-attributes')

            for ip in ip_addresses:
                tp_attributes.create_path('ip-address', ip)
            tp_attributes.create_path('interface-name', endpoint_name)

    @staticmethod
    def _extract_ip_addresses(resource_value: dict) -> list:
        ip_addresses = []
        if 'address_ip' in resource_value:
            ip_addresses.append(resource_value['address_ip'])
        if 'address_ipv6' in resource_value:
            ip_addresses.append(resource_value['address_ipv6'])
        return ip_addresses

    def compose_link(self, link_specs: Link, name_mappings: NameMappings, network: Any, include_te: bool = False) -> None:
        link_name = link_specs.name
        link_id = self._to_uri(link_name, 'link')
        links = network.create_path(f'ietf-network-topology:link[link-id="{link_id}"]')
        links.create_path('link-id', link_id)

        self._create_link_endpoint(links, 'source', link_specs.link_endpoint_ids[0], name_mappings)
        self._create_link_endpoint(links, 'destination', link_specs.link_endpoint_ids[-1], name_mappings)

        if include_te:
            te_data = self._load_te_data()
            te_key = self.get_te_link_key(link_name)
            if te_key in te_data:
                te_info = te_data[te_key]

                te = links.create_path('ietf-te-topology:te')
                te_attrs = te.create_path('te-link-attributes')

                max_bw = te_info.get('max_bandwidth', te_info.get('bandwidth'))
                if max_bw:
                    te_attrs.create_path('max-link-bandwidth/te-bandwidth/generic', self._to_te_bandwidth(max_bw))

                unreserved_bw = te_info.get('unreserved_bandwidth')
                if unreserved_bw and isinstance(unreserved_bw, list) and len(unreserved_bw) == 8:
                     for i, val in enumerate(unreserved_bw):
                        ub = te_attrs.create_path(f'unreserved-bandwidth[priority="{i}"]')
                        ub.create_path('priority', i)
                        ub.create_path('te-bandwidth/generic', self._to_te_bandwidth(val))
                elif 'bandwidth' in te_info:
                    bw_val = self._to_te_bandwidth(te_info['bandwidth'])
                    for i in range(8):
                        ub = te_attrs.create_path(f'unreserved-bandwidth[priority="{i}"]')
                        ub.create_path('priority', i)
                        ub.create_path('te-bandwidth/generic', bw_val)

                if 'latency' in te_info:
                    te_attrs.create_path('ietf-te-topology-packet:performance-metrics-one-way/one-way-delay', int(te_info['latency']))


    def _create_link_endpoint(self, links: Any, endpoint_type: str, endpoint_id: Any, name_mappings: NameMappings) -> None:
        endpoint = links.create_path(endpoint_type)
        if endpoint_type == 'destination': endpoint_type = 'dest'

        node_name = name_mappings.get_device_name(endpoint_id.device_id)
        endpoint.create_path(f'{endpoint_type}-node', self._to_uri(node_name, 'node'))

        tp_name = name_mappings.get_endpoint_name(endpoint_id)
        endpoint.create_path(f'{endpoint_type}-tp', self._to_uri(tp_name, 'tp'))

    def destroy(self) -> None:
        self._yang_context.destroy()
