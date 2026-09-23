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

from device.service.drivers.gnmi_openconfig.GnmiSessionHandler import (
    _extract_target_facts_from_chassis_state,
    _extract_target_facts_from_system_state,
    _prepare_set_operation,
)
from device.service.drivers.gnmi_openconfig.handlers.Interface import EOS_TAGGED_L3_REPLACE_FIELD


def test_prepare_set_operation_uses_replace_for_arista_tagged_l3_access() -> None:
    operation, prepared_value = _prepare_set_operation(
        {'vendor': 'ARISTA'},
        '/interface[Ethernet11]/subinterface[0]',
        {
            'name': 'Ethernet11',
            'type': 'l3ipvlan',
            'index': 0,
            'vlan_id': 125,
            'address_ip': '172.17.1.1',
            'address_prefix': 24,
            'enabled': True,
        },
    )

    assert operation == 'replace'
    assert prepared_value[EOS_TAGGED_L3_REPLACE_FIELD] is True


def test_prepare_set_operation_keeps_update_for_untagged_interface() -> None:
    operation, prepared_value = _prepare_set_operation(
        {'vendor': 'ARISTA'},
        '/interface[Ethernet10]/subinterface[0]',
        {
            'name': 'Ethernet10',
            'type': 'l3ipvlan',
            'index': 0,
            'address_ip': '172.16.1.1',
            'address_prefix': 24,
            'enabled': True,
        },
    )

    assert operation == 'update'
    assert EOS_TAGGED_L3_REPLACE_FIELD not in prepared_value


def test_prepare_set_operation_keeps_update_for_non_arista_tagged_l3_access() -> None:
    operation, prepared_value = _prepare_set_operation(
        {'vendor': 'NOKIA'},
        '/interface[Ethernet11]/subinterface[0]',
        {
            'name': 'Ethernet11',
            'type': 'l3ipvlan',
            'index': 0,
            'vlan_id': 125,
            'address_ip': '172.17.1.1',
            'address_prefix': 24,
            'enabled': True,
        },
    )

    assert operation == 'update'
    assert EOS_TAGGED_L3_REPLACE_FIELD not in prepared_value


def test_prepare_set_operation_uses_replace_for_discovered_arista_target() -> None:
    operation, prepared_value = _prepare_set_operation(
        {'_target_facts': {'vendor': 'Arista', 'platform': 'EOS', 'model': 'cEOSLab'}},
        '/interface[Ethernet11]/subinterface[0]',
        {
            'name': 'Ethernet11',
            'type': 'l3ipvlan',
            'index': 0,
            'vlan_id': 125,
            'address_ip': '172.17.1.1',
            'address_prefix': 24,
            'enabled': True,
        },
    )

    assert operation == 'replace'
    assert prepared_value[EOS_TAGGED_L3_REPLACE_FIELD] is True


def test_extract_target_facts_from_system_state() -> None:
    facts = _extract_target_facts_from_system_state({
        'openconfig-system:hostname': 'r1',
        'openconfig-system:software-version': '4.32.2F',
    })

    assert facts == {
        'hostname': 'r1',
        'software_version': '4.32.2F',
    }


def test_extract_target_facts_from_chassis_state() -> None:
    facts = _extract_target_facts_from_chassis_state({
        'openconfig-platform:mfg-name': 'Arista',
        'openconfig-platform:part-no': 'cEOSLab',
        'openconfig-platform:description': 'cEOSLab',
        'openconfig-platform:serial-no': 'SERIAL123',
    })

    assert facts == {
        'vendor': 'Arista',
        'model': 'cEOSLab',
        'description': 'cEOSLab',
        'serial_no': 'SERIAL123',
    }
