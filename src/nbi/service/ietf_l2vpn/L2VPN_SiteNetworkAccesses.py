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
from typing import Dict, List
from flask import request
from flask.json import jsonify
from flask_restful import Resource
from werkzeug.exceptions import UnsupportedMediaType
from common.proto.context_pb2 import ServiceTypeEnum
from common.tools.context_queries.Service import get_services
from context.client.ContextClient import ContextClient
from nbi.service._tools.Authentication import HTTP_AUTH
from nbi.service._tools.HttpStatusCodes import (
    HTTP_CREATED, HTTP_NOCONTENT, HTTP_SERVERERROR
)
from .Constants import DEFAULT_MTU
from .Handlers import process_site_network_access
from .YangValidator import YangValidator

LOGGER = logging.getLogger(__name__)

class L2VPN_SiteNetworkAccesses(Resource):
    @HTTP_AUTH.login_required
    def post(self, site_id : str):
        if not request.is_json: raise UnsupportedMediaType('JSON payload is required')
        request_data : Dict = request.json
        LOGGER.debug('Site_Id: {:s}'.format(str(site_id)))
        LOGGER.debug('Request: {:s}'.format(str(request_data)))
        errors = self._process_site_network_accesses(site_id, request_data)
        if len(errors) > 0:
            LOGGER.error('Errors: {:s}'.format(str(errors)))
        else:
            LOGGER.debug('Errors: {:s}'.format(str(errors)))
        response = jsonify(errors)
        response.status_code = HTTP_CREATED if len(errors) == 0 else HTTP_SERVERERROR
        return response

    @HTTP_AUTH.login_required
    def put(self, site_id : str):
        if not request.is_json: raise UnsupportedMediaType('JSON payload is required')
        request_data : Dict = request.json
        LOGGER.debug('Site_Id: {:s}'.format(str(site_id)))
        LOGGER.debug('Request: {:s}'.format(str(request_data)))
        errors = self._process_site_network_accesses(site_id, request_data)
        if len(errors) > 0:
            LOGGER.error('Errors: {:s}'.format(str(errors)))
        else:
            LOGGER.debug('Errors: {:s}'.format(str(errors)))
        response = jsonify(errors)
        response.status_code = HTTP_NOCONTENT if len(errors) == 0 else HTTP_SERVERERROR
        return response

    def _prepare_request_payload(self, site_id : str, request_data : Dict, errors : List[Dict]) -> Dict:
        if 'ietf-l2vpn-svc:l2vpn-svc' in request_data:
            # processing single (standard) request formatted as:
            #{"ietf-l2vpn-svc:l2vpn-svc": {
            #  "sites": {"site": [
            #    {
            #      "site-id": ...,
            #      "site-network-accesses": {"site-network-access": [
            #        {
            #          "network-access-id": ...,
            #          ...
            #        }
            #      ]}
            #    }
            #  ]}
            #}}
            return request_data

        if 'ietf-l2vpn-svc:site-network-access' in request_data:
            # processing OSM-style payload request formatted as:
            #{
            #  "ietf-l2vpn-svc:site-network-access": [
            site_network_accesses = request_data['ietf-l2vpn-svc:site-network-access']

            location_refs = set()
            location_refs.add('fake-location')

            device_refs = dict()
            device_refs['fake-device'] = 'fake-location'

            # Add mandatory fields OSM RO driver skips and fix wrong ones
            for site_network_access in site_network_accesses:
                location = 'fake-location'
                if 'location-reference' in site_network_access:
                    location = site_network_access['location-reference']
                    site_network_access.pop('location-reference')
                #else:
                #    site_network_access['location-reference'] = location
                location_refs.add(location)

                if 'device-reference' in site_network_access:
                    device = site_network_access['device-reference']
                else:
                    device = 'fake-device'
                    site_network_access['device-reference'] = device
                device_refs[device] = location

                if 'connection' in site_network_access:
                    connection = site_network_access['connection']
                    if 'encapsulation-type' in connection:
                        if connection['encapsulation-type'] == 'dot1q-vlan-tagged':
                            connection['encapsulation-type'] = 'vlan'
                            if 'eth-inf-type' not in connection:
                                connection['eth-inf-type'] = 'tagged'
                        else:
                            connection['encapsulation-type'] = 'ethernet'
                            if 'eth-inf-type' not in connection:
                                connection['eth-inf-type'] = 'untagged'
                    if 'tagged-interface' in connection:
                        tagged_interface = connection['tagged-interface']
                        if 'dot1q-vlan-tagged' in tagged_interface:
                            if 'type' not in tagged_interface:
                                tagged_interface['type'] = 'dot1q'

                    if 'oam' not in connection:
                        connection['oam'] = dict()
                    if 'md-name' not in connection['oam']:
                        connection['oam']['md-name'] = 'fake-md-name'
                    if 'md-level' not in connection['oam']:
                        connection['oam']['md-level'] = 0

                if 'service' not in site_network_access:
                    site_network_access['service'] = dict()
                if 'svc-mtu' not in site_network_access['service']:
                    site_network_access['service']['svc-mtu'] = DEFAULT_MTU

            context_client = ContextClient()
            vpn_services = list()
            for service in get_services(context_client):
                if service.service_type not in (
                    ServiceTypeEnum.SERVICETYPE_L2NM,
                    ServiceTypeEnum.SERVICETYPE_L3NM,
                ):
                    continue

                # De-duplicate services uuid/names in case service_uuid == service_name
                vpn_ids = {service.service_id.service_uuid.uuid, service.name}
                for vpn_id in vpn_ids:
                    vpn_services.append({
                        'vpn-id': vpn_id,
                        'frame-delivery': {
                            'multicast-gp-port-mapping': 'ietf-l2vpn-svc:static-mapping'
                        },
                        'ce-vlan-preservation': True,
                        'ce-vlan-cos-preservation': True,
                    })

            MSG = '[_prepare_request_payload] vpn_services={:s}'
            LOGGER.debug(MSG.format(str(vpn_services)))

            request_data = {'ietf-l2vpn-svc:l2vpn-svc': {
                'vpn-services': {
                    'vpn-service': vpn_services
                },
                'sites': {'site': [{
                    'site-id': site_id,
                    'default-ce-vlan-id': 1,
                    'management': {'type': 'provider-managed'},
                    'locations': {'location': [
                        {'location-id': location_ref}
                        for location_ref in location_refs
                    ]},
                    'devices': {'device': [
                        {'device-id': device_ref, 'location': location_ref}
                        for device_ref, location_ref in device_refs.items()
                    ]},
                    'site-network-accesses': {
                        'site-network-access': site_network_accesses
                    }
                }]}
            }}

            MSG = '[_prepare_request_payload] request_data={:s}'
            LOGGER.debug(MSG.format(str(request_data)))
            return request_data

        errors.append('Unexpected request: {:s}'.format(str(request_data)))
        return None

    def _process_site_network_accesses(self, site_id : str, request_data : Dict) -> List[Dict]:
        errors = list()
        request_data = self._prepare_request_payload(site_id, request_data, errors)
        if len(errors) > 0: return errors

        yang_validator = YangValidator('ietf-l2vpn-svc')
        request_data = yang_validator.parse_to_dict(request_data)
        yang_validator.destroy()

        sites = (
            request_data.get('l2vpn-svc', dict())
            .get('sites', dict())
            .get('site', list())
        )
        for site in sites:
            site_network_accesses = (
                site.get('site-network-accesses', dict())
                .get('site-network-access', list())
            )
            for site_network_access in site_network_accesses:
                process_site_network_access(site_id, site_network_access, errors)

        return errors
