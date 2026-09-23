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
import json
from flask_restful import Resource, request
from common.proto.context_pb2 import ConfigActionEnum, ConfigRule, Device, Service, ServiceTypeEnum, ServiceStatusEnum
from device.client.DeviceClient import DeviceClient
from service.client.ServiceClient import ServiceClient
import requests
LOGGER = logging.getLogger(__name__)

class OpticalSliceService(Resource):
    def __init__(self):
        super().__init__()
        self.device_client = DeviceClient()
        self.service_client = ServiceClient()

    def post(self, sliceId: str):
        LOGGER.info("Received POST request for optical slice: %s", sliceId)

        data = request.get_json()
        LOGGER.info("Optical Slice data: %s", json.dumps(data, indent=2))

        if 'data' in data and 'tapi-common:context' in data['data']:
            context = data['data']['tapi-common:context']
        elif 'tapi-common:context' in data:
            context = data['tapi-common:context']
        else:
            return {'status': 'error', 'message': 'Missing tapi-common:context'}, 400

        slice_uuid = context.get('uuid')
        service_interface_points = context.get('service-interface-point', [])
        topology_context = context.get('tapi-topology:topology-context', {})

        LOGGER.info(f"Service Interface Points: {len(service_interface_points)}")

        try:
            service = Service()
            service.service_id.service_uuid.uuid = sliceId
            service.service_id.context_id.context_uuid.uuid = "admin"
            service.service_type = ServiceTypeEnum.SERVICETYPE_TAPI_CONNECTIVITY_SERVICE
            service.service_status.service_status = ServiceStatusEnum.SERVICESTATUS_ACTIVE
            service.name = f"OpticalSlice-{slice_uuid}"

            service_response = self.service_client.CreateService(service)
            LOGGER.info("Created TFS optical slice service: %s", service_response)

        except Exception as e:
            LOGGER.error("Failed to create TFS optical slice service: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': f'Failed to create TFS service: {str(e)}'}, 500

        device_id_str = "TFS-TAPI"
        try:
            device = Device()
            device.device_id.device_uuid.uuid = device_id_str
            config_rule = ConfigRule()
            config_rule.action = ConfigActionEnum.CONFIGACTION_SET
            config_rule.custom.resource_key = f'/optical_slice/context/{slice_uuid}'
            config_rule.custom.resource_value = json.dumps(data)
            device.device_config.config_rules.append(config_rule)
            self.device_client.ConfigureDevice(device)
            LOGGER.info("Configured device %s with optical slice %s", device_id_str, sliceId)

        except Exception as e:
            LOGGER.error("Failed to configure device: %s", str(e))
            return {'status': 'error', 'message': f'Failed to configure device: {str(e)}'}, 500

        return {
            'status': 'success',
            'message': f'Optical slice created for {sliceId}',
            'sliceId': sliceId,
            'slice_uuid': slice_uuid
        }, 201

    def delete(self, sliceId: str):
        LOGGER.info("Received DELETE request for optical slice: %s", sliceId)

        try:
            from common.proto.context_pb2 import ServiceId

            service_id = ServiceId()
            service_id.service_uuid.uuid = sliceId
            service_id.context_id.context_uuid.uuid = "admin"

            self.service_client.DeleteService(service_id)
            LOGGER.info("Deleted TFS service: %s", sliceId)

        except Exception as e:
            LOGGER.error("Failed to delete TFS optical slice service: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': f'Failed to delete TFS service: {str(e)}'}, 500

        headers = {
                    "Content-Type": "application/json",
                    "Expect": ""
                }
        try:
            # TODO Dynamic IP
            url = f'http://11.1.1.101:4900/restconf/data/tapi-common:context={sliceId}'
            response = requests.delete(url, headers=headers, timeout=10)
            LOGGER.info("Deleted optical slice from device %s: %s", sliceId, url)

        except Exception as e:
            LOGGER.warning("Failed to delete from device: %s", str(e))
            return {'status': 'error', 'message': f'Failed to delete from device: {str(e)}'}, 500


        return {
            'status': 'success',
            'message': f'Optical Slice deleted for {sliceId}',
            'sliceId': sliceId,
            'service_uuid': sliceId
        }, 200
