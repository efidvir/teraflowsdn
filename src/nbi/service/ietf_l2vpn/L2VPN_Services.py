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
from nbi.service._tools.Authentication import HTTP_AUTH
from nbi.service._tools.HttpStatusCodes import HTTP_CREATED, HTTP_SERVERERROR
from .Handlers import process_site, process_vpn_service
from .YangValidator import YangValidator

LOGGER = logging.getLogger(__name__)

class L2VPN_Services(Resource):
    @HTTP_AUTH.login_required
    def get(self):
        return {}

    @HTTP_AUTH.login_required
    def post(self):
        if not request.is_json: raise UnsupportedMediaType('JSON payload is required')
        request_data : Dict = request.json
        LOGGER.debug('Request: {:s}'.format(str(request_data)))

        errors = list()
        if 'ietf-l2vpn-svc:l2vpn-svc' in request_data:
            # processing single (standard) request formatted as:
            #{
            #  "ietf-l2vpn-svc:l2vpn-svc": {
            #    "vpn-services": {
            #      "vpn-service": [
            errors.extend(self._process_l2vpn(request_data))
        elif 'ietf-l2vpn-svc:vpn-service' in request_data:
            # processing OSM-style payload request formatted as:
            #{
            #  "ietf-l2vpn-svc:vpn-service": [
            vpn_services = request_data['ietf-l2vpn-svc:vpn-service']

            # Add mandatory fields OSM RO driver skips
            for vpn_service in vpn_services:
                if 'ce-vlan-preservation' not in vpn_service:
                    vpn_service['ce-vlan-preservation'] = True
                if 'ce-vlan-cos-preservation' not in vpn_service:
                    vpn_service['ce-vlan-cos-preservation'] = True
                if 'frame-delivery' not in vpn_service:
                    vpn_service['frame-delivery'] = dict()
                if 'multicast-gp-port-mapping' not in vpn_service['frame-delivery']:
                    vpn_service['frame-delivery']['multicast-gp-port-mapping'] = \
                        'ietf-l2vpn-svc:static-mapping'

            request_data = {
                'ietf-l2vpn-svc:l2vpn-svc': {
                    'vpn-services': {
                        'vpn-service': vpn_services
                    }
                }
            }
            errors.extend(self._process_l2vpn(request_data))
        else:
            errors.append('Unexpected request: {:s}'.format(str(request_data)))

        if len(errors) > 0:
            LOGGER.error('Errors: {:s}'.format(str(errors)))
        else:
            LOGGER.debug('Errors: {:s}'.format(str(errors)))

        response = jsonify(errors)
        response.status_code = HTTP_CREATED if len(errors) == 0 else HTTP_SERVERERROR
        return response

    def _process_l2vpn(self, request_data : Dict) -> List[Dict]:
        yang_validator = YangValidator('ietf-l2vpn-svc')
        request_data = yang_validator.parse_to_dict(request_data)
        yang_validator.destroy()

        errors = list()

        vpn_services = (
            request_data.get('l2vpn-svc', dict())
            .get('vpn-services', dict())
            .get('vpn-service', list())
        )
        for vpn_service in vpn_services:
            process_vpn_service(vpn_service, errors)

        sites = (
            request_data.get('l2vpn-svc', dict())
            .get('sites', dict())
            .get('site', list())
        )
        for site in sites:
            process_site(site, errors)

        return errors
