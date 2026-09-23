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

import acl.Acl;
import context.ContextOuterClass;
import context.ContextOuterClass.ContextId;
import context.ContextOuterClass.DeviceId;
import context.ContextOuterClass.DeviceOperationalStatusEnum;
import context.ContextOuterClass.Uuid;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.etsi.tfs.policy.acl.AclAction;
import org.etsi.tfs.policy.acl.AclEntry;
import org.etsi.tfs.policy.acl.AclForwardActionEnum;
import org.etsi.tfs.policy.acl.AclLogActionEnum;
import org.etsi.tfs.policy.acl.AclMatch;
import org.etsi.tfs.policy.acl.AclRuleSet;
import org.etsi.tfs.policy.acl.AclRuleTypeEnum;
import org.etsi.tfs.policy.context.model.ConfigActionEnum;
import org.etsi.tfs.policy.context.model.ConfigRule;
import org.etsi.tfs.policy.context.model.ConfigRuleAcl;
import org.etsi.tfs.policy.context.model.ConfigRuleCustom;
import org.etsi.tfs.policy.context.model.ConfigRuleTypeAcl;
import org.etsi.tfs.policy.context.model.ConfigRuleTypeCustom;
import org.etsi.tfs.policy.context.model.Constraint;
import org.etsi.tfs.policy.context.model.ConstraintCustom;
import org.etsi.tfs.policy.context.model.ConstraintEndPointLocation;
import org.etsi.tfs.policy.context.model.ConstraintSchedule;
import org.etsi.tfs.policy.context.model.ConstraintSlaAvailability;
import org.etsi.tfs.policy.context.model.ConstraintSlaCapacity;
import org.etsi.tfs.policy.context.model.ConstraintSlaIsolationLevel;
import org.etsi.tfs.policy.context.model.ConstraintSlaLatency;
import org.etsi.tfs.policy.context.model.ConstraintTypeCustom;
import org.etsi.tfs.policy.context.model.ConstraintTypeEndPointLocation;
import org.etsi.tfs.policy.context.model.ConstraintTypeSchedule;
import org.etsi.tfs.policy.context.model.ConstraintTypeSlaAvailability;
import org.etsi.tfs.policy.context.model.ConstraintTypeSlaCapacity;
import org.etsi.tfs.policy.context.model.ConstraintTypeSlaIsolationLevel;
import org.etsi.tfs.policy.context.model.ConstraintTypeSlaLatency;
import org.etsi.tfs.policy.context.model.Device;
import org.etsi.tfs.policy.context.model.DeviceConfig;
import org.etsi.tfs.policy.context.model.DeviceDriverEnum;
import org.etsi.tfs.policy.context.model.DeviceOperationalStatus;
import org.etsi.tfs.policy.context.model.Empty;
import org.etsi.tfs.policy.context.model.EndPoint.EndPointBuilder;
import org.etsi.tfs.policy.context.model.EndPointId;
import org.etsi.tfs.policy.context.model.Event;
import org.etsi.tfs.policy.context.model.EventTypeEnum;
import org.etsi.tfs.policy.context.model.GpsPosition;
import org.etsi.tfs.policy.context.model.IsolationLevelEnum;
import org.etsi.tfs.policy.context.model.Location;
import org.etsi.tfs.policy.context.model.LocationTypeGpsPosition;
import org.etsi.tfs.policy.context.model.LocationTypeRegion;
import org.etsi.tfs.policy.context.model.Service;
import org.etsi.tfs.policy.context.model.ServiceConfig;
import org.etsi.tfs.policy.context.model.ServiceId;
import org.etsi.tfs.policy.context.model.ServiceStatus;
import org.etsi.tfs.policy.context.model.ServiceStatusEnum;
import org.etsi.tfs.policy.context.model.ServiceTypeEnum;
import org.etsi.tfs.policy.context.model.TopologyId;
import org.etsi.tfs.policy.kpi_sample_types.model.KpiSampleType;
import org.etsi.tfs.policy.policy.model.PolicyRuleAction;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionConfig;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionEnum;
import org.etsi.tfs.policy.policy.model.PolicyRuleBasic;
import org.etsi.tfs.policy.policy.model.PolicyRuleDevice;
import org.etsi.tfs.policy.policy.model.PolicyRuleService;
import org.etsi.tfs.policy.policy.model.PolicyRuleState;
import org.etsi.tfs.policy.policy.model.PolicyRuleStateEnum;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import policy.Policy;
import policy.Policy.PolicyRuleId;
import policy.PolicyAction;

@QuarkusTest
class SerializerTest {
    @Inject Serializer serializer;

    private AclMatch createAclMatch(
            int dscp,
            int protocol,
            String srcAddress,
            String dstAddress,
            int srcPort,
            int dstPort,
            int startMplsLabel,
            int endMplsLabel) {
        return new AclMatch(
                dscp, protocol, srcAddress, dstAddress, srcPort, dstPort, startMplsLabel, endMplsLabel);
    }

    private AclAction createAclAction(
            AclForwardActionEnum forwardActionEnum, AclLogActionEnum logActionEnum) {

        return new AclAction(forwardActionEnum, logActionEnum);
    }

    private AclEntry createAclEntry(
            int sequenceId, String description, AclMatch aclMatch, AclAction aclAction) {

        return new AclEntry(sequenceId, description, aclMatch, aclAction);
    }

    private PolicyRuleBasic createPolicyRuleBasic() {
        final var expectedPolicyRuleId = "expectedPolicyRuleId";
        final var expectedPolicyRuleState =
                new PolicyRuleState(PolicyRuleStateEnum.POLICY_EFFECTIVE, "Policy was effective");
        final var expectedPriority = 3;

        final var firstExpectedPolicyRuleAction =
                new PolicyRuleAction(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        List.of(new PolicyRuleActionConfig("parameter1", "parameter2")));

        final var secondExpectedPolicyRuleAction =
                new PolicyRuleAction(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONFIGRULE,
                        List.of(new PolicyRuleActionConfig("parameter3", "parameter4")));

        final var expectedPolicyRuleActions =
                List.of(firstExpectedPolicyRuleAction, secondExpectedPolicyRuleAction);

        final var expectedPolicyRuleKPIs = List.of("df7efb41-8e6f-4af0-a214-d9863402eca3");

        return new PolicyRuleBasic(
                expectedPolicyRuleId,
                expectedPolicyRuleState,
                expectedPriority,
                expectedPolicyRuleActions,
                expectedPolicyRuleKPIs);
    }

    private ConfigRule createConfigRule() {
        final var contextIdUuid = "contextId";
        final var topologyIdUuid = "topologyUuid";
        final var deviceIdUuid = "deviceIdUuid";
        final var endpointIdUuid = "endpointIdUuid";

        final var topologyId = new TopologyId(contextIdUuid, topologyIdUuid);
        final var endPointId = new EndPointId(topologyId, deviceIdUuid, endpointIdUuid);

        final var aclMatch = createAclMatch(1, 1, "127.0.0.1", "127.0.0.2", 5601, 5602, 1, 2);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(1, "aclEntryDescription", aclMatch, aclAction);

        final var aclRuleSet =
                new AclRuleSet(
                        "aclRuleName", AclRuleTypeEnum.IPV4, "AclRuleDescription", "userId", List.of(aclEntry));

        final var configRuleAcl = new ConfigRuleAcl(endPointId, aclRuleSet);
        final var configRuleTypeAcl = new ConfigRuleTypeAcl(configRuleAcl);

        return new ConfigRule(ConfigActionEnum.SET, configRuleTypeAcl);
    }

    @Test
    void shouldSerializeDeviceId() {
        final var deviceId = "deviceId";

        final var deviceIdUuid = serializer.serializeUuid(deviceId);
        final var expectedDeviceId =
                ContextOuterClass.DeviceId.newBuilder().setDeviceUuid(deviceIdUuid).build();

        final var serializedDeviceId = serializer.serializeDeviceId(deviceId);

        assertThat(serializedDeviceId).usingRecursiveComparison().isEqualTo(expectedDeviceId);
    }

    @Test
    void shouldDeserializeDeviceId() {
        final var expectedDeviceId = "expectedDeviceId";

        final var serializedDeviceIdUuid = serializer.serializeUuid(expectedDeviceId);
        final var serializedDeviceId =
                DeviceId.newBuilder().setDeviceUuid(serializedDeviceIdUuid).build();

        final var deviceId = serializer.deserialize(serializedDeviceId);

        assertThat(deviceId).isEqualTo(expectedDeviceId);
    }

    @Test
    void shouldSerializeContextId() {
        final var contextId = "contextId";

        final var contextIdUuid = serializer.serializeUuid(contextId);

        final var expectedContextId =
                ContextOuterClass.ContextId.newBuilder().setContextUuid(contextIdUuid).build();

        final var serializedContextId = serializer.serializeContextId(contextId);

        assertThat(serializedContextId).usingRecursiveComparison().isEqualTo(expectedContextId);
    }

    @Test
    void shouldDeserializeContextId() {
        final var expectedContextId = "expectedContextId";

        final var serializedContextIdUuid = serializer.serializeUuid(expectedContextId);
        final var serializedContextId =
                ContextId.newBuilder().setContextUuid(serializedContextIdUuid).build();

        final var contextId = serializer.deserialize(serializedContextId);

        assertThat(contextId).isEqualTo(expectedContextId);
    }

    @Test
    void shouldSerializePolicyRuleId() {
        final var policyRuleId = "policyRuleId";

        final var policyRuleIdUuid = serializer.serializeUuid(policyRuleId);
        final var expectedPolicyRuleId =
                Policy.PolicyRuleId.newBuilder().setUuid(policyRuleIdUuid).build();

        final var serializedPolicyRuleId = serializer.serializePolicyRuleId(policyRuleId);

        assertThat(serializedPolicyRuleId).usingRecursiveComparison().isEqualTo(expectedPolicyRuleId);
    }

    @Test
    void shouldDeserializePolicyRuleId() {
        final var expectedPolicyRuleId = "expectedPolicyRuleId";

        final var serializedPolicyRuleIdUuid = serializer.serializeUuid(expectedPolicyRuleId);
        final var serializedPolicyRuleId =
                PolicyRuleId.newBuilder().setUuid(serializedPolicyRuleIdUuid).build();

        final var policyRuleId = serializer.deserialize(serializedPolicyRuleId);

        assertThat(policyRuleId).isEqualTo(expectedPolicyRuleId);
    }

    @Test
    void shouldSerializeTopologyId() {
        final var expectedContextId = "expectedContextId";
        final var expectedId = "expectedId";
        final var topologyId = new TopologyId(expectedContextId, expectedId);

        final var serializedContextId = serializer.serializeContextId(expectedContextId);
        final var serializedIdUuid = serializer.serializeUuid(expectedId);

        final var expectedTopologyId =
                ContextOuterClass.TopologyId.newBuilder()
                        .setContextId(serializedContextId)
                        .setTopologyUuid(serializedIdUuid)
                        .build();

        final var serializedTopologyId = serializer.serialize(topologyId);

        assertThat(serializedTopologyId).usingRecursiveComparison().isEqualTo(expectedTopologyId);
    }

    @Test
    void shouldDeserializeTopologyId() {
        final var expectedContextId = "expectedContextId";
        final var expectedId = "expectedId";

        final var expectedTopologyId = new TopologyId(expectedContextId, expectedId);

        final var serializedTopologyId = serializer.serialize(expectedTopologyId);
        final var topologyId = serializer.deserialize(serializedTopologyId);

        assertThat(topologyId).usingRecursiveComparison().isEqualTo(expectedTopologyId);
    }

    private static Stream<Arguments> provideConfigActionEnum() {
        return Stream.of(
                Arguments.of(ConfigActionEnum.SET, ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET),
                Arguments.of(
                        ConfigActionEnum.DELETE, ContextOuterClass.ConfigActionEnum.CONFIGACTION_DELETE),
                Arguments.of(
                        ConfigActionEnum.UNDEFINED, ContextOuterClass.ConfigActionEnum.CONFIGACTION_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideConfigActionEnum")
    void shouldSerializeConfigActionEnum(
            ConfigActionEnum configActionEnum,
            ContextOuterClass.ConfigActionEnum expectedConfigActionEnum) {
        final var serializedType = serializer.serialize(configActionEnum);
        assertThat(serializedType.getNumber()).isEqualTo(expectedConfigActionEnum.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideConfigActionEnum")
    void shouldDeserializeConfigActionEnum(
            ConfigActionEnum expectedConfigActionEnum,
            ContextOuterClass.ConfigActionEnum serializedConfigActionEnum) {

        final var configActionEnum = serializer.deserialize(serializedConfigActionEnum);

        assertThat(configActionEnum).isEqualTo(expectedConfigActionEnum);
    }

    private static Stream<Arguments> provideAclRuleTypeEnum() {
        return Stream.of(
                Arguments.of(AclRuleTypeEnum.IPV4, Acl.AclRuleTypeEnum.ACLRULETYPE_IPV4),
                Arguments.of(AclRuleTypeEnum.IPV6, Acl.AclRuleTypeEnum.ACLRULETYPE_IPV6),
                Arguments.of(AclRuleTypeEnum.L2, Acl.AclRuleTypeEnum.ACLRULETYPE_L2),
                Arguments.of(AclRuleTypeEnum.MPLS, Acl.AclRuleTypeEnum.ACLRULETYPE_MPLS),
                Arguments.of(AclRuleTypeEnum.MIXED, Acl.AclRuleTypeEnum.ACLRULETYPE_MIXED),
                Arguments.of(AclRuleTypeEnum.UNDEFINED, Acl.AclRuleTypeEnum.ACLRULETYPE_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideAclRuleTypeEnum")
    void shouldSerializeAclRuleTypeEnum(
            AclRuleTypeEnum aclRuleTypeEnum, Acl.AclRuleTypeEnum expectedAclRuleTypeEnum) {
        final var serializedAclRuleTypeEnum = serializer.serialize(aclRuleTypeEnum);
        assertThat(serializedAclRuleTypeEnum.getNumber())
                .isEqualTo(expectedAclRuleTypeEnum.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideAclRuleTypeEnum")
    void shouldDeserializeAclRuleTypeEnum(
            AclRuleTypeEnum expectedAclRuleTypeEnum, Acl.AclRuleTypeEnum serializedAclRuleTypeEnum) {
        final var aclRuleTypeEnum = serializer.deserialize(serializedAclRuleTypeEnum);
        assertThat(aclRuleTypeEnum).isEqualTo(expectedAclRuleTypeEnum);
    }

    private static Stream<Arguments> provideAclForwardActionEnum() {
        return Stream.of(
                Arguments.of(AclForwardActionEnum.DROP, Acl.AclForwardActionEnum.ACLFORWARDINGACTION_DROP),
                Arguments.of(
                        AclForwardActionEnum.ACCEPT, Acl.AclForwardActionEnum.ACLFORWARDINGACTION_ACCEPT),
                Arguments.of(
                        AclForwardActionEnum.REJECT, Acl.AclForwardActionEnum.ACLFORWARDINGACTION_REJECT),
                Arguments.of(
                        AclForwardActionEnum.UNDEFINED,
                        Acl.AclForwardActionEnum.ACLFORWARDINGACTION_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideAclForwardActionEnum")
    void shouldSerializeAclForwardActionEnum(
            AclForwardActionEnum aclForwardActionEnum,
            Acl.AclForwardActionEnum expectedAclForwardActionEnum) {
        final var serializedAclForwardActionEnum = serializer.serialize(aclForwardActionEnum);
        assertThat(serializedAclForwardActionEnum.getNumber())
                .isEqualTo(expectedAclForwardActionEnum.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideAclForwardActionEnum")
    void shouldDeserializeAclForwardActionEnum(
            AclForwardActionEnum expectedAclForwardActionEnum,
            Acl.AclForwardActionEnum serializedAclForwardActionEnum) {
        final var aclForwardActionEnum = serializer.deserialize(serializedAclForwardActionEnum);
        assertThat(aclForwardActionEnum).isEqualTo(expectedAclForwardActionEnum);
    }

    private static Stream<Arguments> provideAclLogActionEnum() {
        return Stream.of(
                Arguments.of(AclLogActionEnum.NO_LOG, Acl.AclLogActionEnum.ACLLOGACTION_NOLOG),
                Arguments.of(AclLogActionEnum.SYSLOG, Acl.AclLogActionEnum.ACLLOGACTION_SYSLOG),
                Arguments.of(AclLogActionEnum.UNDEFINED, Acl.AclLogActionEnum.ACLLOGACTION_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideAclLogActionEnum")
    void shouldSerializeAclLogActionEnum(
            AclLogActionEnum aclLogActionEnum, Acl.AclLogActionEnum expectedAclLogActionEnum) {
        final var serializedAclLogActionEnum = serializer.serialize(aclLogActionEnum);
        assertThat(serializedAclLogActionEnum.getNumber())
                .isEqualTo(expectedAclLogActionEnum.getNumber());
    }

    @Test
    void shouldSerializeAclAction() {
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);

        final var expectedAclAction =
                Acl.AclAction.newBuilder()
                        .setForwardAction(Acl.AclForwardActionEnum.ACLFORWARDINGACTION_ACCEPT)
                        .setLogAction(Acl.AclLogActionEnum.ACLLOGACTION_SYSLOG)
                        .build();

        final var serializedAclAction = serializer.serialize(aclAction);

        assertThat(serializedAclAction).usingRecursiveComparison().isEqualTo(expectedAclAction);
    }

    @Test
    void shouldDeserializeAclAction() {
        final var expectedAclAction =
                createAclAction(AclForwardActionEnum.DROP, AclLogActionEnum.NO_LOG);

        final var serializedAclAction = serializer.serialize(expectedAclAction);
        final var aclAction = serializer.deserialize(serializedAclAction);

        assertThat(aclAction).usingRecursiveComparison().isEqualTo(expectedAclAction);
    }

    @Test
    void shouldSerializeAclMatch() {
        final var aclMatch = createAclMatch(1, 1, "127.0.0.1", "127.0.0.2", 5601, 5602, 1, 2);

        final var expectedAclMatch =
                Acl.AclMatch.newBuilder()
                        .setDscp(1)
                        .setProtocol(1)
                        .setSrcAddress("127.0.0.1")
                        .setDstAddress("127.0.0.2")
                        .setSrcPort(5601)
                        .setDstPort(5602)
                        .setStartMplsLabel(1)
                        .setEndMplsLabel(2)
                        .build();

        final var serializedAclMatch = serializer.serialize(aclMatch);

        assertThat(serializedAclMatch).usingRecursiveComparison().isEqualTo(expectedAclMatch);
    }

    @Test
    void shouldDeserializeAclMatch() {
        final var expectedAclMatch = createAclMatch(7, 2, "127.0.0.5", "127.0.0.6", 32456, 3123, 5, 10);

        final var serializedAclMatch = serializer.serialize(expectedAclMatch);
        final var aclMatch = serializer.deserialize(serializedAclMatch);

        assertThat(aclMatch).usingRecursiveComparison().isEqualTo(expectedAclMatch);
    }

    @Test
    void shouldSerializeAclEntry() {
        final var sequenceId = 1;
        final var description = "aclEntryDescription";

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(sequenceId, description, aclMatch, aclAction);

        final var serializedAclMatch = serializer.serialize(aclMatch);
        final var serializedAclAction = serializer.serialize(aclAction);

        final var expectedAclEntry =
                Acl.AclEntry.newBuilder()
                        .setSequenceId(sequenceId)
                        .setDescription(description)
                        .setMatch(serializedAclMatch)
                        .setAction(serializedAclAction)
                        .build();

        final var serializedAclEntry = serializer.serialize(aclEntry);

        assertThat(serializedAclEntry).usingRecursiveComparison().isEqualTo(expectedAclEntry);
    }

    @Test
    void shouldDeserializeAclEntry() {
        final var sequenceId = 7;
        final var description = "aclEntryDescriptor";

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var expectedAclEntry = createAclEntry(sequenceId, description, aclMatch, aclAction);

        final var serializedAclEntry = serializer.serialize(expectedAclEntry);
        final var aclEntry = serializer.deserialize(serializedAclEntry);

        assertThat(aclEntry).usingRecursiveComparison().isEqualTo(expectedAclEntry);
    }

    @Test
    void shouldSerializeAclRuleSet() {
        final var sequenceId = 1;
        final var aclEntryDescription = "aclEntryDescription";

        final var aclRuleSetName = "aclRuleSetName";
        final var aclRuleSetDescription = "aclRuleSetDescription";
        final var aclRuleSetUserId = "aclRuleSetUserId";

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(sequenceId, aclEntryDescription, aclMatch, aclAction);
        final var aclRuleSet =
                new AclRuleSet(
                        aclRuleSetName,
                        AclRuleTypeEnum.MIXED,
                        aclRuleSetDescription,
                        aclRuleSetUserId,
                        List.of(aclEntry));

        final var serializedAclEntry = serializer.serialize(aclEntry);
        final var serializedAclEntries = List.of(serializedAclEntry);

        final var expectedAclRuleSet =
                Acl.AclRuleSet.newBuilder()
                        .setName(aclRuleSetName)
                        .setType(Acl.AclRuleTypeEnum.ACLRULETYPE_MIXED)
                        .setDescription(aclRuleSetDescription)
                        .setUserId(aclRuleSetUserId)
                        .addAllEntries(serializedAclEntries)
                        .build();

        final var serializedAclRuleset = serializer.serialize(aclRuleSet);

        assertThat(serializedAclRuleset).usingRecursiveComparison().isEqualTo(expectedAclRuleSet);
    }

    @Test
    void shouldDeserializeAclRuleSet() {
        final var sequenceId = 1;
        final var aclEntryDescription = "aclEntryDescription";

        final var aclRuleSetName = "aclRuleSetName";
        final var aclRuleSetDescription = "aclRuleSetDescription";
        final var aclRuleSetUserId = "aclRuleSetUserId";

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(sequenceId, aclEntryDescription, aclMatch, aclAction);
        final var expectedAclRuleSet =
                new AclRuleSet(
                        aclRuleSetName,
                        AclRuleTypeEnum.MIXED,
                        aclRuleSetDescription,
                        aclRuleSetUserId,
                        List.of(aclEntry));

        final var serializedAclRuleSet = serializer.serialize(expectedAclRuleSet);
        final var aclRuleSet = serializer.deserialize(serializedAclRuleSet);

        assertThat(aclRuleSet).usingRecursiveComparison().isEqualTo(expectedAclRuleSet);
    }

    @ParameterizedTest
    @MethodSource("provideAclLogActionEnum")
    void shouldDeserializeAclLogActionEnum(
            AclLogActionEnum expectedAclLogActionEnum, Acl.AclLogActionEnum serializedAclLogActionEnum) {
        final var aclLogActionEnum = serializer.deserialize(serializedAclLogActionEnum);
        assertThat(aclLogActionEnum).isEqualTo(expectedAclLogActionEnum);
    }

    @Test
    void shouldSerializeConfigRuleAcl() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";

        final var sequenceId = 1;
        final var aclEntryDescription = "aclEntryDescription";

        final var aclRuleSetName = "aclRuleSetName";
        final var aclRuleSetDescription = "aclRuleSetDescription";
        final var aclRuleSetUserId = "aclRuleSetUserId";

        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(sequenceId, aclEntryDescription, aclMatch, aclAction);
        final var aclRuleSet =
                new AclRuleSet(
                        aclRuleSetName,
                        AclRuleTypeEnum.MIXED,
                        aclRuleSetDescription,
                        aclRuleSetUserId,
                        List.of(aclEntry));

        final var configRuleAcl = new ConfigRuleAcl(endPointId, aclRuleSet);

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedAclRuleSet = serializer.serialize(aclRuleSet);

        final var expectedConfigRuleAcl =
                ContextOuterClass.ConfigRule_ACL.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setRuleSet(serializedAclRuleSet)
                        .build();

        final var serializedConfigRuleAcl = serializer.serialize(configRuleAcl);

        assertThat(serializedConfigRuleAcl).usingRecursiveComparison().isEqualTo(expectedConfigRuleAcl);
    }

    @Test
    void shouldDeserializeConfigRuleAcl() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";

        final var sequenceId = 1;
        final var aclEntryDescription = "aclEntryDescription";

        final var aclRuleSetName = "aclRuleSetName";
        final var aclRuleSetDescription = "aclRuleSetDescription";
        final var aclRuleSetUserId = "aclRuleSetUserId";

        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var aclEntry = createAclEntry(sequenceId, aclEntryDescription, aclMatch, aclAction);
        final var aclRuleSet =
                new AclRuleSet(
                        aclRuleSetName,
                        AclRuleTypeEnum.MIXED,
                        aclRuleSetDescription,
                        aclRuleSetUserId,
                        List.of(aclEntry));

        final var expectedConfigRuleAcl = new ConfigRuleAcl(endPointId, aclRuleSet);

        final var serializedConfigRuleAcl = serializer.serialize(expectedConfigRuleAcl);
        final var configRuleAcl = serializer.deserialize(serializedConfigRuleAcl);

        assertThat(configRuleAcl).usingRecursiveComparison().isEqualTo(expectedConfigRuleAcl);
    }

    @Test
    void shouldSerializeConfigRuleCustom() {
        final var resourceKey = "resourceKey";
        final var resourceValue = "resourceValue";

        final var configRuleCustom = new ConfigRuleCustom(resourceKey, resourceValue);

        final var expectedConfigRuleCustom =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey(resourceKey)
                        .setResourceValue(resourceValue)
                        .build();

        final var serializedConfigRuleCustom = serializer.serialize(configRuleCustom);

        assertThat(serializedConfigRuleCustom)
                .usingRecursiveComparison()
                .isEqualTo(expectedConfigRuleCustom);
    }

    @Test
    void shouldDeserializeConfigRuleCustom() {
        final var resourceKey = "resourceKey";
        final var resourceValue = "resourceValue";

        final var expectedConfigRuleCustom = new ConfigRuleCustom(resourceKey, resourceValue);

        final var serializedConfigRuleCustom = serializer.serialize(expectedConfigRuleCustom);
        final var configRuleCustom = serializer.deserialize(serializedConfigRuleCustom);

        assertThat(configRuleCustom).usingRecursiveComparison().isEqualTo(expectedConfigRuleCustom);
    }

    @Test
    void shouldSerializeConfigRuleofTypeConfigRuleAcl() {
        final var contextIdUuid = "contextId";
        final var topologyIdUuid = "topologyUuid";
        final var deviceIdUuid = "deviceIdUuid";
        final var endpointIdUuid = "endpointIdUuid";

        final var expectedSerializedContextId = serializer.serializeContextId(contextIdUuid);
        final var expectedSerializedTopologyIdUuid = serializer.serializeUuid(topologyIdUuid);
        final var expectedSerializedDeviceId = serializer.serializeDeviceId(deviceIdUuid);
        final var expectedSerializedEndPointIdUuid = serializer.serializeUuid(endpointIdUuid);

        final var expectedSerializedTopologyId =
                ContextOuterClass.TopologyId.newBuilder()
                        .setContextId(expectedSerializedContextId)
                        .setTopologyUuid(expectedSerializedTopologyIdUuid)
                        .build();

        final var topologyId = new TopologyId(contextIdUuid, topologyIdUuid);

        final var expectedSerializedEndPointId =
                ContextOuterClass.EndPointId.newBuilder()
                        .setTopologyId(expectedSerializedTopologyId)
                        .setDeviceId(expectedSerializedDeviceId)
                        .setEndpointUuid(expectedSerializedEndPointIdUuid)
                        .build();

        final var endPointId = new EndPointId(topologyId, deviceIdUuid, endpointIdUuid);

        final var expectedSerializedAclMatch =
                Acl.AclMatch.newBuilder()
                        .setDscp(1)
                        .setProtocol(1)
                        .setSrcAddress("127.0.0.1")
                        .setDstAddress("127.0.0.2")
                        .setSrcPort(5601)
                        .setDstPort(5602)
                        .setStartMplsLabel(1)
                        .setEndMplsLabel(2)
                        .build();

        final var aclMatch = createAclMatch(1, 1, "127.0.0.1", "127.0.0.2", 5601, 5602, 1, 2);

        final var expectedSerializedAclAction =
                Acl.AclAction.newBuilder()
                        .setForwardAction(Acl.AclForwardActionEnum.ACLFORWARDINGACTION_ACCEPT)
                        .setLogAction(Acl.AclLogActionEnum.ACLLOGACTION_SYSLOG)
                        .build();

        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);

        final var expectedSerializedAclEntry =
                Acl.AclEntry.newBuilder()
                        .setSequenceId(1)
                        .setDescription("aclEntryDescription")
                        .setMatch(expectedSerializedAclMatch)
                        .setAction(expectedSerializedAclAction)
                        .build();

        final var aclEntry = createAclEntry(1, "aclEntryDescription", aclMatch, aclAction);

        final var expectedSerializedAclRuleSet =
                Acl.AclRuleSet.newBuilder()
                        .setName("aclRuleName")
                        .setType(Acl.AclRuleTypeEnum.ACLRULETYPE_IPV4)
                        .setDescription("AclRuleDescription")
                        .setUserId("userId")
                        .addEntries(expectedSerializedAclEntry)
                        .build();

        final var aclRuleSet =
                new AclRuleSet(
                        "aclRuleName", AclRuleTypeEnum.IPV4, "AclRuleDescription", "userId", List.of(aclEntry));

        final var expectedSerializedConfigRuleAcl =
                ContextOuterClass.ConfigRule_ACL.newBuilder()
                        .setEndpointId(expectedSerializedEndPointId)
                        .setRuleSet(expectedSerializedAclRuleSet)
                        .build();

        final var configRuleAcl = new ConfigRuleAcl(endPointId, aclRuleSet);

        final var expectedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setAcl(expectedSerializedConfigRuleAcl)
                        .build();

        final var configRuleTypeAcl = new ConfigRuleTypeAcl(configRuleAcl);
        final var configRule = new ConfigRule(ConfigActionEnum.SET, configRuleTypeAcl);
        final var serializedConfigRule = serializer.serialize(configRule);

        assertThat(serializedConfigRule).isEqualTo(expectedConfigRule);
    }

    @Test
    void shouldDeserializeConfigRuleOfTypeConfigRuleAcl() {
        final var contextIdUuid = "contextId";
        final var topologyIdUuid = "topologyUuid";
        final var deviceIdUuid = "deviceIdUuid";
        final var endpointIdUuid = "endpointIdUuid";

        final var serializedContextId = serializer.serializeContextId(contextIdUuid);
        final var serializedTopologyIdUuid = serializer.serializeUuid(topologyIdUuid);
        final var serializedDeviceId = serializer.serializeDeviceId(deviceIdUuid);
        final var serializedEndPointIdUuid = serializer.serializeUuid(endpointIdUuid);

        final var topologyId = new TopologyId(contextIdUuid, topologyIdUuid);
        final var serializedTopologyId =
                ContextOuterClass.TopologyId.newBuilder()
                        .setContextId(serializedContextId)
                        .setTopologyUuid(serializedTopologyIdUuid)
                        .build();

        final var endPointId = new EndPointId(topologyId, deviceIdUuid, endpointIdUuid);
        final var serializedEndPointId =
                ContextOuterClass.EndPointId.newBuilder()
                        .setTopologyId(serializedTopologyId)
                        .setDeviceId(serializedDeviceId)
                        .setEndpointUuid(serializedEndPointIdUuid)
                        .build();

        final var aclMatch = createAclMatch(1, 2, "127.0.0.1", "127.0.0.2", 5601, 5602, 5, 10);
        final var serializedAclMatch =
                Acl.AclMatch.newBuilder()
                        .setDscp(1)
                        .setProtocol(2)
                        .setSrcAddress("127.0.0.1")
                        .setDstAddress("127.0.0.2")
                        .setSrcPort(5601)
                        .setDstPort(5602)
                        .setStartMplsLabel(5)
                        .setEndMplsLabel(10)
                        .build();

        final var aclAction = createAclAction(AclForwardActionEnum.ACCEPT, AclLogActionEnum.SYSLOG);
        final var serializedAclAction =
                Acl.AclAction.newBuilder()
                        .setForwardAction(Acl.AclForwardActionEnum.ACLFORWARDINGACTION_ACCEPT)
                        .setLogAction(Acl.AclLogActionEnum.ACLLOGACTION_SYSLOG)
                        .build();

        final var aclEntry = createAclEntry(1, "aclEntryDescription", aclMatch, aclAction);

        final var serializedAclEntry =
                Acl.AclEntry.newBuilder()
                        .setSequenceId(1)
                        .setDescription("aclEntryDescription")
                        .setMatch(serializedAclMatch)
                        .setAction(serializedAclAction)
                        .build();

        final var aclRuleSet =
                new AclRuleSet(
                        "aclRuleName",
                        org.etsi.tfs.policy.acl.AclRuleTypeEnum.IPV4,
                        "AclRuleDescription",
                        "userId",
                        List.of(aclEntry));

        final var serializedAclRuleSet =
                Acl.AclRuleSet.newBuilder()
                        .setName("aclRuleName")
                        .setType(Acl.AclRuleTypeEnum.ACLRULETYPE_IPV4)
                        .setDescription("AclRuleDescription")
                        .setUserId("userId")
                        .addEntries(serializedAclEntry)
                        .build();

        final var configRuleAcl = new ConfigRuleAcl(endPointId, aclRuleSet);
        final var configRuleTypeAcl = new ConfigRuleTypeAcl(configRuleAcl);

        final var expectedConfigRule = new ConfigRule(ConfigActionEnum.DELETE, configRuleTypeAcl);

        final var serializedConfigRuleAcl =
                ContextOuterClass.ConfigRule_ACL.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setRuleSet(serializedAclRuleSet)
                        .build();

        final var serializedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_DELETE)
                        .setAcl(serializedConfigRuleAcl)
                        .build();

        final var configRule = serializer.deserialize(serializedConfigRule);

        assertThat(configRule).usingRecursiveComparison().isEqualTo(expectedConfigRule);
    }

    @Test
    void shouldSerializeConfigRuleOfTypeConfigRuleCustom() {
        final var expectedSerializedConfigRuleCustom =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKey")
                        .setResourceValue("resourceValue")
                        .build();

        final var configRuleCustom = new ConfigRuleCustom("resourceKey", "resourceValue");

        final var expectedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setCustom(expectedSerializedConfigRuleCustom)
                        .build();

        final var configRuleTypeCustom = new ConfigRuleTypeCustom(configRuleCustom);
        final var configRule = new ConfigRule(ConfigActionEnum.SET, configRuleTypeCustom);
        final var serializedConfigRule = serializer.serialize(configRule);

        assertThat(serializedConfigRule).isEqualTo(expectedConfigRule);
    }

    @Test
    void shouldDeserializeConfigRuleOfTypeConfigRuleCustom() {
        final var serializedConfigRuleCustom =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKey")
                        .setResourceValue("resourceValue")
                        .build();

        final var expectedConfigRuleCustom = new ConfigRuleCustom("resourceKey", "resourceValue");
        final var configRuleTypeCustom = new ConfigRuleTypeCustom(expectedConfigRuleCustom);
        final var expectedConfigRule = new ConfigRule(ConfigActionEnum.SET, configRuleTypeCustom);

        final var serializedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setCustom(serializedConfigRuleCustom)
                        .build();

        final var configRule = serializer.deserialize(serializedConfigRule);

        assertThat(configRule).usingRecursiveComparison().isEqualTo(expectedConfigRule);
    }

    @Test
    void shouldThrowIllegalStateExceptionDuringDeserializationOfNonSpecifiedConfigRule() {
        final var serializedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .build();

        assertThatExceptionOfType(IllegalStateException.class)
                .isThrownBy(() -> serializer.deserialize(serializedConfigRule));
    }

    @Test
    void shouldSerializeConstraintCustom() {
        final var expectedConstraintType = "constraintType";
        final var expectedConstraintValue = "constraintValue";

        final var constraintCustom =
                new ConstraintCustom(expectedConstraintType, expectedConstraintValue);

        final var expectedConstraintCustom =
                ContextOuterClass.Constraint_Custom.newBuilder()
                        .setConstraintType(expectedConstraintType)
                        .setConstraintValue(expectedConstraintValue)
                        .build();

        final var serializedConstraintCustom = serializer.serialize(constraintCustom);

        assertThat(serializedConstraintCustom)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintCustom);
    }

    @Test
    void shouldDeserializeConstraintCustom() {
        final var expectedConstraintType = "constraintType";
        final var expectedConstraintValue = "constraintValue";
        final var expectedConstraintCustom =
                new ConstraintCustom(expectedConstraintType, expectedConstraintValue);

        final var serializedConstraintCustom =
                ContextOuterClass.Constraint_Custom.newBuilder()
                        .setConstraintType(expectedConstraintType)
                        .setConstraintValue(expectedConstraintValue)
                        .build();

        final var constraintCustom = serializer.deserialize(serializedConstraintCustom);

        assertThat(constraintCustom).usingRecursiveComparison().isEqualTo(expectedConstraintCustom);
    }

    @Test
    void shouldSerializeConstraintSchedule() {
        final var expectedStartTimestamp = 10;
        final var expectedDurationDays = 2.2f;

        final var constraintSchedule =
                new ConstraintSchedule(expectedStartTimestamp, expectedDurationDays);

        final var expectedConstraintSchedule =
                ContextOuterClass.Constraint_Schedule.newBuilder()
                        .setStartTimestamp(expectedStartTimestamp)
                        .setDurationDays(expectedDurationDays)
                        .build();

        final var serializedConstraintSchedule = serializer.serialize(constraintSchedule);

        assertThat(serializedConstraintSchedule)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSchedule);
    }

    @Test
    void shouldDeserializeConstraintSchedule() {
        final var expectedStartTimestamp = 10;
        final var expectedDurationDays = 2.2f;

        final var expectedConstraintSchedule =
                new ConstraintSchedule(expectedStartTimestamp, expectedDurationDays);

        final var serializedConstraintSchedule =
                ContextOuterClass.Constraint_Schedule.newBuilder()
                        .setStartTimestamp(expectedStartTimestamp)
                        .setDurationDays(expectedDurationDays)
                        .build();

        final var constraintSchedule = serializer.deserialize(serializedConstraintSchedule);

        assertThat(constraintSchedule).usingRecursiveComparison().isEqualTo(expectedConstraintSchedule);
    }

    @Test
    void shouldSerializeLocationOfTypeRegion() {
        final var region = "Tokyo";

        final var locationTypeRegion = new LocationTypeRegion(region);
        final var location = new Location(locationTypeRegion);

        final var expectedLocation = ContextOuterClass.Location.newBuilder().setRegion(region).build();

        final var serializedLocation = serializer.serialize(location);

        assertThat(serializedLocation).isEqualTo(expectedLocation);
    }

    @Test
    void shouldDeserializeLocationOfTypeRegion() {
        final var region = "Tokyo";

        final var locationTypeRegion = new LocationTypeRegion(region);
        final var expectedLocation = new Location(locationTypeRegion);

        final var serializedLocation =
                ContextOuterClass.Location.newBuilder().setRegion(region).build();

        final var location = serializer.deserialize(serializedLocation);

        assertThat(location).usingRecursiveComparison().isEqualTo(expectedLocation);
    }

    @Test
    void shouldSerializeLocationOfTypeGpsPosition() {
        final var latitude = 33.3f;
        final var longitude = 86.4f;

        final var gpsPosition = new GpsPosition(latitude, longitude);
        final var locationTypeGpsPosition = new LocationTypeGpsPosition(gpsPosition);
        final var location = new Location(locationTypeGpsPosition);

        final var serializedGpsPosition =
                ContextOuterClass.GPS_Position.newBuilder()
                        .setLatitude(latitude)
                        .setLongitude(longitude)
                        .build();

        final var expectedLocation =
                ContextOuterClass.Location.newBuilder().setGpsPosition(serializedGpsPosition).build();

        final var serializedLocation = serializer.serialize(location);

        assertThat(serializedLocation).isEqualTo(expectedLocation);
    }

    @Test
    void shouldDeserializeLocationOfTypeGpsPosition() {
        final var latitude = 33.3f;
        final var longitude = 86.4f;

        final var gpsPosition = new GpsPosition(latitude, longitude);
        final var locationTypeGpsPosition = new LocationTypeGpsPosition(gpsPosition);
        final var expectedLocation = new Location(locationTypeGpsPosition);

        final var serializedGpsPosition =
                ContextOuterClass.GPS_Position.newBuilder()
                        .setLatitude(latitude)
                        .setLongitude(longitude)
                        .build();

        final var serializedLocation =
                ContextOuterClass.Location.newBuilder().setGpsPosition(serializedGpsPosition).build();

        final var location = serializer.deserialize(serializedLocation);

        assertThat(location).usingRecursiveComparison().isEqualTo(expectedLocation);
    }

    @Test
    void shouldThrowIllegalStateExceptionDuringDeserializationOfNonSpecifiedLocation() {
        final var serializedLocation = ContextOuterClass.Location.newBuilder().build();

        assertThatExceptionOfType(IllegalStateException.class)
                .isThrownBy(() -> serializer.deserialize(serializedLocation));
    }

    private static Stream<Arguments> provideIsolationLevelEnum() {
        return Stream.of(
                Arguments.of(
                        IsolationLevelEnum.NO_ISOLATION, ContextOuterClass.IsolationLevelEnum.NO_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.PHYSICAL_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.PHYSICAL_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.LOGICAL_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.LOGICAL_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.PROCESS_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.PROCESS_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.PHYSICAL_MEMORY_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.PHYSICAL_MEMORY_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.PHYSICAL_NETWORK_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.PHYSICAL_NETWORK_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.VIRTUAL_RESOURCE_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.VIRTUAL_RESOURCE_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.NETWORK_FUNCTIONS_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.NETWORK_FUNCTIONS_ISOLATION),
                Arguments.of(
                        IsolationLevelEnum.SERVICE_ISOLATION,
                        ContextOuterClass.IsolationLevelEnum.SERVICE_ISOLATION));
    }

    @ParameterizedTest
    @MethodSource("provideIsolationLevelEnum")
    void shouldSerializeIsolationLevelEnum(
            IsolationLevelEnum isolationLevelEnum,
            ContextOuterClass.IsolationLevelEnum expectedIsolationLevelEnum) {
        final var serializedIsolationLevelEnum = serializer.serialize(isolationLevelEnum);

        assertThat(serializedIsolationLevelEnum.getNumber())
                .isEqualTo(expectedIsolationLevelEnum.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideIsolationLevelEnum")
    void shouldDeserializeIsolationLevelEnum(
            IsolationLevelEnum expectedIsolationLevelEnum,
            ContextOuterClass.IsolationLevelEnum serializedIsolationLevelEnum) {
        final var isolationLevelEnum = serializer.deserialize(serializedIsolationLevelEnum);

        assertThat(isolationLevelEnum).isEqualTo(expectedIsolationLevelEnum);
    }

    @Test
    void shouldSerializeConstraintEndPointLocation() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var locationType = new LocationTypeRegion("ATH");
        final var location = new Location(locationType);

        final var constraintEndPointLocation = new ConstraintEndPointLocation(endPointId, location);

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedLocation = serializer.serialize(location);

        final var expectedConstraintEndPointLocation =
                ContextOuterClass.Constraint_EndPointLocation.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setLocation(serializedLocation)
                        .build();

        final var serializedConstraintEndPointLocation =
                serializer.serialize(constraintEndPointLocation);

        assertThat(serializedConstraintEndPointLocation)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintEndPointLocation);
    }

    @Test
    void shouldDeserializeConstraintEndPointLocation() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var latitude = 54.6f;
        final var longitude = 123.7f;
        final var gpsPosition = new GpsPosition(latitude, longitude);

        final var locationType = new LocationTypeGpsPosition(gpsPosition);
        final var location = new Location(locationType);

        final var expectedConstraintEndPointLocation =
                new ConstraintEndPointLocation(endPointId, location);

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedLocation = serializer.serialize(location);

        final var serializedConstraintEndPointLocation =
                ContextOuterClass.Constraint_EndPointLocation.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setLocation(serializedLocation)
                        .build();

        final var constraintEndPointLocation =
                serializer.deserialize(serializedConstraintEndPointLocation);

        assertThat(constraintEndPointLocation)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintEndPointLocation);
    }

    @Test
    void shouldSerializeConstraintSlaAvailability() {
        final var numDisJointPaths = 2;
        final var isAllActive = true;

        final var constraintSlaAvailability =
                new ConstraintSlaAvailability(numDisJointPaths, isAllActive);

        final var expectedConstraintSlaAvailability =
                ContextOuterClass.Constraint_SLA_Availability.newBuilder()
                        .setNumDisjointPaths(numDisJointPaths)
                        .setAllActive(isAllActive)
                        .build();

        final var serializedConstraintSlaAvailability = serializer.serialize(constraintSlaAvailability);

        assertThat(serializedConstraintSlaAvailability)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaAvailability);
    }

    @Test
    void shouldDeserializeConstraintSlaAvailability() {
        final var numDisJointPaths = 2;
        final var isAllActive = true;

        final var expectedConstraintSlaAvailability =
                new ConstraintSlaAvailability(numDisJointPaths, isAllActive);

        final var serializedConstraintSlaAvailability =
                ContextOuterClass.Constraint_SLA_Availability.newBuilder()
                        .setNumDisjointPaths(numDisJointPaths)
                        .setAllActive(isAllActive)
                        .build();

        final var constraintSlaAvailability =
                serializer.deserialize(serializedConstraintSlaAvailability);

        assertThat(constraintSlaAvailability)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaAvailability);
    }

    @Test
    void shouldSerializeConstraintSlaCapacity() {
        final var capacityGbps = 5;

        final var constraintSlaCapacity = new ConstraintSlaCapacity(capacityGbps);

        final var expectedConstraintSlaCapacity =
                ContextOuterClass.Constraint_SLA_Capacity.newBuilder()
                        .setCapacityGbps(capacityGbps)
                        .build();

        final var serializedConstraintSlaCapacity = serializer.serialize(constraintSlaCapacity);

        assertThat(serializedConstraintSlaCapacity)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaCapacity);
    }

    @Test
    void shouldDeserializeConstraintSlaCapacity() {
        final var capacityGbps = 5;

        final var expectedConstraintSlaCapacity = new ConstraintSlaCapacity(capacityGbps);

        final var serializedConstraintSlaCapacity =
                ContextOuterClass.Constraint_SLA_Capacity.newBuilder()
                        .setCapacityGbps(capacityGbps)
                        .build();

        final var constraintSlaCapacity = serializer.deserialize(serializedConstraintSlaCapacity);

        assertThat(constraintSlaCapacity)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaCapacity);
    }

    @Test
    void shouldSerializeConstraintSlaIsolationLevel() {
        final var isolationLevelEnums =
                List.of(
                        IsolationLevelEnum.PHYSICAL_MEMORY_ISOLATION,
                        IsolationLevelEnum.NETWORK_FUNCTIONS_ISOLATION);

        final var constraintSlaIsolationLevel = new ConstraintSlaIsolationLevel(isolationLevelEnums);

        final var serializedIsolationLevelEnums =
                isolationLevelEnums.stream()
                        .map(isolationLevelEnum -> serializer.serialize(isolationLevelEnum))
                        .collect(Collectors.toList());
        final var expectedConstraintSlaIsolationLevel =
                ContextOuterClass.Constraint_SLA_Isolation_level.newBuilder()
                        .addAllIsolationLevel(serializedIsolationLevelEnums)
                        .build();

        final var serializedConstraintSlaIsolationLevel =
                serializer.serialize(constraintSlaIsolationLevel);

        assertThat(serializedConstraintSlaIsolationLevel)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaIsolationLevel);
    }

    @Test
    void shouldDeserializeConstraintSlaIsolationLevel() {
        final var isolationLevelEnums =
                List.of(IsolationLevelEnum.PROCESS_ISOLATION, IsolationLevelEnum.SERVICE_ISOLATION);

        final var expectedConstraintSlaIsolationLevel =
                new ConstraintSlaIsolationLevel(isolationLevelEnums);

        final var serializedIsolationLevelEnums =
                isolationLevelEnums.stream()
                        .map(isolationLevelEnum -> serializer.serialize(isolationLevelEnum))
                        .collect(Collectors.toList());
        final var serializedConstraintSlaIsolationLevel =
                ContextOuterClass.Constraint_SLA_Isolation_level.newBuilder()
                        .addAllIsolationLevel(serializedIsolationLevelEnums)
                        .build();

        final var constraintSlaIsolationLevel =
                serializer.deserialize(serializedConstraintSlaIsolationLevel);

        assertThat(constraintSlaIsolationLevel)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaIsolationLevel);
    }

    @Test
    void shouldSerializeConstraintSlaLatency() {
        final var e2eLatencyMs = 5.7f;

        final var constraintSlaLatency = new ConstraintSlaLatency(e2eLatencyMs);

        final var expectedConstraintSlaLatency =
                ContextOuterClass.Constraint_SLA_Latency.newBuilder().setE2ELatencyMs(e2eLatencyMs).build();

        final var serializedConstraintSlaLatency = serializer.serialize(constraintSlaLatency);

        assertThat(serializedConstraintSlaLatency)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaLatency);
    }

    @Test
    void shouldDeserializeConstraintSlaLatency() {
        final var e2eLatencyMs = 5.7f;

        final var expectedConstraintSlaLatency = new ConstraintSlaLatency(e2eLatencyMs);

        final var serializedConstraintSlaLatency =
                ContextOuterClass.Constraint_SLA_Latency.newBuilder().setE2ELatencyMs(e2eLatencyMs).build();

        final var constraintSlaLatency = serializer.deserialize(serializedConstraintSlaLatency);

        assertThat(constraintSlaLatency)
                .usingRecursiveComparison()
                .isEqualTo(expectedConstraintSlaLatency);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintCustom() {
        final var expectedConstraintType = "constraintType";
        final var expectedConstraintValue = "constraintValue";

        final var constraintCustom =
                new ConstraintCustom(expectedConstraintType, expectedConstraintValue);
        final var constraintTypeCustom = new ConstraintTypeCustom(constraintCustom);
        final var constraint = new Constraint(constraintTypeCustom);

        final var expectedConstraintCustom =
                ContextOuterClass.Constraint_Custom.newBuilder()
                        .setConstraintType(expectedConstraintType)
                        .setConstraintValue(expectedConstraintValue)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder().setCustom(expectedConstraintCustom).build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintCustom() {
        final var expectedConstraintType = "constraintType";
        final var expectedConstraintValue = "constraintValue";

        final var constraintCustom =
                new ConstraintCustom(expectedConstraintType, expectedConstraintValue);
        final var constraintTypeCustom = new ConstraintTypeCustom(constraintCustom);
        final var expectedConstraint = new Constraint(constraintTypeCustom);

        final var serializedConstraintCustom =
                ContextOuterClass.Constraint_Custom.newBuilder()
                        .setConstraintType(expectedConstraintType)
                        .setConstraintValue(expectedConstraintValue)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder().setCustom(serializedConstraintCustom).build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintSchedule() {
        final var startTimeSTamp = 2.2f;
        final var durationDays = 5.73f;

        final var constraintSchedule = new ConstraintSchedule(startTimeSTamp, durationDays);
        final var constraintTypeSchedule = new ConstraintTypeSchedule(constraintSchedule);
        final var constraint = new Constraint(constraintTypeSchedule);

        final var expectedConstraintSchedule =
                ContextOuterClass.Constraint_Schedule.newBuilder()
                        .setStartTimestamp(startTimeSTamp)
                        .setDurationDays(durationDays)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder().setSchedule(expectedConstraintSchedule).build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintSchedule() {
        final var startTimeSTamp = 2.2f;
        final var durationDays = 5.73f;

        final var expectedConstraintSchedule = new ConstraintSchedule(startTimeSTamp, durationDays);
        final var expectedConstraintTypeSchedule =
                new ConstraintTypeSchedule(expectedConstraintSchedule);
        final var expectedConstraint = new Constraint(expectedConstraintTypeSchedule);

        final var serializedConstraintSchedule =
                ContextOuterClass.Constraint_Schedule.newBuilder()
                        .setStartTimestamp(startTimeSTamp)
                        .setDurationDays(durationDays)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder().setSchedule(serializedConstraintSchedule).build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintEndPointLocation() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var locationType = new LocationTypeRegion("ATH");
        final var location = new Location(locationType);

        final var constraintEndPointLocation = new ConstraintEndPointLocation(endPointId, location);
        final var constraintTypeEndPointLocation =
                new ConstraintTypeEndPointLocation(constraintEndPointLocation);
        final var constraint = new Constraint(constraintTypeEndPointLocation);

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedLocation = serializer.serialize(location);

        final var expectedConstraintEndPointLocation =
                ContextOuterClass.Constraint_EndPointLocation.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setLocation(serializedLocation)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setEndpointLocation(expectedConstraintEndPointLocation)
                        .build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintEndPointLocation() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var locationType = new LocationTypeRegion("ATH");
        final var location = new Location(locationType);

        final var expectedConstraintEndPointLocation =
                new ConstraintEndPointLocation(endPointId, location);
        final var expectedConstraintTypeEndPointLocation =
                new ConstraintTypeEndPointLocation(expectedConstraintEndPointLocation);
        final var expectedConstraint = new Constraint(expectedConstraintTypeEndPointLocation);

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedLocation = serializer.serialize(location);

        final var serializedEndPointLocation =
                ContextOuterClass.Constraint_EndPointLocation.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setLocation(serializedLocation)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setEndpointLocation(serializedEndPointLocation)
                        .build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintSlaAvailability() {
        final var numDisjointPaths = 2;
        final var isAllActive = true;

        final var constraintSlaAvailability =
                new ConstraintSlaAvailability(numDisjointPaths, isAllActive);
        final var constraintTypeSlaAvailability =
                new ConstraintTypeSlaAvailability(constraintSlaAvailability);
        final var constraint = new Constraint(constraintTypeSlaAvailability);

        final var expectedConstraintSlaAvailability =
                ContextOuterClass.Constraint_SLA_Availability.newBuilder()
                        .setNumDisjointPaths(numDisjointPaths)
                        .setAllActive(isAllActive)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaAvailability(expectedConstraintSlaAvailability)
                        .build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintSlaAvailability() {
        final var numDisjointPaths = 2;
        final var isAllActive = true;

        final var expectedConstraintSlaAvailability =
                new ConstraintSlaAvailability(numDisjointPaths, isAllActive);
        final var expectedConstraintTypeSlaAvailability =
                new ConstraintTypeSlaAvailability(expectedConstraintSlaAvailability);
        final var expectedConstraint = new Constraint(expectedConstraintTypeSlaAvailability);

        final var serializedConstraintSlaAvailability =
                ContextOuterClass.Constraint_SLA_Availability.newBuilder()
                        .setNumDisjointPaths(numDisjointPaths)
                        .setAllActive(isAllActive)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaAvailability(serializedConstraintSlaAvailability)
                        .build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintSlaCapacity() {
        final var capacityGbps = 77.3f;

        final var constraintSlaCapacity = new ConstraintSlaCapacity(capacityGbps);
        final var constraintTypeSlaCapacity = new ConstraintTypeSlaCapacity(constraintSlaCapacity);
        final var constraint = new Constraint(constraintTypeSlaCapacity);

        final var expectedConstraintSlaCapacity =
                ContextOuterClass.Constraint_SLA_Capacity.newBuilder()
                        .setCapacityGbps(capacityGbps)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaCapacity(expectedConstraintSlaCapacity)
                        .build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintSlaCapacity() {
        final var capacityGbps = 77.3f;

        final var expectedConstraintSlaCapacity = new ConstraintSlaCapacity(capacityGbps);
        final var expectedConstraintTypeSlaCapacity =
                new ConstraintTypeSlaCapacity(expectedConstraintSlaCapacity);
        final var expectedConstraint = new Constraint(expectedConstraintTypeSlaCapacity);

        final var serializedConstraintSlaCapacity =
                ContextOuterClass.Constraint_SLA_Capacity.newBuilder()
                        .setCapacityGbps(capacityGbps)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaCapacity(serializedConstraintSlaCapacity)
                        .build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintSlaIsolationLevel() {
        final var isolationLevelEnums =
                List.of(IsolationLevelEnum.PHYSICAL_ISOLATION, IsolationLevelEnum.NO_ISOLATION);

        final var expectedConstraintSlaIsolationLevel =
                new ConstraintSlaIsolationLevel(isolationLevelEnums);
        final var expectedConstraintTypeSlaIsolationLevel =
                new ConstraintTypeSlaIsolationLevel(expectedConstraintSlaIsolationLevel);
        final var expectedConstraint = new Constraint(expectedConstraintTypeSlaIsolationLevel);

        final var serializedIsolationLevelEnums =
                isolationLevelEnums.stream()
                        .map(isolationLevelEnum -> serializer.serialize(isolationLevelEnum))
                        .collect(Collectors.toList());

        final var serializedConstraintSlaIsolationLevel =
                ContextOuterClass.Constraint_SLA_Isolation_level.newBuilder()
                        .addAllIsolationLevel(serializedIsolationLevelEnums)
                        .build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaIsolation(serializedConstraintSlaIsolationLevel)
                        .build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintSlaIsolationLevel() {
        final var isolationLevelEnums =
                List.of(
                        IsolationLevelEnum.VIRTUAL_RESOURCE_ISOLATION,
                        IsolationLevelEnum.PHYSICAL_MEMORY_ISOLATION);

        final var constraintSlaIsolationLevel = new ConstraintSlaIsolationLevel(isolationLevelEnums);
        final var constraintTypeSlaIsolationLevel =
                new ConstraintTypeSlaIsolationLevel(constraintSlaIsolationLevel);
        final var constraint = new Constraint(constraintTypeSlaIsolationLevel);

        final var serializedIsolationLevelEnums =
                isolationLevelEnums.stream()
                        .map(isolationLevelEnum -> serializer.serialize(isolationLevelEnum))
                        .collect(Collectors.toList());

        final var expectedConstraintSlaIsolationLevel =
                ContextOuterClass.Constraint_SLA_Isolation_level.newBuilder()
                        .addAllIsolationLevel(serializedIsolationLevelEnums)
                        .build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaIsolation(expectedConstraintSlaIsolationLevel)
                        .build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeConstraintOfTypeConstraintSlaLatency() {
        final var e2eLatencyMs = 45.32f;

        final var constraintSlaLatency = new ConstraintSlaLatency(e2eLatencyMs);
        final var constraintTypeSlaLatency = new ConstraintTypeSlaLatency(constraintSlaLatency);
        final var constraint = new Constraint(constraintTypeSlaLatency);

        final var expectedConstraintSlaLatency =
                ContextOuterClass.Constraint_SLA_Latency.newBuilder().setE2ELatencyMs(e2eLatencyMs).build();

        final var expectedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaLatency(expectedConstraintSlaLatency)
                        .build();

        final var serializedConstraint = serializer.serialize(constraint);

        assertThat(serializedConstraint).isEqualTo(expectedConstraint);
    }

    @Test
    void shouldDeserializeConstraintOfTypeConstraintSlaLatency() {
        final var e2eLatencyMs = 45.32f;

        final var expectedConstraintSlaLatency = new ConstraintSlaLatency(e2eLatencyMs);
        final var expectedConstraintTypeSlaLatency =
                new ConstraintTypeSlaLatency(expectedConstraintSlaLatency);
        final var expectedConstraint = new Constraint(expectedConstraintTypeSlaLatency);

        final var serializedConstraintSlaLatency =
                ContextOuterClass.Constraint_SLA_Latency.newBuilder().setE2ELatencyMs(e2eLatencyMs).build();

        final var serializedConstraint =
                ContextOuterClass.Constraint.newBuilder()
                        .setSlaLatency(serializedConstraintSlaLatency)
                        .build();

        final var constraint = serializer.deserialize(serializedConstraint);

        assertThat(constraint).usingRecursiveComparison().isEqualTo(expectedConstraint);
    }

    @Test
    void shouldSerializeEndPointId() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";

        final var endPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var serializedTopologyId = serializer.serialize(expectedTopologyId);
        final var serializedDeviceId = serializer.serializeDeviceId(expectedDeviceId);
        final var serializedEndPointUuid = serializer.serializeUuid(expectedId);

        final var expectedEndPointId =
                ContextOuterClass.EndPointId.newBuilder()
                        .setTopologyId(serializedTopologyId)
                        .setDeviceId(serializedDeviceId)
                        .setEndpointUuid(serializedEndPointUuid)
                        .build();

        final var serializedEndPointId = serializer.serialize(endPointId);

        assertThat(serializedEndPointId).usingRecursiveComparison().isEqualTo(expectedEndPointId);
    }

    @Test
    void shouldDeserializeEndPointId() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";

        final var expectedEndPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);

        final var serializedEndPointId = serializer.serialize(expectedEndPointId);
        final var endPointId = serializer.deserialize(serializedEndPointId);

        assertThat(endPointId).usingRecursiveComparison().isEqualTo(expectedEndPointId);
    }

    private static Stream<Arguments> provideEventTypeEnum() {
        return Stream.of(
                Arguments.of(EventTypeEnum.CREATE, ContextOuterClass.EventTypeEnum.EVENTTYPE_CREATE),
                Arguments.of(EventTypeEnum.REMOVE, ContextOuterClass.EventTypeEnum.EVENTTYPE_REMOVE),
                Arguments.of(EventTypeEnum.UNDEFINED, ContextOuterClass.EventTypeEnum.EVENTTYPE_UNDEFINED),
                Arguments.of(EventTypeEnum.UPDATE, ContextOuterClass.EventTypeEnum.EVENTTYPE_UPDATE));
    }

    @ParameterizedTest
    @MethodSource("provideEventTypeEnum")
    void shouldSerializeEventType(
            EventTypeEnum eventType, ContextOuterClass.EventTypeEnum expectedSerializedType) {
        final var serializedType = serializer.serialize(eventType);

        assertThat(serializedType.getNumber()).isEqualTo(expectedSerializedType.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideEventTypeEnum")
    void shouldDeserializeEventType(
            EventTypeEnum expectedEventType, ContextOuterClass.EventTypeEnum serializedEventType) {
        final var eventType = serializer.deserialize(serializedEventType);

        assertThat(eventType).isEqualTo(expectedEventType);
    }

    @Test
    void shouldSerializeEvent() {
        final var timestamp = ContextOuterClass.Timestamp.newBuilder().setTimestamp(1).build();

        final var expectedEvent =
                ContextOuterClass.Event.newBuilder()
                        .setTimestamp(timestamp)
                        .setEventType(ContextOuterClass.EventTypeEnum.EVENTTYPE_CREATE)
                        .build();

        final var event = new Event(1, EventTypeEnum.CREATE);
        final var serializedEvent = serializer.serialize(event);

        assertThat(serializedEvent).usingRecursiveComparison().isEqualTo(expectedEvent);
    }

    @Test
    void shouldDeserializeEvent() {
        final var expectedEvent = new Event(1, EventTypeEnum.CREATE);
        final var timestamp = ContextOuterClass.Timestamp.newBuilder().setTimestamp(1).build();

        final var serializedEvent =
                ContextOuterClass.Event.newBuilder()
                        .setTimestamp(timestamp)
                        .setEventType(ContextOuterClass.EventTypeEnum.EVENTTYPE_CREATE)
                        .build();
        final var event = serializer.deserialize(serializedEvent);

        assertThat(event).usingRecursiveComparison().isEqualTo(expectedEvent);
    }

    @Test
    void shouldSerializeServiceId() {
        final var expectedContextId = "expectedContextId";
        final var expectedId = "expectedId";
        final var serviceId = new ServiceId(expectedContextId, expectedId);

        final var serializedContextId = serializer.serializeContextId(expectedContextId);
        final var serializedIdUuid = serializer.serializeUuid(expectedId);

        final var expectedServiceId =
                ContextOuterClass.ServiceId.newBuilder()
                        .setContextId(serializedContextId)
                        .setServiceUuid(serializedIdUuid)
                        .build();

        final var serializedServiceId = serializer.serialize(serviceId);

        assertThat(serializedServiceId).usingRecursiveComparison().isEqualTo(expectedServiceId);
    }

    @Test
    void shouldDeserializeServiceId() {
        final var expectedContextId = "expectedContextId";
        final var expectedId = "expectedId";

        final var expectedServiceId = new ServiceId(expectedContextId, expectedId);

        final var serializedServiceId = serializer.serialize(expectedServiceId);

        final var serviceId = serializer.deserialize(serializedServiceId);

        assertThat(serviceId).usingRecursiveComparison().isEqualTo(expectedServiceId);
    }

    private static Stream<Arguments> provideServiceStatusEnum() {
        return Stream.of(
                Arguments.of(
                        ServiceStatusEnum.ACTIVE, ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_ACTIVE),
                Arguments.of(
                        ServiceStatusEnum.PLANNED, ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_PLANNED),
                Arguments.of(
                        ServiceStatusEnum.PENDING_REMOVAL,
                        ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_PENDING_REMOVAL),
                Arguments.of(
                        ServiceStatusEnum.SLA_VIOLATED,
                        ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_SLA_VIOLATED),
                Arguments.of(
                        ServiceStatusEnum.UPDATING, ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_UPDATING),
                Arguments.of(
                        ServiceStatusEnum.UNDEFINED,
                        ContextOuterClass.ServiceStatusEnum.SERVICESTATUS_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideServiceStatusEnum")
    void shouldSerializeServiceStatusEnum(
            ServiceStatusEnum serviceStatusEnum,
            ContextOuterClass.ServiceStatusEnum expectedSerializedType) {
        final var serializedServiceStatusEnum = serializer.serialize(serviceStatusEnum);

        assertThat(serializedServiceStatusEnum.getNumber())
                .isEqualTo(expectedSerializedType.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideServiceStatusEnum")
    void shouldDeserializeServiceStatusEnum(
            ServiceStatusEnum expectedServiceStatusEnum,
            ContextOuterClass.ServiceStatusEnum serializedServiceStatusEnum) {
        final var serviceStatusEnum = serializer.deserialize(serializedServiceStatusEnum);

        assertThat(serviceStatusEnum).isEqualTo(expectedServiceStatusEnum);
    }

    private static Stream<Arguments> provideServiceTypeEnum() {
        return Stream.of(
                Arguments.of(ServiceTypeEnum.L2NM, ContextOuterClass.ServiceTypeEnum.SERVICETYPE_L2NM),
                Arguments.of(ServiceTypeEnum.L3NM, ContextOuterClass.ServiceTypeEnum.SERVICETYPE_L3NM),
                Arguments.of(
                        ServiceTypeEnum.TAPI_CONNECTIVITY_SERVICE,
                        ContextOuterClass.ServiceTypeEnum.SERVICETYPE_TAPI_CONNECTIVITY_SERVICE),
                Arguments.of(
                        ServiceTypeEnum.UNKNOWN, ContextOuterClass.ServiceTypeEnum.SERVICETYPE_UNKNOWN));
    }

    @ParameterizedTest
    @MethodSource("provideServiceTypeEnum")
    void shouldSerializeServiceTypeEnum(
            ServiceTypeEnum serviceTypeEnum, ContextOuterClass.ServiceTypeEnum expectedSerializedType) {
        final var serializedServiceTypeEnum = serializer.serialize(serviceTypeEnum);

        assertThat(serializedServiceTypeEnum.getNumber()).isEqualTo(expectedSerializedType.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideServiceTypeEnum")
    void shouldDeserializeServiceTypeEnum(
            ServiceTypeEnum expectedServiceTypeEnum,
            ContextOuterClass.ServiceTypeEnum serializedServiceTypeEnum) {
        final var serviceTypeEnum = serializer.deserialize(serializedServiceTypeEnum);

        assertThat(serviceTypeEnum).isEqualTo(expectedServiceTypeEnum);
    }

    @Test
    void shouldSerializeServiceStatus() {
        final var expectedServiceStatusEnum = ServiceStatusEnum.ACTIVE;
        final var serviceStatus = new ServiceStatus(expectedServiceStatusEnum);

        final var serializedServiceStatusEnum = serializer.serialize(expectedServiceStatusEnum);

        final var expectedServiceStatus =
                ContextOuterClass.ServiceStatus.newBuilder()
                        .setServiceStatus(serializedServiceStatusEnum)
                        .build();

        final var serializedServiceStatus = serializer.serialize(serviceStatus);

        assertThat(serializedServiceStatus).usingRecursiveComparison().isEqualTo(expectedServiceStatus);
    }

    @Test
    void shouldDeserializeServiceStatus() {
        final var expectedServiceStatus = new ServiceStatus(ServiceStatusEnum.PENDING_REMOVAL);

        final var serializedServiceStatus = serializer.serialize(expectedServiceStatus);
        final var serviceStatus = serializer.deserialize(serializedServiceStatus);

        assertThat(serviceStatus).usingRecursiveComparison().isEqualTo(expectedServiceStatus);
    }

    @Test
    void shouldSerializeServiceConfig() {
        final var configRuleA = createConfigRule();
        final var configRuleB = createConfigRule();
        final var serviceConfig = new ServiceConfig(List.of(configRuleA, configRuleB));

        final var expectedConfigRuleA = serializer.serialize(configRuleA);
        final var expectedConfigRuleB = serializer.serialize(configRuleB);

        final var expectedServiceConfig =
                ContextOuterClass.ServiceConfig.newBuilder()
                        .addAllConfigRules(List.of(expectedConfigRuleA, expectedConfigRuleB))
                        .build();

        final var serializedServiceConfig = serializer.serialize(serviceConfig);

        assertThat(serializedServiceConfig).usingRecursiveComparison().isEqualTo(expectedServiceConfig);
    }

    @Test
    void shouldDeserializeServiceConfig() {
        final var expectedConfigRuleA = createConfigRule();
        final var expectedConfigRuleB = createConfigRule();
        final var expectedServiceConfig =
                new ServiceConfig(List.of(expectedConfigRuleA, expectedConfigRuleB));

        final var configRuleA = serializer.serialize(expectedConfigRuleA);
        final var configRuleB = serializer.serialize(expectedConfigRuleB);
        final var serializedServiceConfig =
                ContextOuterClass.ServiceConfig.newBuilder()
                        .addAllConfigRules(List.of(configRuleA, configRuleB))
                        .build();

        final var serviceConfig = serializer.deserialize(serializedServiceConfig);

        assertThat(serviceConfig).usingRecursiveComparison().isEqualTo(expectedServiceConfig);
    }

    @Test
    void shouldSerializeService() {
        final var expectedServiceId = new ServiceId("contextId", "serviceId");
        final var expectedServiceTypeEnum = ServiceTypeEnum.TAPI_CONNECTIVITY_SERVICE;
        final var firstExpectedTopologyId = new TopologyId("contextId", "firstTopologyId");
        final var secondExpectedTopologyId = new TopologyId("contextId", "secondTopologyId");

        final var firstExpectedEndPointId =
                new EndPointId(firstExpectedTopologyId, "firstDeviceId", "firstEndPointId");
        final var secondExpectedEndPointId =
                new EndPointId(secondExpectedTopologyId, "firstDeviceId", "firstEndPointId");
        final var expectedServiceEndPointIds =
                List.of(firstExpectedEndPointId, secondExpectedEndPointId);

        final var expectedConstraintTypeA = "constraintTypeA";
        final var expectedConstraintValueA = "constraintValueA";

        final var constraintCustomA =
                new ConstraintCustom(expectedConstraintTypeA, expectedConstraintValueA);
        final var constraintTypeCustomA = new ConstraintTypeCustom(constraintCustomA);
        final var firstExpectedConstraint = new Constraint(constraintTypeCustomA);

        final var expectedConstraintTypeB = "constraintTypeB";
        final var expectedConstraintValueB = "constraintValueB";

        final var constraintCustomB =
                new ConstraintCustom(expectedConstraintTypeB, expectedConstraintValueB);
        final var constraintTypeCustomB = new ConstraintTypeCustom(constraintCustomB);
        final var secondExpectedConstraint = new Constraint(constraintTypeCustomB);

        final var expectedServiceConstraints =
                List.of(firstExpectedConstraint, secondExpectedConstraint);

        final var expectedServiceStatus = new ServiceStatus(ServiceStatusEnum.PLANNED);

        final var expectedConfigRuleA = createConfigRule();
        final var expectedConfigRuleB = createConfigRule();

        final var expectedConfigRules = List.of(expectedConfigRuleA, expectedConfigRuleB);

        final var expectedServiceConfig = new ServiceConfig(expectedConfigRules);

        final var expectedTimestamp = 2.3;

        final var service =
                new Service(
                        expectedServiceId,
                        expectedServiceTypeEnum,
                        expectedServiceEndPointIds,
                        expectedServiceConstraints,
                        expectedServiceStatus,
                        expectedServiceConfig,
                        expectedTimestamp);

        final var serializedServiceId = serializer.serialize(expectedServiceId);
        final var serializedServiceType = serializer.serialize(expectedServiceTypeEnum);
        final var serializedServiceEndPointIds =
                expectedServiceEndPointIds.stream()
                        .map(endPointId -> serializer.serialize(endPointId))
                        .collect(Collectors.toList());
        final var serializedServiceConstraints =
                expectedServiceConstraints.stream()
                        .map(constraint -> serializer.serialize(constraint))
                        .collect(Collectors.toList());
        final var serializedServiceStatus = serializer.serialize(expectedServiceStatus);
        final var serializedServiceConfig = serializer.serialize(expectedServiceConfig);
        final var serializedTimestamp = serializer.serialize(expectedTimestamp);

        final var expectedService =
                ContextOuterClass.Service.newBuilder()
                        .setServiceId(serializedServiceId)
                        .setServiceType(serializedServiceType)
                        .addAllServiceEndpointIds(serializedServiceEndPointIds)
                        .addAllServiceConstraints(serializedServiceConstraints)
                        .setServiceStatus(serializedServiceStatus)
                        .setServiceConfig(serializedServiceConfig)
                        .setTimestamp(serializedTimestamp)
                        .build();

        final var serializedService = serializer.serialize(service);

        assertThat(serializedService).isEqualTo(expectedService);
    }

    @Test
    void shouldDeserializeService() {
        final var expectedServiceId = new ServiceId("contextId", "serviceId");
        final var expectedServiceTypeEnum = ServiceTypeEnum.TAPI_CONNECTIVITY_SERVICE;
        final var firstExpectedTopologyId = new TopologyId("contextId", "firstTopologyId");
        final var secondExpectedTopologyId = new TopologyId("contextId", "secondTopologyId");

        final var firstExpectedEndPointId =
                new EndPointId(firstExpectedTopologyId, "firstDeviceId", "firstEndPointId");
        final var secondExpectedEndPointId =
                new EndPointId(secondExpectedTopologyId, "firstDeviceId", "firstEndPointId");
        final var expectedServiceEndPointIds =
                List.of(firstExpectedEndPointId, secondExpectedEndPointId);

        final var expectedConstraintTypeA = "constraintTypeA";
        final var expectedConstraintValueA = "constraintValueA";

        final var constraintCustomA =
                new ConstraintCustom(expectedConstraintTypeA, expectedConstraintValueA);
        final var constraintTypeCustomA = new ConstraintTypeCustom(constraintCustomA);
        final var firstExpectedConstraint = new Constraint(constraintTypeCustomA);

        final var expectedConstraintTypeB = "constraintTypeB";
        final var expectedConstraintValueB = "constraintValueB";

        final var constraintCustomB =
                new ConstraintCustom(expectedConstraintTypeB, expectedConstraintValueB);
        final var constraintTypeCustomB = new ConstraintTypeCustom(constraintCustomB);
        final var secondExpectedConstraint = new Constraint(constraintTypeCustomB);

        final var expectedServiceConstraints =
                List.of(firstExpectedConstraint, secondExpectedConstraint);

        final var expectedServiceStatus = new ServiceStatus(ServiceStatusEnum.PLANNED);

        final var firstExpectedConfigRuleA = createConfigRule();
        final var secondExpectedConfigRuleB = createConfigRule();

        final var expectedConfigRules = List.of(firstExpectedConfigRuleA, secondExpectedConfigRuleB);

        final var expectedServiceConfig = new ServiceConfig(expectedConfigRules);

        final var expectedTimestamp = 7.8;

        final var expectedService =
                new Service(
                        expectedServiceId,
                        expectedServiceTypeEnum,
                        expectedServiceEndPointIds,
                        expectedServiceConstraints,
                        expectedServiceStatus,
                        expectedServiceConfig,
                        expectedTimestamp);

        final var serializedServiceId = serializer.serialize(expectedServiceId);
        final var serializedServiceType = serializer.serialize(expectedServiceTypeEnum);
        final var serializedServiceEndPointIds =
                expectedServiceEndPointIds.stream()
                        .map(endPointId -> serializer.serialize(endPointId))
                        .collect(Collectors.toList());
        final var serializedServiceConstraints =
                expectedServiceConstraints.stream()
                        .map(constraint -> serializer.serialize(constraint))
                        .collect(Collectors.toList());
        final var serializedServiceStatus = serializer.serialize(expectedServiceStatus);
        final var serializedServiceConfig = serializer.serialize(expectedServiceConfig);
        final var serializedTimestamp = serializer.serialize(expectedTimestamp);

        final var serializedService =
                ContextOuterClass.Service.newBuilder()
                        .setServiceId(serializedServiceId)
                        .setServiceType(serializedServiceType)
                        .addAllServiceEndpointIds(serializedServiceEndPointIds)
                        .addAllServiceConstraints(serializedServiceConstraints)
                        .setServiceStatus(serializedServiceStatus)
                        .setServiceConfig(serializedServiceConfig)
                        .setTimestamp(serializedTimestamp)
                        .build();

        final var service = serializer.deserialize(serializedService);

        assertThat(service).usingRecursiveComparison().isEqualTo(expectedService);
    }

    private static Stream<Arguments> provideRuleState() {
        return Stream.of(
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_UNDEFINED, Policy.PolicyRuleStateEnum.POLICY_UNDEFINED),
                Arguments.of(PolicyRuleStateEnum.POLICY_FAILED, Policy.PolicyRuleStateEnum.POLICY_FAILED),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_INSERTED, Policy.PolicyRuleStateEnum.POLICY_INSERTED),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_VALIDATED, Policy.PolicyRuleStateEnum.POLICY_VALIDATED),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_PROVISIONED, Policy.PolicyRuleStateEnum.POLICY_PROVISIONED),
                Arguments.of(PolicyRuleStateEnum.POLICY_ACTIVE, Policy.PolicyRuleStateEnum.POLICY_ACTIVE),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_ENFORCED, Policy.PolicyRuleStateEnum.POLICY_ENFORCED),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_INEFFECTIVE, Policy.PolicyRuleStateEnum.POLICY_INEFFECTIVE),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_EFFECTIVE, Policy.PolicyRuleStateEnum.POLICY_EFFECTIVE),
                Arguments.of(PolicyRuleStateEnum.POLICY_UPDATED, Policy.PolicyRuleStateEnum.POLICY_UPDATED),
                Arguments.of(
                        PolicyRuleStateEnum.POLICY_REMOVED, Policy.PolicyRuleStateEnum.POLICY_REMOVED));
    }

    @ParameterizedTest
    @MethodSource("provideRuleState")
    void shouldSerializeRuleState(
            PolicyRuleStateEnum ruleState, Policy.PolicyRuleStateEnum expectedSerializedType) {
        final var serializedRuleState = serializer.serialize(ruleState);

        assertThat(serializedRuleState.getNumber()).isEqualTo(expectedSerializedType.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideRuleState")
    void shouldDeserializeRuleState(
            PolicyRuleStateEnum expectedRuleState, Policy.PolicyRuleStateEnum serializedRuleState) {
        final var ruleState = serializer.deserialize(serializedRuleState);

        assertThat(ruleState).isEqualTo(expectedRuleState);
    }

    @Test
    void shouldSerializePolicyRuleState() {
        final var expectedRuleState = PolicyRuleStateEnum.POLICY_ACTIVE;
        final var policyRuleState = new PolicyRuleState(expectedRuleState, "");

        final var serializedRuleState = serializer.serialize(expectedRuleState);

        final var expectedPolicyRuleState =
                Policy.PolicyRuleState.newBuilder().setPolicyRuleState(serializedRuleState).build();

        final var serializedPolicyRuleState = serializer.serialize(policyRuleState);

        assertThat(serializedPolicyRuleState)
                .usingRecursiveComparison()
                .isEqualTo(expectedPolicyRuleState);
    }

    @Test
    void shouldDeserializePolicyRuleState() {
        final var expectedRuleState = PolicyRuleStateEnum.POLICY_ENFORCED;
        final var expectedPolicyRuleState = new PolicyRuleState(expectedRuleState, "");

        final var serializedPolicyRuleState = serializer.serialize(expectedPolicyRuleState);

        final var policyRuleState = serializer.deserialize(serializedPolicyRuleState);

        assertThat(policyRuleState).usingRecursiveComparison().isEqualTo(expectedPolicyRuleState);
    }

    private static Stream<Arguments> providePolicyRuleActionEnum() {
        return Stream.of(
                Arguments.of(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_SET_DEVICE_STATUS,
                        PolicyAction.PolicyRuleActionEnum.POLICYRULE_ACTION_SET_DEVICE_STATUS),
                Arguments.of(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONFIGRULE,
                        PolicyAction.PolicyRuleActionEnum.POLICYRULE_ACTION_ADD_SERVICE_CONFIGRULE),
                Arguments.of(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT,
                        PolicyAction.PolicyRuleActionEnum.POLICYRULE_ACTION_ADD_SERVICE_CONSTRAINT),
                Arguments.of(
                        PolicyRuleActionEnum.POLICY_RULE_ACTION_NO_ACTION,
                        PolicyAction.PolicyRuleActionEnum.POLICYRULE_ACTION_NO_ACTION));
    }

    @ParameterizedTest
    @MethodSource("providePolicyRuleActionEnum")
    void shouldSerializePolicyRuleActionEnum(
            PolicyRuleActionEnum policyRuleActionEnum,
            PolicyAction.PolicyRuleActionEnum expectedPolicyRuleActionEnum) {
        final var serializedPolicyRuleActionEnum = serializer.serialize(policyRuleActionEnum);

        assertThat(serializedPolicyRuleActionEnum).isEqualTo(expectedPolicyRuleActionEnum);
    }

    @ParameterizedTest
    @MethodSource("providePolicyRuleActionEnum")
    void shouldDeserializePolicyRuleActionEnum(
            PolicyRuleActionEnum expectedPolicyRuleActionEnum,
            PolicyAction.PolicyRuleActionEnum serializedPolicyRuleActionEnum) {
        final var policyRuleActionEnum = serializer.deserialize(serializedPolicyRuleActionEnum);

        assertThat(policyRuleActionEnum).isEqualTo(expectedPolicyRuleActionEnum);
    }

    @Test
    void shouldSerializePolicyRuleAction() {
        final var expectedPolicyRuleActionEnum =
                PolicyRuleActionEnum.POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT;
        final var expectedPolicyRuleActionConfigs =
                List.of(new PolicyRuleActionConfig("parameter1", "parameter2"));
        final var policyRuleAction =
                new PolicyRuleAction(expectedPolicyRuleActionEnum, expectedPolicyRuleActionConfigs);

        final var serializedPolicyRuleActionEnum = serializer.serialize(expectedPolicyRuleActionEnum);
        final var serializedPolicyRuleActionConfigList =
                expectedPolicyRuleActionConfigs.stream()
                        .map(id -> serializer.serialize(id))
                        .collect(Collectors.toList());

        final var expectedPolicyRuleAction =
                PolicyAction.PolicyRuleAction.newBuilder()
                        .setAction(serializedPolicyRuleActionEnum)
                        .addAllActionConfig(serializedPolicyRuleActionConfigList)
                        .build();

        final var serializedPolicyRuleAction = serializer.serialize(policyRuleAction);

        assertThat(serializedPolicyRuleAction)
                .usingRecursiveComparison()
                .isEqualTo(expectedPolicyRuleAction);
    }

    @Test
    void shouldDeserializePolicyRuleAction() {
        final var expectedPolicyRuleActionEnum = PolicyRuleActionEnum.POLICY_RULE_ACTION_NO_ACTION;
        final var expectedPolicyRuleActionConfigs =
                List.of(new PolicyRuleActionConfig("parameter1", "parameter2"));
        final var expectedPolicyRuleAction =
                new PolicyRuleAction(expectedPolicyRuleActionEnum, expectedPolicyRuleActionConfigs);

        final var serializedPolicyRuleAction = serializer.serialize(expectedPolicyRuleAction);

        final var policyRuleAction = serializer.deserialize(serializedPolicyRuleAction);

        assertThat(policyRuleAction).usingRecursiveComparison().isEqualTo(expectedPolicyRuleAction);
    }

    @Test
    void shouldSerializePolicyRuleBasic() {
        final var policyRuleBasic = createPolicyRuleBasic();

        final var expectedPolicyRuleId = policyRuleBasic.getPolicyRuleId();
        final var expectedPolicyRuleState = policyRuleBasic.getPolicyRuleState();
        final var expectedPolicyRuleActions = policyRuleBasic.getPolicyRuleActions();
        final var expectedPolicyRuleKpis = policyRuleBasic.getPolicyRuleKPIs();
        final var expectedPriority = policyRuleBasic.getPolicyRulePriority();

        final var serializedPolicyRuleId = serializer.serializePolicyRuleId(expectedPolicyRuleId);
        final var serializedPolicyRuleState = serializer.serialize(expectedPolicyRuleState);

        final var serializedPolicyRuleActions =
                expectedPolicyRuleActions.stream()
                        .map(policyRuleAction -> serializer.serialize(policyRuleAction))
                        .collect(Collectors.toList());

        final var serializedPolicyRuleKpis =
                expectedPolicyRuleKpis.stream()
                        .map(policyRuleKpiId -> serializer.serializePolicyRuleKpiId(policyRuleKpiId))
                        .collect(Collectors.toList());

        final var expectedPolicyRuleBasic =
                Policy.PolicyRuleBasic.newBuilder()
                        .setPolicyRuleId(serializedPolicyRuleId)
                        .setPolicyRulePriority(expectedPriority)
                        .setPolicyRuleState(serializedPolicyRuleState)
                        .addAllActionList(serializedPolicyRuleActions)
                        .addAllPolicyRuleKpiList(serializedPolicyRuleKpis)
                        .build();

        final var serializedPolicyRuleBasic = serializer.serialize(policyRuleBasic);

        assertThat(serializedPolicyRuleBasic)
                .usingRecursiveComparison()
                .isEqualTo(expectedPolicyRuleBasic);
    }

    @Test
    void shouldDeserializePolicyRuleBasic() {
        final var expectedPolicyRuleBasic = createPolicyRuleBasic();

        final var expectedPolicyRuleId = expectedPolicyRuleBasic.getPolicyRuleId();
        final var expectedPolicyRuleState = expectedPolicyRuleBasic.getPolicyRuleState();
        final var expectedPriority = expectedPolicyRuleBasic.getPolicyRulePriority();
        final var expectedPolicyRuleActions = expectedPolicyRuleBasic.getPolicyRuleActions();
        final var expectedPolicyRuleKpis = expectedPolicyRuleBasic.getPolicyRuleKPIs();

        final var serializedPolicyRuleId = serializer.serializePolicyRuleId(expectedPolicyRuleId);
        final var serializedPolicyRuleState = serializer.serialize(expectedPolicyRuleState);

        final var serializedPolicyRuleActions =
                expectedPolicyRuleActions.stream()
                        .map(policyRuleAction -> serializer.serialize(policyRuleAction))
                        .collect(Collectors.toList());

        final var serializedPolicyRuleKpis =
                expectedPolicyRuleKpis.stream()
                        .map(policyRuleKpiId -> serializer.serializePolicyRuleKpiId(policyRuleKpiId))
                        .collect(Collectors.toList());

        final var serializedPolicyRuleBasic =
                Policy.PolicyRuleBasic.newBuilder()
                        .setPolicyRuleId(serializedPolicyRuleId)
                        .setPolicyRuleState(serializedPolicyRuleState)
                        .setPolicyRulePriority(expectedPriority)
                        .addAllActionList(serializedPolicyRuleActions)
                        .addAllPolicyRuleKpiList(serializedPolicyRuleKpis)
                        .build();

        final var policyRuleBasic = serializer.deserialize(serializedPolicyRuleBasic);

        assertThat(policyRuleBasic).usingRecursiveComparison().isEqualTo(expectedPolicyRuleBasic);
    }

    @Test
    void shouldSerializePolicyRuleService() {
        final var policyRuleBasic = createPolicyRuleBasic();
        final var serviceId = new ServiceId("contextId", "serviceId");
        final var deviceIds = List.of("deviceId1", "deviceId2");

        final var policyRuleService = new PolicyRuleService(policyRuleBasic, serviceId, deviceIds);

        final var serializedPolicyRuleBasic = serializer.serialize(policyRuleBasic);
        final var serializedPolicyRuleServiceId = serializer.serialize(serviceId);
        final var serializedPolicyRuleDeviceIds =
                deviceIds.stream()
                        .map(deviceId -> serializer.serializeDeviceId(deviceId))
                        .collect(Collectors.toList());

        final var expectedPolicyRuleService =
                Policy.PolicyRuleService.newBuilder()
                        .setPolicyRuleBasic(serializedPolicyRuleBasic)
                        .setServiceId(serializedPolicyRuleServiceId)
                        .addAllDeviceList(serializedPolicyRuleDeviceIds)
                        .build();

        final var serializedPolicyRuleService = serializer.serialize(policyRuleService);

        assertThat(serializedPolicyRuleService)
                .usingRecursiveComparison()
                .isEqualTo(expectedPolicyRuleService);
    }

    @Test
    void shouldDeserializePolicyRuleService() {
        final var expectedPolicyRuleBasic = createPolicyRuleBasic();
        final var expectedServiceId = new ServiceId("contextId", "serviceId");
        final var expectedDeviceIds = List.of("deviceId1", "deviceId2");
        final var expectedPolicyRuleService =
                new PolicyRuleService(expectedPolicyRuleBasic, expectedServiceId, expectedDeviceIds);

        final var serializedPolicyRuleBasic = serializer.serialize(expectedPolicyRuleBasic);
        final var serializedPolicyRuleServiceId = serializer.serialize(expectedServiceId);
        final var serializedPolicyRuleDeviceIds =
                expectedDeviceIds.stream()
                        .map(deviceId -> serializer.serializeDeviceId(deviceId))
                        .collect(Collectors.toList());

        final var serializedPolicyRuleService =
                Policy.PolicyRuleService.newBuilder()
                        .setPolicyRuleBasic(serializedPolicyRuleBasic)
                        .setServiceId(serializedPolicyRuleServiceId)
                        .addAllDeviceList(serializedPolicyRuleDeviceIds)
                        .build();

        final var policyRuleService = serializer.deserialize(serializedPolicyRuleService);

        assertThat(policyRuleService).usingRecursiveComparison().isEqualTo(expectedPolicyRuleService);
    }

    @Test
    void shouldSerializePolicyRuleDevice() {
        final var policyRuleBasic = createPolicyRuleBasic();
        final var deviceIds = List.of("deviceId1", "deviceId2");

        final var policyRuleDevice = new PolicyRuleDevice(policyRuleBasic, deviceIds);

        final var serializedPolicyRuleBasic = serializer.serialize(policyRuleBasic);
        final var serializedPolicyRuleDeviceIds =
                deviceIds.stream()
                        .map(deviceId -> serializer.serializeDeviceId(deviceId))
                        .collect(Collectors.toList());

        final var expectedPolicyRuleDevice =
                Policy.PolicyRuleDevice.newBuilder()
                        .setPolicyRuleBasic(serializedPolicyRuleBasic)
                        .addAllDeviceList(serializedPolicyRuleDeviceIds)
                        .build();

        final var serializedPolicyRuleDevice = serializer.serialize(policyRuleDevice);

        assertThat(serializedPolicyRuleDevice)
                .usingRecursiveComparison()
                .isEqualTo(expectedPolicyRuleDevice);
    }

    @Test
    void shouldDeserializePolicyRuleDevice() {
        final var expectedPolicyRuleBasic = createPolicyRuleBasic();
        final var expectedDeviceIds = List.of("deviceId1", "deviceId2");
        final var expectedPolicyRuleDevice =
                new PolicyRuleDevice(expectedPolicyRuleBasic, expectedDeviceIds);

        final var serializedPolicyRuleBasic = serializer.serialize(expectedPolicyRuleBasic);
        final var serializedPolicyRuleDeviceIds =
                expectedDeviceIds.stream()
                        .map(deviceId -> serializer.serializeDeviceId(deviceId))
                        .collect(Collectors.toList());

        final var serializedPolicyRuleDevice =
                Policy.PolicyRuleDevice.newBuilder()
                        .setPolicyRuleBasic(serializedPolicyRuleBasic)
                        .addAllDeviceList(
                                (Iterable<? extends context.ContextOuterClass.DeviceId>)
                                        serializedPolicyRuleDeviceIds)
                        .build();

        final var policyRuleDevice = serializer.deserialize(serializedPolicyRuleDevice);

        assertThat(policyRuleDevice).usingRecursiveComparison().isEqualTo(expectedPolicyRuleDevice);
    }

    @Test
    void shouldSerializeDeviceConfig() {
        final var expectedConfigRuleCustomA =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyA")
                        .setResourceValue("resourceValueA")
                        .build();

        final var configRuleCustomA = new ConfigRuleCustom("resourceKeyA", "resourceValueA");

        final var expectedConfigRuleCustomB =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyB")
                        .setResourceValue("resourceValueB")
                        .build();

        final var configRuleCustomB = new ConfigRuleCustom("resourceKeyB", "resourceValueB");

        final var expectedConfigRuleA =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setCustom(expectedConfigRuleCustomA)
                        .build();
        final var expectedConfigRuleB =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_DELETE)
                        .setCustom(expectedConfigRuleCustomB)
                        .build();

        final var expectedDeviceConfig =
                ContextOuterClass.DeviceConfig.newBuilder()
                        .addAllConfigRules(List.of(expectedConfigRuleA, expectedConfigRuleB))
                        .build();

        final var configRuleTypeA = new ConfigRuleTypeCustom(configRuleCustomA);
        final var configRuleTypeB = new ConfigRuleTypeCustom(configRuleCustomB);

        final var configRuleA = new ConfigRule(ConfigActionEnum.SET, configRuleTypeA);
        final var configRuleB = new ConfigRule(ConfigActionEnum.DELETE, configRuleTypeB);

        final var deviceConfig = new DeviceConfig(List.of(configRuleA, configRuleB));
        final var serializedDeviceConfig = serializer.serialize(deviceConfig);

        assertThat(serializedDeviceConfig).isEqualTo(expectedDeviceConfig);
    }

    @Test
    void shouldDeserializeDeviceConfig() {
        final var expectedConfigRuleCustomA = new ConfigRuleCustom("resourceKeyA", "resourceValueA");
        final var expectedConfigRuleCustomB = new ConfigRuleCustom("resourceKeyB", "resourceValueB");

        final var expectedConfigRuleTypeA = new ConfigRuleTypeCustom(expectedConfigRuleCustomA);
        final var expectedConfigRuleTypeB = new ConfigRuleTypeCustom(expectedConfigRuleCustomB);

        final var expectedConfigRuleA = new ConfigRule(ConfigActionEnum.SET, expectedConfigRuleTypeA);
        final var expectedConfigRuleB =
                new ConfigRule(ConfigActionEnum.DELETE, expectedConfigRuleTypeB);

        final var expectedDeviceConfig =
                new DeviceConfig(List.of(expectedConfigRuleA, expectedConfigRuleB));

        final var configRuleCustomA =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyA")
                        .setResourceValue("resourceValueA")
                        .build();

        final var configRuleCustomB =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyB")
                        .setResourceValue("resourceValueB")
                        .build();

        final var configRuleA =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setCustom(configRuleCustomA)
                        .build();
        final var configRuleB =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_DELETE)
                        .setCustom(configRuleCustomB)
                        .build();
        final var serializedDeviceConfig =
                ContextOuterClass.DeviceConfig.newBuilder()
                        .addAllConfigRules(List.of(configRuleA, configRuleB))
                        .build();
        final var deviceConfig = serializer.deserialize(serializedDeviceConfig);

        assertThat(deviceConfig).usingRecursiveComparison().isEqualTo(expectedDeviceConfig);
    }

    private static Stream<Arguments> provideOperationalStatusEnum() {
        return Stream.of(
                Arguments.of(
                        DeviceOperationalStatus.ENABLED,
                        DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_ENABLED),
                Arguments.of(
                        DeviceOperationalStatus.DISABLED,
                        DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_DISABLED),
                Arguments.of(
                        DeviceOperationalStatus.UNDEFINED,
                        DeviceOperationalStatusEnum.DEVICEOPERATIONALSTATUS_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideOperationalStatusEnum")
    void shouldSerializeOperationalStatusEnum(
            DeviceOperationalStatus opStatus,
            ContextOuterClass.DeviceOperationalStatusEnum expectedOpStatus) {
        final var serializedOpStatus = serializer.serialize(opStatus);
        assertThat(serializedOpStatus.getNumber()).isEqualTo(expectedOpStatus.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideOperationalStatusEnum")
    void shouldDeserializeOperationalStatusEnum(
            DeviceOperationalStatus expectedOpStatus,
            ContextOuterClass.DeviceOperationalStatusEnum serializedOpStatus) {
        final var operationalStatus = serializer.deserialize(serializedOpStatus);
        assertThat(operationalStatus).isEqualTo(expectedOpStatus);
    }

    private static Stream<Arguments> provideDeviceDriverEnum() {
        return Stream.of(
                Arguments.of(
                        DeviceDriverEnum.OPENCONFIG,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_OPENCONFIG),
                Arguments.of(
                        DeviceDriverEnum.TRANSPORT_API,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_TRANSPORT_API),
                Arguments.of(DeviceDriverEnum.P4, ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_P4),
                Arguments.of(
                        DeviceDriverEnum.IETF_NETWORK_TOPOLOGY,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_IETF_NETWORK_TOPOLOGY),
                Arguments.of(
                        DeviceDriverEnum.ONF_TR_532,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_ONF_TR_532),
                Arguments.of(DeviceDriverEnum.XR, ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_XR),
                Arguments.of(
                        DeviceDriverEnum.IETF_L2VPN,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_IETF_L2VPN),
                Arguments.of(
                        DeviceDriverEnum.GNMI_OPENCONFIG,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_GNMI_OPENCONFIG),
                Arguments.of(
                        DeviceDriverEnum.OPTICAL_TFS,
                        ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_OPTICAL_TFS),
                Arguments.of(
                        DeviceDriverEnum.IETF_ACTN, ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_IETF_ACTN),
                Arguments.of(
                        DeviceDriverEnum.UNDEFINED, ContextOuterClass.DeviceDriverEnum.DEVICEDRIVER_UNDEFINED));
    }

    @ParameterizedTest
    @MethodSource("provideDeviceDriverEnum")
    void shouldSerializeDeviceDriverEnum(
            DeviceDriverEnum deviceDriverEnum,
            ContextOuterClass.DeviceDriverEnum expectedDeviceDriverEnum) {
        final var serializedDeviceDriverEnum = serializer.serialize(deviceDriverEnum);

        assertThat(serializedDeviceDriverEnum.getNumber())
                .isEqualTo(expectedDeviceDriverEnum.getNumber());
    }

    @ParameterizedTest
    @MethodSource("provideDeviceDriverEnum")
    void shouldDeserializeDeviceDriverEnum(
            DeviceDriverEnum expectedDeviceDriverEnum,
            ContextOuterClass.DeviceDriverEnum serializedDeviceDriverEnum) {
        final var deviceDriverEnum = serializer.deserialize(serializedDeviceDriverEnum);

        assertThat(deviceDriverEnum).isEqualTo(expectedDeviceDriverEnum);
    }

    @Test
    void shouldSerializeEndPoint() {
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

        final var serializedEndPointId = serializer.serialize(endPointId);
        final var serializedKpiSampleTypes =
                kpiSampleTypes.stream()
                        .map(kpiSampleType -> serializer.serialize(kpiSampleType))
                        .collect(Collectors.toList());
        final var serializedLocation = serializer.serialize(location);

        final var expectedEndPoint =
                ContextOuterClass.EndPoint.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setEndpointType(endPointType)
                        .addAllKpiSampleTypes(serializedKpiSampleTypes)
                        .setEndpointLocation(serializedLocation)
                        .build();

        final var serializedEndPoint = serializer.serialize(endPoint);

        assertThat(serializedEndPoint).usingRecursiveComparison().isEqualTo(expectedEndPoint);
    }

    @Test
    void shouldDeserializeEndPoint() {
        final var expectedTopologyId = new TopologyId("contextId", "id");
        final var expectedDeviceId = "expectedDeviceId";
        final var expectedId = "expectedId";
        final var expectedEndPointId = new EndPointId(expectedTopologyId, expectedDeviceId, expectedId);
        final var expectedEndPointType = "expectedEndPointType";
        final var expectedKpiSampleTypes =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);

        final var expectedLocationTypeRegion = new LocationTypeRegion("ATH");
        final var expectedLocation = new Location(expectedLocationTypeRegion);

        final var expectedEndPoint =
                new EndPointBuilder(expectedEndPointId, expectedEndPointType, expectedKpiSampleTypes)
                        .location(expectedLocation)
                        .build();

        final var serializedEndPointId = serializer.serialize(expectedEndPointId);
        final var serializedKpiSampleTypes =
                expectedKpiSampleTypes.stream()
                        .map(kpiSampleType -> serializer.serialize(kpiSampleType))
                        .collect(Collectors.toList());
        final var serializedLocation = serializer.serialize(expectedLocation);

        final var serializedEndPoint =
                ContextOuterClass.EndPoint.newBuilder()
                        .setEndpointId(serializedEndPointId)
                        .setEndpointType(expectedEndPointType)
                        .addAllKpiSampleTypes(serializedKpiSampleTypes)
                        .setEndpointLocation(serializedLocation)
                        .build();

        final var endPoint = serializer.deserialize(serializedEndPoint);

        assertThat(endPoint).usingRecursiveComparison().isEqualTo(expectedEndPoint);
    }

    @Test
    void shouldSerializeDevice() {
        final var expectedConfigRuleCustomA =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyA")
                        .setResourceValue("resourceValueA")
                        .build();
        final var configRuleCustomA = new ConfigRuleCustom("resourceKeyA", "resourceValueA");

        final var expectedConfigRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_SET)
                        .setCustom(expectedConfigRuleCustomA)
                        .build();

        final var configRuleTypeA = new ConfigRuleTypeCustom(configRuleCustomA);
        final var deviceConfig =
                new DeviceConfig(List.of(new ConfigRule(ConfigActionEnum.SET, configRuleTypeA)));

        final var deviceDrivers = List.of(DeviceDriverEnum.IETF_NETWORK_TOPOLOGY, DeviceDriverEnum.P4);

        final var expectedTopologyIdA = new TopologyId("contextIdA", "idA");
        final var expectedDeviceIdA = "expectedDeviceIdA";
        final var expectedIdA = "expectedIdA";
        final var endPointIdA = new EndPointId(expectedTopologyIdA, expectedDeviceIdA, expectedIdA);

        final var endPointTypeA = "endPointTypeA";
        final var kpiSampleTypesA =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);
        final var locationTypeRegionA = new LocationTypeRegion("ATH");
        final var locationA = new Location(locationTypeRegionA);
        final var endPointA =
                new EndPointBuilder(endPointIdA, endPointTypeA, kpiSampleTypesA)
                        .location(locationA)
                        .build();

        final var expectedTopologyIdB = new TopologyId("contextIdB", "idB");
        final var expectedDeviceIdB = "expectedDeviceIdB";
        final var expectedIdB = "expectedIdB";
        final var endPointIdB = new EndPointId(expectedTopologyIdB, expectedDeviceIdB, expectedIdB);

        final var endPointTypeB = "endPointTypeB";
        final var kpiSampleTypesB =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);
        final var locationTypeRegionB = new LocationTypeRegion("ATH");
        final var locationB = new Location(locationTypeRegionB);
        final var endPointB =
                new EndPointBuilder(endPointIdB, endPointTypeB, kpiSampleTypesB)
                        .location(locationB)
                        .build();

        final var endPoints = List.of(endPointA, endPointB);

        final var expectedDeviceConfig =
                ContextOuterClass.DeviceConfig.newBuilder().addConfigRules(expectedConfigRule).build();

        final var serializedDeviceId = serializer.serializeDeviceId("deviceId");
        final var serializedDrivers =
                deviceDrivers.stream()
                        .map(deviceDriverEnum -> serializer.serialize(deviceDriverEnum))
                        .collect(Collectors.toList());

        final var serializedEndPoints =
                endPoints.stream()
                        .map(endPoint -> serializer.serialize(endPoint))
                        .collect(Collectors.toList());

        final var deviceBuilder = ContextOuterClass.Device.newBuilder();

        deviceBuilder.setDeviceId(serializedDeviceId);
        deviceBuilder.setDeviceType("deviceType");
        deviceBuilder.setDeviceConfig(expectedDeviceConfig);
        deviceBuilder.setDeviceOperationalStatus(serializer.serialize(DeviceOperationalStatus.ENABLED));
        deviceBuilder.addAllDeviceDrivers(serializedDrivers);
        deviceBuilder.addAllDeviceEndpoints(serializedEndPoints);

        final var expectedDevice = deviceBuilder.build();

        final var device =
                new Device(
                        "deviceId",
                        "deviceType",
                        deviceConfig,
                        DeviceOperationalStatus.ENABLED,
                        deviceDrivers,
                        endPoints);
        final var serializedDevice = serializer.serialize(device);

        assertThat(serializedDevice).isEqualTo(expectedDevice);
    }

    @Test
    void shouldDeserializeDevice() {
        final var configRuleCustom = new ConfigRuleCustom("resourceKeyA", "resourceValueA");
        final var expectedConfigRuleCustom =
                ContextOuterClass.ConfigRule_Custom.newBuilder()
                        .setResourceKey("resourceKeyA")
                        .setResourceValue("resourceValueA")
                        .build();
        final var configRuleType = new ConfigRuleTypeCustom(configRuleCustom);

        final var expectedConfig =
                new DeviceConfig(List.of(new ConfigRule(ConfigActionEnum.DELETE, configRuleType)));

        final var deviceDrivers = List.of(DeviceDriverEnum.IETF_NETWORK_TOPOLOGY, DeviceDriverEnum.P4);

        final var expectedTopologyIdA = new TopologyId("contextIdA", "idA");
        final var expectedDeviceIdA = "expectedDeviceIdA";
        final var expectedIdA = "expectedIdA";
        final var endPointIdA = new EndPointId(expectedTopologyIdA, expectedDeviceIdA, expectedIdA);

        final var endPointTypeA = "endPointTypeA";
        final var kpiSampleTypesA =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);
        final var locationTypeRegionA = new LocationTypeRegion("ATH");
        final var locationA = new Location(locationTypeRegionA);
        final var endPointA =
                new EndPointBuilder(endPointIdA, endPointTypeA, kpiSampleTypesA)
                        .location(locationA)
                        .build();

        final var expectedTopologyIdB = new TopologyId("contextIdB", "idB");
        final var expectedDeviceIdB = "expectedDeviceIdB";
        final var expectedIdB = "expectedIdB";
        final var endPointIdB = new EndPointId(expectedTopologyIdB, expectedDeviceIdB, expectedIdB);

        final var endPointTypeB = "endPointTypeB";
        final var kpiSampleTypesB =
                List.of(KpiSampleType.BYTES_RECEIVED, KpiSampleType.BYTES_TRANSMITTED);
        final var locationTypeRegionB = new LocationTypeRegion("ATH");
        final var locationB = new Location(locationTypeRegionB);
        final var endPointB =
                new EndPointBuilder(endPointIdB, endPointTypeB, kpiSampleTypesB)
                        .location(locationB)
                        .build();

        final var endPoints = List.of(endPointA, endPointB);

        final var expectedDevice =
                new Device(
                        "deviceId",
                        "deviceType",
                        expectedConfig,
                        DeviceOperationalStatus.ENABLED,
                        deviceDrivers,
                        endPoints);

        final var configRule =
                ContextOuterClass.ConfigRule.newBuilder()
                        .setAction(ContextOuterClass.ConfigActionEnum.CONFIGACTION_DELETE)
                        .setCustom(expectedConfigRuleCustom)
                        .build();
        final var deviceConfig =
                ContextOuterClass.DeviceConfig.newBuilder().addConfigRules(configRule).build();

        final var serializedDeviceId = serializer.serializeDeviceId("deviceId");
        final var serializedDeviceOperationalStatus =
                serializer.serialize(DeviceOperationalStatus.ENABLED);

        final var serializedDrivers =
                deviceDrivers.stream()
                        .map(deviceDriverEnum -> serializer.serialize(deviceDriverEnum))
                        .collect(Collectors.toList());

        final var serializedEndPoints =
                endPoints.stream()
                        .map(endPoint -> serializer.serialize(endPoint))
                        .collect(Collectors.toList());

        final var deviceBuilder = ContextOuterClass.Device.newBuilder();
        deviceBuilder.setDeviceId(serializedDeviceId);
        deviceBuilder.setDeviceType("deviceType");
        deviceBuilder.setDeviceConfig(deviceConfig);
        deviceBuilder.setDeviceOperationalStatus(serializedDeviceOperationalStatus);
        deviceBuilder.addAllDeviceDrivers(serializedDrivers);
        deviceBuilder.addAllDeviceEndpoints(serializedEndPoints);

        final var serializedDevice = deviceBuilder.build();
        final var device = serializer.deserialize(serializedDevice);

        assertThat(device).usingRecursiveComparison().isEqualTo(expectedDevice);
    }

    @Test
    void shouldSerializeEmpty() {
        final var empty = new Empty();
        final var expectedEmpty = ContextOuterClass.Empty.newBuilder().build();

        final var serializeEmpty = serializer.serializeEmpty(empty);

        assertThat(serializeEmpty).isEqualTo(expectedEmpty);
    }

    @Test
    void shouldDeserializeEmpty() {
        final var expectedEmpty = new Empty();

        final var serializedEmpty = serializer.serializeEmpty(expectedEmpty);

        final var empty = serializer.deserializeEmpty(serializedEmpty);

        assertThat(empty).usingRecursiveComparison().isEqualTo(expectedEmpty);
    }

    @Test
    void shouldSerializeUuid() {
        final var expectedUuid = "uuid";

        final var serializeUuid = serializer.serializeUuid(expectedUuid);

        assertThat(serializeUuid.getUuid()).isEqualTo(expectedUuid);
    }

    @Test
    void shouldDeserializeUuid() {
        final var expectedUuid = "uuid";

        final var uuid = serializer.deserialize(Uuid.newBuilder().setUuid(expectedUuid).build());

        assertThat(uuid).isEqualTo(expectedUuid);
    }
}
