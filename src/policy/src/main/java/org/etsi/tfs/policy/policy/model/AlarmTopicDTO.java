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

package org.etsi.tfs.policy.policy.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class AlarmTopicDTO {

    @JsonProperty("value_threshold_low")
    private Boolean valueThresholdLow;

    @JsonProperty("value_threshold_high")
    private Boolean valueThresholdHigh;

    @JsonProperty("value")
    private Double value;

    @JsonProperty("kpi_id")
    private String kpiId;

    public boolean isValid() {
        return this.getKpiId() != null
                && this.getValue() != null
                && this.getValueThresholdLow() != null
                && this.getValueThresholdHigh() != null;
    }

    public boolean isTriggered() {
        return this.getValueThresholdLow() || this.getValueThresholdHigh();
    }
}
