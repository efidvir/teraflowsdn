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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

import io.quarkus.test.junit.QuarkusTest;
import io.smallrye.mutiny.Uni;
import jakarta.inject.Inject;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import org.etsi.tfs.policy.context.ContextService;
import org.etsi.tfs.policy.context.model.ConfigActionEnum;
import org.etsi.tfs.policy.context.model.ConfigRule;
import org.etsi.tfs.policy.context.model.ConfigRuleCustom;
import org.etsi.tfs.policy.context.model.ConfigRuleTypeCustom;
import org.etsi.tfs.policy.context.model.Device;
import org.etsi.tfs.policy.context.model.DeviceConfig;
import org.etsi.tfs.policy.context.model.DeviceDriverEnum;
import org.etsi.tfs.policy.context.model.DeviceOperationalStatus;
import org.etsi.tfs.policy.context.model.EndPoint.EndPointBuilder;
import org.etsi.tfs.policy.context.model.EndPointId;
import org.etsi.tfs.policy.context.model.Location;
import org.etsi.tfs.policy.context.model.LocationTypeRegion;
import org.etsi.tfs.policy.context.model.ServiceId;
import org.etsi.tfs.policy.context.model.TopologyId;
import org.etsi.tfs.policy.kpi_sample_types.model.KpiSampleType;
import org.etsi.tfs.policy.policy.model.PolicyRuleAction;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionConfig;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionEnum;
import org.etsi.tfs.policy.policy.model.PolicyRuleBasic;
import org.etsi.tfs.policy.policy.model.PolicyRuleService;
import org.etsi.tfs.policy.policy.model.PolicyRuleState;
import org.etsi.tfs.policy.policy.model.PolicyRuleStateEnum;
import org.etsi.tfs.policy.policy.service.PolicyRuleConditionValidator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

@QuarkusTest
class PolicyRuleServiceValidationTest {
    @Inject Serializer serializer;

    private ContextService contextService;
    private PolicyRuleConditionValidator policyRuleConditionValidator;

    @BeforeEach
    void setUp() {
        contextService = Mockito.mock(ContextService.class);
        policyRuleConditionValidator = new PolicyRuleConditionValidator(contextService);
    }

    @Test
    void testIsDeviceIdValidReturnsTrue() {
        String deviceId = "deviceId";
        Device device = createDevice(deviceId);

        when(contextService.getDevice(anyString())).thenReturn(Uni.createFrom().item(device));

        Boolean result = policyRuleConditionValidator.isDeviceIdValid(deviceId).await().indefinitely();

        assertThat(result).isEqualTo(true);
    }

    @Test
    void testIsDeviceIdValidReturnsFalse() {
        String deviceId = "deviceId";

        when(contextService.getDevice(anyString()))
                .thenReturn(Uni.createFrom().failure(new RuntimeException("Failure")));

        Boolean result = policyRuleConditionValidator.isDeviceIdValid(deviceId).await().indefinitely();

        assertThat(result).isEqualTo(false);
    }

    Device createDevice(String deviceId) {

        final var configRuleCustom = new ConfigRuleCustom("resourceKeyA", "resourceValueA");
        final var configRuleType = new ConfigRuleTypeCustom(configRuleCustom);
        final var deviceConfig =
                new DeviceConfig(List.of(new ConfigRule(ConfigActionEnum.SET, configRuleType)));

        final var deviceDrivers = List.of(DeviceDriverEnum.IETF_NETWORK_TOPOLOGY, DeviceDriverEnum.P4);

        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var endPointType = "endPointType";
        final var kpiSampleTypes =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);
        final var locationTypeRegion = new LocationTypeRegion("ATH");
        final var location = new Location(locationTypeRegion);
        final var endPoint =
                new EndPointBuilder(endPointId, endPointType, kpiSampleTypes).location(location).build();

        final var endPoints = List.of(endPoint);

        return new Device(
                deviceId,
                "deviceType",
                deviceConfig,
                DeviceOperationalStatus.ENABLED,
                deviceDrivers,
                endPoints);
    }

    private List<PolicyRuleAction> createPolicyRuleActions(
            PolicyRuleActionEnum policyRuleActionEnum, List<PolicyRuleActionConfig> parameters) {
        final var policyRuleAction = new PolicyRuleAction(policyRuleActionEnum, parameters);

        return List.of(policyRuleAction);
    }

    private PolicyRuleBasic createPolicyRuleBasic(
            String policyRuleId,
            PolicyRuleState policyRuleState,
            int priority,
            List<PolicyRuleAction> policyRuleActions,
            List<String> policyRuleKpiIds) {

        return new PolicyRuleBasic(
                policyRuleId, policyRuleState, priority, policyRuleActions, policyRuleKpiIds);
    }

    private ServiceId createServiceId(String contextId, String id) {
        return new ServiceId(contextId, id);
    }

    private PolicyRuleService createPolicyRuleService(
            PolicyRuleBasic policyRuleBasic, ServiceId serviceId, List<String> deviceIds) {

        return new PolicyRuleService(policyRuleBasic, serviceId, deviceIds);
    }

    @Test
    void shouldCreatePolicyRuleServiceObjectGivenEmptyDeviceIds() {
        final var serviceId = createServiceId("contextId", "id");
        final var deviceIds = Collections.<String>emptyList();

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
                        "policyRuleId", policyRuleState, 0, policyRuleActions, policyRuleKpiIds);

        final var expectedPolicyRuleService =
                new PolicyRuleService(policyRuleBasic, serviceId, deviceIds);

        final var policyRuleService = createPolicyRuleService(policyRuleBasic, serviceId, deviceIds);

        assertThat(policyRuleService).usingRecursiveComparison().isEqualTo(expectedPolicyRuleService);
    }

    @Test
    void shouldCreatePolicyRuleServiceObject() {
        final var serviceId = createServiceId("contextId", "id");
        final var deviceIds = List.of("deviceIdA", "deviceIdB");

        final var policyRuleActions =
                createPolicyRuleActions(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT,
                        List.of(
                                new PolicyRuleActionConfig(
                                        UUID.randomUUID().toString(), UUID.randomUUID().toString())));

        final var policyRuleState = new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "1");

        final var policyRuleKpiIds = List.of("df7efb41-8e6f-4af0-a214-d9863402eca3");

        final var policyRuleBasic =
                createPolicyRuleBasic(
                        "policyRuleId", policyRuleState, 0, policyRuleActions, policyRuleKpiIds);

        final var expectedPolicyRuleService =
                new PolicyRuleService(policyRuleBasic, serviceId, deviceIds);

        final var policyRuleService = createPolicyRuleService(policyRuleBasic, serviceId, deviceIds);

        assertThat(policyRuleService).usingRecursiveComparison().isEqualTo(expectedPolicyRuleService);
    }
}
