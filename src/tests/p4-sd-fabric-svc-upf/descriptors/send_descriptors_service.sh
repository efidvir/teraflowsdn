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

##### Raw HTTP requests to provision the UPF TFS service
# curl -X PUT --header "Content-Type: application/json" --data @service-upf.json --user "admin:admin" http://192.168.5.137/tfs-api/context/admin/service/p4-service-upf

curl -X PUT  --header "${HEADER}" --data @service-upf.json --user ${CREDENTIALS} http://${TFS_IP}/tfs-api/context/${CONTEXT}/service/p4-service-upf
