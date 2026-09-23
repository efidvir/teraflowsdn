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

import json, logging, os
from typing import Dict, List
from .Tools import do_rest_delete_request, do_rest_get_request

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

ACL_URL = '/restconf/data/device=firewall/ietf-access-control-list:acls'
ACL_GET_URL_TEMPLATE = '/restconf/data/device=firewall/ietf-access-control-list:acl={acl_name}'
ACL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'ietf-acl.json'
)


def load_acl_payload() -> Dict:
    with open(ACL_FILE, 'r', encoding='UTF-8') as f:
        return json.load(f)

def get_acl_names(payload: Dict) -> List[str]:
    return [
        acl['name']
        for acl in payload['ietf-access-control-list:acls']['acl']
    ]


def test_ietf_acl_delete() -> None:
    acl_payload = load_acl_payload()
    acl_names = get_acl_names(acl_payload)

    for acl_name in acl_names:
        do_rest_delete_request(
            ACL_GET_URL_TEMPLATE.format(acl_name=acl_name), logger=LOGGER,
            expected_status_codes={200, 204}
        )
        do_rest_get_request(
            ACL_GET_URL_TEMPLATE.format(acl_name=acl_name), logger=LOGGER,
            expected_status_codes={404}
        )
