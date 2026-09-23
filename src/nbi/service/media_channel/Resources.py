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
from common.proto.context_pb2 import ConfigActionEnum, ConfigRule, DeviceId, Device, Service, ServiceTypeEnum, ServiceStatusEnum
from device.client.DeviceClient import DeviceClient
from service.client.ServiceClient import ServiceClient
import requests
LOGGER = logging.getLogger(__name__)

class MediaChannelService(Resource):
    def __init__(self):
        super().__init__()
        self.device_client = DeviceClient()
        self.service_client = ServiceClient()

    def post(self, allocationId: str):
        LOGGER.info("Received POST request for allocationId: %s", allocationId)

        data = request.get_json()
        LOGGER.info("Media Channel data: %s", json.dumps(data, indent=2))

        required_str_fields = ['input_sip', 'output_sip', 'uuid', 'tenant_uuid', 'direction',
                               'layer_protocol_name', 'layer_protocol_qualifier',
                               'granularity', 'grid_type','bw', 'lower_frequency_mhz',
                               'upper_frequency_mhz']
        optional_str_fields = ['capacity_unit', 'capacity_value', 'route_objective_function', 'url']

        for field in required_str_fields:
            if field not in data:
                return {'status': 'error', 'message': f'Missing required field: {field}'}, 400
            if not isinstance(data[field], str):
                return {'status': 'error', 'message': f'Field {field} must be a string'}, 400

        for field in optional_str_fields:
            if field in data and not isinstance(data[field], str):
                return {'status': 'error', 'message': f'Field {field} must be a string'}, 400
        if 'link_uuid_path' in data and not isinstance(data['link_uuid_path'], list):
            return {'status': 'error', 'message': 'Field link_uuid_path must be a list'}, 400

        try:
            service = Service()
            service.service_id.service_uuid.uuid = data["uuid"]
            service.service_id.context_id.context_uuid.uuid = "admin"
            service.service_type = ServiceTypeEnum.SERVICETYPE_TAPI_LSP
            service.service_status.service_status = ServiceStatusEnum.SERVICESTATUS_ACTIVE
            service.name = f"MediaChannel-{allocationId}"

            service_response = self.service_client.CreateService(service)
            LOGGER.info("Created TFS service: %s", service_response)

        except Exception as e:
            LOGGER.error("Failed to create TFS service: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': f'Failed to create TFS service: {str(e)}'}, 500

        device_id_str = data.get('device_id')
        if device_id_str:
            LOGGER.info("Processing device_id: %s", device_id_str)
            try:
                device = Device()
                device.device_id.device_uuid.uuid = device_id_str

                config_rule = ConfigRule()
                config_rule.action = ConfigActionEnum.CONFIGACTION_SET
                config_rule.custom.resource_key = f'/media_channel/service/{data["uuid"]}'

                service_data = {
                    "input_sip": data["input_sip"],
                    "output_sip": data["output_sip"],
                    "uuid": data["uuid"],
                    "bw": str(data["bw"]),
                    "tenant_uuid": data["tenant_uuid"],
                    "layer_protocol_name": data["layer_protocol_name"],
                    "layer_protocol_qualifier": data["layer_protocol_qualifier"],
                    "lower_frequency_mhz": str(data["lower_frequency_mhz"]),
                    "upper_frequency_mhz": str(data["upper_frequency_mhz"]),
                    "link_uuid_path": data.get("link_uuid_path", []),
                    "granularity": data["granularity"],
                    "grid_type": data["grid_type"],
                    "direction": data["direction"]
                }

                if "capacity_unit" in data:
                    service_data["capacity_unit"] = data["capacity_unit"]
                if "capacity_value" in data:
                    service_data["capacity_value"] = data["capacity_value"]
                if "route_objective_function" in data:
                    service_data["route_objective_function"] = data["route_objective_function"]
                if "url" in data:
                    service_data["url"] = data["url"]

                config_rule.custom.resource_value = json.dumps(service_data)

                device.device_config.config_rules.append(config_rule)
                self.device_client.ConfigureDevice(device)
                LOGGER.info("Configured device %s with media channel service %s", device_id_str, data["uuid"])

            except Exception as e:
                LOGGER.error("Failed to configure device: %s", str(e))
                return {'status': 'error', 'message': f'Failed to configure device: {str(e)}'}, 500

        return {
            'status': 'success',
            'message': f'Media channel service created for {allocationId}',
            'allocationId': allocationId,
            'service_uuid': data.get('uuid')
        }, 201

    def delete(self, allocationId: str):
        LOGGER.info("Received DELETE request for allocationId: %s", allocationId)
        aux = None
        if ":" in allocationId:
            aux = allocationId.split(":")
            optical_slice = aux[0]
            service_uuid = aux[1]
        else:
            service_uuid = allocationId
        try:
            from common.proto.context_pb2 import ServiceId

            service_id = ServiceId()
            service_id.service_uuid.uuid = service_uuid
            service_id.context_id.context_uuid.uuid = "admin"

            self.service_client.DeleteService(service_id)
            LOGGER.info("Deleted TFS service: %s", service_uuid)

        except Exception as e:
            LOGGER.error("Failed to delete TFS service: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': f'Failed to delete TFS service: {str(e)}'}, 500

        headers = {
                    "Content-Type": "application/json",
                    "Expect": ""
                }
        try:
            if aux is not None:
                url = f'http://11.1.1.101:4900/{optical_slice}/restconf/data/tapi-common:context/tapi-connectivity:connectivity-context/connectivity-service={service_uuid}'
                response = requests.delete(url, headers=headers, timeout=10)
                LOGGER.info("Deleted media channel from device %s: %s", optical_slice, url)
            else:
                url = f'http://11.1.1.101:4900/restconf/data/tapi-common:context/tapi-connectivity:connectivity-context/connectivity-service={service_uuid}'
                response = requests.delete(url, headers=headers, timeout=10)
                LOGGER.info("Deleted media channel from device %s: %s", service_uuid, url)

        except Exception as e:
            LOGGER.warning("Failed to delete from device: %s", str(e))
            return {'status': 'error', 'message': f'Failed to delete from device: {str(e)}'}, 500


        return {
            'status': 'success',
            'message': f'Media channel service deleted for {allocationId}',
            'allocationId': allocationId,
            'service_uuid': service_uuid
        }, 200
