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
LAB_NAME="osm_end2end_gnmic"
TOPO_FILE="${SCRIPT_DIR}/osm_end2end_gnmic.clab.yml"
RESULTS_DIR="${SCRIPT_DIR}/results"

OSM_GNMIC_USE_SUDO="${OSM_GNMIC_USE_SUDO:-yes}"
GNMIC_USER="${GNMIC_USER:-admin}"
GNMIC_PASS="${GNMIC_PASS:-admin}"
GNMIC_PORT="${GNMIC_PORT:-6030}"
GNMIC_ENCODING="${GNMIC_ENCODING:-json_ietf}"
GNMIC_TIMEOUT="${GNMIC_TIMEOUT:-30s}"

mkdir -p "${RESULTS_DIR}"

clab() {
    if [[ "${OSM_GNMIC_USE_SUDO}" == "yes" ]]; then
        sudo containerlab "$@"
    else
        containerlab "$@"
    fi
}

gnmi() {
    local address=$1
    shift
    gnmic --address "${address}" --port "${GNMIC_PORT}" \
        --username "${GNMIC_USER}" --password "${GNMIC_PASS}" \
        --insecure --encoding "${GNMIC_ENCODING}" --timeout "${GNMIC_TIMEOUT}" "$@"
}

wait_for_router_ready() {
    local router=$1
    local address
    address="$(router_address "${router}")"

    echo "Waiting for ${router} gNMI readiness at ${address}..."
    for _ in $(seq 1 60); do
        if gnmi "${address}" capabilities >/dev/null 2>&1 && \
           gnmi "${address}" get --path /system/state/hostname >/dev/null 2>&1; then
            echo "${router} is ready."
            return 0
        fi
        sleep 2
    done

    echo "Timed out waiting for ${router} gNMI readiness" >&2
    return 1
}

gnmi_update_json() {
    local address=$1
    local path=$2
    local json_value=$3
    local payload_file
    payload_file="$(mktemp)"
    printf '%s\n' "${json_value}" > "${payload_file}"
    gnmi "${address}" set --update-path "${path}" --update-file "${payload_file}"
    rm -f "${payload_file}"
}

gnmi_replace_json() {
    local address=$1
    local path=$2
    local json_value=$3
    local payload_file
    payload_file="$(mktemp)"
    printf '%s\n' "${json_value}" > "${payload_file}"
    gnmi "${address}" set --replace-path "${path}" --replace-file "${payload_file}"
    rm -f "${payload_file}"
}

router_address() {
    case "$1" in
        r1) echo "172.20.30.101" ;;
        r2) echo "172.20.30.102" ;;
        r3) echo "172.20.30.103" ;;
        *) echo "Unknown router: $1" >&2; exit 1 ;;
    esac
}

show_run() {
    local router=$1
    docker exec "clab-${LAB_NAME}-${router}" \
        bash -lc 'FastCli -p 15 -c "show running-config"'
}

show_run_interfaces() {
    local router=$1
    local iface_list=$2
    docker exec "clab-${LAB_NAME}-${router}" \
        bash -lc "FastCli -p 15 -c 'show running-config interfaces ${iface_list}'"
}

cli_config() {
    local router=$1
    local commands=$2
    docker exec "clab-${LAB_NAME}-${router}" \
        bash -lc "printf '%b' \"configure terminal\n${commands}\nend\n\" | Cli -p 15"
}

ping_node() {
    local node=$1
    local ip=$2
    clab exec --name "${LAB_NAME}" --label "clab-node-name=${node}" \
        --cmd "ping -n -c3 ${ip}" --format json
}

deploy() {
    clab destroy --cleanup --topo "${TOPO_FILE}" || true
    clab deploy --reconfigure --topo "${TOPO_FILE}"
    wait_for_router_ready r1
    wait_for_router_ready r2
    wait_for_router_ready r3
}

destroy() {
    clab destroy --cleanup --topo "${TOPO_FILE}" || true
}

baseline() {
    show_run r1 | tee "${RESULTS_DIR}/r1-baseline.txt"
    show_run r2 | tee "${RESULTS_DIR}/r2-baseline.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-baseline.txt"
    gnmi "$(router_address r1)" get --path /interfaces/interface --path /network-instances/network-instance \
        > "${RESULTS_DIR}/r1-baseline-gnmi.json"
    gnmi "$(router_address r2)" get --path /interfaces/interface --path /network-instances/network-instance \
        > "${RESULTS_DIR}/r2-baseline-gnmi.json"
    gnmi "$(router_address r3)" get --path /interfaces/interface --path /network-instances/network-instance \
        > "${RESULTS_DIR}/r3-baseline-gnmi.json"
}

capture_router_state() {
    local label=$1
    local router=$2
    local address
    local output_dir
    local interface_args=()
    local interface_show=""
    address="$(router_address "${router}")"
    output_dir="${RESULTS_DIR}/${label}"

    mkdir -p "${output_dir}"
    show_run "${router}" > "${output_dir}/${router}-show-run.txt"

    case "${router}" in
        r1|r3)
            interface_show="Ethernet2 Ethernet10 Ethernet11"
            interface_args=(
                --path "/interfaces/interface[name=Ethernet2]"
                --path "/interfaces/interface[name=Ethernet10]"
                --path "/interfaces/interface[name=Ethernet11]"
            )
            ;;
        r2)
            interface_show="Ethernet1 Ethernet3"
            interface_args=(
                --path "/interfaces/interface[name=Ethernet1]"
                --path "/interfaces/interface[name=Ethernet3]"
            )
            ;;
        *)
            echo "Unsupported router for capture: ${router}" >&2
            exit 1
            ;;
    esac

    show_run_interfaces "${router}" "${interface_show}" \
        > "${output_dir}/${router}-show-run-interfaces.txt"
    gnmi "${address}" get \
        "${interface_args[@]}" \
        --path "/network-instances/network-instance[name=default]/protocols/protocol[identifier=STATIC][name=STATIC]" \
        > "${output_dir}/${router}-state.json"
}

capture_lab_state() {
    local label=$1
    capture_router_state "${label}" r1
    capture_router_state "${label}" r2
    capture_router_state "${label}" r3
}

configure_router_l3_links() {
    local router=$1
    local uplink=$2
    local uplink_ip=$3
    local uplink_prefix=$4
    local downlink=${5:-}
    local downlink_ip=${6:-}
    local downlink_prefix=${7:-}

    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${uplink}]" \
        "{\"name\":\"${uplink}\",\"config\":{\"name\":\"${uplink}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${uplink_ip}\",\"config\":{\"ip\":\"${uplink_ip}\",\"prefix-length\":${uplink_prefix}}}]}}}]}}"

    if [[ -n "${downlink}" ]]; then
        gnmi_update_json "${address}" \
            "/interfaces/interface[name=${downlink}]" \
            "{\"name\":\"${downlink}\",\"config\":{\"name\":\"${downlink}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${downlink_ip}\",\"config\":{\"ip\":\"${downlink_ip}\",\"prefix-length\":${downlink_prefix}}}]}}}]}}"
    fi
}

configure_static_route() {
    local router=$1
    local prefix=$2
    local next_hop=$3
    local index=$4
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/network-instances/network-instance[name=default]/protocols/protocol[identifier=STATIC][name=STATIC]" \
        "{\"identifier\":\"openconfig-policy-types:STATIC\",\"name\":\"STATIC\",\"config\":{\"identifier\":\"openconfig-policy-types:STATIC\",\"name\":\"STATIC\",\"enabled\":true},\"static-routes\":{\"static\":[{\"prefix\":\"${prefix}\",\"config\":{\"prefix\":\"${prefix}\"},\"next-hops\":{\"next-hop\":[{\"index\":\"${index}\",\"config\":{\"index\":\"${index}\",\"next-hop\":\"${next_hop}\",\"metric\":1}}]}}]}}"
}

configure_access_subif0() {
    local router=$1
    local iface=$2
    local ip=$3
    local prefix=$4
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${ip}\",\"config\":{\"ip\":\"${ip}\",\"prefix-length\":${prefix}}}]}}}]}}"
}

configure_access_subif0_empty() {
    local router=$1
    local iface=$2
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true}}}]}}"
}

configure_access_subif125() {
    local router=$1
    local iface=$2
    local ip=$3
    local prefix=$4
    local vlan_id=$5
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":${vlan_id},\"config\":{\"index\":${vlan_id},\"enabled\":true},\"openconfig-vlan:vlan\":{\"match\":{\"single-tagged\":{\"config\":{\"vlan-id\":${vlan_id}}}}},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${ip}\",\"config\":{\"ip\":\"${ip}\",\"prefix-length\":${prefix}}}]}}}]}}"
}

configure_access_subif0_and_125() {
    local router=$1
    local iface=$2
    local ip=$3
    local prefix=$4
    local vlan_id=$5
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true}}},{\"index\":${vlan_id},\"config\":{\"index\":${vlan_id},\"enabled\":true},\"openconfig-vlan:vlan\":{\"match\":{\"single-tagged\":{\"config\":{\"vlan-id\":${vlan_id}}}}},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${ip}\",\"config\":{\"ip\":\"${ip}\",\"prefix-length\":${prefix}}}]}}}]}}"
}

replace_access_subif0_and_125() {
    local router=$1
    local iface=$2
    local ip=$3
    local prefix=$4
    local vlan_id=$5
    local address
    address="$(router_address "${router}")"

    gnmi_replace_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true}}},{\"index\":${vlan_id},\"config\":{\"index\":${vlan_id},\"enabled\":true},\"openconfig-vlan:vlan\":{\"match\":{\"single-tagged\":{\"config\":{\"vlan-id\":${vlan_id}}}}},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${ip}\",\"config\":{\"ip\":\"${ip}\",\"prefix-length\":${prefix}}}]}}}]}}"
}

configure_access_subif0_vlan125() {
    local router=$1
    local iface=$2
    local ip=$3
    local prefix=$4
    local vlan_id=$5
    local address
    address="$(router_address "${router}")"

    gnmi_update_json "${address}" \
        "/interfaces/interface[name=${iface}]" \
        "{\"name\":\"${iface}\",\"config\":{\"name\":\"${iface}\",\"type\":\"iana-if-type:ethernetCsmacd\",\"enabled\":true},\"subinterfaces\":{\"subinterface\":[{\"index\":0,\"config\":{\"index\":0,\"enabled\":true},\"openconfig-vlan:vlan\":{\"match\":{\"single-tagged\":{\"config\":{\"vlan-id\":${vlan_id}}}}},\"openconfig-if-ip:ipv4\":{\"config\":{\"enabled\":true},\"addresses\":{\"address\":[{\"ip\":\"${ip}\",\"config\":{\"ip\":\"${ip}\",\"prefix-length\":${prefix}}}]}}}]}}"
}

configure_core() {
    configure_router_l3_links r1 Ethernet2 10.254.203.193 30
    configure_router_l3_links r2 Ethernet1 10.254.203.194 30 Ethernet3 10.254.218.241 30
    configure_router_l3_links r3 Ethernet2 10.254.218.242 30

    configure_static_route r1 172.16.3.0/24 10.254.203.194 AUTO_1_10-254-203-194
    configure_static_route r2 172.16.1.0/24 10.254.203.193 AUTO_1_10-254-203-193
    configure_static_route r2 172.16.3.0/24 10.254.218.242 AUTO_1_10-254-218-242
    configure_static_route r3 172.16.1.0/24 10.254.218.241 AUTO_1_10-254-218-241
}

configure_tagged_routes() {
    configure_static_route r1 172.17.3.0/24 10.254.203.194 AUTO_1_10-254-203-194-tagged
    configure_static_route r2 172.17.1.0/24 10.254.203.193 AUTO_1_10-254-203-193-tagged
    configure_static_route r2 172.17.3.0/24 10.254.218.242 AUTO_1_10-254-218-242-tagged
    configure_static_route r3 172.17.1.0/24 10.254.218.241 AUTO_1_10-254-218-241-tagged
}

experiment_untagged() {
    configure_core
    configure_access_subif0 r1 Ethernet10 172.16.1.1 24
    configure_access_subif0 r3 Ethernet10 172.16.3.1 24
    show_run r1 | tee "${RESULTS_DIR}/r1-untagged.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-untagged.txt"
    ping_node dc1_untagged 172.16.1.1 | tee "${RESULTS_DIR}/ping-dc1-localgw-untagged.json"
    ping_node dc1_untagged 172.16.3.1 | tee "${RESULTS_DIR}/ping-dc1-remotegw-untagged.json"
    ping_node dc1_untagged 172.16.3.10 | tee "${RESULTS_DIR}/ping-dc1-remotehost-untagged.json"
}

experiment_tagged_subif125() {
    configure_core
    configure_tagged_routes
    configure_access_subif125 r1 Ethernet11 172.17.1.1 24 125
    configure_access_subif125 r3 Ethernet11 172.17.3.1 24 125
    show_run r1 | tee "${RESULTS_DIR}/r1-tagged-subif125.txt"
    show_run r2 | tee "${RESULTS_DIR}/r2-tagged-subif125.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-tagged-subif125.txt"
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-subif125.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-subif125.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-subif125.json"
}

experiment_tagged_subif0_and_125() {
    configure_core
    configure_tagged_routes
    configure_access_subif0_and_125 r1 Ethernet11 172.17.1.1 24 125
    configure_access_subif0_and_125 r3 Ethernet11 172.17.3.1 24 125
    show_run r1 | tee "${RESULTS_DIR}/r1-tagged-subif0-and-125.txt"
    show_run r2 | tee "${RESULTS_DIR}/r2-tagged-subif0-and-125.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-tagged-subif0-and-125.txt"
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-subif0-and-125.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-subif0-and-125.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-subif0-and-125.json"
}

experiment_tagged_subif0_then_125() {
    configure_core
    configure_tagged_routes
    configure_access_subif0_empty r1 Ethernet11
    configure_access_subif0_empty r3 Ethernet11
    configure_access_subif125 r1 Ethernet11 172.17.1.1 24 125
    configure_access_subif125 r3 Ethernet11 172.17.3.1 24 125
    show_run r1 | tee "${RESULTS_DIR}/r1-tagged-subif0-then-125.txt"
    show_run r2 | tee "${RESULTS_DIR}/r2-tagged-subif0-then-125.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-tagged-subif0-then-125.txt"
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-subif0-then-125.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-subif0-then-125.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-subif0-then-125.json"
}

experiment_tagged_subif0_vlan125() {
    configure_core
    configure_tagged_routes
    configure_access_subif0_vlan125 r1 Ethernet11 172.17.1.1 24 125
    configure_access_subif0_vlan125 r3 Ethernet11 172.17.3.1 24 125
    show_run r1 | tee "${RESULTS_DIR}/r1-tagged-subif0-vlan125.txt"
    show_run r2 | tee "${RESULTS_DIR}/r2-tagged-subif0-vlan125.txt"
    show_run r3 | tee "${RESULTS_DIR}/r3-tagged-subif0-vlan125.txt"
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-subif0-vlan125.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-subif0-vlan125.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-subif0-vlan125.json"
}

configure_cli_working_tagged_access() {
    cli_config r1 \
        "interface Ethernet11\nno switchport\ninterface Ethernet11.125\nencapsulation dot1q vlan 125\nip address 172.17.1.1/24"
    cli_config r3 \
        "interface Ethernet11\nno switchport\ninterface Ethernet11.125\nencapsulation dot1q vlan 125\nip address 172.17.3.1/24"
}

experiment_tagged_cli_baseline_and_capture() {
    capture_lab_state tagged-cli-clean
    configure_core
    configure_tagged_routes
    configure_cli_working_tagged_access
    capture_lab_state tagged-cli-working
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-tagged-cli.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-tagged-cli.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-tagged-cli.json"
}

experiment_tagged_replace_inferred() {
    configure_core
    configure_tagged_routes
    replace_access_subif0_and_125 r1 Ethernet11 172.17.1.1 24 125
    replace_access_subif0_and_125 r3 Ethernet11 172.17.3.1 24 125
    capture_lab_state tagged-replace-inferred
    ping_node dc3_tagged 172.17.1.1 | tee "${RESULTS_DIR}/ping-dc3-localgw-tagged-replace.json"
    ping_node dc3_tagged 172.17.3.1 | tee "${RESULTS_DIR}/ping-dc3-remotegw-tagged-replace.json"
    ping_node dc3_tagged 172.17.3.10 | tee "${RESULTS_DIR}/ping-dc3-remotehost-tagged-replace.json"
}

get_interfaces() {
    local router=$1
    gnmi "$(router_address "${router}")" get --path /interfaces/interface \
        | tee "${RESULTS_DIR}/${router}-interfaces.json"
}

main() {
    local action="${1:-}"
    case "${action}" in
        deploy) deploy ;;
        destroy) destroy ;;
        baseline) baseline ;;
        capture-tagged-state) capture_lab_state tagged-snapshot ;;
        experiment-untagged) experiment_untagged ;;
        experiment-tagged-subif125) experiment_tagged_subif125 ;;
        experiment-tagged-subif0-and-125) experiment_tagged_subif0_and_125 ;;
        experiment-tagged-subif0-then-125) experiment_tagged_subif0_then_125 ;;
        experiment-tagged-subif0-vlan125) experiment_tagged_subif0_vlan125 ;;
        experiment-tagged-cli-baseline-and-capture) experiment_tagged_cli_baseline_and_capture ;;
        experiment-tagged-replace-inferred) experiment_tagged_replace_inferred ;;
        get-r1-interfaces) get_interfaces r1 ;;
        get-r2-interfaces) get_interfaces r2 ;;
        get-r3-interfaces) get_interfaces r3 ;;
        *)
            echo "Usage: $0 {deploy|destroy|baseline|capture-tagged-state|experiment-untagged|experiment-tagged-subif125|experiment-tagged-subif0-and-125|experiment-tagged-subif0-then-125|experiment-tagged-subif0-vlan125|experiment-tagged-cli-baseline-and-capture|experiment-tagged-replace-inferred|get-r1-interfaces|get-r2-interfaces|get-r3-interfaces}" >&2
            exit 1
            ;;
    esac
}

main "$@"
