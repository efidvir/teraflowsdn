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


import os, pytest
import logging
from typing import Union

from common.Constants import ServiceNameEnum
from common.Settings import ( 
    ENVVAR_SUFIX_SERVICE_HOST, ENVVAR_SUFIX_SERVICE_PORT_GRPC, get_env_var_name, get_service_port_grpc)
from common.tests.MockServicerImpl_Context import MockServicerImpl_Context
from common.proto.context_pb2_grpc import add_ContextServiceServicer_to_server

from common.tools.service.GenericGrpcService import GenericGrpcService

from kpi_manager.service.KpiManagerService import KpiManagerService
from kpi_manager.client.KpiManagerClient import KpiManagerClient



LOGGER = logging.getLogger(__name__)

LOCAL_HOST = '127.0.0.1'

KPIMANAGER_SERVICE_PORT = get_service_port_grpc(ServiceNameEnum.KPIMANAGER)  # type: ignore
os.environ[get_env_var_name(ServiceNameEnum.KPIMANAGER, ENVVAR_SUFIX_SERVICE_HOST     )] = str(LOCAL_HOST)
os.environ[get_env_var_name(ServiceNameEnum.KPIMANAGER, ENVVAR_SUFIX_SERVICE_PORT_GRPC)] = str(KPIMANAGER_SERVICE_PORT)


# NOTE: ---> For local testing, without need of running TFS services.

class MockContextService(GenericGrpcService):
    # Mock Service implementing Context to simplify unitary tests of Monitoring

    def __init__(self, bind_port: Union[str, int]) -> None:
        super().__init__(bind_port, LOCAL_HOST, enable_health_servicer=False, cls_name='MockService')

    # pylint: disable=attribute-defined-outside-init
    def install_servicers(self):
        self.context_servicer = MockServicerImpl_Context()
        add_ContextServiceServicer_to_server(self.context_servicer, self.server)

# This fixture will be requested by test cases and last during testing session
@pytest.fixture(scope='session')
def kpi_manager_service():
    LOGGER.info('Initializing KpiManagerService...')
    _service = KpiManagerService()
    _service.start()

    # yield the server, when test finishes, execution will resume to stop it
    LOGGER.info('Yielding KpiManagerService...')
    yield _service

    LOGGER.info('Terminating KpiManagerService...')
    _service.stop()

    LOGGER.info('Terminated KpiManagerService...')

# This fixture will be requested by test cases and last during testing session.
# The client requires the server, so client fixture has the server as dependency.
# def monitoring_client(monitoring_service : MonitoringService): (Add for better understanding)
@pytest.fixture(scope='session')
def kpi_manager_client(kpi_manager_service : KpiManagerService): # pylint: disable=redefined-outer-name,unused-argument
    LOGGER.info('Initializing KpiManagerClient...')
    _client = KpiManagerClient()

    # yield the server, when test finishes, execution will resume to stop it
    LOGGER.info('Yielding KpiManagerClient...')
    yield _client

    LOGGER.info('Closing KpiManagerClient...')
    _client.close()

    LOGGER.info('Closed KpiManagerClient...')