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

import json, libyang, logging
from typing import Any, Dict, List, Tuple
from ._Handler import _Handler
from .Tools import get_bool, get_int, get_str
from .YangHandler import YangHandler

LOGGER = logging.getLogger(__name__)

MIN_MTU = 68
EOS_TAGGED_L3_REPLACE_FIELD = '_eos_tagged_l3_replace'


def _normalize_interface_type(if_type: str, sif_index: int) -> str:
    if if_type == 'l3ipvlan' and sif_index is not None:
        return 'iana-if-type:ethernetCsmacd'
    if ':' not in if_type:
        return 'iana-if-type:{:s}'.format(if_type)
    return if_type

class InterfaceHandler(_Handler):
    def get_resource_key(self) -> str: return '/interface/subinterface'
    def get_path(self) -> str: return '/openconfig-interfaces:interfaces'

    @staticmethod
    def _create_subinterface(
        yang_sifs: libyang.DContainer, sif_index: int, enabled: bool = None,
        vlan_id: int = None, address_ip: str = None, address_prefix: int = None
    ) -> libyang.DContainer:
        yang_sif_path = 'subinterface[index="{:d}"]'.format(sif_index)
        yang_sif: libyang.DContainer = yang_sifs.create_path(yang_sif_path)
        yang_sif.create_path('config/index', sif_index)
        if enabled is not None:
            yang_sif.create_path('config/enabled', enabled)

        if vlan_id is not None:
            yang_subif_vlan : libyang.DContainer = yang_sif.create_path('openconfig-vlan:vlan')
            yang_subif_vlan.create_path('match/single-tagged/config/vlan-id', vlan_id)

        yang_ipv4 : libyang.DContainer = yang_sif.create_path('openconfig-if-ip:ipv4')
        if enabled is not None:
            yang_ipv4.create_path('config/enabled', enabled)

        if address_ip is not None and address_prefix is not None:
            yang_ipv4_addrs : libyang.DContainer = yang_ipv4.create_path('addresses')
            yang_ipv4_addr_path = 'address[ip="{:s}"]'.format(address_ip)
            yang_ipv4_addr : libyang.DContainer = yang_ipv4_addrs.create_path(yang_ipv4_addr_path)
            yang_ipv4_addr.create_path('config/ip',            address_ip)
            yang_ipv4_addr.create_path('config/prefix-length', address_prefix)

        return yang_sif

    def compose(
        self, resource_key : str, resource_value : Dict, yang_handler : YangHandler, delete : bool = False
    ) -> Tuple[str, str]:
        if_name   = get_str(resource_value, 'name'       )  # ethernet-1/1
        sif_index = get_int(resource_value, 'index', None)  # 0
        vlan_id   = get_int(resource_value, 'vlan_id', None)
        eos_tagged_l3_replace = get_bool(resource_value, EOS_TAGGED_L3_REPLACE_FIELD, False)

        if delete:
            if eos_tagged_l3_replace:
                root_node : libyang.DContainer = yang_handler.get_data_path(
                    '/openconfig-interfaces:interfaces'
                )
                str_path = '/interfaces/interface[name={:s}]'.format(if_name)
                yang_if = root_node.find_path('/'.join([
                    '',
                    'openconfig-interfaces:interfaces',
                    'interface[name="{:s}"]'.format(if_name),
                ]))
                if yang_if is not None:
                    yang_if.unlink()
                    yang_if.free()
                str_data = json.dumps({})
                return str_path, str_data

            if sif_index is None:
                return None, None

            root_node : libyang.DContainer = yang_handler.get_data_path(
                '/openconfig-interfaces:interfaces'
            )

            address_ip = get_str(resource_value, 'address_ip', None)
            if address_ip is None:
                PATH_TMPL = '/interfaces/interface[name={:s}]/subinterfaces/subinterface[index={:d}]'
                str_path = PATH_TMPL.format(if_name, sif_index)

                yang_sif = root_node.find_path('/'.join([
                    '', # add slash at the beginning
                    'openconfig-interfaces:interfaces',
                    'interface[name="{:s}"]'.format(if_name),
                    'subinterfaces',
                    'subinterface[index="{:d}"]'.format(sif_index),
                ]))
            else:
                PATH_TMPL = (
                    '/interfaces/interface[name={:s}]/subinterfaces/subinterface[index={:d}]'
                    '/openconfig-if-ip:ipv4/addresses/address[ip={:s}]'
                )
                str_path = PATH_TMPL.format(if_name, sif_index, address_ip)

                yang_sif = root_node.find_path('/'.join([
                    '', # add slash at the beginning
                    'openconfig-interfaces:interfaces',
                    'interface[name="{:s}"]'.format(if_name),
                    'subinterfaces',
                    'subinterface[index="{:d}"]'.format(sif_index),
                    'openconfig-if-ip:ipv4',
                    'addresses',
                    'address[ip="{:s}"]'.format(address_ip)
                ]))

            if yang_sif is not None:
                yang_sif.unlink()
                yang_sif.free()

            str_data = json.dumps({})
            return str_path, str_data

        enabled        = get_bool(resource_value, 'enabled'       ) # True/False
        if_type        = get_str (resource_value, 'type'          ) # 'l3ipvlan'
        address_ip     = get_str (resource_value, 'address_ip'    ) # 172.16.0.1
        address_prefix = get_int (resource_value, 'address_prefix') # 24
        mtu            = get_int (resource_value, 'mtu'           ) # 1500

        yang_ifs : libyang.DContainer = yang_handler.get_data_path('/openconfig-interfaces:interfaces')
        yang_if_path = 'interface[name="{:s}"]'.format(if_name)
        yang_if : libyang.DContainer = yang_ifs.create_path(yang_if_path)
        yang_if.create_path('config/name',    if_name   )
        if if_type is not None:
            yang_if.create_path('config/type', _normalize_interface_type(if_type, sif_index))
        if enabled is not None:
            yang_if.create_path('config/enabled', enabled)
        
        if mtu is not None and mtu >= MIN_MTU:
            yang_if.create_path('config/mtu', mtu)

        if sif_index is None:
            str_path = '/interfaces/interface[name={:s}]'.format(if_name)
            str_data = yang_if.print_mem('json')
            json_data = json.loads(str_data)
            json_data = json_data['openconfig-interfaces:interface'][0]
            str_data = json.dumps(json_data)
            return str_path, str_data

        yang_sifs : libyang.DContainer = yang_if.create_path('subinterfaces')
        if eos_tagged_l3_replace and sif_index == 0 and vlan_id is not None:
            self._create_subinterface(yang_sifs, 0, enabled=enabled)
            self._create_subinterface(
                yang_sifs, vlan_id, enabled=enabled, vlan_id=vlan_id,
                address_ip=address_ip, address_prefix=address_prefix
            )
        else:
            self._create_subinterface(
                yang_sifs, sif_index, enabled=enabled, vlan_id=vlan_id,
                address_ip=address_ip, address_prefix=address_prefix
            )

        str_path = '/interfaces/interface[name={:s}]'.format(if_name)
        str_data = yang_if.print_mem('json')
        json_data = json.loads(str_data)
        json_data = json_data['openconfig-interfaces:interface'][0]
        str_data = json.dumps(json_data)
        return str_path, str_data

    def parse(
        self, json_data : Dict, yang_handler : YangHandler
    ) -> List[Tuple[str, Dict[str, Any]]]:
        LOGGER.debug('json_data = {:s}'.format(json.dumps(json_data)))

        yang_interfaces_path = self.get_path()
        json_data_valid = yang_handler.parse_to_dict(yang_interfaces_path, json_data, fmt='json')

        entries = []
        for interface in json_data_valid['interfaces']['interface']:
            LOGGER.debug('interface={:s}'.format(str(interface)))

            interface_name = interface['name']
            interface_config = interface.get('config', {})

            #yang_interfaces : libyang.DContainer = yang_handler.get_data_path(yang_interfaces_path)
            #yang_interface_path = 'interface[name="{:s}"]'.format(interface_name)
            #yang_interface : libyang.DContainer = yang_interfaces.create_path(yang_interface_path)
            #yang_interface.merge_data_dict(interface, strict=True, validate=False)

            interface_state = interface.get('state', {})
            interface_type = interface_state.get('type')
            if interface_type is None: continue
            interface_type = interface_type.split(':')[-1]
            if interface_type not in {'ethernetCsmacd'}: continue

            _interface = {
                'name'         : interface_name,
                'type'         : interface_type,
                'admin-status' : interface_state['admin-status'],
                'oper-status'  : interface_state['oper-status'],
                'management'   : interface_state['management'],
            }
            if not interface_state['management'] and 'ifindex' in interface_state:
                _interface['ifindex'] = interface_state['ifindex']
            if 'description' in interface_config:
                _interface['description'] = interface_config['description']
            if 'enabled' in interface_config:
                _interface['enabled'] = interface_config['enabled']
            if 'hardware-port' in interface_state:
                _interface['hardware-port'] = interface_state['hardware-port']
            if 'transceiver' in interface_state:
                _interface['transceiver'] = interface_state['transceiver']
            if 'mtu' in interface_state:
                mtu = interface_state['mtu']
                if mtu > 0: _interface['mtu'] = mtu

            entry_interface_key = '/interface[{:s}]'.format(interface_name)
            entries.append((entry_interface_key, _interface))

            if interface_type == 'ethernetCsmacd':
                ethernet_state = interface['ethernet']['state']

                _ethernet = {
                    'mac-address'           : ethernet_state['mac-address'],
                    'hw-mac-address'        : ethernet_state['hw-mac-address'],
                    'port-speed'            : ethernet_state['port-speed'].split(':')[-1],
                    'negotiated-port-speed' : ethernet_state['negotiated-port-speed'].split(':')[-1],
                }
                entry_ethernet_key = '{:s}/ethernet'.format(entry_interface_key)
                entries.append((entry_ethernet_key, _ethernet))

            subinterfaces = interface.get('subinterfaces', {}).get('subinterface', [])
            for subinterface in subinterfaces:
                LOGGER.debug('subinterface={:s}'.format(str(subinterface)))

                subinterface_index = subinterface['index']
                subinterface_state = subinterface.get('state', {})

                _subinterface = {'index': subinterface_index}
                if 'name' in subinterface_state:
                    _subinterface['name'] = subinterface_state['name']
                if 'enabled' in subinterface_state:
                    _subinterface['enabled'] = subinterface_state['enabled']
                if 'mtu' in subinterface_state:
                    mtu = subinterface_state['mtu']
                    if mtu > 0:
                        _subinterface['mtu'] = mtu
                        if 'mtu' not in _interface:
                            _interface['mtu'] = mtu

                if 'vlan' in subinterface:
                    vlan = subinterface['vlan']
                    vlan_match = vlan['match']

                    single_tagged = vlan_match.pop('single-tagged', None)
                    if single_tagged is not None:
                        single_tagged_config = single_tagged['config']
                        vlan_id = single_tagged_config['vlan-id']
                        _subinterface['vlan_id'] = vlan_id

                    if len(vlan_match) > 0:
                        raise Exception('Unsupported VLAN schema: {:s}'.format(str(vlan)))

                ipv4_addresses = subinterface.get('ipv4', {}).get('addresses', {}).get('address', [])
                if len(ipv4_addresses) > 1:
                    raise Exception('Multiple IPv4 Addresses not supported: {:s}'.format(str(ipv4_addresses)))
                for ipv4_address in ipv4_addresses:
                    LOGGER.debug('ipv4_address={:s}'.format(str(ipv4_address)))
                    _subinterface['address_ip'] = ipv4_address['ip']
                    ipv4_address_state = ipv4_address.get('state', {})
                    #if 'origin' in ipv4_address_state:
                    #    _subinterface['origin'] = ipv4_address_state['origin']
                    if 'prefix-length' in ipv4_address_state:
                        _subinterface['address_prefix'] = ipv4_address_state['prefix-length']

                ipv6_addresses = subinterface.get('ipv6', {}).get('addresses', {}).get('address', [])
                if len(ipv6_addresses) > 1:
                    raise Exception('Multiple IPv6 Addresses not supported: {:s}'.format(str(ipv6_addresses)))
                for ipv6_address in ipv6_addresses:
                    LOGGER.debug('ipv6_address={:s}'.format(str(ipv6_address)))
                    _subinterface['address_ipv6'] = ipv6_address['ip']
                    ipv6_address_state = ipv6_address.get('state', {})
                    #if 'origin' in ipv6_address_state:
                    #    _subinterface['origin_ipv6'] = ipv6_address_state['origin']
                    if 'prefix-length' in ipv6_address_state:
                        _subinterface['address_prefix_ipv6'] = ipv6_address_state['prefix-length']

                entry_subinterface_key = '{:s}/subinterface[{:d}]'.format(entry_interface_key, subinterface_index)
                entries.append((entry_subinterface_key, _subinterface))

        return entries
