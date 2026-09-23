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

from typing import Optional
import uuid
from common.proto import kpi_manager_pb2
from common.proto.kpi_sample_types_pb2 import KpiSampleType
from src.telemetry.backend.service.collectors.gnmi_oc.KPI import KPI

# Test device connection parameters
devices = {
    'device1': {
        'host'    : '10.1.1.86',
        'port'    : '6030',
        'username': 'ocnos',
        'password': 'ocnos',
        'insecure': True,
        'kpi'     : KPI.KPISAMPLETYPE_PACKETS_RECEIVED,
        'resource': 'interface',
        'endpoint': 'Management0',
    },
    'device2': {
        'host'    : '10.1.1.87',
        'port'    : '6030',
        'username': 'ocnos',
        'password': 'ocnos',
        'insecure': True,
        'kpi'     : KPI.KPISAMPLETYPE_PACKETS_RECEIVED,
        'resource': 'interface',
        'endpoint': 'Management0',
    },
    'device3': {
        'host'    : '172.20.20.101',
        'port'    : '6030',
        'username': 'admin',
        'password': 'admin',
        'insecure': True,
        'kpi'     : KPI.KPISAMPLETYPE_PACKETS_RECEIVED,
        'resource': 'interface',
        'endpoint': 'Management0',
    },
    'mgon': {
        'host'       : '172.17.254.24',
        'port'       : '50061',
        'username'   : 'admin',
        'password'   : 'admin',
        'insecure'   : True,
        'kpi'        : KPI.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER,
        'resource'   : 'wavelength-router',    #TODO: verify resource name form mg-on model
        'endpoint'   : '1',
        'skip_verify': True,
    },
}

def creat_basic_sub_request_parameters() -> dict:

    device = devices['mgon']
    if device:
        kpi      = device['kpi']
        resource = device['resource']
        endpoint = device['endpoint']
        return {
            'target'            : (device['host'], device['port']),
            'username'          : device['username'],
            'password'          : device['password'],
            'connect_timeout'   : 15,
            'insecure'          : device['insecure'],
            'skip_verify'       : device.get('skip_verify', True),
            'mode'              : 'sample',            # Subscription internal mode posibly: on_change, poll, sample
            'sample_interval_ns': '3s',  
            'sample_interval'   : '10s',
            'kpi'               : kpi,
            'resource'          : resource,
            'endpoint'          : endpoint,
        }
    return {}

def create_kpi_descriptor_request(descriptor_name: str = "Test_name"):
    _create_kpi_request                                    = kpi_manager_pb2.KpiDescriptor()
    _create_kpi_request.kpi_id.kpi_id.uuid                 = "6e22f180-ba28-4641-b190-2287bf447777"
    _create_kpi_request.kpi_description                    = descriptor_name
    _create_kpi_request.kpi_sample_type                    = KpiSampleType.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER
    _create_kpi_request.device_id.device_uuid.uuid         = "ddb3ef8e-ee65-5cf9-9d21-dac56a27f85b"        # confirm for TFS
    _create_kpi_request.service_id.service_uuid.uuid       = "fd7a7b7d-4cd1-5453-bf79-47c7b53c31da"
    # _create_kpi_request.slice_id.slice_uuid.uuid           = 'SLC1'
    # _create_kpi_request.endpoint_id.endpoint_uuid.uuid     = "END1"
    # _create_kpi_request.connection_id.connection_uuid.uuid = 'CON1' 
    # _create_kpi_request.link_id.link_uuid.uuid             = 'LNK1' 
    return _create_kpi_request

