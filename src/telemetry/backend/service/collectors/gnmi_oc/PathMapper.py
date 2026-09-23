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
from typing import Dict, List, Optional, Union
from .KPI import KPI

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)


class PathMapper:
    """
    Generate **multiple candidate paths** for an interface KPI.
    The mapper is deliberately generic: it knows only the leaf names commonly used across OpenConfig, and
    a prefix variants ('.../state/counters', '.../state').

    Subscription logic will try each candidate until one succeeds
    against the target device.
    """

    # --------------------------------------------------------------#
    #  Leaf names that can satisfy each KPI                         #
    # --------------------------------------------------------------#
    _LEAF_CANDIDATES: Dict[KPI, List[str]] = {
        # There are multiple leaf names that can satisfy each KPI but they can be added or removed
        # in the future. The list is not exhaustive, but it covers the most common cases
        # across OpenConfig implementations. The collector will try each until one succeeds.
        # ---- packets ---------------------------------------------------
        KPI.KPISAMPLETYPE_PACKETS_TRANSMITTED: [
            "out-pkts", "out-unicast-pkts", "tx-pkts", "packets-output"
        ],
        KPI.KPISAMPLETYPE_PACKETS_RECEIVED: [
            "in-pkts", "in-unicast-pkts", "rx-pkts", "packets-input"
        ],
        KPI.KPISAMPLETYPE_PACKETS_DROPPED: [
            "in-discards", "out-discards", "packets-drop"
        ],

        # ---- bytes -----------------------------------------------------
        KPI.KPISAMPLETYPE_BYTES_TRANSMITTED: [
            "out-octets", "tx-octets", "bytes-output"
        ],
        KPI.KPISAMPLETYPE_BYTES_RECEIVED: [
            "in-octets", "rx-octets", "bytes-input"
        ],
        KPI.KPISAMPLETYPE_BYTES_DROPPED: [
            "in-octets-discarded", "out-octets-discarded", "bytes-drop"
        ],

        # ---- power (TODO: List time need to be verified) -------------
        # Note: Inband power is not a standard leaf in OpenConfig, but
        # it is included here for completeness. The actual leaf names
        # may vary by implementation.
        KPI.KPISAMPLETYPE_INBAND_POWER: [
            "inband-power", "inband-power-state"
        ],
        
        # ---- total power (optical wavelength router) ----------------
        # For optical devices using FlexScale MGON YANG model
        KPI.KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER : [
            "optical-power-total-input/instant",        
        ],
    }

    # --------------------------------------------------------------#
    #  Prefix variants (no explicit origin)                         #
    # --------------------------------------------------------------#
    # More leaf prefixes can be added here if needed. 
    # The collector will try each prefix with the endpoint and leaf names.
    _PREFIXES = [
        'interfaces/interface[name={endpoint}]/state/counters/{leaf}',
        # 'interfaces/interface[name="{endpoint}"]/state/{leaf}',
    ]
    
    # Wavelength router prefixes (for optical devices)
    # Uses oc-wave-router and fsmgon module prefixes to avoid origin extraction issues
    _WAVELENGTH_ROUTER_PREFIXES = [
        'oc-wave-router:wavelength-router/fsmgon:optical-bands/optical-band[index={endpoint}]/state/{leaf}',
        # Also try without the root prefix as fallback
        'wavelength-router/fsmgon:optical-bands/optical-band[index={endpoint}]/state/{leaf}',
    ]
    # --------------------------------------------------------------#
    #  Public helper                                                #
    # --------------------------------------------------------------#
    @classmethod
    def build(cls,
              endpoint: str, kpi: Union[KPI, int], resource: Optional[str] = None
              ) -> List[str]:
        """
        Return **a list** of path strings.

        :param endpoint:  Interface name (e.g. 'Ethernet0') or optical band index (e.g. '1')
        :param kpi:       KPI enum
        :param resource:  Resource type: 'interface' or 'wavelength-router'
        """
        try:
            kpi_enum = KPI(kpi)
        except ValueError as exc:
            raise ValueError(f"Unsupported KPI code: {kpi}") from exc

        leaves = cls._LEAF_CANDIDATES.get(kpi_enum, [])
        if not leaves:
            raise ValueError(f"No leaf candidates for KPI {kpi_enum}")

        paths: List[str] = []
        for leaf in leaves:
            if resource == "interface":
                # Use standard interface prefixes
                for prefix in cls._PREFIXES:
                    paths.append(prefix.format(endpoint=endpoint, leaf=leaf))
            elif resource == "wavelength-router":
                # Use wavelength router prefixes with module prefixes to avoid origin extraction
                for prefix in cls._WAVELENGTH_ROUTER_PREFIXES:
                    paths.append(prefix.format(endpoint=endpoint, leaf=leaf))
            else:
                raise ValueError(f"Unsupported resource: {resource}")

        logger.debug("Built %d candidate path(s) for %s on %s (resource=%s)",
                     len(paths), kpi_enum.name, endpoint, resource)
        return paths
