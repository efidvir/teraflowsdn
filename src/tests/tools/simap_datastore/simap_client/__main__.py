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


import json, logging, random, time
from common.tools.rest_conf.client.RestConfClient import RestConfClient

from .SimapClient import SimapClient
from .SimapMetricsGenerator import SimapMetricsGenerator
from .Tools import (create_simap_aggnet, create_simap_e2enet, 
                    create_simap_te, create_simap_trans)

logging.basicConfig(level=logging.INFO)
logging.getLogger('RestConfClient').setLevel(logging.WARN)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    restconf_client = RestConfClient(
        '127.0.0.1', port=8080,
        logger=logging.getLogger('RestConfClient')
    )
    simap_client = SimapClient(restconf_client)
    generator = SimapMetricsGenerator(service_count=5)

    try:
        create_simap_te(simap_client)
        create_simap_trans(simap_client)
        create_simap_aggnet(simap_client)
        create_simap_e2enet(simap_client)
    except Exception as e:
        error_msg = str(e)
        if 'status_code=409' in error_msg or 'already exists' in error_msg.lower():
            LOGGER.warning('SIMAP topology already exists, skipping further creation requests.')
        else:
            LOGGER.error('Error creating SIMAP topology: %s', e)
            return

    print('networks=', json.dumps(simap_client.networks()))

    # TE links for path: ONT1 -> OLT -> PE1 -> P1 -> PE2 -> POP1
    te_network = simap_client.network('te')
    te_links = {
        'L1' : te_network.link('L1'),   # ONT1 -> OLT
        'L3' : te_network.link('L3'),   # OLT  -> PE1
        'L5' : te_network.link('L5'),   # PE1  -> P1
        'L9' : te_network.link('L9'),   # P1   -> PE2
        'L13': te_network.link('L13'),  # PE2  -> POP1
    }

    # Abstract layer links
    abstract_links = {
        'Trans-L1' : simap_client.network('simap-trans').link('Trans-L1'),    # L5 + L9
        'AggNet-L1': simap_client.network('simap-aggnet').link('AggNet-L1'),  # L3 + Trans-L1 + L13
        'E2E-L1'   : simap_client.network('simap-e2e').link('E2E-L1'),        # L1 + AggNet-L1
    }

    # Initialize metrics generator with service count (0-5)
    generator = SimapMetricsGenerator(service_count=4)

    for i in range(1000):
        # Randomly change service count (1-5) every 5 iterations
        if i % 5 == 0:
            generator.set_service_count(random.randint(1, 5))

        # Generate TE link metrics based on current service count
        te_metrics = generator.generate_all_te_metrics()

        # Get domain-specific service IDs
        te_service_ids    = generator.get_service_ids('te')
        trans_service_ids = generator.get_service_ids('trans')
        agg_service_ids   = generator.get_service_ids('agg')
        e2e_service_ids   = generator.get_service_ids('e2e')

        # Update TE link telemetry with TE domain service IDs
        for link_id, (bw, lat) in te_metrics.items():
            te_links[link_id].telemetry.update(bw, lat, related_service_ids=te_service_ids)

        # Aggregate and update abstract layer telemetry with domain-specific service IDs
        abstract_metrics = generator.aggregate_abstract_metrics(te_metrics)
        domain_service_map = {
            'Trans-L1' : trans_service_ids,
            'AggNet-L1': agg_service_ids,
            'E2E-L1'   : e2e_service_ids,
        }
        for link_id, (bw, lat) in abstract_metrics.items():
            abstract_links[link_id].telemetry.update(bw, lat, related_service_ids=domain_service_map[link_id])

        # Print telemetry summary
        if i != 0 and i % 5 == 0:
            print(f'--- Iteration {i} | Services: {generator.service_count} ---')
            for link_id, (bw, lat) in te_metrics.items():
                print(f'TE {link_id:4s}: BW={bw:5.2f}%, Lat={lat:.3f}ms  SvcIDs: {te_service_ids}')
            for link_id, (bw, lat) in abstract_metrics.items():
                print(f'{link_id:10s}: BW={bw:5.2f}%, Lat={lat:.3f}ms  SvcIDs: {domain_service_map[link_id]}')

        time.sleep(10)


if __name__ == '__main__':
    main()
