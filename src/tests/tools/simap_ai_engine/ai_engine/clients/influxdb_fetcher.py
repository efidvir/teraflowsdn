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
InfluxDB Fetcher module.

Provides functionality to fetch performance metrics from InfluxDB.
"""

from urllib import response
import pandas as pd
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from numpy import average
from common.tools.client.RetryDecorator import delay_exponential, retry
from influxdb_client_3 import InfluxDBClient3, Point, WritePrecision
from ..ai_model.sla_policy import SLAPolicyConfig

LOGGER = logging.getLogger(__name__)

# Retry decorator for external service calls
RETRY_DECORATOR = retry(
    max_retries=15,
    delay_function=delay_exponential(initial=0.01, increment=2.0, maximum=5.0)
)


class InfluxDBFetcher:
    """
    Fetches performance metrics from InfluxDB.

    This class handles communication with InfluxDB to retrieve time-series
    performance data for network devices and services.
    """

    def __init__(
        self,
        influxdb_host: str,
        influxdb_port: int,
        influxdb_token: str,
        influxdb_database: str
    ) -> None:
        """
        Initialize the InfluxDBFetcher.

        Args:
            influxdb_host: InfluxDB server hostname or IP address.
            influxdb_port: InfluxDB server port number.
            influxdb_token: Authentication token for InfluxDB.
            influxdb_database: Name of the InfluxDB database to query.
        """
        self.influxdb_host     = influxdb_host
        self.influxdb_port     = influxdb_port
        self.influxdb_token    = influxdb_token
        self.influxdb_database = influxdb_database
        self.influxdb_url      = f"http://{influxdb_host}:{influxdb_port}"
        
        LOGGER.info( f"InfluxDBFetcher initialized for database '{influxdb_database}' "
                     f"at {self.influxdb_url}")
        self._client = InfluxDBClient3(
                            host     = self.influxdb_url,
                            token    = self.influxdb_token,
                            database = self.influxdb_database
                        )

    def is_connected(self) -> bool:
        """
        Check if InfluxDB client is initialized and ready.
        
        Returns:
            True if client is ready, False otherwise.
        """
        try:
            if isinstance(self._client, InfluxDBClient3):
                LOGGER.debug("InfluxDB client is initialized")
                return True
            else:
                LOGGER.warning("InfluxDB client is not initialized")
                return False
        except Exception as e:
            LOGGER.error(f"Error checking InfluxDB connection: {e}")
            return False

    def process_response_table(
        self,
        table: Any,
    ) -> Dict[str, Any]:
        """
        Process InfluxDB response table into structured data.

        Args:
            table: Raw response table from InfluxDB query.

        Returns:
            Dictionary containing processed performance metrics and values.
        """
        if table is None or not isinstance(table, pd.DataFrame):
            LOGGER.warning("No data returned from InfluxDB query")
            return {
                'metrics':       [],
                'metric_values': []
            }

        LOGGER.debug(f"Processing {len(table)} rows from InfluxDB response")
        
        # Sort by time column (old to new) if it exists
        if 'time' in table.columns:
            table = table.sort_values(by='time', ascending=True)
            LOGGER.debug("Sorted data by time (ascending: old to new)")
        
        # Define columns for each output dataframe
        full_columns   = ['bandwidth_utilization', 'latency', 'time', 'link_id']
        metric_columns = ['bandwidth_utilization', 'latency']
        
        # Create DataFrame 1: Full metrics with time and link_id
        # Filter only columns that exist in the table
        available_full_cols = [col for col in full_columns if col in table.columns]
        df_full             = table[available_full_cols]
        metrics             = df_full.to_dict('records')
        
        # Create DataFrame 2: Only metric values (bandwidth_utilization, latency)
        available_metric_cols = [col for col in metric_columns if col in table.columns]
        df_metrics           = table[available_metric_cols]
        metric_values        = df_metrics.to_dict('records')
        
        LOGGER.debug(f"Processed {len(metrics)} metric records with {len(available_full_cols)} columns")
        LOGGER.debug(f"Extracted {len(metric_values)} metric value records with {len(available_metric_cols)} columns")
        LOGGER.info(f"Response values are: {metric_values} ")
        
        return {
            'metrics':       metrics,
            'metric_values': metric_values
        }


    @RETRY_DECORATOR
    def fetch_performance_data(
        self,
        sla_policy: SLAPolicyConfig
    ) -> Dict[str, Any]:
        
        if not self.is_connected():
            raise ConnectionError("Unable to connect to InfluxDB")
        
        if sla_policy.latency_threshold_ms is None:
            raise ValueError("SLA policy missing latency threshold for data fetch")
        
        LOGGER.debug(
            f"Fetching performance data for simap_id={sla_policy.simap_id}, "
            f"time_window={sla_policy.time_window_seconds}s, "
            f"required_samples={sla_policy.forecast_sample_count}"
        )
        
        try:
            # Initial time window
            current_time_window = sla_policy.time_window_seconds
            max_attempts        = 3
            attempt             = 1
            final_table         = None
            
            while attempt <= max_attempts:
                query = (
                    f"SELECT * FROM link_telemetry "
                    f"WHERE link_id = '{sla_policy.simap_id}' "
                    f"AND time >= now() - INTERVAL '{current_time_window} seconds' "
                    f"ORDER BY time DESC"
                )
                
                LOGGER.debug(f"Attempt {attempt}/{max_attempts}: Executing query with time_window={current_time_window}s")
                LOGGER.debug(f"Query: {query}")
                
                final_table = self._client.query(query=query, language="sql", mode="pandas")
                
                # Count samples from raw table
                samples_fetched = 0 if final_table is None or not isinstance(final_table, pd.DataFrame) else len(final_table)
                
                LOGGER.info(
                    f"Attempt {attempt}: Fetched {samples_fetched} samples "
                    f"(required: {sla_policy.forecast_sample_count})"
                )
                
                # Check if we have enough samples
                if samples_fetched >= sla_policy.forecast_sample_count:
                    LOGGER.info(f"Required samples met")
                    break
                
                # If not enough samples and not last attempt, calculate new time window
                if attempt < max_attempts:
                    if samples_fetched > 0:
                        # Calculate required time window based on sample density
                        # Formula: new_window = current_window * (required_samples / fetched_samples) * 1.2
                        # The 1.2 factor adds 20% buffer to account for non-uniform data distribution
                        ratio               = sla_policy.forecast_sample_count / samples_fetched
                        current_time_window = int(current_time_window * ratio * 1.2)
                        LOGGER.debug(f"Extending time window to {current_time_window}s(ratio: {ratio:.2f})")
                    else:
                        # If no samples, double the time window
                        current_time_window *= 2
                        LOGGER.warning(f"No samples found, doubling time window to {current_time_window}s")
                    
                    attempt += 1
                else:
                    LOGGER.warning(
                        f"Max attempts reached. Returning {samples_fetched} samples "
                        f"(required: {sla_policy.forecast_sample_count})"
                    )
                    break
            
            # Process the response table after fetch is completed
            result = self.process_response_table(final_table)
            
            return {
                'metrics':               result.get('metrics', []),
                'metric_values':         result.get('metric_values', []),
                'fetch_window_size_sec': current_time_window,
                'timestamp_range':       {},
            }
        except Exception as e:
            LOGGER.error(f"Error fetching performance data from InfluxDB: {e}", exc_info=True)
            raise e

    @RETRY_DECORATOR
    def notify_telemetry_update(
        self,
        notification_data: Dict[str, Any]
    ) -> bool:
        """
        Process telemetry update notifications.

        Validates and stores status notifications (UPGRADE or DOWNGRADE)
        in InfluxDB for telemetry tracking. The retry decorator ensures
        resilience against transient failures.

        Args:
            notification_data: Dictionary containing:
                - 'status': Required. Must be "UPGRADE" or "DOWNGRADE".
                - 'timestamp': Optional. Any string value.

        Returns:
            True if notification was processed and stored successfully.

        Raises:
            ValueError: If status is not "UPGRADE" or "DOWNGRADE".
            Exception: If InfluxDB is unavailable after all retries.
        """
        status = notification_data.get('status')
        timestamp = notification_data.get('timestamp',  datetime.now(timezone.utc).isoformat())

        # Validate status value
        if status not in {'UPGRADE', 'DOWNGRADE'}:
            raise ValueError(
                f"Invalid status value '{status}': must be UPGRADE or DOWNGRADE"
            )

        LOGGER.info(
            f"Storing telemetry notification in InfluxDB: "
            f"status={status}, timestamp={timestamp}"
        )

        point = Point("telemetry_notifications") \
            .tag("status",      status) \
            .field("timestamp", timestamp)
        self._client.write(point)

        LOGGER.info("Telemetry notification stored successfully in InfluxDB")
        return True

    def write_predicted_telemetry(
        self,
        results: list[dict[str, Any]],
        network_id: str = 'e2e',
        link_id: str = 'E2E-L1'
    ) -> bool:
        """
        Write predicted telemetry (forecasted metrics) to InfluxDB.

        Args:
            results: List of forecast results from AIModelProcessor.
                    Each dict contains metric_name, forecasted_values, etc.
            network_id: Network identifier (default: 'e2e')
            link_id: Link identifier (default: 'E2E-L1')

        Returns:
            True if write succeeded, False otherwise.
        """
        if not self.is_connected():
            LOGGER.warning("InfluxDB client not initialized, skipping write to DB")
            return False

        if not results:
            LOGGER.warning("No results to write to DB")
            return False

        try:
            # Extract metric predictions and calculate averages
            metric_averages = {}
            for result in results:
                metric_name = result.get("metric_name")
                forecasted_values = result.get("forecasted_values", [])
                
                if metric_name and forecasted_values:
                    # Calculate average of forecasted values
                    avg_value = float(average(forecasted_values))
                    metric_averages[metric_name] = avg_value
                    LOGGER.debug(f"Average forecast for {metric_name}: {avg_value:.4f}")

            # Create InfluxDB point for predicted telemetry
            point = (
                Point("predicted_telemetry")
                .tag("network_id", network_id)
                .tag("link_id", link_id)
            )

            # Add predicted metric fields with pred_ prefix
            if "bandwidth_utilization" in metric_averages:
                point = point.field(
                    "pred_bandwidth_utilization",
                    metric_averages["bandwidth_utilization"]
                )
            
            if "latency" in metric_averages:
                point = point.field(
                    "pred_latency",
                    metric_averages["latency"]
                )

            # Write to InfluxDB
            self._client.write(record=point, write_precision=WritePrecision.S)
            
            LOGGER.info(
                "Wrote predicted telemetry to InfluxDB: network=%s, link=%s, metrics=%s",
                network_id, link_id, list(metric_averages.keys())
            )
            return True

        except Exception as e:
            LOGGER.error(f"Failed to write predicted telemetry to InfluxDB: {e}", exc_info=True)
            return False
