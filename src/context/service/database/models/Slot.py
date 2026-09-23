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

from sqlalchemy.types import String, TypeDecorator


class SlotType(TypeDecorator):
    impl = String
    cache_ok = True

    start_point = 0
    width = 0

    def _valid_key_range(self):
        return range(self.start_point, self.start_point + self.width)

    def _normalize(self, value):
        if value is None:
            return None

        normalized = {}
        for key, slot_value in value.items():
            key_int = int(key)
            if key_int not in self._valid_key_range():
                msg = 'Slot key {:d} out of valid range [{:d}, {:d}]'
                raise ValueError(msg.format(key_int, self.start_point, self.start_point + self.width - 1))

            bit_value = int(slot_value)
            if bit_value not in {0, 1}:
                raise ValueError('Slot value must be 0 or 1, got {:d}'.format(bit_value))

            normalized[key_int] = bit_value
        return normalized

    def process_bind_param(self, value, dialect):
        normalized = self._normalize(value)
        if normalized is None:
            return None

        int_num = 0
        for key in self._valid_key_range():
            bit_value = normalized.get(key, 0)
            if bit_value == 1:
                int_num |= 1 << (key - self.start_point)

        return str(int_num)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        int_num = int(value)
        slot = {}
        for key in self._valid_key_range():
            slot[str(key)] = (int_num >> (key - self.start_point)) & 1
        return slot


class C_Slot(SlotType):
    start_point = 0
    width = 320


class L_Slot(SlotType):
    start_point = 0
    width = 550


class S_Slot(SlotType):
    start_point = 0
    width = 720
