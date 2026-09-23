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

import pytest
from common.Constants import ServiceNameEnum
from common.Settings import get_service_host, get_service_port_http
from context.client.ContextClient import ContextClient
from device.client.DeviceClient import DeviceClient
from service.client.ServiceClient import ServiceClient
from .MockOSM import MockOSM
from .OSM_Constants import WIM_MAPPING

NBI_ADDRESS  = get_service_host(ServiceNameEnum.NBI)
NBI_PORT     = get_service_port_http(ServiceNameEnum.NBI)
NBI_USERNAME = 'admin'
NBI_PASSWORD = 'admin'
NBI_BASE_URL = ''

@pytest.fixture(scope='session')
def osm_wim() -> MockOSM:
    wim_url = 'http://{:s}:{:d}'.format(NBI_ADDRESS, NBI_PORT)
    return MockOSM(wim_url, WIM_MAPPING, NBI_USERNAME, NBI_PASSWORD)

@pytest.fixture(scope='session')
def context_client() -> ContextClient:
    _client = ContextClient()
    yield _client
    _client.close()

@pytest.fixture(scope='session')
def device_client() -> DeviceClient:
    _client = DeviceClient()
    yield _client
    _client.close()

@pytest.fixture(scope='session')
def service_client() -> ServiceClient:
    _client = ServiceClient()
    yield _client
    _client.close()
