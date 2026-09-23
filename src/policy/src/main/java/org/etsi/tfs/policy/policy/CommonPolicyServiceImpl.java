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

package org.etsi.tfs.policy.policy;

import static org.etsi.tfs.policy.common.ApplicationProperties.ACTIVE_POLICYRULE_STATE;
import static org.etsi.tfs.policy.common.ApplicationProperties.ENFORCED_POLICYRULE_STATE;
import static org.etsi.tfs.policy.common.ApplicationProperties.INVALID_MESSAGE;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
// import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
// import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import org.etsi.tfs.policy.context.ContextService;
import org.etsi.tfs.policy.context.model.ConfigActionEnum;
import org.etsi.tfs.policy.context.model.ConfigRule;
import org.etsi.tfs.policy.context.model.ConfigRuleCustom;
import org.etsi.tfs.policy.context.model.ConfigRuleTypeCustom;
import org.etsi.tfs.policy.context.model.Constraint;
import org.etsi.tfs.policy.context.model.ConstraintCustom;
import org.etsi.tfs.policy.context.model.ConstraintTypeCustom;
import org.etsi.tfs.policy.context.model.ServiceConfig;
import org.etsi.tfs.policy.device.DeviceService;
import org.etsi.tfs.policy.policy.model.PolicyRule;
import org.etsi.tfs.policy.policy.model.PolicyRuleAction;
import org.etsi.tfs.policy.policy.model.PolicyRuleActionConfig;
import org.etsi.tfs.policy.policy.model.PolicyRuleDevice;
import org.etsi.tfs.policy.policy.model.PolicyRuleService;
import org.etsi.tfs.policy.policy.model.PolicyRuleState;
import org.etsi.tfs.policy.policy.model.PolicyRuleStateEnum;
import org.etsi.tfs.policy.policy.model.PolicyRuleTypeDevice;
import org.etsi.tfs.policy.policy.model.PolicyRuleTypeService;
import org.etsi.tfs.policy.service.ServiceService;
import org.jboss.logging.Logger;

@ApplicationScoped
public class CommonPolicyServiceImpl {

    private static final Logger LOGGER = Logger.getLogger(CommonPolicyServiceImpl.class);

    @Inject private ContextService contextService;
    @Inject private ServiceService serviceService;
    @Inject private DeviceService deviceService;

    // private static final int POLICY_EVALUATION_TIMEOUT = 5;
    // private static final int ACCEPTABLE_NUMBER_OF_ALARMS = 3;
    // private static final int MONITORING_WINDOW_IN_SECONDS = 5;

    // private static String gen() {
    //     Random r = new Random(System.currentTimeMillis());
    //     return String.valueOf((1 + r.nextInt(2)) * 10000 + r.nextInt(10000));
    // }

    // private static double getTimeStamp() {
    //     long now = Instant.now().getEpochSecond();
    //     return Long.valueOf(now).doubleValue();
    // }

    // ToDo: Find a better way to disregard alarms while reconfiguring path
    private ConcurrentHashMap<String, PolicyRuleService> activePolicyRuleServices =
            new ConcurrentHashMap<>();
    private ConcurrentHashMap<String, PolicyRuleDevice> activePolicyRuleDevices =
            new ConcurrentHashMap<>();
    private ConcurrentHashMap<String, PolicyRuleAction> activePolicyRuleActions =
            new ConcurrentHashMap<>();

    // Service-level rules
    public ConcurrentHashMap<String, PolicyRuleService> getActivePolicyRuleServices() {
        return activePolicyRuleServices;
    }

    public void addActivePolicyRuleService(
            String policyRuleKpiId, PolicyRuleService policyRuleService) {
        activePolicyRuleServices.put(policyRuleKpiId, policyRuleService);
    }

    public void removeActivePolicyRuleService(String policyRuleKpiId) {
        activePolicyRuleServices.remove(policyRuleKpiId);
    }

    public boolean hasActivePolicyRuleService(String policyRuleKpiId) {
        return activePolicyRuleServices.contains(policyRuleKpiId);
    }

    // Device-level rules
    public ConcurrentHashMap<String, PolicyRuleDevice> getActivePolicyRuleDevices() {
        return activePolicyRuleDevices;
    }

    public void addActivePolicyRuleDevice(String policyRuleKpiId, PolicyRuleDevice policyRuleDevice) {
        activePolicyRuleDevices.put(policyRuleKpiId, policyRuleDevice);
    }

    public void removeActivePolicyRuleDevice(String policyRuleKpiId) {
        activePolicyRuleDevices.remove(policyRuleKpiId);
    }

    public boolean hasActivePolicyRuleDevice(String policyRuleKpiId) {
        return activePolicyRuleDevices.contains(policyRuleKpiId);
    }

    // Rule actions
    public ConcurrentHashMap<String, PolicyRuleAction> getActivePolicyRuleActions() {
        return activePolicyRuleActions;
    }

    public void addActivePolicyRuleAction(String policyRuleKpiId, PolicyRuleAction policyRuleAction) {
        activePolicyRuleActions.put(policyRuleKpiId, policyRuleAction);
    }

    public void removeActivePolicyRuleAction(String policyRuleKpiId) {
        activePolicyRuleActions.remove(policyRuleKpiId);
    }

    public boolean hasActivePolicyRuleAction(String policyRuleKpiId) {
        return activePolicyRuleActions.contains(policyRuleKpiId);
    }

    public void applyActionServiceBasedOnKpiId(String policyRuleKpiId) {
        LOGGER.infof("Apply Policy action for service with KPI ID: %s", policyRuleKpiId);
        if (!activePolicyRuleServices.containsKey(policyRuleKpiId)) {
            LOGGER.errorf("No Policy for KPI ID %s", policyRuleKpiId);
            return;
        }

        // Do not re-apply action
        if (hasActivePolicyRuleAction(policyRuleKpiId)) {
            LOGGER.warnf("Action already applied for KPI ID %s", policyRuleKpiId);
            return;
        }

        PolicyRuleService policyRuleService = activePolicyRuleServices.get(policyRuleKpiId);
        PolicyRuleAction policyRuleAction =
                policyRuleService.getPolicyRuleBasic().getPolicyRuleActions().get(0);

        setPolicyRuleServiceToContext(policyRuleService, ACTIVE_POLICYRULE_STATE);

        boolean applied = true;
        switch (policyRuleAction.getPolicyRuleActionEnum()) {
            case POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT:
                {
                    LOGGER.infof("Policy for KPI %s with action: Add Service Constraint", policyRuleKpiId);
                    addServiceConstraint(policyRuleService, policyRuleAction);
                    break;
                }
            case POLICY_RULE_ACTION_ADD_SERVICE_CONFIGRULE:
                {
                    LOGGER.infof("Policy for KPI %s with action: Add Service ConfigRule", policyRuleKpiId);
                    addServiceConfigRule(policyRuleService, policyRuleAction);
                    break;
                }
            case POLICY_RULE_ACTION_RECALCULATE_PATH:
                {
                    LOGGER.infof("Policy for KPI %s with action: Recalculate service path", policyRuleKpiId);
                    callRecalculatePathRPC(policyRuleService, policyRuleAction);
                    break;
                }
            case POLICY_RULE_ACTION_CALL_SERVICE_RPC:
                {
                    LOGGER.infof("Policy for KPI %s with action: Update service", policyRuleKpiId);
                    callUpdateServiceRpc(policyRuleService, policyRuleAction);
                    break;
                }
            default:
                {
                    applied = false;
                    LOGGER.errorf(INVALID_MESSAGE, policyRuleAction.getPolicyRuleActionEnum());
                    break;
                }
        }

        if (applied) addActivePolicyRuleAction(policyRuleKpiId, policyRuleAction);
    }

    public void applyActionService(String policyRuleKpiId) {
        PolicyRuleService policyRuleService = activePolicyRuleServices.get(policyRuleKpiId);

        // Do not re-apply action
        if (hasActivePolicyRuleAction(policyRuleKpiId)) {
            LOGGER.warnf("Action already applied for KPI ID %s", policyRuleKpiId);
            return;
        }

        PolicyRuleAction policyRuleAction =
                policyRuleService.getPolicyRuleBasic().getPolicyRuleActions().get(0);

        setPolicyRuleServiceToContext(policyRuleService, ACTIVE_POLICYRULE_STATE);

        boolean applied = true;
        switch (policyRuleAction.getPolicyRuleActionEnum()) {
            case POLICY_RULE_ACTION_ADD_SERVICE_CONSTRAINT:
                {
                    LOGGER.infof("Policy with action: Add Service Constraint");
                    addServiceConstraint(policyRuleService, policyRuleAction);
                    break;
                }
            case POLICY_RULE_ACTION_ADD_SERVICE_CONFIGRULE:
                {
                    LOGGER.infof("Policy with action: Add Service ConfigRule");
                    addServiceConfigRule(policyRuleService, policyRuleAction);
                    break;
                }
            case POLICY_RULE_ACTION_RECALCULATE_PATH:
                {
                    LOGGER.infof("Policy with action: Recalculate service path");
                    callRecalculatePathRPC(policyRuleService, policyRuleAction);
                    break;
                }
            default:
                {
                    applied = false;
                    LOGGER.errorf(INVALID_MESSAGE, policyRuleAction.getPolicyRuleActionEnum());
                    break;
                }
        }

        if (applied) addActivePolicyRuleAction(policyRuleKpiId, policyRuleAction);
    }

    public void applyActionDevice(String policyRuleKpiId) {
        PolicyRuleDevice policyRuleDevice = activePolicyRuleDevices.get(policyRuleKpiId);

        setPolicyRuleDeviceToContext(policyRuleDevice, ACTIVE_POLICYRULE_STATE);

        List<String> deviceIds = policyRuleDevice.getDeviceIds();
        List<PolicyRuleActionConfig> actionConfigs =
                activePolicyRuleActions.get(policyRuleKpiId).getPolicyRuleActionConfigs();

        if (deviceIds.size() != actionConfigs.size()) {
            String message =
                    String.format(
                            "The number of action parameters in PolicyRuleDevice with ID: %s, is not aligned with the number of devices.",
                            policyRuleDevice.getPolicyRuleBasic().getPolicyRuleId());
            setPolicyRuleDeviceToContext(
                    policyRuleDevice, new PolicyRuleState(PolicyRuleStateEnum.POLICY_FAILED, message));
            return;
        }

        for (var i = 0; i < deviceIds.size(); i++) {
            activateDevice(deviceIds.get(i), actionConfigs.get(i));
        }

        setPolicyRuleDeviceToContext(policyRuleDevice, ENFORCED_POLICYRULE_STATE);
    }

    private void activateDevice(String deviceId, PolicyRuleActionConfig actionConfig) {
        Boolean toBeEnabled;
        if (actionConfig.getActionKey() == "ENABLED") {
            toBeEnabled = true;
        } else if (actionConfig.getActionKey() == "DISABLED") {
            toBeEnabled = false;
        } else {
            LOGGER.errorf(INVALID_MESSAGE, actionConfig.getActionKey());
            return;
        }

        final var deserializedDeviceUni = contextService.getDevice(deviceId);

        deserializedDeviceUni
                .subscribe()
                .with(
                        device -> {
                            if (toBeEnabled && device.isDisabled()) {
                                device.enableDevice();
                            } else if (!toBeEnabled && device.isEnabled()) {
                                device.disableDevice();
                            } else {
                                LOGGER.errorf(INVALID_MESSAGE, "Device is already in the desired state");
                                return;
                            }

                            deviceService.configureDevice(device);
                        });
    }

    private void addServiceConfigRule(
            PolicyRuleService policyRuleService, PolicyRuleAction policyRuleAction) {
        ConfigActionEnum configActionEnum = ConfigActionEnum.SET;
        List<PolicyRuleActionConfig> actionConfigs = policyRuleAction.getPolicyRuleActionConfigs();
        List<ConfigRule> newConfigRules = new ArrayList<>();

        for (PolicyRuleActionConfig actionConfig : actionConfigs) {
            ConfigRuleCustom configRuleCustom =
                    new ConfigRuleCustom(actionConfig.getActionKey(), actionConfig.getActionValue());
            ConfigRuleTypeCustom configRuleType = new ConfigRuleTypeCustom(configRuleCustom);
            ConfigRule configRule = new ConfigRule(configActionEnum, configRuleType);
            newConfigRules.add(configRule);
        }

        var deserializedServiceUni = contextService.getService(policyRuleService.getServiceId());
        deserializedServiceUni
                .subscribe()
                .with(
                        deserializedService -> {
                            List<ConfigRule> configRules =
                                    deserializedService.getServiceConfig().getConfigRules();
                            LOGGER.info("Adding service config rules:");
                            LOGGER.info(newConfigRules);
                            configRules.addAll(newConfigRules);
                            deserializedService.setServiceConfig(new ServiceConfig(configRules));
                        });
    }

    private void addServiceConstraint(
            PolicyRuleService policyRuleService, PolicyRuleAction policyRuleAction) {
        List<PolicyRuleActionConfig> actionConfigs = policyRuleAction.getPolicyRuleActionConfigs();
        List<Constraint> constraintList = new ArrayList<>();

        for (PolicyRuleActionConfig actionConfig : actionConfigs) {
            var constraintCustom =
                    new ConstraintCustom(actionConfig.getActionKey(), actionConfig.getActionValue());
            var constraintTypeCustom = new ConstraintTypeCustom(constraintCustom);
            constraintList.add(new Constraint(constraintTypeCustom));
        }

        final var deserializedServiceUni = contextService.getService(policyRuleService.getServiceId());

        deserializedServiceUni
                .subscribe()
                .with(
                        deserializedService -> {
                            LOGGER.info("Adding service constraints:");
                            LOGGER.info(constraintList);
                            deserializedService.appendServiceConstraints(constraintList);
                            serviceService.updateService(deserializedService);
                            setPolicyRuleServiceToContext(policyRuleService, ENFORCED_POLICYRULE_STATE);
                        });
    }

    private void callUpdateServiceRpc(
            PolicyRuleService policyRuleService, PolicyRuleAction policyRuleAction) {
        final var deserializedServiceUni = contextService.getService(policyRuleService.getServiceId());

        deserializedServiceUni
                .subscribe()
                .with(
                        deserializedService -> {
                            serviceService
                                    .updateService(deserializedService)
                                    .subscribe()
                                    .with(
                                            x -> {
                                                LOGGER.info("Updating service:");
                                                LOGGER.info(deserializedService);
                                                setPolicyRuleServiceToContext(policyRuleService, ENFORCED_POLICYRULE_STATE);
                                            });
                        });
    }

    private void callRecalculatePathRPC(
            PolicyRuleService policyRuleService, PolicyRuleAction policyRuleAction) {
        final var deserializedServiceUni = contextService.getService(policyRuleService.getServiceId());

        deserializedServiceUni
                .subscribe()
                .with(
                        deserializedService -> {
                            serviceService
                                    .recomputeConnections(deserializedService)
                                    .subscribe()
                                    .with(
                                            x -> {
                                                LOGGER.info("Recomputing connections for service:");
                                                LOGGER.info(deserializedService);
                                                setPolicyRuleServiceToContext(policyRuleService, ENFORCED_POLICYRULE_STATE);
                                            });
                        });
    }

    public void setPolicyRuleServiceToContext(
            PolicyRuleService policyRuleService, PolicyRuleState policyRuleState) {
        LOGGER.infof("Setting Policy Rule state to [%s]", policyRuleState.toString());

        final var policyRuleBasic = policyRuleService.getPolicyRuleBasic();
        policyRuleService.setPolicyRuleBasic(policyRuleBasic);

        final var policyRuleTypeService = new PolicyRuleTypeService(policyRuleService);
        final var policyRule = new PolicyRule(policyRuleTypeService);
        contextService.setPolicyRule(policyRule).subscribe().with(x -> {});

        LOGGER.infof("Policy Rule state is now [%s]", policyRuleState.toString());
    }

    public void setPolicyRuleDeviceToContext(
            PolicyRuleDevice policyRuleDevice, PolicyRuleState policyRuleState) {
        LOGGER.infof("Setting Policy Rule state to [%s]", policyRuleState.toString());

        final var policyRuleBasic = policyRuleDevice.getPolicyRuleBasic();
        policyRuleDevice.setPolicyRuleBasic(policyRuleBasic);

        final var policyRuleTypeService = new PolicyRuleTypeDevice(policyRuleDevice);
        final var policyRule = new PolicyRule(policyRuleTypeService);
        final var policyRuleId = contextService.setPolicyRule(policyRule).subscribe().with(x -> {});
    }
}
