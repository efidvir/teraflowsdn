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
from typing import Dict, List, Tuple
from context.client.ContextClient import ContextClient
from common.tools.context_queries.Device import get_device
from .SimapClient import SimapClient


LOGGER = logging.getLogger(__name__)

def extract_network_data(context_client: ContextClient, network_id: str, network_connection: dict) -> list[tuple[str, dict]]:

    try:
        # Extract path_hops_endpoint_ids from network_connection dict
        path_hops = network_connection.get('path_hops_endpoint_ids', [])
        
        if not path_hops:
            LOGGER.warning(f"No path_hops_endpoint_ids found in network_connection for network {network_id}")
            return []
        
        if len(path_hops) < 2:
            LOGGER.warning(f"Connection path too short (less than 2 hops) for network {network_id}")
            return []
        
        # Extract first and last hops (SDPs - Service Demarcation Points)
        first_hop = path_hops[0]
        last_hop  = path_hops[-1]
        
        # Extract device and endpoint UUIDs for SDPs
        first_device_uuid   = first_hop.get('device_id', {}).get('device_uuid', {}).get('uuid', '')
        first_endpoint_uuid = first_hop.get('endpoint_uuid', {}).get('uuid', '')
        
        last_device_uuid   = last_hop.get('device_id', {}).get('device_uuid', {}).get('uuid', '')
        last_endpoint_uuid = last_hop.get('endpoint_uuid', {}).get('uuid', '')
        
        if not all([first_device_uuid, first_endpoint_uuid, last_device_uuid, last_endpoint_uuid]):
            LOGGER.warning(f"Invalid first or last hop in path_hops_endpoint_ids for network {network_id}")
            return []
        
        # Prepare results for exactly 2 SDPs
        network_data: List[Tuple[str, Dict[str, List[str]]]] = []
        
        # Process first device (sdp1)
        try:
            first_device = get_device(
                context_client, first_device_uuid, rw_copy=False,
                include_endpoints=True, include_config_rules=False, include_components=False
            )
            if first_device is None:
                LOGGER.warning(f"First device with UUID {first_device_uuid} not found in context")
                return []
            
            first_device_name = first_device.name
            
            # Find the service-facing endpoint name
            first_endpoint_name = None
            for endpoint in first_device.device_endpoints:
                if endpoint.endpoint_id.endpoint_uuid.uuid == first_endpoint_uuid:
                    first_endpoint_name = endpoint.name
                    break
            
            if not first_endpoint_name:
                LOGGER.warning(f"First endpoint {first_endpoint_uuid} not found in device {first_device_name}")
                return []
            
            network_data.append((first_device_name, {'termination_points': [first_endpoint_name]}))
        
        except Exception as e:
            LOGGER.error(f"Error retrieving first device {first_device_uuid} from context: {e}")
            return []
        
        # Process last device (sdp2)
        try:
            last_device = get_device(
                context_client, last_device_uuid, rw_copy=False,
                include_endpoints=True, include_config_rules=False, include_components=False
            )
            if last_device is None:
                LOGGER.warning(f"Last device with UUID {last_device_uuid} not found in context")
                return []
            
            last_device_name = last_device.name
            
            # Find the service-facing endpoint name
            last_endpoint_name = None
            for endpoint in last_device.device_endpoints:
                if endpoint.endpoint_id.endpoint_uuid.uuid == last_endpoint_uuid:
                    last_endpoint_name = endpoint.name
                    break
            
            if not last_endpoint_name:
                LOGGER.warning(f"Last endpoint {last_endpoint_uuid} not found in device {last_device_name}")
                return []
            
            network_data.append((last_device_name, {'termination_points': [last_endpoint_name]}))
        
        except Exception as e:
            LOGGER.error(f"Error retrieving last device {last_device_uuid} from context: {e}")
            return []
        
        LOGGER.info(f"Extracted network data for {network_id}: {network_data}")
        return network_data
    
    except Exception as e:
        LOGGER.error(f"Error extracting network data from connection for network {network_id}: {e}")
        return []


def set_simap_network(context_client: ContextClient, simap_client: SimapClient, network_id: str, network_connection: dict) -> None:
    """
    Configure a SIMAP network with preset configurations.
    
    Args:
        context_client: ContextClient instance
        simap_client: SimapClient instance
        network_id: Network identifier ('e2e', 'agg', or 'trans-pkt')
        network_connection: Dictionary representation of Connection protobuf with path_hops_endpoint_ids
    """

    LOGGER.info(f"Setting SIMAP network: {network_id} for connection with {len(network_connection.get('path_hops_endpoint_ids', []))} hops")
    network_data : list[tuple[str, dict]] = extract_network_data(context_client, network_id, network_connection)

    if network_id == 'e2e':
        try:
            # E2E Network Configuration
            simap = simap_client.network('e2e')
            simap.update(supporting_network_ids=['admin', 'agg'])

            # Configure nodes
            node_names = ['sdp1', 'sdp2']
            endpoints  = []

            for i, (admin_node_id, node_config) in enumerate(network_data):
                node = simap.node(node_names[i])
                node.update(supporting_node_ids=[('admin', admin_node_id)])
                for tp in node_config['termination_points']:
                    node.termination_point(tp).update(supporting_termination_point_ids=[('admin', admin_node_id, tp)])
                    endpoints.append(tp)

            if len(endpoints) != 2:
                MSG = 'Invalid number of endpoints for E2E network configuration. Expected 2, got {:d}.'
                LOGGER.error(MSG.format(len(endpoints)))
                return  
            
            link = simap.link('E2E-L1')
            link.update(
                'sdp1', endpoints[0], 'sdp2', endpoints[1],
                supporting_link_ids=[
                    ('admin', 'L1'), ('agg', 'AggNet-L1')
                ]
            )
        except (KeyError, IndexError, ValueError) as e:
            LOGGER.error(f'Error configuring E2E network: {e}')
            return
        except Exception as e:
            LOGGER.error(f'Unexpected error configuring E2E network: {e}')
            return
        
    elif network_id == 'agg':
        try:
            # Aggregation Network Configuration
            simap = simap_client.network('agg')
            simap.update(supporting_network_ids=['admin', 'trans-pkt'])

            # Configure nodes
            node_names = ['sdp1', 'sdp2']
            endpoints  = []
            for i, (admin_node_id, node_config) in enumerate(network_data):
                node = simap.node(node_names[i])
                node.update(supporting_node_ids=[('admin', admin_node_id)])
                for tp in node_config['termination_points']:
                    node.termination_point(tp).update(supporting_termination_point_ids=[('admin', admin_node_id, tp)])
                    endpoints.append(tp)
            if len(endpoints) != 2:
                MSG = 'Invalid number of endpoints for Aggregation network configuration. Expected 2, got {:d}.'
                LOGGER.error(MSG.format(len(endpoints)))
                return
            
            link = simap.link('AggNet-L1')
            link.update(
                'sdp1', endpoints[0], 'sdp2', endpoints[1],
                supporting_link_ids=[
                    ('trans-pkt', 'Trans-L1'), ('admin', 'L13'), ('admin', 'L3')
                ]
            )
        except (KeyError, IndexError, ValueError) as e:
            LOGGER.error(f'Error configuring Aggregation network: {e}')
            return
        except Exception as e:
            LOGGER.error(f'Unexpected error configuring Aggregation network: {e}')
            return
        
    elif network_id == 'trans-pkt':
        try:
            # Transport Packet Network Configuration
            simap = simap_client.network('trans-pkt')
            simap.update(supporting_network_ids=['admin'])

            # Configure nodes
            node_names = ['site1', 'site2']
            endpoints  = []
            for i, (admin_node_id, node_config) in enumerate(network_data):
                node = simap.node(node_names[i])
                node.update(supporting_node_ids=[('admin', admin_node_id)])
                for tp in node_config['termination_points']:
                    node.termination_point(tp).update(supporting_termination_point_ids=[('admin', admin_node_id, tp)])
                    endpoints.append(tp)
            if len(endpoints) != 2:
                MSG = 'Invalid number of endpoints for Transport Packet network configuration. Expected 2, got {:d}.'
                LOGGER.error(MSG.format(len(endpoints)))
                return

            link = simap.link('Trans-L1')
            link.update(
                'site1', endpoints[0], 'site2', endpoints[1],
                supporting_link_ids=[
                    ('admin', 'L6'), ('admin', 'L10')
                ]
            )
        except (KeyError, IndexError, ValueError) as e:
            LOGGER.error(f'Error configuring Transport Packet network: {e}')
            return
        except Exception as e:
            LOGGER.error(f'Unexpected error configuring Transport Packet network: {e}')
            return
        
    else:
        MSG = 'Unsupported network_id({:s}) to set SIMAP'
        LOGGER.warning(MSG.format(str(network_id)))
        return
    
    LOGGER.info(f'Successfully configured SIMAP network: {network_id}')


def delete_simap_network(simap_client: SimapClient, network_id: str) -> None:
    """
    Delete a SIMAP network configuration.
    
    Args:
        simap_client: SimapClient instance
        network_id: Network identifier ('e2e', 'agg', or 'trans-pkt')
    """
    if network_id == 'e2e':
        simap = simap_client.network('e2e')
        simap.update(supporting_network_ids=['admin', 'agg'])

        link = simap.link('E2E-L1')
        link.delete()
        
    elif network_id == 'agg':
        simap = simap_client.network('agg')
        simap.update(supporting_network_ids=['admin', 'trans-pkt'])

        link = simap.link('AggNet-L1')
        link.delete()

    elif network_id == 'trans-pkt':
        simap = simap_client.network('trans-pkt')
        simap.update(supporting_network_ids=['admin'])

        link = simap.link('Trans-L1')
        link.delete()

    else:
        MSG = 'Unsupported network_id({:s}) to delete SIMAP'
        LOGGER.warning(MSG.format(str(network_id)))
        return
    
    LOGGER.info(f'Successfully deleted SIMAP network: {network_id}')
