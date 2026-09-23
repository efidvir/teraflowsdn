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
import pytest
import time

from ..add_devices import load_topology
from ..Fixtures import context_client, device_client, service_client, kpi_manager_client
from .messages import creat_basic_sub_request_parameters
from .messages import create_kpi_descriptor_request
from common.proto.context_pb2 import TopologyId, ContextId, Empty
from common.proto.kpi_manager_pb2 import KpiId
from common.tools.context_queries.Topology import get_topology
from common.tools.kafka.Variables import KafkaTopic
from common.proto.kpi_manager_pb2 import KpiId, KpiDescriptor

from telemetry.backend.service.HelperMethods import get_collector_by_kpi_id, get_subscription_parameters
from telemetry.backend.service.collector_api.DriverFactory import DriverFactory
from telemetry.backend.service.collector_api.DriverInstanceCache import DriverInstanceCache, preload_drivers
from telemetry.backend.service.collectors import COLLECTORS
from telemetry.backend.service.collectors.gnmi_oc.GnmiOpenConfigCollector import GNMIOpenConfigCollector
from telemetry.backend.service.TelemetryBackendService import TelemetryBackendService


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)8s [%(name)s - %(funcName)s()]: %(message)s",
)
LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------
# -------------------- EXTRA HELPER METHODS --------------------
# --------------------------------------------------------------

# ----- Add Topology -----
# def test_add_to_topology(context_client, device_client):
#     load_topology(context_client, device_client)

# ----- Automatically GET and REMOVE Topology and Context -----
# - This method will remove the topology and context from the DB and only work if there is no devices and links present in the topology.
    # + Otherwise it will raise forigen key error.
    # + First remove all devices and links from the topology through GUI.
# def test_get_and_remove_topology_context(context_client):
#     response = get_topology(context_client = context_client, topology_uuid = "admin", context_uuid = "admin")
#     LOGGER.info(f"Topology: {response}")
#     assert response is not None
#     # create context_id and topology_id from response
#     context_id  = ContextId()
#     context_id  = response.topology_id.context_id
#     topology_id = TopologyId()
#     topology_id = response.topology_id
#     # Remove Topology
#     topology_id.context_id.CopyFrom(context_id)
#     response    = context_client.RemoveTopology(topology_id)
#     LOGGER.info(f"Topology removed Sucessfully")
#     # Remove Context
#     response    = context_client.RemoveContext(context_id)
#     LOGGER.info(f"Context removed Sucessfully")

# ----- Set KPI Descriptor -----
# - This method will set a KPI Descriptor in the KPI DB.
    # + In the messages file, add the correct device_uuid that already exist in the topology. 
# def test_SetKpiDescriptor(kpi_manager_client):
#     LOGGER.info(" >>> test_SetKpiDescriptor: START <<< ")
#     response = kpi_manager_client.SetKpiDescriptor(create_kpi_descriptor_request())
#     LOGGER.info("Response gRPC message object: {:}".format(response))
#     assert isinstance(response, KpiId)

# --------------------------------------------------------------
# -------------------- REQUIRE FIXTURES ------------------------
# --------------------------------------------------------------

@pytest.fixture(autouse=True)
def log_all_methods(request):
    '''
    This fixture logs messages before and after each test function runs, indicating the start and end of the test.
    The autouse=True parameter ensures that this logging happens automatically for all tests in the module.
    '''
    LOGGER.info(f" >>>>> Starting test: {request.node.name} ")
    yield
    LOGGER.info(f" <<<<< Finished test: {request.node.name} ")


@pytest.fixture
def sub_parameters():
    """Fixture to provide subscription parameters."""
    return creat_basic_sub_request_parameters()


@pytest.fixture
def collector(sub_parameters):
    """Fixture to create and connect GNMI collector."""
    collector = GNMIOpenConfigCollector(
        username = sub_parameters['username'],
        password = sub_parameters['password'],
        insecure = sub_parameters['insecure'],
        address  = sub_parameters['target'][0],
        port     = sub_parameters['target'][1],
    )
    collector.Connect()
    yield collector
    collector.Disconnect()


@pytest.fixture
def subscription_data(sub_parameters):
    """Fixture to provide subscription data."""
    # It should return a list of tuples with subscription parameters.
    return [
        (
            "sub_id_123",
            {
                "kpi"      : sub_parameters['kpi'],
                "endpoint" : sub_parameters['endpoint'],
                "resource" : sub_parameters['resource'],
            },
            float(10.0),
            float(5.0),
        ),
    ]

@pytest.fixture
def telemetry_backend_service():
    LOGGER.info('Initializing TelemetryBackendService...')

    KafkaTopic.create_all_topics()

    # Initialize Driver framework
    driver_factory        = DriverFactory(COLLECTORS)
    driver_instance_cache = DriverInstanceCache(driver_factory)

    _service              = TelemetryBackendService(driver_instance_cache)
    _service.start()

    LOGGER.info('Preloading collectors...')
    preload_drivers(driver_instance_cache)

    LOGGER.info('Yielding TelemetryBackendService...')
    yield _service

    LOGGER.info('Terminating TelemetryBackendService...')
    _service.stop()
    LOGGER.info('Terminated TelemetryBackendService...')


# --------------------------------------------------------------
# -------------------- ACTUAL TEST CASES -----------------------
# --------------------------------------------------------------

# This test validates the correct selection of a collector based on a KPI ID. (Not for Gitlab CI pipeline)
# Preconditions:
    # - A device must be added in Context DB with correct device_id.
        # + Uncomment test_add_to_topology() in helper methods section to add a device.
    # - A KPI Descriptor must be added in KPI DB with correct device_id.
        # + Uncomment test_SetKpiDescriptor() in helper methods section to add a KPI Descriptor.
    # - Kafka should be exposed externally 'kubectl port-forward -n kafka service/kafka-service 9092:9092'.
 
def test_helper_get_collector_by_kpi_id(kpi_manager_client, context_client):
    LOGGER.info("Testing get_collector_by_kpi_id...")

    driver_factory        = DriverFactory(COLLECTORS)
    driver_instance_cache = DriverInstanceCache(driver_factory)
    
    _kpi_descriptor = create_kpi_descriptor_request()
    kpi_id          = _kpi_descriptor.kpi_id
    
    try:
        response = kpi_manager_client.GetKpiDescriptor(kpi_id)
        if isinstance(response, KpiDescriptor):
            LOGGER.info("KPI Descriptor already exists with ID: %s. Deleting it for clean testing.", kpi_id.kpi_id.uuid)
            kpi_manager_client.DeleteKpiDescriptor(kpi_id)
    except Exception as e:
        LOGGER.info("No existing KPI Descriptor found with ID: %s. Proceeding to create it. Error: %s", kpi_id.kpi_id.uuid, str(e))

    # _kpi_descriptor = create_kpi_descriptor_request()
    response = kpi_manager_client.SetKpiDescriptor(_kpi_descriptor)
    LOGGER.info("KPI Descriptor created with ID: %s", response.kpi_id.uuid)
    

    kpi_uuid = kpi_id.kpi_id.uuid
    collector = get_collector_by_kpi_id(
        kpi_uuid,
        kpi_manager_client,
        context_client,
        driver_instance_cache
    )
    assert collector is not None
    assert isinstance(collector, GNMIOpenConfigCollector)
    LOGGER.info(f"Collector for KPI ID {kpi_uuid} found: {collector.__class__.__name__}")
    
    LOGGER.info("Testing get_subscription_parameters...")
    resource = 'wavelength-router'
    duration = 10.0
    interval = 5.0
    subscriptions = get_subscription_parameters(
                kpi_uuid,
                kpi_manager_client,
                context_client,
                duration,
                interval,
                resource,
            )
    assert subscriptions is not None
    assert len(subscriptions) > 0
    LOGGER.info(f"Subscription parameters for KPI ID {kpi_uuid}: {subscriptions}")

