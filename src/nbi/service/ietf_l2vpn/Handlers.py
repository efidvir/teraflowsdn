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
from typing import Dict, List, Optional
from common.Constants import DEFAULT_CONTEXT_NAME
from common.proto.context_pb2 import Service, ServiceStatusEnum, ServiceTypeEnum
from common.tools.context_queries.Service import get_service_by_uuid
from common.tools.grpc.ConfigRules import update_config_rule_custom
from common.tools.grpc.Constraints import (
    update_constraint_custom_dict, update_constraint_endpoint_location,
    update_constraint_endpoint_priority, update_constraint_sla_availability,
    update_constraint_sla_capacity, update_constraint_sla_latency,
)
from common.tools.grpc.EndPointIds import update_endpoint_ids
from common.tools.grpc.Tools import grpc_message_to_json_string
from context.client.ContextClient import ContextClient
from service.client.ServiceClient import ServiceClient
from .Constants import (
    #DEFAULT_ADDRESS_FAMILIES, DEFAULT_BGP_AS, DEFAULT_BGP_ROUTE_TARGET,
    BEARER_MAPPINGS, DEFAULT_MTU,
)

LOGGER = logging.getLogger(__name__)

def create_service(
    service_uuid : str,
    service_type : ServiceTypeEnum = ServiceTypeEnum.SERVICETYPE_L2NM,
    context_uuid : Optional[str] = DEFAULT_CONTEXT_NAME,
) -> Optional[Exception]:
    # pylint: disable=no-member
    service_request = Service()
    service_request.service_id.context_id.context_uuid.uuid = context_uuid
    service_request.service_id.service_uuid.uuid = service_uuid
    service_request.service_type = service_type
    service_request.service_status.service_status = ServiceStatusEnum.SERVICESTATUS_PLANNED

    try:
        service_client = ServiceClient()
        service_client.CreateService(service_request)
        return None
    except Exception as e: # pylint: disable=broad-except
        LOGGER.exception('Unhandled exception creating Service')
        return e

def process_vpn_service(
    vpn_service : Dict, errors : List[Dict]
) -> None:
    vpn_id = vpn_service['vpn-id']
    customer_name = vpn_service.get('customer-name')
    if isinstance(customer_name, str) and customer_name.strip().lower() == 'osm':
        service_type = ServiceTypeEnum.SERVICETYPE_L3NM
    else:
        service_type = ServiceTypeEnum.SERVICETYPE_L2NM
    exc = create_service(vpn_id, service_type=service_type)
    if exc is not None: errors.append({'error': str(exc)})


def process_site_network_access(
    site_id : str, network_access : Dict, errors : List[Dict]
) -> None:
    try:
        #device_uuid   = None
        #endpoint_uuid = None
        #if 'device-reference' in network_access:
        #    device_uuid   = network_access['device-reference']
        #    endpoint_uuid = network_access['network-access-id']

        bearer_reference = None
        if 'bearer' in network_access:
            network_access_bearer = network_access['bearer']
            if 'bearer-reference' in network_access_bearer:
                bearer_reference = network_access_bearer['bearer-reference']

        bearer_mapping = BEARER_MAPPINGS.get(bearer_reference)
        if bearer_mapping is None:
            if ':' in bearer_reference:
                bearer_mapping = str(bearer_reference).split(':')
                if len(bearer_mapping) == 2:
                    # assume device:endpoint
                    pass
                elif len(bearer_mapping) == 3:
                    # assume prefix:device:endpoint
                    bearer_mapping.pop(0)
                else:
                    MSG = 'Bearer({:s}) not found; unable to auto-generated mapping'
                    raise Exception(MSG.format(str(bearer_reference)))

                bearer_mapping.extend([None, None, None, None, None, None, None])
                bearer_mapping = tuple(bearer_mapping)
                MSG = 'Bearer({:s}) not found; auto-generated mapping: {:s}'
                LOGGER.warning(MSG.format(str(bearer_reference), str(bearer_mapping)))
            else:
                MSG = 'Bearer({:s}) not found; unable to auto-generated mapping'
                raise Exception(MSG.format(str(bearer_reference)))

        (
            device_uuid, endpoint_uuid, router_id, route_dist, sub_if_index,
            address_ip, address_prefix, remote_router, circuit_id
        ) = bearer_mapping

        service_uuid  = network_access['vpn-attachment']['vpn-id']

        network_access_connection = network_access['connection']

        encapsulation_type = network_access_connection.get('encapsulation-type', 'ietf-l2vpn-svc:ethernet')
        encapsulation_type = encapsulation_type.replace('ietf-l2vpn-svc:', '')

        eth_inf_type = None
        if 'eth-inf-type' not in network_access_connection:
            if 'tagged-interface' in network_access_connection:
                if encapsulation_type == 'ethernet':
                    eth_inf_type = 'untagged'
                elif encapsulation_type == 'vlan':
                    eth_inf_type = 'tagged'
        if eth_inf_type is None:
            eth_inf_type = network_access_connection.get('eth-inf-type', 'ietf-l2vpn-svc:untagged')
            eth_inf_type = eth_inf_type.replace('ietf-l2vpn-svc:', '')

        if encapsulation_type == 'ethernet' and eth_inf_type == 'untagged':
            if 'tagged-interface' in network_access_connection:
                MSG = 'Malformed NetworkAccessConnection({:s})'
                raise Exception(MSG.format(str(network_access_connection)))
        elif encapsulation_type == 'vlan' and eth_inf_type == 'tagged':
            if 'tagged-interface' not in network_access_connection:
                MSG = 'Malformed NetworkAccessConnection({:s})'
                raise Exception(MSG.format(str(network_access_connection)))
        else:
            encapsulation_type = network_access_connection.get('encapsulation-type', 'ietf-l2vpn-svc:ethernet')
            eth_inf_type = network_access_connection.get('eth-inf-type', 'ietf-l2vpn-svc:untagged')
            MSG = 'Combination EncapsulationType({:s})/EthernetInterfaceType({:s}) not supported'
            raise NotImplementedError(MSG.format(str(encapsulation_type), str(eth_inf_type)))

        cvlan_tag_id = None
        if 'tagged-interface' in network_access_connection:
            nac_tagged_if = network_access_connection['tagged-interface']
            nac_tagged_if_type = nac_tagged_if.get('type', 'priority-tagged')
            nac_tagged_if_type = nac_tagged_if_type.replace('ietf-l2vpn-svc:', '')
            if nac_tagged_if_type == 'dot1q':
                encapsulation_data = nac_tagged_if['dot1q-vlan-tagged']
                tag_type = encapsulation_data.get('tg-type', 'c-vlan')
                tag_type = tag_type.replace('ietf-l2vpn-svc:', '')
                if tag_type == 'c-vlan':
                    cvlan_tag_id = encapsulation_data['cvlan-id']
                else:
                    tag_type = encapsulation_data.get('tg-type', 'c-vlan')
                    MSG = 'TagType({:s}) not supported'
                    raise NotImplementedError(MSG.format(str(tag_type)))
            else:
                nac_tagged_if_type = nac_tagged_if.get('type', 'priority-tagged')
                MSG = 'TaggedInterfaceType({:s}) not supported'
                raise NotImplementedError(MSG.format(str(nac_tagged_if_type)))

        network_access_service = network_access.get('service', dict())

        service_mtu              = network_access_service.get('svc-mtu', DEFAULT_MTU)

        max_bandwidth_gbps = None
        max_e2e_latency_ms = None
        availability       = None

        service_bandwidth_bps = 0
        service_input_bandwidth = network_access_service.get('svc-input-bandwidth')
        if service_input_bandwidth is not None:
            service_input_bandwidth = float(service_input_bandwidth)
            service_bandwidth_bps = max(service_bandwidth_bps, service_input_bandwidth)

        service_output_bandwidth = network_access_service.get('svc-output-bandwidth')
        if service_output_bandwidth is not None:
            service_output_bandwidth = float(service_output_bandwidth)
            if service_bandwidth_bps is None:
                service_bandwidth_bps = service_output_bandwidth
            else:
                service_bandwidth_bps = max(service_bandwidth_bps, service_output_bandwidth)

        if service_bandwidth_bps > 1.e-12:
            max_bandwidth_gbps = service_bandwidth_bps / 1.e9

        qos_profile_classes = (
            network_access.get('service', dict())
            .get('qos', dict())
            .get('qos-profile', dict())
            .get('classes', dict())
            .get('class', list())
        )
        for qos_profile_class in qos_profile_classes:
            if qos_profile_class['class-id'] != 'qos-realtime':
                MSG = 'Site Network Access QoS Class Id: {:s}'
                raise NotImplementedError(MSG.format(str(qos_profile_class['class-id'])))

            qos_profile_class_direction = qos_profile_class['direction']
            qos_profile_class_direction = qos_profile_class_direction.replace('ietf-l2vpn-svc:', '')
            if qos_profile_class_direction != 'both':
                MSG = 'Site Network Access QoS Class Direction: {:s}'
                raise NotImplementedError(MSG.format(str(qos_profile_class['direction'])))

            max_e2e_latency_ms = float(qos_profile_class['latency']['latency-boundary'])
            availability       = float(qos_profile_class['bandwidth']['guaranteed-bw-percent'])

        network_access_diversity = network_access.get('access-diversity', {})
        diversity_constraints = network_access_diversity.get('constraints', {}).get('constraint', [])
        raise_if_differs = True
        diversity_constraints = {
            constraint['constraint-type']:([
                target[0]
                for target in constraint['target'].items()
            ][0], raise_if_differs)
            for constraint in diversity_constraints
        }

        network_access_availability = network_access.get('availability', {})
        access_priority : Optional[int] = network_access_availability.get('access-priority')
        single_active   : bool = 'single-active' in network_access_availability
        all_active      : bool = 'all-active' in network_access_availability

        context_client = ContextClient()
        service = get_service_by_uuid(
            context_client, service_uuid, context_uuid=DEFAULT_CONTEXT_NAME, rw_copy=True
        )
        if service is None:
            raise Exception('VPN({:s}) not found in database'.format(str(service_uuid)))

        endpoint_ids = service.service_endpoint_ids
        config_rules = service.service_config.config_rules
        constraints  = service.service_constraints

        endpoint_id = update_endpoint_ids(endpoint_ids, device_uuid, endpoint_uuid)

        update_constraint_endpoint_location(constraints, endpoint_id, region=site_id)
        if access_priority is not None:
            update_constraint_endpoint_priority(constraints, endpoint_id, access_priority)
        if max_bandwidth_gbps is not None:
            update_constraint_sla_capacity(constraints, max_bandwidth_gbps)
        if max_e2e_latency_ms is not None:
            update_constraint_sla_latency(constraints, max_e2e_latency_ms)
        if availability is not None:
            update_constraint_sla_availability(constraints, 1, True, availability)
        if len(diversity_constraints) > 0:
            update_constraint_custom_dict(constraints, 'diversity', diversity_constraints)
        if single_active or all_active:
            # assume 1 disjoint path per endpoint/location included in service
            location_endpoints = {}
            for constraint in constraints:
                if constraint.WhichOneof('constraint') != 'endpoint_location': continue
                str_endpoint_id = grpc_message_to_json_string(constraint.endpoint_location.endpoint_id)
                str_location_id = grpc_message_to_json_string(constraint.endpoint_location.location)
                location_endpoints.setdefault(str_location_id, set()).add(str_endpoint_id)
            num_endpoints_per_location = {len(endpoints) for endpoints in location_endpoints.values()}
            num_disjoint_paths = max(num_endpoints_per_location)
            update_constraint_sla_availability(constraints, num_disjoint_paths, all_active, 0.0)

        service_settings_key = '/settings'
        field_updates = {
            'mtu'             : (service_mtu,              True),
            #'address_families': (DEFAULT_ADDRESS_FAMILIES, True),
            #'bgp_as'          : (DEFAULT_BGP_AS,           True),
            #'bgp_route_target': (DEFAULT_BGP_ROUTE_TARGET, True),
        }
        if cvlan_tag_id   is not None: field_updates['vlan_id'            ] = (cvlan_tag_id,   True)
        update_config_rule_custom(config_rules, service_settings_key, field_updates)

        #ENDPOINT_SETTINGS_KEY = '/device[{:s}]/endpoint[{:s}]/vlan[{:d}]/settings'
        #endpoint_settings_key = ENDPOINT_SETTINGS_KEY.format(device_uuid, endpoint_uuid, cvlan_tag_id)
        ENDPOINT_SETTINGS_KEY = '/device[{:s}]/endpoint[{:s}]/settings'
        endpoint_settings_key = ENDPOINT_SETTINGS_KEY.format(device_uuid, endpoint_uuid)
        field_updates = {}
        if router_id      is not None: field_updates['router_id'          ] = (router_id,      True)
        if route_dist     is not None: field_updates['route_distinguisher'] = (route_dist,     True)
        if sub_if_index   is not None: field_updates['sub_interface_index'] = (sub_if_index,   True)
        if cvlan_tag_id   is not None: field_updates['vlan_id'            ] = (cvlan_tag_id,   True)
        if address_ip     is not None: field_updates['address_ip'         ] = (address_ip,     True)
        if address_prefix is not None: field_updates['address_prefix'     ] = (address_prefix, True)
        if remote_router  is not None: field_updates['remote_router'      ] = (remote_router,  True)
        if circuit_id     is not None: field_updates['circuit_id'         ] = (circuit_id,     True)
        update_config_rule_custom(config_rules, endpoint_settings_key, field_updates)

        service_client = ServiceClient()
        service_client.UpdateService(service)
    except Exception as exc:
        LOGGER.exception('Unhandled Exception')
        errors.append({'error': str(exc)})


def process_site(site : Dict, errors : List[Dict]) -> None:
    site_id = site['site-id']

    site_management_type = site['management']['type']
    site_management_type = site_management_type.replace('ietf-l2vpn-svc:', '')
    if site_management_type != 'provider-managed':
        MSG = 'Site Management Type: {:s}'
        raise NotImplementedError(MSG.format(str(site['management']['type'])))

    network_accesses : List[Dict] = site['site-network-accesses']['site-network-access']
    for network_access in network_accesses:
        process_site_network_access(site_id, network_access, errors)

def update_vpn(site : Dict, errors : List[Dict]) -> None:
    site_management_type = site['management']['type']
    site_management_type = site_management_type.replace('ietf-l2vpn-svc:', '')
    if site_management_type != 'provider-managed':
        MSG = 'Site Management Type: {:s}'
        raise NotImplementedError(MSG.format(str(site['management']['type'])))

    network_accesses : List[Dict] = site['site-network-accesses']['site-network-access']
    for network_access in network_accesses:
        update_site_network_access(network_access, errors)

def update_site_network_access(network_access : Dict, errors : List[Dict]) -> None:
    try:
        site_network_access_type = network_access['site-network-access-type']
        site_network_access_type = site_network_access_type.replace('ietf-l2vpn-svc:', '')
        if site_network_access_type != 'multipoint':
            MSG = 'Site Network Access Type: {:s}'
            msg = MSG.format(str(network_access['site-network-access-type']))
            raise NotImplementedError(msg)

        service_uuid = network_access['vpn-attachment']['vpn-id']

        service_input_bandwidth  = network_access['service']['svc-input-bandwidth']
        service_output_bandwidth = network_access['service']['svc-output-bandwidth']
        service_bandwidth_bps    = max(service_input_bandwidth, service_output_bandwidth)
        max_bandwidth_gbps   = service_bandwidth_bps / 1.e9

        max_e2e_latency_ms = None
        availability       = None

        context_client = ContextClient()
        service = get_service_by_uuid(
            context_client, service_uuid, context_uuid=DEFAULT_CONTEXT_NAME, rw_copy=True
        )
        if service is None:
            MSG = 'VPN({:s}) not found in database'
            raise Exception(MSG.format(str(service_uuid)))

        constraints = service.service_constraints
        if max_bandwidth_gbps is not None:
            update_constraint_sla_capacity(constraints, max_bandwidth_gbps)
        if max_e2e_latency_ms is not None:
            update_constraint_sla_latency(constraints, max_e2e_latency_ms)
        if availability is not None:
            update_constraint_sla_availability(constraints, 1, True, availability)

        service_client = ServiceClient()
        service_client.UpdateService(service)
    except Exception as e: # pylint: disable=broad-except
        LOGGER.exception('Unhandled exception updating Service')
        errors.append({'error': str(e)})
