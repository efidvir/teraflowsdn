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
SLA Policy Configuration dataclass.

Defines the structure for SLA policy configurations used in AI analysis.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class SLAPolicyConfig:
    """
    Configuration for an SLA policy to be analyzed.

    Attributes:
        simap_id: Unique identifier for the SIMAP entity.
        latency_threshold_ms: Maximum acceptable latency in milliseconds.
        bandwidth_utilization_threshold_pct: Maximum acceptable bandwidth
            utilization as a percentage (0-100).
        time_window_seconds: Time window in seconds for data analysis.
        forecast_sample_interval_sec: Sampling interval in seconds for data collection.
        forecast_sample_count: Minimum number of samples to fetch from database.
    """
    simap_id: str
    latency_threshold_ms: float|None
    bandwidth_utilization: float|None
    time_window_seconds: int
    forecast_sample_interval_sec: int
    forecast_sample_count: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SLAPolicyConfig:
        """
        Create an SLAPolicyConfig instance from a dictionary.

        Args:
            data: Dictionary containing the SLA policy configuration fields.
                Required keys: 'simap_id', 'latency_threshold_ms',
                'bandwidth_utilization', 'time_window_seconds'.
                Supports nested 'sla_metrics' structure.

        Returns:
            A new SLAPolicyConfig instance.

        Raises:
            KeyError: If a required field is missing from the data dictionary.
            TypeError: If a field has an invalid type.
            ValueError: If a field has an invalid value.
        """
        try:
            simap_id             = str(data['simap_id'])
            metrics              = data['sla_metrics']
            latency_threshold_ms = float(metrics['latency_threshold_ms'])
            bandwidth_threshold  = float(metrics.get('bandwidth_utilization', 0.0))
            time_window          = int(data['history_window_size_sec'])
            sample_interval      = int(data['forecast_sample_interval_sec'])
            forecast_sample_count         = int(data['forecast_sample_count'])
            
            return cls(
                simap_id              = simap_id,
                latency_threshold_ms  = latency_threshold_ms,
                bandwidth_utilization = bandwidth_threshold,
                time_window_seconds   = time_window,
                forecast_sample_interval_sec   = sample_interval,
                forecast_sample_count          = forecast_sample_count
            )
        except KeyError as e:
            raise KeyError(f"Missing required field: {e.args[0]}") from e

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the SLAPolicyConfig to a dictionary.

        Returns:
            Dictionary representation of the SLA policy configuration.
        """
        return asdict(self)
