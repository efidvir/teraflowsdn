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

package org.etsi.tfs.policy;

import static org.assertj.core.api.Assertions.assertThat;

import io.quarkus.test.junit.QuarkusTest;
import java.util.List;
import java.util.UUID;
import org.etsi.tfs.policy.policy.model.PolicyRuleAction;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionConfig;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionEnum;
import org.etsi.tfs.policy.policy.model.PolicyRuleBasic;
import org.etsi.tfs.policy.policy.model.PolicyRuleDevice;
import org.etsi.tfs.policy.policy.model.PolicyRuleState;
import org.etsi.tfs.policy.policy.model.PolicyRuleStateEnum;
import org.junit.jupiter.api.Test;

@QuarkusTest
class PolicyRuleDeviceValidationTest {

    private PolicyRuleBasic createPolicyRuleBasic(
            String policyRuleId,
            PolicyRuleState policyRuleState,
            int priority,
            List<PolicyRuleAction> policyRuleActions,
            List<String> policyRuleKpiIds) {

        return new PolicyRuleBasic(
                policyRuleId, policyRuleState, priority, policyRuleActions, policyRuleKpiIds);
    }

    private List<PolicyRuleAction> createPolicyRuleActions(
            PolicyRuleActionEnum policyRuleActionEnum, List<PolicyRuleActionConfig> parameters) {
        final var policyRuleAction = new PolicyRuleAction(policyRuleActionEnum, parameters);

        return List.of(policyRuleAction);
    }

    private PolicyRuleDevice createPolicyRuleDevice(
            PolicyRuleBasic policyRuleBasic, List<String> deviceIds) {

        return new PolicyRuleDevice(policyRuleBasic, deviceIds);
    }

    private List<String> createDeviceIds() {
        return List.of("deviceId1", "deviceId2");
    }

    @Test
    void shouldCreatePolicyRuleDeviceObject() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "1");

        final var policyRuleKpiIds = List.of("df7efb41-8e6f-4af0-a214-d9863402eca3");

        final var policyRuleBasic =
                createPolicyRuleBasic(
                        "policyRuleId", policyRuleState, 3, policyRuleActions, policyRuleKpiIds);

        final var deviceIds = createDeviceIds();

        final var expectedPolicyRuleDevice = new PolicyRuleDevice(policyRuleBasic, deviceIds);

        final var policyRuleDevice = createPolicyRuleDevice(policyRuleBasic, deviceIds);

        assertThat(policyRuleDevice).usingRecursiveComparison().isEqualTo(expectedPolicyRuleDevice);
    }
}
