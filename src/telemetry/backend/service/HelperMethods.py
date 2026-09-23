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
import uuid
import logging
from typing import Optional
from .collector_api._Collector               import _Collector
from .collector_api.DriverInstanceCache      import get_driver
from .collectors.int_collector.INTCollector  import INTCollector
from common.proto.kpi_manager_pb2            import KpiId
from common.tools.context_queries.Device     import get_device
from common.tools.context_queries.EndPoint   import get_endpoint_names
from common.tools.context_queries.Service    import get_service_by_uuid

from typing import List, Tuple, Optional
from .collectors.gnmi_oc.GnmiOpenConfigCollector import GNMIOpenConfigCollector

LOGGER = logging.getLogger(__name__)

def get_optical_subscription(
        kpi_id: str, kpi_descriptor, context_client, duration: float, interval: float, resource: str,
) -> Optional[List[Tuple]]:
    """
    Get subscription parameters for optical devices (optical-roadm, optical-transponder) 
    using service uuid from KPI descriptor to find the endpoint in service config rules.    
    Returns:
        List of subscription tuples or None if unable to create subscription
    """
    _service_id = kpi_descriptor.service_id.service_uuid.uuid
    LOGGER.info(f"KPI Descriptor (Service ID): {_service_id}")
    
    service = get_service_by_uuid(context_client, _service_id)
    if not service:
        LOGGER.warning(f"KPI ID: {kpi_id} - Service not found for Service ID: {_service_id}. Skipping...")
        return None
    
    LOGGER.debug(f"Service for KPI ID: {kpi_id} - {service.name} - {service.service_config}")
    if not service.service_config.config_rules:
        LOGGER.warning(f"KPI ID: {kpi_id} - No config rules in service config. Skipping...")
        return None

    # Get the first config rule's custom resource_value
    config_rule = service.service_config.config_rules[0]
    if not config_rule.HasField('custom'):
        LOGGER.warning(f"KPI ID: {kpi_id} - No custom config in service config. Skipping...")
        return None

    resource_value = json.loads(config_rule.custom.resource_value)
    
    if 'ob_id' not in resource_value:
        LOGGER.warning(f"KPI ID: {kpi_id} - Resource ob_id not found in service config. Skipping...")
        return None

    endpoint = resource_value['ob_id']
    return [
        (
            str(uuid.uuid4()),
            {
                "kpi"      : kpi_descriptor.kpi_sample_type,
                "endpoint" : endpoint,
                "resource" : resource,
            },
            float(duration),
            float(interval),
        )
    ]


def get_ip_subscriptions(
        kpi_id: str, kpi_descriptor, device, context_client, duration: float, interval: float, resource: str,
) -> Optional[List[Tuple]]:
    """
    Get subscription parameters for IP/packet devices (routers, switches, etc.) 
    using device endpoints from context to create subscriptions for each endpoint.
    Returns:
        List of subscription tuples (one per endpoint) or None if unable to create subscriptions
    """
    endpoints = device.device_endpoints
    LOGGER.debug(f"Device for KPI ID: {kpi_id} - {endpoints}")
    endpointsIds = [endpoint_id.endpoint_id for endpoint_id in endpoints]
    for endpoint_id in endpoints:
        LOGGER.debug(f"Endpoint UUID: {endpoint_id.endpoint_id}")
        
    # Getting endpoint names
    device_names, endpoint_data = get_endpoint_names(
        context_client = context_client,
        endpoint_ids   = endpointsIds
    )
    LOGGER.debug(f"Device names: {device_names}")
    LOGGER.debug(f"Endpoint data: {endpoint_data}")

    subscriptions = []
    for endpoint in endpointsIds:
        sub_id = str(uuid.uuid4())
        LOGGER.info(f"Endpoint names only: {endpoint_data[endpoint.endpoint_uuid.uuid][0]}") 
        subscriptions.append(
            (
                sub_id,
                {
                    "kpi"      : kpi_descriptor.kpi_sample_type,
                    "endpoint" : endpoint_data[endpoint.endpoint_uuid.uuid][0],
                    "resource" : resource,
                },
                float(duration),
                float(interval),
            )
        )
    return subscriptions


def get_subscription_parameters(
        kpi_id : str, kpi_manager_client, context_client, duration, interval, resource: str = "",
        ) -> Optional[List[Tuple]]:
    """
    Method to get subscription parameters based on KPI ID.
    Returns a list of tuples with subscription parameters.
    Each tuple contains:
        - Subscription ID (str)
        - Dictionary with:
            - "kpi" (str): KPI ID
            - "endpoint" (str): Endpoint name (e.g., 'eth0')
            - "resource" (str): Resource type (e.g., 'interface')
        - Sample interval (float)
        - Report interval (float)
    If the KPI ID is not found or the device is not available, returns None.
    Preconditions:
        - A KPI Descriptor must be added in KPI DB with correct device_id.
        - The device must be available in the context.
    """
    kpi_id_obj             = KpiId()
    kpi_id_obj.kpi_id.uuid = kpi_id              # pyright: ignore[reportAttributeAccessIssue]
    kpi_descriptor         = kpi_manager_client.GetKpiDescriptor(kpi_id_obj)
    if not kpi_descriptor:
        LOGGER.warning(f"KPI ID: {kpi_id} - Descriptor not found. Skipping...")
        return None
    
    device = get_device(context_client       = context_client,
                        device_uuid          = kpi_descriptor.device_id.device_uuid.uuid,
                        include_config_rules = False,
                        include_components   = False
                        )
    if not device:
        raise Exception(f"KPI ID: {kpi_id} - Device not found for KPI descriptor.")
    
    # Route to appropriate subscription handler based on device type
    if device.device_type in ['optical-roadm', 'optical-transponder']:
        return get_optical_subscription(kpi_id, kpi_descriptor, context_client, duration, interval, resource="wavelength-router")
    else:
        return get_ip_subscriptions(kpi_id, kpi_descriptor, device, context_client, duration, interval, resource="interface")

def get_collector_by_kpi_id(kpi_id: str, kpi_manager_client, context_client, driver_instance_cache
                            ) -> Optional[_Collector]:
    """
    Method to get a collector instance based on KPI ID.
    Preconditions:
        - A KPI Descriptor must be added in KPI DB with correct device_id.
        - The device must be available in the context DB.
    Returns:
        - Collector instance if found, otherwise raises exception
          if the KPI ID is not found or the collector cannot be created.
    """
    LOGGER.info(f"Getting collector for KPI ID: {kpi_id}")
    kpi_id_obj             = KpiId()
    kpi_id_obj.kpi_id.uuid = kpi_id              # pyright: ignore[reportAttributeAccessIssue]
    kpi_descriptor         = kpi_manager_client.GetKpiDescriptor(kpi_id_obj)
    if not kpi_descriptor:
        raise Exception(f"KPI ID: {kpi_id} - Descriptor not found.")
    
    device_uuid = kpi_descriptor.device_id.device_uuid.uuid
    device = get_device(
        context_client       = context_client,
        device_uuid          = device_uuid,
        include_config_rules = True,
        include_components   = False,
    )

    # Getting device collector (testing)
    collector : _Collector = get_driver(driver_instance_cache, device)      # NOTE: driver_instance_cache is define in collector_api.DriverInstanceCache
    if collector is None:
        raise Exception(f"KPI ID: {kpi_id} - Collector not found for device {device.device_uuid.uuid}.")        #TODO: Change to TFS NotFoundException 
    # LOGGER.info(f"Collector for KPI ID: {kpi_id} - {collector.__class__.__name__}")
    return collector

def get_node_level_int_collector(collector_id: str, kpi_id: str, address: str, interface: str, port: int,
            service_id: str, context_id: str) -> Optional[_Collector]:
    """
    Method to instantiate an in-band network telemetry collector at a node level.
    Such a collector binds to a physical/virtual interface of a node, expecting
    packets from one or more switches.
    Every packet contains multiple KPIs, therefore this collector is not bound to
    a single KPI.
    Returns:
        - Collector instance if found, otherwise None.
    Raises:
        - Exception if the KPI ID is not found or the collector cannot be created.
    """

    LOGGER.debug(f"INT collector         ID: {collector_id}")
    LOGGER.debug(f"INT collector    address: {address}")
    LOGGER.debug(f"INT collector       port: {port}")
    LOGGER.debug(f"INT collector  interface: {interface}")
    LOGGER.debug(f"INT collector     kpi_id: {kpi_id}")
    LOGGER.debug(f"INT collector service_id: {service_id}")
    LOGGER.debug(f"INT collector context_id: {context_id}")
    # Initialize an INT collector
    try:
        collector : _Collector = INTCollector(
            address=address,
            port=port,
            collector_id=collector_id,
            interface=interface,
            kpi_id=kpi_id,
            service_id=service_id,
            context_id=context_id
        )
    except Exception as ex:
        LOGGER.exception(f"Failed to create INT Collector object on node {address}, {interface}:{port}")

    connected = False
    if not collector:
        return None
    LOGGER.info(f"Collector for KPI ID: {kpi_id} - {collector.__class__.__name__}")

    try:
        connected = collector.Connect()
    except Exception as ex:
        LOGGER.exception(f"Failed to connect INT Collector on node {address}, {interface}:{port}")

    return collector if connected else None


def get_mgon_subscription_parameters(resource: str, endpoint: str, kpi: str, duration: int, interval: int) -> Optional[List[Tuple]]:
        return [(
                str(uuid.uuid4()), # "x123",
                {
                    "kpi"      : kpi,            # sub_parameters['kpi'],
                    "endpoint" : endpoint,       # sub_parameters['endpoint'],
                    "resource" : resource,       #sub_parameters['resource'],
                },
                duration,
                interval,
            ),]


def get_mgon_collector(
    address: str, port: int, username: Optional[str], password: Optional[str], insecure: Optional[bool],
        skip_verify: Optional[bool]
    ) -> Optional[_Collector]:
    
    _collector = GNMIOpenConfigCollector(
        address     = address,
        port        = port,
        username    = username,
        password    = password,
        insecure    = insecure,
        skip_verify = skip_verify,
    )
    try:
        connected = _collector.Connect()
        if not connected:
            LOGGER.error(f"Failed to connect to MG-ON collector at {address}:{port}")
            return None
        return _collector
    except Exception as ex:
        LOGGER.exception(f"Exception while connecting to MG-ON collector at {address}:{port}")
        return None
