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

import json
import os
import tempfile
from pathlib import Path

import pytest

# pylint: disable=unused-import
from .Fixtures import (
    PROFILE_FILENAMES, PROFILE_E2E, PROFILE_IP, PROFILE_OPT,
    RUNTIME_ENV_DIR, tfs_clients, tfs_profiles
)

E2E_TOPOLOGY_DESCRIPTOR = 'topology_e2e.json'


def pytest_addoption(parser):
    parser.addoption(
        '--tfs-profile',
        action='store',
        choices=[PROFILE_OPT, PROFILE_IP, PROFILE_E2E],
        default=None,
        help='TFS deployment profile to use (opt|ip|e2e).',
    )
    parser.addoption(
        '--tfs-runtime-script',
        action='store',
        default=None,
        help='Runtime env script filename under /var/teraflow.',
    )
    parser.addoption(
        '--tfs-topology-descriptor',
        action='store',
        default=None,
        help='Topology descriptor filename (or absolute path).',
    )


def _require_option(request: pytest.FixtureRequest, option_name: str) -> str:
    value = request.config.getoption(option_name)
    if value is None:
        raise ValueError('Missing required pytest option: --{:s}'.format(option_name.replace('_', '-')))
    return value


def _require_runner_ip() -> str:
    runner_ip = os.environ.get('TFS_RUNNER_IP')
    if runner_ip:
        return runner_ip
    raise RuntimeError(
        'Missing TFS_RUNNER_IP environment variable required to materialize the OFC25 E2E topology descriptor'
    )


def _materialize_e2e_descriptor(descriptor_path: Path) -> str:
    runner_ip = _require_runner_ip()
    descriptor_data = json.loads(descriptor_path.read_text(encoding='utf-8'))

    for device in descriptor_data.get('devices', []):
        config_rules = device.get('device_config', {}).get('config_rules', [])
        for config_rule in config_rules:
            custom = config_rule.get('custom', {})
            if custom.get('resource_key') == '_connect/address':
                custom['resource_value'] = runner_ip

    tmp_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='-ofc25-topology-e2e.json', prefix='codex-', delete=False, encoding='utf-8'
    )
    with tmp_file:
        json.dump(descriptor_data, tmp_file, indent=4)
        tmp_file.write('\n')

    return tmp_file.name


@pytest.fixture(scope='session')
def selected_tfs_profile(request: pytest.FixtureRequest) -> str:
    return _require_option(request, 'tfs_profile')


@pytest.fixture(scope='session')
def selected_runtime_script(request: pytest.FixtureRequest, selected_tfs_profile: str) -> str:
    runtime_script = _require_option(request, 'tfs_runtime_script')
    expected_script = PROFILE_FILENAMES[selected_tfs_profile]
    if runtime_script != expected_script:
        msg = 'Runtime script "{:s}" does not match profile "{:s}" (expected "{:s}")'
        raise ValueError(msg.format(runtime_script, selected_tfs_profile, expected_script))
    runtime_file = RUNTIME_ENV_DIR / runtime_script
    if not runtime_file.exists():
        raise FileNotFoundError('Runtime env file not found: {:s}'.format(str(runtime_file)))
    return runtime_script


@pytest.fixture(scope='session')
def selected_topology_descriptor(request: pytest.FixtureRequest) -> str:
    descriptor = _require_option(request, 'tfs_topology_descriptor')
    descriptor_path = Path(descriptor)
    if not descriptor_path.is_absolute():
        descriptor_path = Path(__file__).resolve().parent.parent / 'descriptors' / descriptor
    if not descriptor_path.exists():
        raise FileNotFoundError('Topology descriptor not found: {:s}'.format(str(descriptor_path)))

    if descriptor_path.name == E2E_TOPOLOGY_DESCRIPTOR:
        return _materialize_e2e_descriptor(descriptor_path)

    return str(descriptor_path)


@pytest.fixture(scope='session')
def selected_tfs_client_bundle(
    tfs_clients,
    selected_tfs_profile: str,
    selected_runtime_script: str,  # pylint: disable=unused-argument
):
    if selected_tfs_profile not in tfs_clients:
        raise KeyError('Profile "{:s}" not loaded in tfs_clients'.format(selected_tfs_profile))
    return tfs_clients[selected_tfs_profile]
