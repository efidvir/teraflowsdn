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

from device.service.drivers.gnmi_openconfig.GnmiOpenConfigDriver import GnmiOpenConfigDriver
from device.service.drivers.gnmi_openconfig.GnmiSessionHandler import INITIAL_TARGET_INFO_RESOURCE_KEY
from device.service.drivers.gnmi_openconfig.gnmi.gnmi_pb2 import CapabilityResponse, Encoding, ModelData
from device.service.drivers.gnmi_openconfig.tools.Capabilities import check_capabilities


class _MockGnmiStub:
    def __init__(self, reply):
        self._reply = reply

    def Capabilities(self, req, metadata=None, timeout=None): # pylint: disable=unused-argument
        return self._reply


def test_check_capabilities_extracts_arista_target_facts() -> None:
    reply = CapabilityResponse(
        gNMI_version='0.7.0',
        supported_models=[
            ModelData(name='openconfig-system', organization='OpenConfig working group', version='2.0.0'),
            ModelData(name='arista-exp-eos', organization='Arista Networks <http://arista.com/>', version=''),
        ],
        supported_encodings=[Encoding.JSON_IETF, Encoding.JSON],
    )

    capability_info = check_capabilities(_MockGnmiStub(reply), 'admin', 'admin', timeout=120)

    assert capability_info['gnmi_version'] == '0.7.0'
    assert capability_info['target_facts']['vendor'] == 'Arista'
    assert capability_info['target_facts']['platform'] == 'EOS'


def test_driver_get_initial_config_returns_target_facts() -> None:
    driver = GnmiOpenConfigDriver('127.0.0.1', 6030, username='admin', password='admin')
    driver._GnmiOpenConfigDriver__handler._target_facts = { # pylint: disable=protected-access
        'vendor': 'Arista',
        'platform': 'EOS',
        'model': 'cEOSLab',
        'software_version': '4.32.2F',
    }

    initial_config = driver.GetInitialConfig()

    assert initial_config == [(
        INITIAL_TARGET_INFO_RESOURCE_KEY,
        {
            'vendor': 'Arista',
            'platform': 'EOS',
            'model': 'cEOSLab',
            'software_version': '4.32.2F',
        }
    )]
