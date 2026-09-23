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

import json

from device.service.drivers.gnmi_openconfig.handlers.Interface import (
    EOS_TAGGED_L3_REPLACE_FIELD,
    InterfaceHandler,
)
from device.service.drivers.gnmi_openconfig.handlers.YangHandler import YangHandler


def test_compose_tagged_l3_subinterface_sets_parent_ethernet_type() -> None:
    handler = InterfaceHandler()
    yang_handler = YangHandler()
    try:
        _, str_data = handler.compose(
            '/interface[Ethernet11]/subinterface[125]',
            {
                'name': 'Ethernet11',
                'type': 'l3ipvlan',
                'index': 125,
                'vlan_id': 125,
                'address_ip': '172.17.1.1',
                'address_prefix': 24,
                'enabled': True,
            },
            yang_handler,
            delete=False,
        )
    finally:
        yang_handler.destroy()

    json_data = json.loads(str_data)
    assert json_data['config']['type'] == 'iana-if-type:ethernetCsmacd'

    subinterface = json_data['subinterfaces']['subinterface'][0]
    assert subinterface['index'] == 125
    assert subinterface['openconfig-vlan:vlan']['match']['single-tagged']['config']['vlan-id'] == 125
    address = subinterface['openconfig-if-ip:ipv4']['addresses']['address'][0]
    assert address['config']['ip'] == '172.17.1.1'
    assert address['config']['prefix-length'] == 24


def test_compose_eos_tagged_l3_replace_emits_subif_zero_and_vlan_subif() -> None:
    handler = InterfaceHandler()
    yang_handler = YangHandler()
    try:
        _, str_data = handler.compose(
            '/interface[Ethernet11]/subinterface[0]',
            {
                'name': 'Ethernet11',
                'type': 'l3ipvlan',
                'index': 0,
                'vlan_id': 125,
                'address_ip': '172.17.1.1',
                'address_prefix': 24,
                'enabled': True,
                EOS_TAGGED_L3_REPLACE_FIELD: True,
            },
            yang_handler,
            delete=False,
        )
    finally:
        yang_handler.destroy()

    json_data = json.loads(str_data)
    assert json_data['config']['type'] == 'iana-if-type:ethernetCsmacd'

    subinterfaces = json_data['subinterfaces']['subinterface']
    assert [subinterface['index'] for subinterface in subinterfaces] == [0, 125]

    subinterface_zero = subinterfaces[0]
    assert subinterface_zero['openconfig-if-ip:ipv4']['config']['enabled'] is True

    subinterface_vlan = subinterfaces[1]
    assert subinterface_vlan['openconfig-vlan:vlan']['match']['single-tagged']['config']['vlan-id'] == 125
    address = subinterface_vlan['openconfig-if-ip:ipv4']['addresses']['address'][0]
    assert address['config']['ip'] == '172.17.1.1'
    assert address['config']['prefix-length'] == 24


def test_delete_subinterface_zero_unlinks_it_from_shared_yang_state() -> None:
    handler = InterfaceHandler()
    yang_handler = YangHandler()
    try:
        handler.compose(
            '/interface[Ethernet10]/subinterface[0]',
            {
                'name': 'Ethernet10',
                'type': 'l3ipvlan',
                'index': 0,
                'address_ip': '172.16.1.1',
                'address_prefix': 24,
                'enabled': True,
            },
            yang_handler,
            delete=False,
        )

        str_path, _ = handler.compose(
            '/interface[Ethernet10]/subinterface[0]',
            {
                'name': 'Ethernet10',
                'index': 0,
            },
            yang_handler,
            delete=True,
        )

        root_node = yang_handler.get_data_path('/openconfig-interfaces:interfaces')
        yang_subif = root_node.find_path('/'.join([
            '',
            'openconfig-interfaces:interfaces',
            'interface[name="Ethernet10"]',
            'subinterfaces',
            'subinterface[index="0"]',
        ]))
    finally:
        yang_handler.destroy()

    assert str_path == '/interfaces/interface[name=Ethernet10]/subinterfaces/subinterface[index=0]'
    assert yang_subif is None


def test_delete_eos_tagged_l3_replace_unlinks_full_interface_from_shared_yang_state() -> None:
    handler = InterfaceHandler()
    yang_handler = YangHandler()
    try:
        handler.compose(
            '/interface[Ethernet11]/subinterface[0]',
            {
                'name': 'Ethernet11',
                'type': 'l3ipvlan',
                'index': 0,
                'vlan_id': 125,
                'address_ip': '172.17.1.1',
                'address_prefix': 24,
                'enabled': True,
                EOS_TAGGED_L3_REPLACE_FIELD: True,
            },
            yang_handler,
            delete=False,
        )

        str_path, _ = handler.compose(
            '/interface[Ethernet11]/subinterface[0]',
            {
                'name': 'Ethernet11',
                'index': 0,
                'vlan_id': 125,
                EOS_TAGGED_L3_REPLACE_FIELD: True,
            },
            yang_handler,
            delete=True,
        )

        root_node = yang_handler.get_data_path('/openconfig-interfaces:interfaces')
        yang_if = root_node.find_path('/'.join([
            '',
            'openconfig-interfaces:interfaces',
            'interface[name="Ethernet11"]',
        ]))
    finally:
        yang_handler.destroy()

    assert str_path == '/interfaces/interface[name=Ethernet11]'
    assert yang_if is None
