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


from enum import IntEnum, unique

@unique
class KPI(IntEnum):         
    # TODO: verify KPI names and codes with KPI proto file. (How many TFS supports)
    """Generic KPI codes that map to interface statistics."""
    KPISAMPLETYPE_PACKETS_TRANSMITTED       = 101
    KPISAMPLETYPE_PACKETS_RECEIVED          = 102
    KPISAMPLETYPE_PACKETS_DROPPED           = 103
    KPISAMPLETYPE_BYTES_TRANSMITTED         = 201
    KPISAMPLETYPE_BYTES_RECEIVED            = 202
    KPISAMPLETYPE_BYTES_DROPPED             = 203
    KPISAMPLETYPE_INBAND_POWER              = 301
    KPISAMPLETYPE_OPTICAL_TOTAL_INPUT_POWER = 503
    # TODO: Add more KPIs as needed,
