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
import static org.assertj.core.api.Assertions.assertThatExceptionOfType;

import io.quarkus.test.junit.QuarkusTest;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import org.etsi.tfs.policy.policy.model.PolicyRuleAction;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionConfig;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionEnum;
import org.etsi.tfs.policy.policy.model.PolicyRuleBasic;
import org.etsi.tfs.policy.policy.model.PolicyRuleState;
import org.etsi.tfs.policy.policy.model.PolicyRuleStateEnum;
import org.junit.jupiter.api.Test;

@QuarkusTest
class PolicyRuleBasicValidationTestHelper {

    private PolicyRuleBasic createPolicyRuleBasic(
            String policyRuleId,
            PolicyRuleState policyRuleState,
            int policyRulePriority,
            List<PolicyRuleAction> policyRuleActions,
            List<String> policyRuleKpiIds) {

        return new PolicyRuleBasic(
                policyRuleId, policyRuleState, policyRulePriority, policyRuleActions, policyRuleKpiIds);
    }

    private List<PolicyRuleAction> createPolicyRuleActions(
            PolicyRuleActionEnum policyRuleActionEnum, List<PolicyRuleActionConfig> parameters) {
        final var policyRuleAction = new PolicyRuleAction(policyRuleActionEnum, parameters);

        return List.of(policyRuleAction);
    }

    @Test
    void shouldThrowNullPointerExceptionGivenNullPolicyRuleId() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "1");

        assertThatExceptionOfType(NullPointerException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic(
                                        null, policyRuleState, 3, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldThrowIllegalArgumentExceptionGivenEmptyPolicyRuleId() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONFIGRULE,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_ENFORCED, "1");

        assertThatExceptionOfType(IllegalArgumentException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic("", policyRuleState, 3, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldThrowIllegalArgumentExceptionGivenWhiteSpacedPolicyRuleId() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_NO_ACTION,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_ENFORCED, "1");

        assertThatExceptionOfType(IllegalArgumentException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic(
                                        " ", policyRuleState, 3, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldThrowIllegalArgumentExceptionGivenNegativePriority() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_INSERTED, "1");

        final var policyRuleId = UUID.randomUUID().toString();

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        assertThatExceptionOfType(IllegalArgumentException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic(
                                        policyRuleId, policyRuleState, -1, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldThrowNullPointerExceptionGivenNullPolicyRuleActions() {
        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_PROVISIONED, "1");

        final var policyRuleId = UUID.randomUUID().toString();

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        assertThatExceptionOfType(NullPointerException.class)
                .isThrownBy(
                        () -> createPolicyRuleBasic(policyRuleId, policyRuleState, 3, null, policyRuleKpiIds));
    }

    @Test
    void shouldThrowIllegalArgumentExceptionGivenEmptyPolicyRuleActions() {
        final var policyRuleActions = Collections.<PolicyRuleAction>emptyList();

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_FAILED, "1");

        final var policyRuleId = UUID.randomUUID().toString();

        final var policyRuleKpiIds = List.of(UUID.randomUUID().toString());

        assertThatExceptionOfType(IllegalArgumentException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic(
                                        policyRuleId, policyRuleState, 3, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldThrowNullPointerExceptionGivenNullPolicyKpis() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_PROVISIONED, "1");

        final var policyRuleId = UUID.randomUUID().toString();

        assertThatExceptionOfType(NullPointerException.class)
                .isThrownBy(
                        () -> createPolicyRuleBasic(policyRuleId, policyRuleState, 3, policyRuleActions, null));
    }

    @Test
    void shouldThrowIllegalArgumentExceptionGivenEmptyPolicyKpis() {
        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_FAILED, "1");

        final var policyRuleId = UUID.randomUUID().toString();

        final var policyRuleKpiIds = Collections.<String>emptyList();

        assertThatExceptionOfType(IllegalArgumentException.class)
                .isThrownBy(
                        () ->
                                createPolicyRuleBasic(
                                        policyRuleId, policyRuleState, 3, policyRuleActions, policyRuleKpiIds));
    }

    @Test
    void shouldCreatePolicyRuleBasicObject() {
        final var expectedPolicyRuleId = "expectedPolicyRuleId";
        final var expectedPolicyRuleState =
                new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "1");
        final var expectedPriority = 3;

        final var firstExpectedPolicyRuleAction =
                new PolicyRuleAction(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(new PolicyRuleActionConfig("parameter1", "parameter2")));

        final var expectedPolicyRuleActions = List.of(firstExpectedPolicyRuleAction);

        final var firstExpectedPolicyKpi = "df7efb41-8e6f-4af0-a214-d9863402eca3";
        final var expectedPolicyKPIs = List.of(firstExpectedPolicyKpi);

        final var expectedPolicyRuleBasic =
                new PolicyRuleBasic(
                        expectedPolicyRuleId,
                        expectedPolicyRuleState,
                        expectedPriority,
                        expectedPolicyRuleActions,
                        expectedPolicyKPIs);

        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(new PolicyRuleActionConfig("parameter1", "parameter2")));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "1");

        final var policyRuleKpiIds = List.of("df7efb41-8e6f-4af0-a214-d9863402eca3");

        final var policyRuleBasic =
                createPolicyRuleBasic(
                        expectedPolicyRuleId, policyRuleState, 3, policyRuleActions, policyRuleKpiIds);

        assertThat(policyRuleBasic).usingRecursiveComparison().isEqualTo(expectedPolicyRuleBasic);
    }
}
