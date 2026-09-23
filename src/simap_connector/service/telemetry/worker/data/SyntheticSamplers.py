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


import random, threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple
from .Sample import Sample


@dataclass
class SyntheticSampler:
    """Simple sampler with temporal continuity - next values stay close to previous values.
    
    Bandwidth ranges based on connection count:
      0 conns: avg=3%,   range 1-10%
      1 conn:  avg=25%,  range 15-30%
      2 conns: avg=45%,  range 35-55%
      3 conns: avg=65%,  range 60-80%
      4+ conns: avg=85%, range 80-95%
    
    Latency uses bandwidth ranges divided by 10 (0-10ms):
      0 conns: avg=0.3ms, range 0.1-1.0ms
      1 conn:  avg=2.5ms, range 1.5-3.0ms
      2 conns: avg=4.5ms, range 3.5-5.5ms
      3 conns: avg=6.5ms, range 6.0-8.0ms
      4+ conns: avg=8.5ms, range 8.0-9.5ms
    
    Values vary by ±1% between consecutive samples for temporal continuity.
    """
    connection_count : int             = field(default = 0)
    link_capacity    : float           = field(default = 100.0)
    prev_bw          : Optional[float] = field(default = None)
    prev_latency     : Optional[float] = field(default = None)
    
    # Connection count to (avg, min, max) percentage mapping
    # Latency uses same ranges divided by 10 (0-10ms range)
    BW_RANGES = {
           0: (3,  5,  10),
           1: (25, 15, 30),
           2: (40, 35, 50),
           3: (60, 65, 80),
           4: (85, 80, 95),
    }
    LAT_RANGES = {
        0: (0.4, 0.1, 0.8),
        1: (1.4, 1.0, 1.8),
        2: (2.4, 2.0, 2.8),
        3: (3.4, 3.0, 3.8),
        4: (4.4, 4.0, 4.8),
    }

    @classmethod
    def create_random(
        cls,
        connection_count   : int    = 0,
        link_capacity      : float  = 100.0
    ) -> 'SyntheticSampler':
        """Factory method for compatibility (ignores unused parameters)."""
        return cls(connection_count=connection_count, link_capacity=link_capacity)

    def get_sample(self) -> Tuple[Sample, Sample]:
        """Generate bandwidth and latency samples with temporal continuity.
        
        Returns:
            Tuple of (bandwidth_sample, latency_sample)
        """
        timestamp = datetime.now().timestamp()
        conn_key  = min(self.connection_count, 4)

        avg, min_bw, max_bw = self.BW_RANGES[conn_key]
        if self.prev_bw is None:
            bw_utilization = avg
        else:
            noise_factor   = random.uniform(-0.01, 0.01) # ±1% noise for bandwidth
            bw_utilization = self.prev_bw * (1.0 + noise_factor)
        
        bw_utilization = max(min_bw, min(max_bw, bw_utilization))
        self.prev_bw   = bw_utilization
        
        avg_lat, min_lat, max_lat = self.LAT_RANGES[conn_key]
        if self.prev_latency is None:
            latency = avg_lat
        else:
            noise_factor = random.uniform(-0.05, 0.05)  # ±5% noise for latency
            latency      = self.prev_latency * (1.0 + noise_factor)
        
        latency           = max(min_lat, min(max_lat, latency))
        self.prev_latency = latency
        
        # actual_bw_utilization = (bw_utilization / 100.0) * self.link_capacity
        
        return (Sample(timestamp, 0, bw_utilization), Sample(timestamp, 0, latency))


class SyntheticSamplers:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samplers : Dict[str, SyntheticSampler] = dict()

    def add_sampler(
        self, sampler_name : str,
        connection_count   : int                 = 0,
        link_capacity      : float               = 100.0
    ) -> None:
        with self._lock:
            if sampler_name in self._samplers:
                MSG = 'SyntheticSampler({:s}) already exists'
                raise Exception(MSG.format(sampler_name))
            self._samplers[sampler_name] = SyntheticSampler.create_random(
                connection_count=connection_count,
                link_capacity=link_capacity
            )

    def remove_sampler(self, sampler_name : str) -> None:
        with self._lock:
            self._samplers.pop(sampler_name, None)

    def get_sample(self, sampler_name : str) -> Tuple[Sample, Sample]:
        """Get both bandwidth and latency samples.
        Returns: Tuple of (bandwidth_sample, latency_sample)
        """
        with self._lock:
            sampler = self._samplers.get(sampler_name)
            if sampler_name not in self._samplers:
                MSG = 'SyntheticSampler({:s}) does not exist'
                raise Exception(MSG.format(sampler_name))
            return sampler.get_sample()
