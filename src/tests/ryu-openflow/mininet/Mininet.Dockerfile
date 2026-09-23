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

# Based on: https://github.com/iwaseyusuke/docker-mininet

FROM ubuntu:22.04

USER root
WORKDIR /root

# Install dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get --yes --quiet --quiet update && \
    apt-get install --yes --no-install-recommends iproute2 net-tools openvswitch-switch ca-certificates && \
    apt-get install --yes --no-install-recommends mininet=2.3.0-1ubuntu1 && \
    apt-get autoremove --yes && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get --yes --quiet --quiet update && \
    apt-get install --yes --no-install-recommends iputils-ping && \
    apt-get autoremove --yes && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY src/tests/ryu-openflow/mininet/custom_pentagon_topology.py /opt/custom_pentagon_topology.py
COPY src/tests/ryu-openflow/mininet/mininet-entrypoint.sh /mininet-entrypoint.sh

EXPOSE 6633 6653 6640 5000

ENTRYPOINT ["/mininet-entrypoint.sh"]
