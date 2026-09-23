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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
TEST_NAME="osm_end2end"

IMAGE_TAG="${OSM_E2E_IMAGE:-${TEST_NAME}:local}"
RESULTS_DIR="${OSM_E2E_RESULTS_DIR:-${SCRIPT_DIR}/local_results}"
COMPONENT_LOGS_DIR="${RESULTS_DIR}/component_logs"
CLAB_TMP_DIR="${OSM_E2E_CLAB_TMPDIR:-/tmp/clab/${TEST_NAME}}"
RUNTIME_ENV_FILE="${REPO_ROOT}/tfs_runtime_env_vars.sh"

OSM_E2E_CLEAN_START="${OSM_E2E_CLEAN_START:-yes}"
OSM_E2E_DEPLOY_TFS="${OSM_E2E_DEPLOY_TFS:-yes}"
OSM_E2E_BUILD_IMAGE="${OSM_E2E_BUILD_IMAGE:-yes}"
OSM_E2E_CONTAINERLAB_USE_SUDO="${OSM_E2E_CONTAINERLAB_USE_SUDO:-yes}"
OSM_E2E_WAIT_AFTER_CREATE="${OSM_E2E_WAIT_AFTER_CREATE:-60}"
OSM_E2E_WAIT_AFTER_REMOVE="${OSM_E2E_WAIT_AFTER_REMOVE:-60}"

read -r -a KUBECTL_CMD_ARR <<< "${KUBECTL_CMD:-kubectl}"
read -r -a HELM_CMD_ARR <<< "${HELM_CMD:-helm3}"
read -r -a MICROK8S_CMD_ARR <<< "${MICROK8S_CMD:-microk8s}"

PHASES=("$@")
if [[ ${#PHASES[@]} -eq 0 ]]; then
    PHASES=("all")
fi

usage() {
    cat <<'EOF'
Usage:
  ./src/tests/osm_end2end/run-local.sh [all|prepare|build-image|deploy-clab|deploy-tfs|onboarding|untagged|tagged|logs|destroy-clab]

Environment:
  OSM_E2E_IMAGE=osm_end2end:local
  OSM_E2E_RESULTS_DIR=src/tests/osm_end2end/local_results
  OSM_E2E_CLEAN_START=yes|no
  OSM_E2E_DEPLOY_TFS=yes|no
  OSM_E2E_BUILD_IMAGE=yes|no
  OSM_E2E_CONTAINERLAB_USE_SUDO=yes|no
  KUBECTL_CMD="kubectl"
  HELM_CMD="helm3"
  MICROK8S_CMD="microk8s"
EOF
}

require_cmd() {
    local cmd=$1
    command -v "${cmd}" >/dev/null 2>&1 || {
        echo "Command not found: ${cmd}" >&2
        exit 1
    }
}

kctl() {
    "${KUBECTL_CMD_ARR[@]}" "$@"
}

hctl() {
    "${HELM_CMD_ARR[@]}" "$@"
}

mctl() {
    "${MICROK8S_CMD_ARR[@]}" "$@"
}

clab() {
    if [[ "${OSM_E2E_CONTAINERLAB_USE_SUDO}" == "yes" ]]; then
        sudo containerlab "$@"
    else
        containerlab "$@"
    fi
}

docker_cleanup_for_test() {
    clab destroy --all --cleanup || true
    docker container prune --force
    docker image prune --force
    docker network prune --force
}

cleanup_k8s_for_test() {
    local existing_namespaces
    existing_namespaces="$(kctl get namespace -o jsonpath='{.items[*].metadata.name}')"
    local old_nats_namespaces
    old_nats_namespaces="$(echo "${existing_namespaces}" | tr ' ' '\n' | grep -E '^nats' || true)"
    for ns in ${old_nats_namespaces}; do
        if hctl status "${ns}" -n "${ns}" >/dev/null 2>&1; then
            hctl uninstall "${ns}" -n "${ns}" || true
        fi
    done

    local old_namespaces
    old_namespaces="$(echo "${existing_namespaces}" | tr ' ' '\n' | grep -E '^(tfs|crdb|qdb|kafka|nats)$' || true)"
    if [[ -n "${old_namespaces}" ]]; then
        kctl delete namespace ${old_namespaces} || true
    fi

    kctl get pods --all-namespaces --no-headers --field-selector=status.phase=Failed \
        -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name \
        | xargs --no-run-if-empty --max-args=2 kctl delete pod --namespace || true
}

wait_for_k8s() {
    mctl status --wait-ready
    local loop_max_attempts=30
    local loop_counter=0
    while ! kctl get pods --all-namespaces >/dev/null 2>&1; do
        printf "."
        sleep 1
        loop_counter=$((loop_counter + 1))
        if [[ "${loop_counter}" -ge "${loop_max_attempts}" ]]; then
            echo "Max attempts reached waiting for Kubernetes API." >&2
            exit 1
        fi
    done
    echo
    kctl get pods --all-namespaces
}

wait_for_tfs_deployments() {
    local namespace="${TFS_K8S_NAMESPACE:-tfs}"
    local deployments=(
        contextservice
        deviceservice
        pathcompservice
        serviceservice
        nbiservice
    )
    local deployment
    for deployment in "${deployments[@]}"; do
        kctl --namespace "${namespace}" rollout status "deployment/${deployment}" --timeout=300s
    done
}

prepare_clab_topology() {
    rm -rf "${CLAB_TMP_DIR}"
    mkdir -p "${CLAB_TMP_DIR}"
    cp -R "${SCRIPT_DIR}/clab/." "${CLAB_TMP_DIR}/"
}

build_image() {
    docker buildx build -t "${IMAGE_TAG}" -f "${SCRIPT_DIR}/Dockerfile" "${REPO_ROOT}"
}

deploy_clab() {
    prepare_clab_topology
    clab deploy --reconfigure --topo "${CLAB_TMP_DIR}/${TEST_NAME}.clab.yml"
}

destroy_clab() {
    if [[ -f "${CLAB_TMP_DIR}/${TEST_NAME}.clab.yml" ]]; then
        clab destroy --cleanup --topo "${CLAB_TMP_DIR}/${TEST_NAME}.clab.yml" || true
    fi
}

dump_router_configs() {
    local label=$1
    local slug
    slug="$(echo "${label}" | tr ' /' '__')"
    {
        echo "==== ${label} ===="
        clab exec --name "${TEST_NAME}" --label clab-node-name=r1 --cmd "Cli --command \"enable"$'\n'"show running-config\""
        clab exec --name "${TEST_NAME}" --label clab-node-name=r2 --cmd "Cli --command \"enable"$'\n'"show running-config\""
        clab exec --name "${TEST_NAME}" --label clab-node-name=r3 --cmd "Cli --command \"enable"$'\n'"show running-config\""
    } | tee "${RESULTS_DIR}/router-config-${slug}.log"
}

dump_component_logs() {
    mkdir -p "${COMPONENT_LOGS_DIR}"
    local namespace="${TFS_K8S_NAMESPACE:-tfs}"
    local components=(
        contextservice:server
        deviceservice:server
        pathcompservice:frontend
        serviceservice:server
        nbiservice:server
    )
    local entry deployment container
    for entry in "${components[@]}"; do
        deployment="${entry%%:*}"
        container="${entry##*:}"
        kctl --namespace "${namespace}" logs "deployment/${deployment}" -c "${container}" \
            > "${COMPONENT_LOGS_DIR}/${deployment}.log" 2>&1 || true
    done
}

require_runtime_env_file() {
    if [[ ! -f "${RUNTIME_ENV_FILE}" ]]; then
        echo "Runtime env file not found: ${RUNTIME_ENV_FILE}" >&2
        echo "Deploy TFS first so tfs_runtime_env_vars.sh is generated." >&2
        exit 1
    fi
}

run_onboarding() {
    require_runtime_env_file
    docker run -t --rm --name "${TEST_NAME}-onboarding" --network=host \
        --volume "${RUNTIME_ENV_FILE}:/var/teraflow/tfs_runtime_env_vars.sh" \
        --volume "${RESULTS_DIR}:/opt/results" \
        "${IMAGE_TAG}" /var/teraflow/run-onboarding.sh
}

run_osm_test() {
    local action=$1
    local variant=$2
    require_runtime_env_file
    docker run -t --rm --name "${TEST_NAME}-${variant}-${action}" --network=host \
        --env OSM_SERVICE_VARIANT="${variant}" \
        --volume "${RUNTIME_ENV_FILE}:/var/teraflow/tfs_runtime_env_vars.sh" \
        --volume "${RESULTS_DIR}:/opt/results" \
        "${IMAGE_TAG}" "/var/teraflow/run-osm-service-${action}.sh"
}

ping_check() {
    local src=$1
    local dst_ip=$2
    local pattern=$3
    local output
    output="$(clab exec --name "${TEST_NAME}" --label clab-node-name="${src}" --cmd "ping -n -c3 ${dst_ip}" --format json)"
    echo "${output}"
    if echo "${output}" | grep -E "${pattern}" >/dev/null; then
        echo "PASSED ${src}->${dst_ip}"
        return 0
    fi
    echo "FAILED ${src}->${dst_ip}"
    return 1
}

assert_no_connectivity() {
    local src=$1
    local local_ip=$2
    local local_gw=$3
    local remote_gw=$4
    local remote_ip=$5
    ping_check "${src}" "${local_ip}" "3 packets transmitted, 3 received, 0% packet loss"
    ping_check "${src}" "${local_gw}" "3 packets transmitted, 0 received,( [\+]{0,1}[0-9]+ error[s]{0,1},)? 100% packet loss"
    ping_check "${src}" "${remote_gw}" "3 packets transmitted, 0 received,( [\+]{0,1}[0-9]+ error[s]{0,1},)? 100% packet loss"
    ping_check "${src}" "${remote_ip}" "3 packets transmitted, 0 received,( [\+]{0,1}[0-9]+ error[s]{0,1},)? 100% packet loss"
}

assert_connectivity() {
    local src=$1
    local local_ip=$2
    local local_gw=$3
    local remote_gw=$4
    local remote_ip=$5
    ping_check "${src}" "${local_ip}" "3 packets transmitted, 3 received, 0% packet loss"
    ping_check "${src}" "${local_gw}" "3 packets transmitted, 3 received, 0% packet loss"
    ping_check "${src}" "${remote_gw}" "3 packets transmitted, 3 received, 0% packet loss"
    ping_check "${src}" "${remote_ip}" "3 packets transmitted, 3 received, 0% packet loss"
}

run_variant_cycle() {
    local variant=$1
    local src=$2
    local local_ip=$3
    local local_gw=$4
    local remote_gw=$5
    local remote_ip=$6

    echo "==== Starting ${variant} OSM service cycle ===="
    assert_no_connectivity "${src}" "${local_ip}" "${local_gw}" "${remote_gw}" "${remote_ip}"

    run_osm_test create "${variant}"
    sleep "${OSM_E2E_WAIT_AFTER_CREATE}"
    dump_router_configs "after configuring ${variant} OSM service"
    assert_connectivity "${src}" "${local_ip}" "${local_gw}" "${remote_gw}" "${remote_ip}"

    run_osm_test remove "${variant}"
    sleep "${OSM_E2E_WAIT_AFTER_REMOVE}"
    dump_router_configs "after removing ${variant} OSM service"
    assert_no_connectivity "${src}" "${local_ip}" "${local_gw}" "${remote_gw}" "${remote_ip}"
}

deploy_tfs() {
    (
        cd "${REPO_ROOT}"
        source "${SCRIPT_DIR}/deploy_specs.sh"
        ./deploy/crdb.sh
        ./deploy/nats.sh
        ./deploy/kafka.sh
        ./deploy/tfs.sh
        ./deploy/show.sh
    )
    wait_for_tfs_deployments
}

prepare() {
    require_cmd docker
    require_cmd containerlab
    require_cmd "${KUBECTL_CMD_ARR[0]}"
    require_cmd "${HELM_CMD_ARR[0]}"
    require_cmd "${MICROK8S_CMD_ARR[0]}"
    require_cmd yq
    mkdir -p "${RESULTS_DIR}" "${COMPONENT_LOGS_DIR}"

    if [[ "${OSM_E2E_CLEAN_START}" == "yes" ]]; then
        docker_cleanup_for_test
        wait_for_k8s
        cleanup_k8s_for_test
    fi

    wait_for_k8s
}

run_all() {
    prepare
    if [[ "${OSM_E2E_BUILD_IMAGE}" == "yes" ]]; then
        build_image
    fi
    deploy_clab
    sleep 3
    dump_router_configs "before any configuration"
    if [[ "${OSM_E2E_DEPLOY_TFS}" == "yes" ]]; then
        deploy_tfs
    fi
    run_onboarding
    dump_router_configs "after onboarding scenario"
    run_variant_cycle "untagged" "dc1_untagged" "172.16.1.10" "172.16.1.1" "172.16.3.1" "172.16.3.10"
    run_variant_cycle "tagged" "dc3_tagged" "172.17.1.10" "172.17.1.1" "172.17.3.1" "172.17.3.10"
    dump_component_logs
}

main() {
    local phase
    for phase in "${PHASES[@]}"; do
        case "${phase}" in
            all) run_all ;;
            prepare) prepare ;;
            build-image) build_image ;;
            deploy-clab) deploy_clab ;;
            deploy-tfs) deploy_tfs ;;
            onboarding) run_onboarding ;;
            untagged) run_variant_cycle "untagged" "dc1_untagged" "172.16.1.10" "172.16.1.1" "172.16.3.1" "172.16.3.10" ;;
            tagged) run_variant_cycle "tagged" "dc3_tagged" "172.17.1.10" "172.17.1.1" "172.17.3.1" "172.17.3.10" ;;
            logs) dump_component_logs ;;
            destroy-clab) destroy_clab ;;
            -h|--help|help) usage ;;
            *)
                echo "Unknown phase: ${phase}" >&2
                usage
                exit 1
                ;;
        esac
    done
}

main
