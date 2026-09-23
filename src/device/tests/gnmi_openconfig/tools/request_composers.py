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

from typing import Dict, Tuple

def interface(if_name, sif_index, ipv4_address=None, ipv4_prefix=None, enabled=True, vlan_id=None) -> Tuple[str, Dict]:
    str_path = '/interface[{:s}]'.format(if_name)
    str_data = {
        'name': if_name,
        'enabled': enabled,
        'index': sif_index,
        'sub_if_index': sif_index,
        'sub_if_enabled': enabled,
        'sub_if_ipv4_enabled': enabled,
        'sub_if_ipv4_address': ipv4_address,
        'sub_if_ipv4_prefix': ipv4_prefix,
        'address_ip': ipv4_address,
        'address_prefix': ipv4_prefix,
        'vlan_id': vlan_id,
    }
    return str_path, str_data

def network_instance(ni_name, ni_type) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]'.format(ni_name)
    str_data = {
        'name': ni_name, 'type': ni_type
    }
    return str_path, str_data

def network_instance_static_route(ni_name, prefix, next_hop_index, next_hop, metric=1) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/static_route[{:s}]'.format(ni_name, prefix)
    str_data = {
        'name': ni_name, 'prefix': prefix, 'next_hop_index': next_hop_index, 'next_hop': next_hop, 'metric': metric
    }
    return str_path, str_data

def network_instance_interface(ni_name, if_name, sif_index) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/interface[{:s}.{:d}]'.format(ni_name, if_name, sif_index)
    str_data = {
        'name': ni_name, 'if_name': if_name, 'sif_index': sif_index
    }
    return str_path, str_data

def mpls_global(ldp_router_id: str, hello_interval: int = None, hello_holdtime: int = None) -> Tuple[str, Dict]:
    str_path = '/mpls'
    str_data = {
        'ldp': {
            'lsr_id': ldp_router_id,
            'hello_interval': hello_interval,
            'hello_holdtime': hello_holdtime,
        }
    }
    return str_path, str_data

def mpls_ldp_interface(if_name: str, hello_interval: int = None, hello_holdtime: int = None) -> Tuple[str, Dict]:
    str_path = '/mpls/interface[{:s}]'.format(if_name)
    str_data = {
        'interface': if_name,
        'hello_interval': hello_interval,
        'hello_holdtime': hello_holdtime,
    }
    return str_path, str_data

def connection_point(ni_name: str, cp_id: str) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/connection_point[{:s}]'.format(ni_name, cp_id)
    str_data = {'name': ni_name, 'connection_point_id': cp_id}
    return str_path, str_data

def connection_point_endpoint_local(
    ni_name: str, cp_id: str, ep_id: str, if_name: str, subif: int = 0, precedence: int = 0, site_id: int = None
) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/connection_point[{:s}]/endpoint[{:s}]'.format(ni_name, cp_id, ep_id)
    str_data = {
        'name': ni_name,
        'connection_point_id': cp_id,
        'endpoint_id': ep_id,
        'type': 'LOCAL',
        'precedence': precedence,
        'interface': if_name,
        'subinterface': subif,
        'site_id': site_id,
    }
    return str_path, str_data

def connection_point_endpoint_remote(
    ni_name: str, cp_id: str, ep_id: str, remote_system: str, vc_id: int,
    precedence: int = 0, site_id: int = None
) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/connection_point[{:s}]/endpoint[{:s}]'.format(ni_name, cp_id, ep_id)
    str_data = {
        'name': ni_name,
        'connection_point_id': cp_id,
        'endpoint_id': ep_id,
        'type': 'REMOTE',
        'precedence': precedence,
        'remote_system': remote_system,
        'virtual_circuit_id': vc_id,
        'site_id': site_id,
    }
    return str_path, str_data

def vlan(ni_name: str, vlan_id: int, vlan_name: str = None) -> Tuple[str, Dict]:
    str_path = '/network_instance[{:s}]/vlan[{:d}]'.format(ni_name, vlan_id)
    str_data = {
        'name': ni_name,
        'vlan_id': vlan_id,
        'vlan_name': vlan_name,
    }
    return str_path, str_data
