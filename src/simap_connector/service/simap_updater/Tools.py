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


import enum
from typing import List, Optional, Set, Tuple, Union
from common.proto.context_pb2 import (
    EVENTTYPE_CREATE, EVENTTYPE_REMOVE, EVENTTYPE_UPDATE, Device, DeviceEvent,
    Link, LinkEvent, Service, ServiceEvent, SliceEvent, TopologyEvent, Empty
)
from common.tools.grpc.Tools import grpc_message_to_json_string
from context.client.ContextClient import ContextClient
from common.tools.context_queries.Connection import get_connection_by_uuid

class EventTypeEnum(enum.IntEnum):
    CREATE = EVENTTYPE_CREATE
    UPDATE = EVENTTYPE_UPDATE
    REMOVE = EVENTTYPE_REMOVE


EVENT_TYPE = Union[DeviceEvent, LinkEvent, TopologyEvent, ServiceEvent, SliceEvent]


def get_event_type(event : EVENT_TYPE) -> EventTypeEnum:
    int_event_type = event.event.event_type
    enum_event_type = EventTypeEnum._value2member_map_.get(int_event_type)
    if enum_event_type is None:
        MSG = 'Unsupported EventType({:s}) in Event({:s})'
        str_event = grpc_message_to_json_string(event)
        raise Exception(MSG.format(str(int_event_type), str_event))


def get_device_endpoint(device : Device) -> Tuple[Optional[str], List[str]]:
    topology_uuids : Set[str] = set()
    endpoint_device_uuids : Set[str] = set()
    endpoint_names : List[str] = list()

    if len(device.device_endpoints) == 0:
        return None, endpoint_names

    for endpoint in device.device_endpoints:
        topology_uuid = endpoint.endpoint_id.topology_id.topology_uuid.uuid
        topology_uuids.add(topology_uuid)

        endpoint_device_uuid = endpoint.endpoint_id.device_id.device_uuid.uuid
        endpoint_device_uuids.add(endpoint_device_uuid)

        endpoint_name = endpoint.name
        endpoint_names.append(endpoint_name)

    try:
        # Check topology UUIDs
        if len(topology_uuids) != 1:
            MSG = 'Unsupported: no/multiple Topologies({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuids)))
        topology_uuid = list(topology_uuids)[0]
        if len(topology_uuid) == 0:
            MSG = 'Unsupported: empty TopologyUUID({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuid)))

        # Check Device UUIDs
        if len(endpoint_device_uuids) != 1:
            MSG = 'Unsupported: no/multiple DeviceUUID({:s}) referenced'
            raise Exception(MSG.format(str(endpoint_device_uuids)))
        endpoint_device_uuid = list(endpoint_device_uuids)[0]
        if len(endpoint_device_uuid) == 0:
            MSG = 'Unsupported: empty Endpoint.DeviceUUID({:s}) referenced'
            raise Exception(MSG.format(str(endpoint_device_uuid)))
        
        device_uuid = device.device_id.device_uuid.uuid
        if endpoint_device_uuid != device_uuid:
            MSG = 'Unsupported: Endpoint.DeviceUUID({:s}) != DeviceUUID({:s})'
            raise Exception(MSG.format(str(endpoint_device_uuid), str(device_uuid)))
    except Exception as e:
        MSG = '{:s} in Device({:s})'
        raise Exception(MSG.format(str(e), grpc_message_to_json_string(device))) from e

    return topology_uuid, endpoint_names


def get_link_endpoint(link : Link) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    topology_uuids : Set[str] = set()
    endpoint_uuids : List[Tuple[str, str]] = list()

    if len(link.link_endpoint_ids) == 0:
        return None, endpoint_uuids

    for endpoint_id in link.link_endpoint_ids:
        topology_uuid = endpoint_id.topology_id.topology_uuid.uuid
        topology_uuids.add(topology_uuid)

        device_uuid = endpoint_id.device_id.device_uuid.uuid
        endpoint_uuid = endpoint_id.endpoint_uuid.uuid
        endpoint_uuids.append((device_uuid, endpoint_uuid))

    try:
        # Check topology UUIDs
        if len(topology_uuids) != 1:
            MSG = 'Unsupported: no/multiple Topologies({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuids)))
        topology_uuid = list(topology_uuids)[0]
        if len(topology_uuid) == 0:
            MSG = 'Unsupported: empty TopologyUUID({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuid)))

        # Check Count Endpoints
        if len(endpoint_uuids) != 2:
            MSG = 'Unsupported: non-p2p link LinkUUIDs({:s})'
            raise Exception(MSG.format(str(endpoint_uuids)))
    except Exception as e:
        MSG = '{:s} in Link({:s})'
        raise Exception(MSG.format(str(e), grpc_message_to_json_string(link))) from e

    return topology_uuid, endpoint_uuids


def get_service_endpoint(service : Service) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    if len(service.service_endpoint_ids) == 0:
        return None, list()

    topology_uuids : Set[str] = set()
    endpoint_uuids : List[Tuple[str, str]] = list()

    for endpoint_id in service.service_endpoint_ids:
        topology_uuid = endpoint_id.topology_id.topology_uuid.uuid
        topology_uuids.add(topology_uuid)

        device_uuid = endpoint_id.device_id.device_uuid.uuid
        endpoint_uuid = endpoint_id.endpoint_uuid.uuid
        endpoint_uuids.append((device_uuid, endpoint_uuid))

    try:
        # Check topology UUIDs
        if len(topology_uuids) != 1:
            MSG = 'Unsupported: no/multiple Topologies({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuids)))

        topology_uuid = list(topology_uuids)[0]
        if len(topology_uuid) == 0:
            MSG = 'Unsupported: empty TopologyUUID({:s}) referenced'
            raise Exception(MSG.format(str(topology_uuid)))

        # Check Count Endpoints
        if len(endpoint_uuids) > 2:
            MSG = 'Unsupported: non-p2p service ServiceUUIDs({:s})'
            raise Exception(MSG.format(str(endpoint_uuids)))

    except Exception as e:
        MSG = '{:s} in Service({:s})'
        raise Exception(MSG.format(str(e), grpc_message_to_json_string(service))) from e

    return topology_uuid, endpoint_uuids


def get_connection_endpoints_and_links(connection_id: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Retrieve connection details and identify associated links.
    Args:
        connection_id: UUID string of the connection
    Returns:
        Tuple of:
        - List of endpoint tuples (device_uuid, endpoint_uuid) in path order
        - List of link UUIDs corresponding to consecutive endpoint pairs
    """
    
    context_client = ContextClient()
    connection = get_connection_by_uuid(context_client, connection_id, rw_copy=False)
    
    if connection is None:
        raise Exception(f"Failed to retrieve Connection({connection_id}): Connection not found")
    
    # Extract path_hops_endpoint_ids
    endpoint_ids = []
    for endpoint_id in connection.path_hops_endpoint_ids:
        device_uuid   = endpoint_id.device_id.device_uuid.uuid
        endpoint_uuid = endpoint_id.endpoint_uuid.uuid
        endpoint_ids.append((device_uuid, endpoint_uuid))
    
    if len(endpoint_ids) < 2:
        # No path or single endpoint - no links
        return endpoint_ids, []
    
    # Find links connecting consecutive endpoint pairs
    # Get all links from context
    
    link_list = context_client.ListLinks(Empty())
    link_uuids = []
    
    # For each consecutive pair of endpoints in the path
    for i in range(len(endpoint_ids) - 1):
        src_device_uuid, src_endpoint_uuid = endpoint_ids[i]
        dst_device_uuid, dst_endpoint_uuid = endpoint_ids[i + 1]
        
        # Find link connecting these endpoints
        for link in link_list.links:
            if len(link.link_endpoint_ids) != 2:
                continue
            
            # Extract link endpoints
            link_ep0_device   = link.link_endpoint_ids[0].device_id.device_uuid.uuid
            link_ep0_endpoint = link.link_endpoint_ids[0].endpoint_uuid.uuid
            link_ep1_device   = link.link_endpoint_ids[1].device_id.device_uuid.uuid
            link_ep1_endpoint = link.link_endpoint_ids[1].endpoint_uuid.uuid
            
            # Check if link matches (bidirectional check)
            if ((link_ep0_device == src_device_uuid and link_ep0_endpoint == src_endpoint_uuid and
                 link_ep1_device == dst_device_uuid and link_ep1_endpoint == dst_endpoint_uuid) or
                (link_ep1_device == src_device_uuid and link_ep1_endpoint == src_endpoint_uuid and
                 link_ep0_device == dst_device_uuid and link_ep0_endpoint == dst_endpoint_uuid)):
                link_uuids.append(link.link_id.link_uuid.uuid)
                break
    
    return endpoint_ids, link_uuids
