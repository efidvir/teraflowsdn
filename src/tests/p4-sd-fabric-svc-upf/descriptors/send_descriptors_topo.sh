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


CREDENTIALS="admin:admin"
CONTEXT="admin"
TFS_IP="192.168.5.137"
HEADER="Content-Type: application/json"

###### Disclaimer: Currently TFS does not possess a single NBI endpoint where all context, topologies, devices, and links can be given at once.
# For this reason, you need to issue 4 different requests to 4 different NBI endpoints as follows.

# curl -X POST --header "Content-Type: application/json" --data @context.json    --user "admin:admin" http://192.168.5.137/tfs-api/contexts
# curl -X POST --header "Content-Type: application/json" --data @topologies.json --user "admin:admin" http://192.168.5.137/tfs-api/context/admin/topologies
# curl -X POST --header "Content-Type: application/json" --data @devices.json    --user "admin:admin" http://192.168.5.137/tfs-api/devices
# curl -X POST --header "Content-Type: application/json" --data @links.json      --user "admin:admin" http://192.168.5.137/tfs-api/links

dispatch() {
    echo "Onboarding topology"
    curl -X POST --header "${HEADER}" --data @context.json    --user ${CREDENTIALS} http://${TFS_IP}/tfs-api/contexts
    curl -X POST --header "${HEADER}" --data @topologies.json --user ${CREDENTIALS} http://${TFS_IP}/tfs-api/context/${CONTEXT}/topologies
    curl -X POST --header "${HEADER}" --data @devices.json    --user ${CREDENTIALS} http://${TFS_IP}/tfs-api/devices
    curl -X POST --header "${HEADER}" --data @links.json      --user ${CREDENTIALS} http://${TFS_IP}/tfs-api/links
}

dispatch

exit 0
