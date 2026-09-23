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

from typing import Any, Dict, List, Optional, Set
from common.tools.grpc.Tools import grpc_message_to_json
from ..gnmi.gnmi_pb2 import CapabilityRequest   # pylint: disable=no-name-in-module
from ..gnmi.gnmi_pb2_grpc import gNMIStub

def _normalize_string(value : Any) -> Optional[str]:
    if not isinstance(value, str): return None
    value = value.strip()
    if len(value) == 0: return None
    return value

def _infer_target_facts(supported_models : List[Dict[str, Any]]) -> Dict[str, str]:
    facts : Dict[str, str] = dict()

    names = list()
    organizations = list()
    for supported_model in supported_models:
        name = _normalize_string(supported_model.get('name'))
        if name is not None: names.append(name)

        organization = _normalize_string(supported_model.get('organization'))
        if organization is not None: organizations.append(organization)

    signatures = [*names, *organizations]
    signature_blob = ' '.join(signatures).lower()

    if 'arista' in signature_blob:
        facts['vendor'] = 'Arista'
        if any(
            ('eos' in name.lower()) or name.lower().startswith('arista-')
            for name in names
        ):
            facts['platform'] = 'EOS'

    return facts

def check_capabilities(
    stub : gNMIStub, username : str, password : str, timeout : Optional[int] = None
) -> Dict[str, Any]:
    metadata = [('username', username), ('password', password)]
    req = CapabilityRequest()
    reply = stub.Capabilities(req, metadata=metadata, timeout=timeout)

    data = grpc_message_to_json(reply)

    gnmi_version = data.get('gNMI_version')
    if gnmi_version is None or gnmi_version != '0.7.0':
        raise Exception('Unsupported gNMI version: {:s}'.format(str(gnmi_version)))

    supported_models = [
        supported_model
        for supported_model in data.get('supported_models', [])
        if isinstance(supported_model, dict)
    ]

    supported_encodings = {
        supported_encoding
        for supported_encoding in data.get('supported_encodings', [])
        if isinstance(supported_encoding, str)
    }
    if len(supported_encodings) == 0:
        # pylint: disable=broad-exception-raised
        raise Exception('No supported encodings found')
    if 'JSON_IETF' not in supported_encodings:
        # pylint: disable=broad-exception-raised
        raise Exception('JSON_IETF encoding not supported')

    return {
        'gnmi_version': gnmi_version,
        'supported_models': supported_models,
        'supported_encodings': sorted(supported_encodings),
        'target_facts': _infer_target_facts(supported_models),
    }
