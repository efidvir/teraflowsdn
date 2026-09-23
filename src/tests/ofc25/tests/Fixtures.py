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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

import pytest

from context.client.ContextClient import ContextClient
from device.client.DeviceClient import DeviceClient
from service.client.ServiceClient import ServiceClient
from vnt_manager.client.VNTManagerClient import VNTManagerClient

PROFILE_OPT = 'opt'
PROFILE_IP = 'ip'
PROFILE_E2E = 'e2e'

RUNTIME_ENV_DIR = Path('/var/teraflow')
PROFILE_FILENAMES = {
    PROFILE_OPT: 'tfs_runtime_env_vars_opt.sh',
    PROFILE_IP: 'tfs_runtime_env_vars_ip.sh',
    PROFILE_E2E: 'tfs_runtime_env_vars_e2e.sh',
}
EXPORT_REGEX = re.compile(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$')


@dataclass(frozen=True)
class ServiceEndpoint:
    host: str
    port: int


@dataclass(frozen=True)
class TfsProfile:
    name: str
    env_vars: Mapping[str, str]
    context: ServiceEndpoint
    device: ServiceEndpoint
    service: ServiceEndpoint
    vnt_manager: Optional[ServiceEndpoint]


@dataclass(frozen=True)
class TfsClientBundle:
    context: ContextClient
    device: DeviceClient
    service: ServiceClient
    vnt_manager: Optional[VNTManagerClient]
    env_vars: Mapping[str, str]


def _parse_runtime_env_file(filepath: Path) -> Dict[str, str]:
    env_vars: Dict[str, str] = {}
    for raw_line in filepath.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        match = EXPORT_REGEX.match(line)
        if match is None:
            continue
        key, value = match.groups()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env_vars[key] = value
    return env_vars


def _read_service_endpoint(env_vars: Mapping[str, str], service_name: str) -> ServiceEndpoint:
    host_key = '{:s}_SERVICE_HOST'.format(service_name)
    port_key = '{:s}_SERVICE_PORT_GRPC'.format(service_name)

    if host_key not in env_vars:
        raise KeyError('Missing key "{:s}" in runtime env vars'.format(host_key))
    if port_key not in env_vars:
        raise KeyError('Missing key "{:s}" in runtime env vars'.format(port_key))

    return ServiceEndpoint(host=env_vars[host_key], port=int(env_vars[port_key]))


def _read_optional_service_endpoint(env_vars: Mapping[str, str], service_name: str) -> Optional[ServiceEndpoint]:
    host_key = '{:s}_SERVICE_HOST'.format(service_name)
    port_key = '{:s}_SERVICE_PORT_GRPC'.format(service_name)
    if host_key not in env_vars or port_key not in env_vars:
        return None
    return ServiceEndpoint(host=env_vars[host_key], port=int(env_vars[port_key]))


def _load_tfs_profile(profile_name: str) -> TfsProfile:
    filepath = RUNTIME_ENV_DIR / PROFILE_FILENAMES[profile_name]
    if not filepath.exists():
        raise FileNotFoundError('Runtime env file not found: {:s}'.format(str(filepath)))

    env_vars = _parse_runtime_env_file(filepath)
    return TfsProfile(
        name=profile_name,
        env_vars=env_vars,
        context=_read_service_endpoint(env_vars, 'CONTEXTSERVICE'),
        device=_read_service_endpoint(env_vars, 'DEVICESERVICE'),
        service=_read_service_endpoint(env_vars, 'SERVICESERVICE'),
        vnt_manager=_read_optional_service_endpoint(env_vars, 'VNT_MANAGERSERVICE'),
    )


@pytest.fixture(scope='session')
def tfs_profiles() -> Dict[str, TfsProfile]:
    profiles: Dict[str, TfsProfile] = {}
    for profile_name in [PROFILE_OPT, PROFILE_IP, PROFILE_E2E]:
        filepath = RUNTIME_ENV_DIR / PROFILE_FILENAMES[profile_name]
        if not filepath.exists():
            continue
        profiles[profile_name] = _load_tfs_profile(profile_name)
    if len(profiles) == 0:
        raise FileNotFoundError('No runtime env files found in {:s}'.format(str(RUNTIME_ENV_DIR)))
    return profiles


@pytest.fixture(scope='session')
def tfs_clients(tfs_profiles: Dict[str, TfsProfile]) -> Dict[str, TfsClientBundle]:
    clients: Dict[str, TfsClientBundle] = {}
    for profile_name, profile in tfs_profiles.items():
        clients[profile_name] = TfsClientBundle(
            context=ContextClient(profile.context.host, profile.context.port),
            device=DeviceClient(profile.device.host, profile.device.port),
            service=ServiceClient(profile.service.host, profile.service.port),
            vnt_manager=(
                VNTManagerClient(profile.vnt_manager.host, profile.vnt_manager.port)
                if profile.vnt_manager is not None else None
            ),
            env_vars=profile.env_vars,
        )

    yield clients

    for bundle in clients.values():
        bundle.context.close()
        bundle.device.close()
        bundle.service.close()
        if bundle.vnt_manager is not None:
            bundle.vnt_manager.close()
