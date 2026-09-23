#!/bin/bash
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

PROJECTDIR=`pwd`
cd $PROJECTDIR/src
RCFILE=$PROJECTDIR/coverage/.coveragerc

export KFK_SERVER_ADDRESS='127.0.0.1:9092'


IP_KPI=$(kubectl get all --all-namespaces | grep service/kpi-managerservice | awk '{print $4}')
export IP_KPI
echo "KPI Manager Service IP: ${IP_KPI}"

IP_TELE=$(kubectl get all --all-namespaces | grep service/telemetryservice | awk '{print $4}')
export IP_TELE
echo "Telemetry Frontend Service IP: ${IP_TELE}"

IP_CONTEXT=$(kubectl get all --all-namespaces | grep service/contextservice | awk '{print $4}')
export IP_CONTEXT
echo "Context Service IP: ${IP_CONTEXT}"

# This is unit test (should be tested with container-lab running)
python3 -m pytest --log-level=info --log-cli-level=info --verbose \
    telemetry/backend/tests/gnmi_oc/test_unit_GnmiOpenConfigCollector.py::test_full_workflow

# This is integration test (should be tested with container-lab running)
# python3 -m pytest --log-level=info --log-cli-level=info --verbose \
#     telemetry/backend/tests/gnmi_oc/test_integration_GnmiOCcollector.py

echo "Bye!"
