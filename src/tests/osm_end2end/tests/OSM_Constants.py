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


import os
from typing import Dict, List, Optional

SERVICE_VARIANT_UNTAGGED = 'untagged'
SERVICE_VARIANT_TAGGED = 'tagged'
DEFAULT_SERVICE_VARIANT = SERVICE_VARIANT_TAGGED


def _connection_point(service_endpoint_id: str, vlan_id: Optional[int] = None) -> Dict:
    connection_point = {
        'service_endpoint_id': service_endpoint_id,
        'service_endpoint_encapsulation_type': 'none',
    }
    if vlan_id is not None:
        connection_point['service_endpoint_encapsulation_type'] = 'dot1q'
        connection_point['service_endpoint_encapsulation_info'] = {'vlan': vlan_id}
    return connection_point


def get_service_variant() -> str:
    service_variant = os.environ.get('OSM_SERVICE_VARIANT', DEFAULT_SERVICE_VARIANT)
    service_variant = str(service_variant).strip().lower()
    if service_variant not in {SERVICE_VARIANT_UNTAGGED, SERVICE_VARIANT_TAGGED}:
        msg = 'Unsupported OSM service variant: {:s}'.format(str(service_variant))
        raise ValueError(msg)
    return service_variant


def get_service_connection_points(service_variant: Optional[str] = None) -> List[Dict]:
    service_variant = get_service_variant() if service_variant is None else service_variant
    if service_variant == SERVICE_VARIANT_UNTAGGED:
        return [
            _connection_point('ep-untagged-1'),
            _connection_point('ep-untagged-2'),
        ]
    if service_variant == SERVICE_VARIANT_TAGGED:
        return [
            _connection_point('ep-tagged-1', vlan_id=125),
            _connection_point('ep-tagged-2', vlan_id=125),
        ]
    msg = 'Unsupported OSM service variant: {:s}'.format(str(service_variant))
    raise ValueError(msg)


# Ref: https://osm.etsi.org/wikipub/index.php/WIM
WIM_MAPPING = [
    {
        'device-id': 'dc1_untagged',              # pop_switch_dpid
        #'device_interface_id' : ??,               # pop_switch_port
        'service_endpoint_id': 'ep-untagged-1',    # wan_service_endpoint_id
        'service_mapping_info': {                  # wan_service_mapping_info, other extra info
            'bearer': {'bearer-reference': 'OSM-E2E:r1:Ethernet10'},
            'site-id': '1',
        },
        #'switch_dpid'         : ??,               # wan_switch_dpid
        #'switch_port'         : ??,               # wan_switch_port
        #'datacenter_id'       : ??,               # vim_account
    },
    {
        'device-id': 'dc2_untagged',              # pop_switch_dpid
        #'device_interface_id' : ??,               # pop_switch_port
        'service_endpoint_id': 'ep-untagged-2',    # wan_service_endpoint_id
        'service_mapping_info': {                  # wan_service_mapping_info, other extra info
            'bearer': {'bearer-reference': 'OSM-E2E:r3:Ethernet10'},
            'site-id': '2',
        },
        #'switch_dpid'         : ??,               # wan_switch_dpid
        #'switch_port'         : ??,               # wan_switch_port
        #'datacenter_id'       : ??,               # vim_account
    },
    {
        'device-id': 'dc3_tagged',                # pop_switch_dpid
        #'device_interface_id' : ??,               # pop_switch_port
        'service_endpoint_id': 'ep-tagged-1',      # wan_service_endpoint_id
        'service_mapping_info': {                  # wan_service_mapping_info, other extra info
            'bearer': {'bearer-reference': 'OSM-E2E:r1:Ethernet11'},
            'site-id': '1',
        },
        #'switch_dpid'         : ??,               # wan_switch_dpid
        #'switch_port'         : ??,               # wan_switch_port
        #'datacenter_id'       : ??,               # vim_account
    },
    {
        'device-id': 'dc4_tagged',                # pop_switch_dpid
        #'device_interface_id' : ??,               # pop_switch_port
        'service_endpoint_id': 'ep-tagged-2',      # wan_service_endpoint_id
        'service_mapping_info': {                  # wan_service_mapping_info, other extra info
            'bearer': {'bearer-reference': 'OSM-E2E:r3:Ethernet11'},
            'site-id': '2',
        },
        #'switch_dpid'         : ??,               # wan_switch_dpid
        #'switch_port'         : ??,               # wan_switch_port
        #'datacenter_id'       : ??,               # vim_account
    },
]

SERVICE_TYPE = 'ELINE'
SERVICE_VARIANT = get_service_variant()
SERVICE_CONNECTION_POINTS = get_service_connection_points(SERVICE_VARIANT)
