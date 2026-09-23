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

import pytest
import sqlalchemy
from sqlalchemy import Column, Integer
from sqlalchemy.orm import Session, declarative_base

from context.service.database.models.Slot import C_Slot, L_Slot, S_Slot


Base = declarative_base()


class SlotSmokeModel(Base):
    __tablename__ = 'slot_smoke'

    id = Column(Integer, primary_key=True)
    c_slots = Column(C_Slot, nullable=True)
    l_slots = Column(L_Slot, nullable=True)
    s_slots = Column(S_Slot, nullable=True)


def build_expected_slot_map(start_slot: int, width: int, active_slots):
    active_slots = set(active_slots)
    return {str(slot): (1 if slot in active_slots else 0) for slot in range(start_slot, start_slot + width)}


def build_sparse_slot_input(active_slots):
    return {str(slot): 1 for slot in reversed(active_slots)}


@pytest.mark.parametrize(
    'slot_type,active_slots',
    [
        (C_Slot(), [0, 17, 319]),
        (L_Slot(), [0, 101, 549]),
        (S_Slot(), [0, 205, 719]),
    ],
)
def test_slot_type_roundtrip_preserves_positions(slot_type, active_slots) -> None:
    sparse_input = build_sparse_slot_input(active_slots)
    encoded = slot_type.process_bind_param(sparse_input, dialect=None)
    decoded = slot_type.process_result_value(encoded, dialect=None)

    assert encoded is not None
    assert decoded == build_expected_slot_map(
        slot_type.start_point, slot_type.width, active_slots
    )


@pytest.mark.parametrize(
    'slot_type,invalid_key',
    [
        (C_Slot(), 320),
        (L_Slot(), 550),
        (S_Slot(), 720),
    ],
)
def test_slot_type_rejects_out_of_range_keys(slot_type, invalid_key: int) -> None:
    with pytest.raises(ValueError):
        slot_type.process_bind_param({str(invalid_key): 1}, dialect=None)


def _run_slot_smoke_test(engine: sqlalchemy.engine.Engine) -> None:
    Base.metadata.create_all(engine)
    try:
        c_slots = build_sparse_slot_input([0, 10, 319])
        l_slots = build_sparse_slot_input([0, 12, 549])
        s_slots = build_sparse_slot_input([0, 14, 719])

        with Session(engine) as session:
            session.add(SlotSmokeModel(id=1, c_slots=c_slots, l_slots=l_slots, s_slots=s_slots))
            session.commit()

        with Session(engine) as session:
            stored = session.query(SlotSmokeModel).filter_by(id=1).one()
            assert stored.c_slots == build_expected_slot_map(0, 320, [0, 10, 319])
            assert stored.l_slots == build_expected_slot_map(0, 550, [0, 12, 549])
            assert stored.s_slots == build_expected_slot_map(0, 720, [0, 14, 719])
    finally:
        Base.metadata.drop_all(engine)


def test_slot_smoke_sqlite() -> None:
    engine = sqlalchemy.create_engine('sqlite:///:memory:', future=True)
    _run_slot_smoke_test(engine)


def test_slot_smoke_cockroachdb() -> None:
    crdb_uri = os.environ['CRDB_URI']
    engine = sqlalchemy.create_engine(
        crdb_uri, connect_args={'application_name': 'tfs-slot-smoketest'}, future=True
    )
    _run_slot_smoke_test(engine)
