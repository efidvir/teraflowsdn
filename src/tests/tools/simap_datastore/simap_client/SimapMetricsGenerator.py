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

import random
import math
import logging
from typing import Dict, List, Tuple

LOGGER = logging.getLogger(__name__)

# Congestion curve types
CURVE_LINEAR      = 'linear'       # x - steady increase
CURVE_EXPONENTIAL = 'exponential'  # exp(x)-1 - slow start, rapid end
CURVE_LOGARITHMIC = 'logarithmic'  # log(1+x) - fast start, plateau

# Link profiles: (base_bw%, base_latency_ms, sensitivity, curve_type)
# - sensitivity: 1.0 = highly affected by load, 0.3 = minimally affected
# - curve_type: how congestion scales with load
LINK_PROFILES = {
    'L1' : (15.0, 1.0, 1.0, CURVE_EXPONENTIAL),
    'L3' : (10.0, 0.8, 0.7, CURVE_EXPONENTIAL),
    'L5' : ( 8.0, 0.3, 0.3, CURVE_LINEAR),
    'L9' : ( 8.0, 0.3, 0.3, CURVE_LINEAR),
    'L13': (12.0, 0.5, 0.5, CURVE_LOGARITHMIC),
}

MAX_SERVICES = 5


class SimapMetricsGenerator:
    """
    Generates realistic SIMAP telemetry metrics based on service count.
    Higher service counts cause non-linear congestion effects.
    Access links are more sensitive to load than core links.
    """

    def __init__(self, service_count: int = 0):
        LOGGER.info("Initiating SimapMetricsGenerator")
        self._service_count = 0
        self._service_ids: Dict[str, List[str]] = {
            'te'    : [],
            'trans' : [],
            'agg'   : [],
            'e2e'   : [],
        }
        self.set_service_count(service_count)

    @property
    def service_count(self) -> int:
        return self._service_count

    def set_service_count(self, count: int) -> None:
        """Update service count and regenerate domain-specific service IDs."""
        if count < 0 or count > MAX_SERVICES:
            raise ValueError(f"Service count must be 0-{MAX_SERVICES}, got {count}")
        self._service_count = count
        # Each domain has its own service IDs
        self._service_ids = {
            'te'    : [f'te-svc-{i+1}'    for i in range(count)],
            'trans' : [f'trans-svc-{i+1}' for i in range(count)],
            'agg'   : [f'agg-svc-{i+1}'   for i in range(count)],
            'e2e'   : [f'e2e-svc-{i+1}'   for i in range(count)],
        }
        LOGGER.info(f"Service count set to {count}, IDs per domain: {self._service_ids}")

    def get_service_ids(self, domain: str = 'e2e') -> List[str]:
        """Return current list of active service IDs for a specific domain."""
        if domain not in self._service_ids:
            raise ValueError(f"Unknown domain: {domain}. Valid: {list(self._service_ids.keys())}")
        return self._service_ids[domain].copy()

    def get_all_service_ids(self) -> Dict[str, List[str]]:
        """Return all domain service IDs."""
        return {k: v.copy() for k, v in self._service_ids.items()}

    def _compute_congestion_factor(self, curve_type: str, load_ratio: float) -> float:
        """
        Compute congestion factor based on curve type and load ratio (0-1).
        """
        if curve_type == CURVE_LINEAR:
            return load_ratio
        elif curve_type == CURVE_EXPONENTIAL:
            # Exponential: slow start, rapid increase at high load
            return (math.exp(load_ratio * 2) - 1) / (math.e ** 2 - 1)
        elif curve_type == CURVE_LOGARITHMIC:
            # Logarithmic: fast initial increase, then plateau
            return math.log1p(load_ratio * 2.7) / math.log1p(2.7)
        else:
            return load_ratio  # Default to linear

    def generate_link_metrics(self, link_id: str) -> Tuple[float, float]:
        """
        Generate BW and latency for a specific TE link using distinct congestion patterns.
        Returns:
            Tuple of (bandwidth_utilization%, latency_ms)
        """
        if link_id not in LINK_PROFILES:
            raise ValueError(f"Unknown link ID: {link_id}")

        base_bw, base_latency, sensitivity, curve_type = LINK_PROFILES[link_id]

        # Load ratio (0 to 1)
        load_ratio = self._service_count / MAX_SERVICES

        # Compute congestion factor using link-specific curve
        congestion_factor = self._compute_congestion_factor(curve_type, load_ratio)

        # Calculate base metrics with congestion
        bw_utilization = base_bw + (congestion_factor * sensitivity * 60.0)
        latency        = base_latency * (1.0 + congestion_factor * sensitivity * 4.0)

        # Add uniform noise (5%)
        bw_noise  = random.uniform(-0.05, 0.05) * bw_utilization
        lat_noise = random.uniform(-0.05, 0.05) * latency

        bw_utilization = max(0.0, min(100.0, bw_utilization + bw_noise))
        latency        = max(0.1, latency + lat_noise)

        return (bw_utilization, latency)

    def generate_all_te_metrics(self) -> Dict[str, Tuple[float, float]]:
        """
        Generate metrics for all TE links in the path.
        
        Returns:
            Dict mapping link_id to (bandwidth%, latency_ms)
        """
        return {link_id: self.generate_link_metrics(link_id) for link_id in LINK_PROFILES}

    def aggregate_abstract_metrics(
        self, te_metrics: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Aggregate TE metrics into abstract layer metrics.
        BW: average, Latency: sum
        
        Returns:
            Dict with 'Trans-L1', 'AggNet-L1', 'E2E-L1' metrics
        """
        bw_L1,  lat_L1  = te_metrics['L1']
        bw_L3,  lat_L3  = te_metrics['L3']
        bw_L5,  lat_L5  = te_metrics['L5']
        bw_L9,  lat_L9  = te_metrics['L9']
        bw_L13, lat_L13 = te_metrics['L13']

        # Trans-L1: L5 + L9
        bw_trans  = (bw_L5 + bw_L9) / 2
        lat_trans = lat_L5 + lat_L9

        # AggNet-L1: L3 + Trans-L1 + L13
        bw_aggnet  = (bw_L3 + bw_trans + bw_L13) / 3
        lat_aggnet = lat_L3 + lat_trans + lat_L13

        # E2E-L1: L1 + AggNet-L1
        bw_e2e  = (bw_L1 + bw_aggnet) / 2
        lat_e2e = lat_L1 + lat_aggnet

        return {
            'Trans-L1' : (bw_trans,  lat_trans),
            'AggNet-L1': (bw_aggnet, lat_aggnet),
            'E2E-L1'   : (bw_e2e,    lat_e2e),
        }
