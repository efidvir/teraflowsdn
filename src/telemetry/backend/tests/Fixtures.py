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
import logging
import os

from context.client.ContextClient        import ContextClient
from device.client.DeviceClient          import DeviceClient
from service.client.ServiceClient        import ServiceClient
from kpi_manager.client.KpiManagerClient import KpiManagerClient

# Import ENV variables
_ip_kpi_address     = os.getenv('IP_KPI',  None)
_ip_tele_address    = os.getenv('IP_TELE', None)
_ip_context_address = os.getenv('IP_CONTEXT', None)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


@pytest.fixture(scope='session')
def context_client():
    _client = ContextClient(host=_ip_context_address)
    _client.connect()
    LOGGER.info('Yielding Connected ContextClient...')
    yield _client
    LOGGER.info('Closing ContextClient...')
    _client.close()

@pytest.fixture(scope='session')
def device_client():
    _client = DeviceClient(host="10.152.183.212")
    _client.connect()
    LOGGER.info('Yielding Connected DeviceClient...')
    yield _client
    LOGGER.info('Closing DeviceClient...')
    _client.close()

@pytest.fixture(scope='session')
def service_client():
    _client = ServiceClient(host="10.152.183.98")
    _client.connect()
    LOGGER.info('Yielding Connected ServiceClient...')
    yield _client
    LOGGER.info('Closing ServiceClient...')
    _client.close()

@pytest.fixture(scope='session')
def kpi_manager_client():
    _client = KpiManagerClient(host=_ip_kpi_address)
    _client.connect()
    LOGGER.info('Yielding Connected KpiManagerClient...')
    yield _client
    LOGGER.info('Closed KpiManagerClient...')
    _client.close()

