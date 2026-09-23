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

import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy_cockroachdb import run_transaction
from typing import Dict, List, Optional
from common.method_wrappers.ServiceExceptions import NotFoundException
from common.proto.context_pb2 import OpticalBand, OpticalBandId, OpticalBandList
from .models.OpticalConfig.OpticalBandModel import OpticalBandModel


LOGGER = logging.getLogger(__name__)


def get_optical_band(db_engine : Engine) -> OpticalBandList:
    def callback(session : Session) -> List[Dict]:
        obj_list : List[OpticalBandModel] = session.query(OpticalBandModel).all()
        return [obj.dump() for obj in obj_list]
    optical_bands = run_transaction(sessionmaker(bind=db_engine), callback)
    return OpticalBandList(opticalbands=optical_bands)


def select_optical_band(db_engine : Engine, request : OpticalBandId) -> OpticalBand:
    ob_uuid = request.opticalband_uuid.uuid
    def callback(session : Session) -> Optional[Dict]:
        stmt = session.query(OpticalBandModel)
        stmt = stmt.filter_by(ob_uuid=ob_uuid)
        obj = stmt.one_or_none()
        return None if obj is None else obj.dump()
    obj = run_transaction(sessionmaker(bind=db_engine, expire_on_commit=False), callback)
    if obj is None:
        raw_ob_uuid = request.opticalband_uuid.uuid
        raise NotFoundException('OpticalBand', raw_ob_uuid, extra_details=[
            'opticalband_uuid generated was: {:s}'.format(ob_uuid)
        ])
    return OpticalBand(**obj)


def set_optical_band(db_engine : Engine, ob_data : List[Dict]) -> Dict:
    LOGGER.debug('[update_opticalconfig] ob_data={:s}'.format(str(ob_data)))

    def callback(session : Session) -> Optional[str]:
        if len(ob_data) == 0: return None

        stmt = insert(OpticalBandModel).values(ob_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[OpticalBandModel.ob_uuid],
            set_=dict(
                connection_uuid = stmt.excluded.connection_uuid
            )
        )
        stmt = stmt.returning(OpticalBandModel.ob_uuid)
        ob_id = session.execute(stmt).fetchone()
        return ob_id

    ob_id = run_transaction(sessionmaker(bind=db_engine), callback)
    LOGGER.debug('[update_opticalconfig] ob_id={:s}'.format(str(ob_id)))
    return {'ob_id': ob_id}
