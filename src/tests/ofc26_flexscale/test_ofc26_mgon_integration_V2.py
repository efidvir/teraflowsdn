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
import time
from common.proto.kpi_manager_pb2 import KpiId
from common.proto.telemetry_frontend_pb2 import CollectorId
import time
import threading

from common.proto import kpi_manager_pb2
from common.proto.kpi_sample_types_pb2 import KpiSampleType

from src.telemetry.backend.service.collector_api import DriverFactory
from tests.ofc26_flexscale.test_ofc26_messages import create_kpi_descriptor_request, create_collector_request
from src.tests.ofc26_flexscale.test_ofc26_messages import create_basic_sub_request_parameters

from src.telemetry.backend.service.TelemetryBackendService import DriverInstanceCache, TelemetryBackendService


WITH_TFS = True     #True/False
if WITH_TFS:
    from .Fixtures import kpi_manager_client, telemetry_frontend_client
else:
    from .mock_tfs_services import kpi_manager_client

LOGGER = logging.getLogger(__name__)


def create_kpi_descriptor_request(descriptor_name: str = "Test_name"):
    _create_kpi_request                                    = kpi_manager_pb2.KpiDescriptor()
    _create_kpi_request.kpi_id.kpi_id.uuid                 = "6e22f180-ba28-4641-b190-2287bf447777"
    _create_kpi_request.kpi_description                    = descriptor_name
    _create_kpi_request.kpi_sample_type                    = KpiSampleType.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER
    _create_kpi_request.device_id.device_uuid.uuid         = "ddb3ef8e-ee65-5cf9-9d21-dac56a27f85b"         # confirm for TFS
    _create_kpi_request.service_id.service_uuid.uuid       = "b2a60c5b-8c46-5707-a64a-9c6539d395f2"
    # _create_kpi_request.slice_id.slice_uuid.uuid           = 'SLC1'
    # _create_kpi_request.endpoint_id.endpoint_uuid.uuid     = str(uuid.uuid4())
    # _create_kpi_request.connection_id.connection_uuid.uuid = 'CON1' 
    # _create_kpi_request.link_id.link_uuid.uuid             = 'LNK1' 
    return _create_kpi_request

# def create_collector_filter():
#     _create_collector_filter = telemetry_frontend_pb2.CollectorFilter()
#     kpi_id_obj               = KpiId()
#     # kpi_id_obj.kpi_id.uuid   = str(uuid.uuid4())
#     kpi_id_obj.kpi_id.uuid   = "8c5ca114-cdc7-4081-b128-b667fd159832"
#     _create_collector_filter.kpi_id.append(kpi_id_obj)
#     return _create_collector_filter


def test_Complete_MGON_Integration(kpi_manager_client, telemetry_frontend_client):
    
    # 1. KPI Descriptor Creation
    LOGGER.info(" >>> test_Complete_MGON_Integration: START <<< ")
    kpi_descriptor_obj = create_kpi_descriptor_request()
    _search_kpi_id     = kpi_descriptor_obj.kpi_id
    
    try:
        response = kpi_manager_client.GetKpiDescriptor(_search_kpi_id)
        if isinstance(response, kpi_manager_pb2.KpiDescriptor):
            LOGGER.info("KPI Descriptor already exists with ID: %s. Skipping creation.", _search_kpi_id.kpi_id.uuid)
    except Exception as e:
        LOGGER.info("No existing KPI Descriptor found with ID: %s. Proceeding to create it. Error: %s", _search_kpi_id.kpi_id.uuid, str(e))
        response = kpi_manager_client.SetKpiDescriptor(kpi_descriptor_obj)
        LOGGER.info("Response gRPC message object: {:}".format(response))
        assert isinstance(response, KpiId)

    # 2. Telemetry Collector Creation
    
    # _collector_request = create_collector_request()
    # _search_collector_id = CollectorId()
    # _search_collector_id = _collector_request.collector_id
    # try:
    #     response_col = telemetry_frontend_client.StopCollector(_search_collector_id)
    #     LOGGER.info("Response gRPC message object: {:}".format(response_col))
    #     if response is not None:
    #         response = telemetry_frontend_client.StartCollector(_collector_request)
    #         LOGGER.info("Response gRPC message object: {:}".format(response))
    #         assert isinstance(response, CollectorId)
    # except Exception as e:
    #     LOGGER.info("Error finding the collector with ID: %s. Proceeding to create it.", _search_collector_id.collector_id.uuid)
    #     response = telemetry_frontend_client.StartCollector(_collector_request)
    #     LOGGER.info("Response gRPC message object: {:}".format(response))
    #     assert isinstance(response, CollectorId)
    
    # step 2: Telemetry Collector backup option
    from telemetry.backend.service.collectors import COLLECTORS
    from telemetry.backend.service.collector_api.DriverFactory import DriverFactory
    from telemetry.backend.service.collector_api.DriverInstanceCache import DriverInstanceCache, preload_drivers
    
    driver_factory        = DriverFactory(COLLECTORS)
    driver_instance_cache = DriverInstanceCache(driver_factory)
    _service              = TelemetryBackendService(driver_instance_cache)
    
    _collector_request = create_collector_request()
    _collector         = create_basic_sub_request_parameters()
    _coll_id           = "mgon_collector_id"
    LOGGER.info("Subscription for collector %s parameters: %s", _coll_id, _collector)
    
    _duration          = _collector_request.duration_s
    _interval          = _collector_request.interval_s
    
    stop_event       = threading.Event()
    collector_thread = threading.Thread(
        target=_service.GenericCollectorHandler,
        args=(
            _coll_id, _collector, "6e22f180-ba28-4641-b190-2287bf447777", _duration, _interval,
            None, None, None, "43813baf-195e-5da6-af20-b3d0922e71a7", stop_event
        ),
        daemon=False
    )
    collector_thread.start()

    def stop_after_duration(completion_time, stop_event):
        time.sleep(completion_time)
        if not stop_event.is_set():
            LOGGER.warning(f"Execution duration ({completion_time}) completed for Collector: {_coll_id}")
            stop_event.set()

    duration_thread = threading.Thread(
        target=stop_after_duration, daemon=True, name=f"stop_after_duration_{_coll_id}",
        args=(_duration, stop_event)
    )
    duration_thread.start()

    LOGGER.info("Sleeping for %d seconds...", _duration)
    time.sleep(_duration)
    
    LOGGER.info("Setting stop event for Collector: %s", _coll_id)
    stop_event.set()
    
    # Wait for collector thread to complete
    collector_thread.join(timeout=10)
    if collector_thread.is_alive():
        LOGGER.warning("Collector thread did not terminate within timeout")
    
    LOGGER.info("Done sleeping.")
    LOGGER.info(" >>> test_Complete_MGON_Integration: END <<< ")


# def test_get_state_updates(collector, subscription_data):
#     """Test getting state updates."""
#     LOGGER.info("----- Testing State Updates -----")
#     collector.SubscribeState(subscription_data)
    
#     LOGGER.info("Requesting state updates for 300 seconds ...")
#     updates_received = []
#     for samples in collector.GetState(duration=300, blocking=True):
#         LOGGER.info("Received state update: %s", samples)
#         updates_received.append(samples)
    
#     assert len(updates_received) > 0


if __name__ == "__main__":
    test_Complete_MGON_Integration(kpi_manager_client, telemetry_frontend_client)

    
