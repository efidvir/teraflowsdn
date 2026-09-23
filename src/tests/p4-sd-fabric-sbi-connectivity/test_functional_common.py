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

import os

DEV_NB = 4
CONNECTION_RULES = 3
ENDPOINT_RULES = 3

INT_RULES = 19
L2_RULES = 10
L3_RULES = 4
ACL_RULES = 1

DATAPLANE_RULES_NB_INT_B1 = 5
DATAPLANE_RULES_NB_INT_B2 = 6
DATAPLANE_RULES_NB_INT_B3 = 8
DATAPLANE_RULES_NB_RT_WEST = 7
DATAPLANE_RULES_NB_RT_EAST = 7
DATAPLANE_RULES_NB_ACL = 1
DATAPLANE_RULES_NB_TOT = \
    DATAPLANE_RULES_NB_INT_B1 +\
    DATAPLANE_RULES_NB_INT_B2 +\
    DATAPLANE_RULES_NB_INT_B3 +\
    DATAPLANE_RULES_NB_RT_WEST +\
    DATAPLANE_RULES_NB_RT_EAST +\
    DATAPLANE_RULES_NB_ACL

TEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)) +
    '/descriptors')
assert os.path.exists(TEST_PATH), "Invalid path to P4 SD-Fabric tests"

# Topology descriptor
DESC_TOPOLOGY = os.path.join(TEST_PATH, 'topology.json')
assert os.path.exists(DESC_TOPOLOGY), "Invalid path to the SD-Fabric topology descriptor"

# SBI descriptors for Rule INSERTION
# The switch cannot digest all rules at once, hence we insert in batches
DESC_FILE_RULES_INSERT_INT_B1 = os.path.join(TEST_PATH, 'sbi-rules-insert-int-b1.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_INT_B1),\
    "Invalid path to the SD-Fabric INT SBI descriptor (batch #1)"

DESC_FILE_RULES_INSERT_INT_B2 = os.path.join(TEST_PATH, 'sbi-rules-insert-int-b2.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_INT_B2),\
    "Invalid path to the SD-Fabric INT SBI descriptor (batch #2)"

DESC_FILE_RULES_INSERT_INT_B3 = os.path.join(TEST_PATH, 'sbi-rules-insert-int-b3.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_INT_B3),\
    "Invalid path to the SD-Fabric INT SBI descriptor (batch #3)"

DESC_FILE_RULES_INSERT_ROUTING_WEST = os.path.join(TEST_PATH, 'sbi-rules-insert-routing-west.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_ROUTING_WEST),\
    "Invalid path to the SD-Fabric routing SBI descriptor (domain1-side)"

DESC_FILE_RULES_INSERT_ROUTING_EAST = os.path.join(TEST_PATH, 'sbi-rules-insert-routing-east.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_ROUTING_EAST),\
    "Invalid path to the SD-Fabric routing SBI descriptor (domain2-side)"

DESC_FILE_RULES_INSERT_ACL = os.path.join(TEST_PATH, 'sbi-rules-insert-acl.json')
assert os.path.exists(DESC_FILE_RULES_INSERT_ACL),\
    "Invalid path to the SD-Fabric ACL SBI descriptor"

# SBI descriptors for Rule DELETION
DESC_FILE_RULES_DELETE_ALL = os.path.join(TEST_PATH, 'sbi-rules-remove.json')
assert os.path.exists(DESC_FILE_RULES_DELETE_ALL),\
    "Invalid path to the SD-Fabric rule removal SBI descriptor"
