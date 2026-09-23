/*
 * Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.etsi.tfs.policy.kpi_sample_types.model;

public enum KpiSampleType {
    UNKNOWN,
    PACKETS_TRANSMITTED,
    PACKETS_RECEIVED,
    PACKETS_DROPPED,
    BYTES_TRANSMITTED,
    BYTES_RECEIVED,
    BYTES_DROPPED,
    LINK_TOTAL_CAPACITY_GBPS,
    LINK_USED_CAPACITY_GBPS,
    ML_CONFIDENCE,
    OPTICAL_SECURITY_STATUS,
    L3_UNIQUE_ATTACK_CONNS,
    L3_TOTAL_DROPPED_PACKTS,
    L3_UNIQUE_ATTACKERS,
    L3_UNIQUE_COMPROMISED_CLIENTS,
    L3_SECURITY_STATUS_CRYPTO,
    SERVICE_LATENCY_MS,
    PACKETS_TRANSMITTED_AGG_OUTPUT,
    PACKETS_RECEIVED_AGG_OUTPUT,
    PACKETS_DROPPED_AGG_OUTPUT,
    BYTES_TRANSMITTED_AGG_OUTPUT,
    BYTES_RECEIVED_AGG_OUTPUT,
    BYTES_DROPPED_AGG_OUTPUT,
    SERVICE_LATENCY_MS_AGG_OUTPUT,
    INT_SEQ_NUM,
    INT_TS_ING,
    INT_TS_EGR,
    INT_HOP_LAT,
    INT_PORT_ID_ING,
    INT_PORT_ID_EGR,
    INT_QUEUE_OCCUP,
    INT_QUEUE_ID,
    INT_HOP_LAT_SW01,
    INT_HOP_LAT_SW02,
    INT_HOP_LAT_SW03,
    INT_HOP_LAT_SW04,
    INT_HOP_LAT_SW05,
    INT_HOP_LAT_SW06,
    INT_HOP_LAT_SW07,
    INT_HOP_LAT_SW08,
    INT_HOP_LAT_SW09,
    INT_HOP_LAT_SW10,
    INT_LAT_ON_TOTAL,
    INT_IS_DROP,
    INT_DROP_REASON
}
