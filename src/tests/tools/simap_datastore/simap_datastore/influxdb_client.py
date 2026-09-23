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

"""
InfluxDB client wrapper for SIMAP telemetry data storage.
"""

import json
import logging
from typing import List, Optional

from influxdb_client_3 import InfluxDBClient3, Point, WritePrecision

from .Config import INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_DATABASE, INFLUXDB_TOKEN


LOGGER = logging.getLogger(__name__)


class SimapInfluxDBClient:
    """
    Client wrapper for writing SIMAP telemetry data to InfluxDB 3.x.
    """

    def __init__( self, 
        host:  Optional[str] = None, port:     Optional[int] = None, 
        token: Optional[str] = None, database: Optional[str] = None
    ) -> None:
        """
        Initialize the InfluxDB client.
        Args:
            host: InfluxDB server hostname (default: from INFLUXDB_HOST env or 'localhost')
            port: InfluxDB server port (default: from INFLUXDB_PORT env or 8181)
            token: Authentication token (default: from INFLUXDB_TOKEN env)
            database: Database/bucket name (default: from INFLUXDB_DATABASE env or 'simap_telemetry')
        """
        self._host     = host     if host is not None     else INFLUXDB_HOST
        self._port     = port     if port is not None     else INFLUXDB_PORT
        self._database = database if database is not None else INFLUXDB_DATABASE
        self._token    = token    if token is not None    else INFLUXDB_TOKEN
        self._client: Optional[InfluxDBClient3] = None

        try:
            self._client = InfluxDBClient3(
                token    = self._token,
                host     = f"http://{self._host}:{self._port}",
                database = self._database
            )
            LOGGER.info("InfluxDB client initialized: host=%s:%d, database=%s",
                self._host, self._port, self._database)
            
            # Test the connection
            if not self._test_connection():
                LOGGER.error("InfluxDB client initialized but connection test failed")
                self._client = None
            else:
                LOGGER.info("InfluxDB connection test successful")
                
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error("Failed to initialize InfluxDB client: %s", str(e))
            self._client = None

    def _test_connection(self) -> bool:
        """
        Test the InfluxDB connection by attempting a simple system query.
        Returns:
            True if connection is accessible, False otherwise
        """
        if self._client is None:
            LOGGER.warning("InfluxDB client not initialized, cannot test connection")
            return False
        
        try:
            query = "SHOW TABLES"
            self._client.query(query=query, language="sql")
            return True
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error("InfluxDB connection test failed: %s", str(e))
            return False

    def is_connected(self) -> bool:
        """Check if client is initialized."""
        return self._client is not None

    def write_link_telemetry(
        self,
        network_id: str,
        link_id: str,
        bandwidth_utilization: float,
        latency: float,
        related_service_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Write link telemetry data to InfluxDB.

        Args:
            network_id: Network identifier (e.g., 'te', 'simap-trans')
            link_id: Link identifier (e.g., 'L1', 'Trans-L1')
            bandwidth_utilization: Bandwidth utilization percentage (0-100)
            latency: Latency in milliseconds
            related_service_ids: Optional list of related service IDs

        Returns:
            True if write succeeded, False otherwise
        """
        if self._client is None:
            LOGGER.warning("InfluxDB client not initialized, skipping write")
            return False

        try:
            point = (
                Point("link_telemetry")
                .tag("network_id", network_id)
                .tag("link_id", link_id)
                .field("bandwidth_utilization", float(bandwidth_utilization))
                .field("latency", float(latency))
            )

            if related_service_ids:
                point = point.field("related_service_ids", json.dumps(related_service_ids))

            self._client.write(record=point, write_precision=WritePrecision.S)

            LOGGER.debug(
                "Wrote link telemetry: network=%s, link=%s, bw=%.2f, lat=%.3f",
                network_id, link_id, bandwidth_utilization, latency
            )
            return True

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                "Failed to write link telemetry (network=%s, link=%s): %s",
                network_id, link_id, str(e)
            )
            return False

    def write_node_telemetry(
        self,
        network_id: str,
        node_id: str,
        cpu_utilization: float,
        related_service_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Write node telemetry data to InfluxDB.

        Args:
            network_id: Network identifier
            node_id: Node identifier (e.g., 'PE1', 'ONT1')
            cpu_utilization: CPU utilization percentage (0-100)
            related_service_ids: Optional list of related service IDs

        Returns:
            True if write succeeded, False otherwise
        """
        if self._client is None:
            LOGGER.warning("InfluxDB client not initialized, skipping write")
            return False

        try:
            point = (
                Point("node_telemetry")
                .tag("network_id", network_id)
                .tag("node_id", node_id)
                .field("cpu_utilization", float(cpu_utilization))
            )

            if related_service_ids:
                point = point.field("related_service_ids", json.dumps(related_service_ids))

            self._client.write(record=point, write_precision=WritePrecision.S)

            LOGGER.debug(
                "Wrote node telemetry: network=%s, node=%s, cpu=%.2f",
                network_id, node_id, cpu_utilization
            )
            return True

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                "Failed to write node telemetry (network=%s, node=%s): %s",
                network_id, node_id, str(e)
            )
            return False

    def close(self) -> None:
        """Close the InfluxDB client connection."""
        if self._client is not None:
            try:
                self._client.close()
                LOGGER.info("InfluxDB client closed")
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.error("Error closing InfluxDB client: %s", str(e))
            finally:
                self._client = None
