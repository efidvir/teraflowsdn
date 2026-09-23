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

ALLOWED_LINKS_PER_CONTROLLER = {
    'e2e'      : { 'L1',  'L2'                          },
    'agg'      : { 'L14'                                },
    'trans-pkt': { 'L3',  'L5', 'L6', 'L9', 'L10', 'L13' },
    # The remaining can not be monitored therefore they are not included in the allowed links for the controllers
    # 'agg'      : { 'L7ab',  'L7ba',  'L8ab',  'L8ba', 'L11ab', 'L11ba', 'L12ab', 'L12ba',  },
}
# NOTE: Ranges should be less than 100 because the schema does not allow
# bandwidth-utilization to exceed 100% 
# As per schema below: (percentage of link capacity)
#     /* --- Local typedefs --- */
    # typedef percent {
    #     type decimal64 {
    #         fraction-digits 2;
    #         range "0 .. 100";
    #     }
    #     units "percent";
    #     description "0–100 percent value.";
    # }
LINKS_CAPACITY = {
    'L1'    : 100, 'L2'   : 100,   'L3'   : 100,  'L4'   : 100,
    'L5'    : 100, 'L6'   : 100,  'L9'   : 100,  'L10'  : 100,
    'L7ab'  : 100, 'L7ba' : 100, 'L8ab' : 100, 'L8ba' : 100, 'L11ab' : 100,
    'L11ba' : 100, 'L12ab': 100, 'L12ba': 100, 'L13'  : 100,  'L14'   : 100,
}
