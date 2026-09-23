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

import logging
import os
import time
from typing import Dict, List, Optional, Set, Tuple

from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import ContextId, Device, Empty, Link, LinkTypeEnum, ServiceStatusEnum, ServiceTypeEnum
from common.tools.grpc.Tools import grpc_message_list_to_json_string, grpc_message_to_json, grpc_message_to_json_string
from common.tools.object_factory.Context import json_context_id

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

ADMIN_CONTEXT_ID = ContextId(**json_context_id(DEFAULT_CONTEXT_NAME))

VIRTUAL_LINK_DESCRIPTORS = [
    ('virtual_link_01.json', 'IP1/PORT-xe1==IP2/PORT-xe1'),
    ('virtual_link_02.json', 'IP1/PORT-xe2==IP2/PORT-xe2'),
    ('virtual_link_03.json', 'IP1/PORT-xe3==IP2/PORT-xe3'),
]
DESCRIPTORS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'descriptors')


def is_imported_device(device: Device) -> bool:
    return device.HasField('controller_id') and bool(device.controller_id.device_uuid.uuid)


def split_imported_devices(devices: List[Device]) -> Tuple[List[Device], List[Device]]:
    imported_devices = [device for device in devices if is_imported_device(device)]
    local_devices = [device for device in devices if not is_imported_device(device)]
    return local_devices, imported_devices


def log_device_inventory(context_client, profile_name: str, log_prefix: str = 'Device inventory') -> Tuple[List[Device], List[Device]]:
    response = context_client.ListDevices(Empty())
    local_devices, imported_devices = split_imported_devices(response.devices)

    LOGGER.info(
        '[%s] %s: total=%d local=%d imported=%d',
        profile_name,
        log_prefix,
        len(response.devices),
        len(local_devices),
        len(imported_devices),
    )
    LOGGER.info('[%s] Local devices: %s', profile_name, grpc_message_list_to_json_string(local_devices))
    LOGGER.info('[%s] Imported devices: %s', profile_name, grpc_message_list_to_json_string(imported_devices))
    return local_devices, imported_devices


def split_descriptor_links(
    links: List[Link], descriptor_link_aliases: Set[str]
) -> Tuple[List[Link], List[Link], List[Link]]:
    descriptor_links = []
    management_links = []
    imported_links = []

    for link in links:
        runtime_aliases = {link.link_id.link_uuid.uuid}
        if link.name:
            runtime_aliases.add(link.name)

        if runtime_aliases.intersection(descriptor_link_aliases):
            descriptor_links.append(link)
        elif _is_management_link(link):
            management_links.append(link)
        else:
            imported_links.append(link)

    return descriptor_links, management_links, imported_links


def log_link_inventory(context_client, descriptor_loader, profile_name: str) -> Tuple[List[Link], List[Link], List[Link]]:
    response = context_client.ListLinks(Empty())
    descriptor_link_aliases = set()
    for link in descriptor_loader.links:
        link_uuid = link.get('link_id', {}).get('link_uuid', {}).get('uuid')
        if link_uuid:
            descriptor_link_aliases.add(link_uuid)
        link_name = link.get('name')
        if link_name:
            descriptor_link_aliases.add(link_name)

    descriptor_links, management_links, imported_links = split_descriptor_links(
        response.links, descriptor_link_aliases
    )

    LOGGER.info(
        '[%s] Descriptor validation link inventory: total=%d descriptor=%d management=%d imported=%d',
        profile_name,
        len(response.links),
        len(descriptor_links),
        len(management_links),
        len(imported_links),
    )
    LOGGER.info('[%s] Descriptor links: %s', profile_name, grpc_message_list_to_json_string(descriptor_links))
    LOGGER.info('[%s] Management links: %s', profile_name, grpc_message_list_to_json_string(management_links))
    LOGGER.info('[%s] Imported links: %s', profile_name, grpc_message_list_to_json_string(imported_links))
    return descriptor_links, management_links, imported_links


def _is_management_link(link: Link) -> bool:
    if link.link_type == LinkTypeEnum.LINKTYPE_MANAGEMENT:
        return True

    if 'mgmt' in link.name.lower():
        return True

    for endpoint_id in link.link_endpoint_ids:
        if 'mgmt' in endpoint_id.endpoint_uuid.uuid.lower():
            return True

    return False


def validate_descriptor_state(context_client, descriptor_loader, profile_name: str) -> None:
    contexts = context_client.ListContexts(Empty())
    assert len(contexts.contexts) == descriptor_loader.num_contexts

    for context_uuid, num_topologies in descriptor_loader.num_topologies.items():
        response = context_client.ListTopologies(ContextId(**json_context_id(context_uuid)))
        assert len(response.topologies) == num_topologies

    local_devices, imported_devices = log_device_inventory(
        context_client, profile_name, log_prefix='Descriptor validation device inventory'
    )
    assert len(local_devices) == descriptor_loader.num_devices
    if imported_devices:
        LOGGER.info(
            '[%s] Ignoring %d imported devices for descriptor validation because they are learned via controllers',
            profile_name,
            len(imported_devices),
        )

    descriptor_links, management_links, imported_links = log_link_inventory(
        context_client, descriptor_loader, profile_name
    )
    assert len(descriptor_links) == descriptor_loader.num_links
    if management_links:
        LOGGER.info(
            '[%s] Found %d management links auto-added during device import',
            profile_name,
            len(management_links),
        )
    if imported_links:
        LOGGER.info(
            '[%s] Ignoring %d imported non-descriptor links during descriptor validation',
            profile_name,
            len(imported_links),
        )

    response = context_client.GetOpticalLinkList(Empty())
    assert len(response.optical_links) == descriptor_loader.num_optical_links

    for context_uuid, num_services in descriptor_loader.num_services.items():
        response = context_client.ListServices(ContextId(**json_context_id(context_uuid)))
        assert len(response.services) == num_services

    for context_uuid, num_slices in descriptor_loader.num_slices.items():
        response = context_client.ListSlices(ContextId(**json_context_id(context_uuid)))
        assert len(response.slices) == num_slices


def list_active_optical_services(context_client) -> List:
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    LOGGER.info('Services[%d] = %s', len(response.services), grpc_message_to_json_string(response))

    active_optical_services = []
    for service in response.services:
        if service.service_type != ServiceTypeEnum.SERVICETYPE_OPTICAL_CONNECTIVITY:
            continue
        if service.service_status.service_status != ServiceStatusEnum.SERVICESTATUS_ACTIVE:
            continue
        active_optical_services.append(service)
    return active_optical_services


def count_service_connections(context_client, service) -> int:
    response = context_client.ListConnections(service.service_id)
    LOGGER.info(
        'ServiceId[%s] => Connections[%d] = %s',
        grpc_message_to_json_string(service.service_id),
        len(response.connections),
        grpc_message_to_json_string(response),
    )
    return len(response.connections)


def describe_services(context_client, profile_name: str) -> str:
    response = context_client.ListServices(ADMIN_CONTEXT_ID)
    services = []
    for service in response.services:
        service_json = grpc_message_to_json(service)
        status_value = service.service_status.service_status
        service_json['service_status_name'] = ServiceStatusEnum.Name(status_value)
        try:
            service_json['num_connections'] = count_service_connections(context_client, service)
        except Exception as exc:  # pylint: disable=broad-except
            service_json['num_connections_error'] = str(exc)
        services.append(service_json)
    LOGGER.info('[%s] Service snapshot: %s', profile_name, str(services))
    return str(services)


def get_virtual_link_identifiers(context_client) -> Tuple[Set[str], Set[str]]:
    response = context_client.ListLinks(Empty())
    virtual_link_uuids = set()
    virtual_link_names = set()
    for link in response.links:
        if link.link_type != LinkTypeEnum.LINKTYPE_VIRTUAL:
            continue
        virtual_link_uuids.add(link.link_id.link_uuid.uuid)
        if len(link.name) > 0:
            virtual_link_names.add(link.name)

    LOGGER.info('VirtualLinkNames[%d] = %s', len(virtual_link_names), str(sorted(virtual_link_names)))
    LOGGER.info('VirtualLinkUuids[%d] = %s', len(virtual_link_uuids), str(sorted(virtual_link_uuids)))
    return virtual_link_uuids, virtual_link_names


def describe_links(context_client, profile_name: str) -> str:
    response = context_client.ListLinks(Empty())
    links = []
    for link in response.links:
        link_json = grpc_message_to_json(link)
        link_json['link_type_name'] = LinkTypeEnum.Name(link.link_type)
        links.append(link_json)
    LOGGER.info('[%s] Link snapshot: %s', profile_name, str(links))
    return str(links)


def log_global_state(ip_context_client, e2e_context_client, opt_context_client) -> None:
    describe_links(ip_context_client, 'ip')
    describe_services(ip_context_client, 'ip')
    describe_services(e2e_context_client, 'e2e')
    describe_services(opt_context_client, 'opt')


def assert_expected_set(actual_items: Set[str], expected_items: Optional[Set[str]], label: str) -> None:
    if expected_items is None:
        return

    assert actual_items == expected_items, (
        '{:s} mismatch: expected={:s} actual={:s}'.format(
            label, str(sorted(expected_items)), str(sorted(actual_items))
        )
    )


def get_service_identifiers(service) -> Set[str]:
    identifiers = {service.service_id.service_uuid.uuid}
    if len(service.name) > 0:
        identifiers.add(service.name)
    return identifiers


def build_expected_optical_connections(expected_virtual_link_names: Set[str]) -> Dict[str, int]:
    expected_connections = dict()
    first_optical_service_name = VIRTUAL_LINK_DESCRIPTORS[0][1]

    for _, virtual_link_name in VIRTUAL_LINK_DESCRIPTORS:
        if virtual_link_name not in expected_virtual_link_names:
            continue
        expected_connections[virtual_link_name] = 2 if virtual_link_name == first_optical_service_name else 1

    return expected_connections


def assert_global_state(
    ip_context_client,
    e2e_context_client,
    opt_context_client,
    expected_virtual_link_uuids: Optional[Set[str]],
    expected_virtual_link_names: Optional[Set[str]],
    expected_e2e_services: int,
    expected_opt_services: int,
    expected_opt_connections: Optional[Dict[str, int]],
) -> None:
    response = ip_context_client.ListServices(ADMIN_CONTEXT_ID)
    assert len(response.services) == 0

    virtual_link_uuids, virtual_link_names = get_virtual_link_identifiers(ip_context_client)
    assert_expected_set(virtual_link_uuids, expected_virtual_link_uuids, 'Virtual link UUIDs')
    assert_expected_set(virtual_link_names, expected_virtual_link_names, 'Virtual link names')

    e2e_services = list_active_optical_services(e2e_context_client)
    if expected_e2e_services == 0:
        response = e2e_context_client.ListServices(ADMIN_CONTEXT_ID)
        assert len(response.services) == 0
    else:
        assert len(e2e_services) == expected_e2e_services
        for service in e2e_services:
            assert count_service_connections(e2e_context_client, service) == 1

    opt_services = list_active_optical_services(opt_context_client)
    if expected_opt_services == 0:
        response = opt_context_client.ListServices(ADMIN_CONTEXT_ID)
        assert len(response.services) == 0
    else:
        assert len(opt_services) == expected_opt_services

        if expected_opt_connections is not None:
            unmatched_expected = dict(expected_opt_connections)
            for service in opt_services:
                service_identifiers = get_service_identifiers(service)
                matching_identifiers = [
                    identifier for identifier in service_identifiers if identifier in unmatched_expected
                ]
                assert len(matching_identifiers) == 1, (
                    'Unable to match optical service identifiers={:s} against expected={:s}'.format(
                        str(sorted(service_identifiers)), str(sorted(unmatched_expected.keys()))
                    )
                )

                service_identifier = matching_identifiers[0]
                actual_connections = count_service_connections(opt_context_client, service)
                expected_connections = unmatched_expected.pop(service_identifier)
                assert actual_connections == expected_connections, (
                    'Optical service {:s} connections mismatch: expected={:d} actual={:d}'.format(
                        service_identifier, expected_connections, actual_connections
                    )
                )

            assert len(unmatched_expected) == 0, (
                'Missing optical services for expected connection checks: {:s}'.format(
                    str(sorted(unmatched_expected.keys()))
                )
            )


def wait_for_state_or_raise(
    ip_context_client,
    e2e_context_client,
    opt_context_client,
    expected_virtual_link_uuids: Optional[Set[str]],
    expected_virtual_link_names: Optional[Set[str]],
    expected_e2e_services: int,
    expected_opt_services: int,
    expected_opt_connections: Optional[Dict[str, int]],
    max_retry: int = 5,
    wait_seconds: float = 15.0,
) -> None:
    last_error: Exception = Exception('state not reached')
    for attempt in range(1, max_retry + 1):
        try:
            LOGGER.info(
                'Checking expected state attempt %d/%d: virtual_link_uuids=%s virtual_link_names=%s '
                'e2e_services=%d opt_services=%d opt_connections=%s',
                attempt,
                max_retry,
                '<ignored>' if expected_virtual_link_uuids is None else str(sorted(expected_virtual_link_uuids)),
                '<ignored>' if expected_virtual_link_names is None else str(sorted(expected_virtual_link_names)),
                expected_e2e_services,
                expected_opt_services,
                expected_opt_connections,
            )
            assert_global_state(
                ip_context_client=ip_context_client,
                e2e_context_client=e2e_context_client,
                opt_context_client=opt_context_client,
                expected_virtual_link_uuids=expected_virtual_link_uuids,
                expected_virtual_link_names=expected_virtual_link_names,
                expected_e2e_services=expected_e2e_services,
                expected_opt_services=expected_opt_services,
                expected_opt_connections=expected_opt_connections,
            )
            return
        except Exception as error:  # pylint: disable=broad-except
            last_error = error
            LOGGER.warning(
                'Expected state not reached on attempt %d/%d: %s',
                attempt, max_retry, str(error)
            )
            log_global_state(ip_context_client, e2e_context_client, opt_context_client)
            time.sleep(wait_seconds)

    LOGGER.error(
        'Timed out waiting expected state: virtual_link_uuids=%s virtual_link_names=%s '
        'e2e_services=%d opt_services=%d opt_connections=%s',
        '<ignored>' if expected_virtual_link_uuids is None else str(sorted(expected_virtual_link_uuids)),
        '<ignored>' if expected_virtual_link_names is None else str(sorted(expected_virtual_link_names)),
        expected_e2e_services,
        expected_opt_services,
        expected_opt_connections,
    )
    raise last_error
