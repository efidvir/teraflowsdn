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

"""
Integration validation of GnmiOpenConfigDriver for L2VPN (VPLS) over MPLS/LDP
using the ContainerLab dataplane (dc1--r1--r2--dc2).
"""

import grpc, logging, os, pytest, time
from typing import Dict, List, Tuple
from device.service.drivers.gnmi_openconfig.GnmiOpenConfigDriver import GnmiOpenConfigDriver
from device.tests.gnmi_openconfig.tools.request_composers import (
    connection_point, connection_point_endpoint_local, connection_point_endpoint_remote,
    interface, mpls_global, mpls_ldp_interface, network_instance, vlan,
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# Skip unless the lab is explicitly enabled
RUN_LAB = os.environ.get('RUN_L2VPN_LAB', '0') == '1'
pytestmark = pytest.mark.skipif(not RUN_LAB, reason='Requires running ContainerLab L2VPN dataplane')

GNMI_PORT = 6030
USERNAME = 'admin'
PASSWORD = 'admin'

SERVICE_NAME = 'tfs-l2vpn-vpls'
VC_ID = 100
VLAN_ID = 100

ROUTERS = [
    {
        'name'           : 'r1',
        'address'        : '172.20.20.101',
        'ldp_router_id'  : '172.20.20.101',
        'core_interface' : 'Ethernet2',
        'access_interface': 'Ethernet10',
        'peer'           : '172.20.20.102',
    },
    {
        'name'           : 'r2',
        'address'        : '172.20.20.102',
        'ldp_router_id'  : '172.20.20.102',
        'core_interface' : 'Ethernet1',
        'access_interface': 'Ethernet10',
        'peer'           : '172.20.20.101',
    },
]


def _build_l2vpn_resources(router: Dict[str, str]) -> Tuple[List[Tuple[str, Dict]], List[Tuple[str, Dict]]]:
    set_resources : List[Tuple[str, Dict]] = [
        network_instance(SERVICE_NAME, 'L2VSI'),
        connection_point(SERVICE_NAME, 'access'),
        connection_point_endpoint_local(
            SERVICE_NAME, 'access', 'access-ep', router['access_interface'], subif=0, precedence=0
        ),
        connection_point(SERVICE_NAME, 'core'),
        connection_point_endpoint_remote(
            SERVICE_NAME, 'core', 'core-ep', router['peer'], vc_id=VC_ID, precedence=100
        ),
    ]

    del_resources = list(reversed(set_resources))
    return set_resources, del_resources

def _set_with_retry(driver: GnmiOpenConfigDriver, resources: List[Tuple[str, Dict]], attempts: int = 5, wait_s: int = 5):
    """Retry SetConfig while the device reports it is not yet initialized."""
    last_exc = None
    for i in range(attempts):
        try:
            return driver.SetConfig(resources)
        except grpc.RpcError as exc:
            last_exc = exc
            if exc.code() == grpc.StatusCode.UNAVAILABLE and 'system not yet initialized' in exc.details():
                LOGGER.info('Device not ready (attempt %s/%s), waiting %ss', i + 1, attempts, wait_s)
                time.sleep(wait_s)
                continue
            raise
    if last_exc:
        raise last_exc
    return []


@pytest.fixture(scope='session')
def drivers() -> Dict[str, GnmiOpenConfigDriver]:
    _drivers : Dict[str, GnmiOpenConfigDriver] = dict()
    for router in ROUTERS:
        driver = GnmiOpenConfigDriver(
            router['address'], GNMI_PORT, username=USERNAME, password=PASSWORD, use_tls=False
        )
        try:
            driver.Connect()
        except Exception as exc:  # pylint: disable=broad-except
            pytest.skip(f"Cannot connect to {router['name']} ({router['address']}): {exc}")
        _drivers[router['name']] = driver
    yield _drivers
    time.sleep(1)
    for _, driver in _drivers.items():
        driver.Disconnect()


def test_configure_mpls_ldp(drivers: Dict[str, GnmiOpenConfigDriver]) -> None:
    """Enable LDP globally and on the r1<->r2 core links."""
    for router in ROUTERS:
        driver = drivers[router['name']]
        resources = [
            mpls_global(router['ldp_router_id'], hello_interval=5, hello_holdtime=15),
            mpls_ldp_interface(router['core_interface'], hello_interval=5, hello_holdtime=15),
        ]
        LOGGER.info('Configuring MPLS/LDP on %s (%s)', router['name'], router['address'])
        results = _set_with_retry(driver, resources)
        LOGGER.info('MPLS/LDP result: %s', results)
        assert all(
            (result is True) or (isinstance(result, tuple) and len(result) > 1 and result[1] is True)
            for result in results
        )


def test_configure_l2vpn_vpls(drivers: Dict[str, GnmiOpenConfigDriver]) -> None:
    """Fallback validation: create a VLAN in default VRF and attach core/access interfaces."""
    for router in ROUTERS:
        driver = drivers[router['name']]
        vlan_res = vlan('default', VLAN_ID, vlan_name='tfs-vlan')
        if_access = interface(router['access_interface'], VLAN_ID, enabled=True, vlan_id=VLAN_ID,
                              ipv4_address=None, ipv4_prefix=None)
        if_core = interface(router['core_interface'], VLAN_ID, enabled=True, vlan_id=VLAN_ID,
                            ipv4_address=None, ipv4_prefix=None)

        LOGGER.info('Configuring VLAN %s on %s (%s)', VLAN_ID, router['name'], router['address'])
        results_vlan = _set_with_retry(driver, [vlan_res, if_access, if_core])
        LOGGER.info('VLAN result: %s', results_vlan)
        assert all(
            (result is True) or (isinstance(result, tuple) and len(result) > 1 and result[1] is True)
            for result in results_vlan
        )

        LOGGER.info('Tearing down VLAN %s on %s (%s)', VLAN_ID, router['name'], router['address'])
        results_del = driver.DeleteConfig([if_core, if_access, vlan_res])
        assert all(
            (result is True) or (isinstance(result, tuple) and len(result) > 1 and result[1] is True)
            for result in results_del
        )
