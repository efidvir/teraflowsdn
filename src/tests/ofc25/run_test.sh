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
echo "Running OFC 25 tests from $PROJECTDIR/src ..."

# Determine which test suite to run based on argument
TEST_SUITE=${1:-"all"}

case "$TEST_SUITE" in
    "all")
        echo "=== Running Full Test Suite ==="

        echo "--- Running Optical Layer Initialization ---"
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_opt.sh \
            --tfs-profile=opt \
            --tfs-topology-descriptor=topology_opt.json
        echo "Waiting 5 seconds for initialization ..."
        sleep 5

        echo "--- Running IP/Packet Layer Initialization ---"
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_ip.sh \
            --tfs-profile=ip \
            --tfs-topology-descriptor=topology_ip.json
        echo "Waiting 5 seconds for initialization ..."
        sleep 5

        echo "--- Running E2E Layer Initialization ---"
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_e2e.sh \
            --tfs-profile=e2e \
            --tfs-topology-descriptor=topology_e2e.json
        echo "Waiting 5 seconds for initialization ..."
        sleep 5

        echo "--- Running Service Creation/Deletion ---"
        pytest --verbose tests/ofc25/tests/test_functional_create_vlinks.py
        sleep 5
        pytest --verbose tests/ofc25/tests/test_functional_delete_vlinks.py

        echo "--- Running Cleanup In Reverse Order ---"
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_e2e.sh \
            --tfs-profile=e2e \
            --tfs-topology-descriptor=topology_e2e.json
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_ip.sh \
            --tfs-profile=ip \
            --tfs-topology-descriptor=topology_ip.json
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_opt.sh \
            --tfs-profile=opt \
            --tfs-topology-descriptor=topology_opt.json
        ;;

    "init_opt")
        echo "=== Running Optical Layer Initialization ==="
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_opt.sh \
            --tfs-profile=opt \
            --tfs-topology-descriptor=topology_opt.json
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_opt.sh \
            --tfs-profile=opt \
            --tfs-topology-descriptor=topology_opt.json
        ;;

    "init_ip")
        echo "=== Running IP/Packet Layer Initialization ==="
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_ip.sh \
            --tfs-profile=ip \
            --tfs-topology-descriptor=topology_ip.json
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_ip.sh \
            --tfs-profile=ip \
            --tfs-topology-descriptor=topology_ip.json
        ;;

    "init_e2e")
        echo "=== Running E2E Layer Initialization ==="
        pytest --verbose tests/ofc25/tests/test_functional_cleanup.py \
            --tfs-runtime-script=tfs_runtime_env_vars_e2e.sh \
            --tfs-profile=e2e \
            --tfs-topology-descriptor=topology_e2e.json
        pytest --verbose tests/ofc25/tests/test_functional_bootstrap.py \
            --tfs-runtime-script=tfs_runtime_env_vars_e2e.sh \
            --tfs-profile=e2e \
            --tfs-topology-descriptor=topology_e2e.json
        ;;

    "service")
        echo "=== Running Service Creation/Deletion ==="
        pytest --verbose tests/ofc25/tests/test_functional_create_vlinks.py
        sleep 5
        pytest --verbose tests/ofc25/tests/test_functional_delete_vlinks.py
        ;;

    *)
        echo "Usage: $0 [init_opt|init_ip|init_e2e|service|all]"
        echo "  init_opt - Run optical layer initialization only"
        echo "  init_ip  - Run IP/packet layer initialization only"
        echo "  init_e2e - Run E2E orchestration layer initialization only"
        echo "  service  - Run service creation/deletion only"
        echo "  all      - Run complete test suite (default)"
        exit 1
        ;;
esac
