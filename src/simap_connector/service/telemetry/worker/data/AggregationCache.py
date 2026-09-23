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


import logging, threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Tuple


LOGGER = logging.getLogger(__name__)


@dataclass
class LinkSample:
    network_id            : str
    link_id               : str
    bandwidth_utilization : float
    latency               : float
    related_service_ids   : Set[str] = field(default_factory=set)


@dataclass
class AggregatedLinkSample:
    timestamp             : datetime
    bandwidth_utilization : float     = field(default=0.0)
    latency               : float     = field(default=0.0)
    related_service_ids   : Set[str] = field(default_factory=set)


class AggregationCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples : Dict[Tuple[str, str], LinkSample] = dict()
        self._last_valid_aggregation : Optional[AggregatedLinkSample] = None


    def update(self, link_sample : LinkSample) -> None:
        link_key = (link_sample.network_id, link_sample.link_id)
        with self._lock:
            self._samples[link_key] = link_sample
        
        MSG = '[update] Received sample for link ({:s}, {:s}): BW={:.2f}%, Latency={:.3f}ms, Services={:s}'
        LOGGER.debug(MSG.format(
            link_sample.network_id, link_sample.link_id,
            link_sample.bandwidth_utilization, link_sample.latency,
            str(link_sample.related_service_ids)
        ))


    def aggregate(self) -> AggregatedLinkSample:
        with self._lock:
            num_samples = len(self._samples)
            if num_samples > 0:
                MSG = '[aggregate] Aggregating {:d} supporting link(s)'
                LOGGER.info(MSG.format(num_samples))
            
            if num_samples == 0:
                if self._last_valid_aggregation is not None:
                    MSG = '[aggregate] No samples available, reusing last valid aggregation: BW={:.2f}%, Latency={:.3f}ms'
                    LOGGER.warning(MSG.format(
                        self._last_valid_aggregation.bandwidth_utilization,
                        self._last_valid_aggregation.latency
                    ))
                    # Return a copy with updated timestamp
                    return AggregatedLinkSample(
                        timestamp=datetime.now(timezone.utc),
                        bandwidth_utilization=self._last_valid_aggregation.bandwidth_utilization,
                        latency=self._last_valid_aggregation.latency,
                        related_service_ids=self._last_valid_aggregation.related_service_ids.copy()
                    )
                else:
                    MSG = '[aggregate] No samples available and no cached data, returning zeros'
                    LOGGER.warning(MSG)
                    return AggregatedLinkSample(timestamp=datetime.now(timezone.utc))
            
            agg = AggregatedLinkSample(timestamp=datetime.now(timezone.utc))
            for link_key, sample in self._samples.items():
                network_id, link_id = link_key
                
                MSG = '[aggregate]   - Link ({:s}, {:s}): BW={:.2f}%, Latency={:.3f}ms, Services={:s}'
                LOGGER.debug(MSG.format(
                    network_id, link_id,
                    sample.bandwidth_utilization, sample.latency,
                    str(sample.related_service_ids)
                ))
                
                agg.bandwidth_utilization = max(
                    agg.bandwidth_utilization, sample.bandwidth_utilization
                )
                agg.latency = agg.latency + sample.latency
                agg.related_service_ids = agg.related_service_ids.union(
                    sample.related_service_ids
                )
            
            if num_samples > 0:
                MSG = '[aggregate] Result: BW={:.2f}% (max), Latency={:.3f}ms (sum), Services={:s}'
                LOGGER.info(MSG.format(
                    agg.bandwidth_utilization, agg.latency,
                    str(agg.related_service_ids)
                ))
                # Cache this valid aggregation for future use
                self._last_valid_aggregation = agg
            
            return agg
