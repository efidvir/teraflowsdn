#!/bin/bash
# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# Physical interfaces
HOST_IFACE_EXT="mgmt"      # Interface towards TFS (management)
SW_IFACE_DATA_LEFT="dp-1"  # Interface towards the 5G gNB (data plane)
SW_IFACE_DATA_RIGHT="dp-2" # Interface towards the Data Network (data plane)

# Subnets managed by the switch
DOMAIN_IP_LEFT="10.10.1.1/24"  # Left-hand  side subnet (5G gNB)
DOMAIN_IP_RIGHT="10.10.2.1/24" # Right-hand side subnet (DNN)

# Transport port where the P4Runtime gRPC server is deployed on the switch
SW_P4RT_GRPC_PORT="50001"

# Transport port where the P4Runtime gNMI server is deployed on the switch
SW_P4RT_GNMI_PORT="50000"

# Transport port where Stratum listens to local calls
SW_P4RT_LOCAL_PORT="50101"
