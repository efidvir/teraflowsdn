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
from common.proto import kpi_manager_pb2
from common.proto.kpi_sample_types_pb2 import KpiSampleType
from src.telemetry.backend.service.collectors.gnmi_oc.KPI import KPI
from common.proto import telemetry_frontend_pb2


# ---> KPI Manager messages creation for testing

def create_kpi_descriptor_request(descriptor_name: str = "Test_name"):
    _create_kpi_request                                    = kpi_manager_pb2.KpiDescriptor()
    _create_kpi_request.kpi_id.kpi_id.uuid                 = "6e22f180-ba28-4641-b190-2287bf447777"
    _create_kpi_request.kpi_description                    = descriptor_name
    _create_kpi_request.kpi_sample_type                    = KpiSampleType.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER
    _create_kpi_request.device_id.device_uuid.uuid         = "ddb3ef8e-ee65-5cf9-9d21-dac56a27f85b"         # confirm for TFS
    _create_kpi_request.service_id.service_uuid.uuid       = "b2a60c5b-8c46-5707-a64a-9c6539d395f2"
    # _create_kpi_request.slice_id.slice_uuid.uuid           = 'SLC1'
    _create_kpi_request.endpoint_id.endpoint_uuid.uuid     = "2"
    # _create_kpi_request.connection_id.connection_uuid.uuid = 'CON1' 
    # _create_kpi_request.link_id.link_uuid.uuid             = 'LNK1' 
    return _create_kpi_request


# ---> Telemetry messages creation for testing

devices = {
    'mgon': {
        'host'       : '172.17.254.24',
        'port'       : '50061',
        'username'   : 'admin',
        'password'   : 'admin',
        'insecure'   : True,
        'kpi'        : KPI.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER,
        #'resource': 'oc-wave-router:wavelength-router/fsmgon:optical-bands/optical-band[index=4]/state/optical-power-total-input/instant',
        'resource'   : 'wavelength-router',            #TODO: verify resource name form mg-on model
        'endpoint'   : '2',
        'skip_verify': True
    },
}

def create_basic_sub_request_parameters() -> dict:

    device = devices['mgon']
    if device:
        return {
            'host'              : device['host'],
            'port'              : device['port'],
            'username'          : device['username'],
            'password'          : device['password'],
            'connect_timeout'   : 15,
            'insecure'          : device['insecure'],
            'mode'              : 'sample',             # Subscription internal mode posibly: on_change, poll, sample
            'sample_interval'   : 10,                   # This should be in seconds units
            'duration'          : 300.0,                # Duration in seconds for how long to receive samples
            'kpi'               : device['kpi'],
            'resource'          : device['resource'],
            'endpoint'          : device['endpoint'],
        }
    return {}


def create_collector_request():
    _create_collector_request                                = telemetry_frontend_pb2.Collector()
    _create_collector_request.collector_id.collector_id.uuid = "efef4d95-1cf1-43c4-9742-95c283dddddd"
    _create_collector_request.kpi_id.kpi_id.uuid             = "6e22f180-ba28-4641-b190-2287bf447777"
    _create_collector_request.duration_s                     = 300
    _create_collector_request.interval_s                     = 10
    _create_collector_request.int_collector.context_id       = "43813baf-195e-5da6-af20-b3d0922e71a7"
    return _create_collector_request
