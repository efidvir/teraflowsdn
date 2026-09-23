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

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import java.util.List;
import org.etsi.tfs.policy.common.Util;

public class PolicyRuleBasic {

    private String policyRuleId;
    private PolicyRuleState policyRuleState;
    private int policyRulePriority;
    private List<PolicyRuleAction> policyRuleActions;
    private List<String> policyRuleKPIs;
    private Boolean isValid;
    private String exceptionMessage;

    public PolicyRuleBasic(
            String policyRuleId,
            PolicyRuleState policyRuleState,
            int policyRulePriority,
            List<PolicyRuleAction> policyRuleActions,
            List<String> policyRuleKPIs) {

        checkNotNull(policyRuleId, "Policy rule ID must not be NULL.");
        checkArgument(!policyRuleId.isBlank(), "Policy rule ID must not be empty.");
        this.policyRuleId = policyRuleId;
        this.policyRuleState = policyRuleState;
        checkArgument(policyRulePriority >= 0, "Priority value must be greater than or equal to zero.");
        this.policyRulePriority = policyRulePriority;
        checkNotNull(policyRuleActions, "Policy rule actions cannot be NULL.");
        checkArgument(!policyRuleActions.isEmpty(), "Policy rule actions cannot be empty.");
        this.policyRuleActions = policyRuleActions;
        checkNotNull(policyRuleKPIs, "Policy rule KPIs cannot be NULL.");
        checkArgument(!policyRuleKPIs.isEmpty(), "Policy rule KPIs cannot be empty.");
        this.policyRuleKPIs = policyRuleKPIs;
        this.exceptionMessage = "";
        this.isValid = true;
    }

    public boolean areArgumentsValid() {
        return isValid;
    }

    public String getExceptionMessage() {
        return exceptionMessage;
    }

    public String getPolicyRuleId() {
        return policyRuleId;
    }

    public void setPolicyRuleId(String policyRuleId) {
        this.policyRuleId = policyRuleId;
    }

    public PolicyRuleState getPolicyRuleState() {
        return policyRuleState;
    }

    public void setPolicyRuleState(PolicyRuleState policyRuleState) {
        this.policyRuleState = policyRuleState;
    }

    public int getPolicyRulePriority() {
        return policyRulePriority;
    }

    public void setPolicyRulePriority(int policyRulePriority) {
        this.policyRulePriority = policyRulePriority;
    }

    public List<PolicyRuleAction> getPolicyRuleActions() {
        return policyRuleActions;
    }

    public List<String> getPolicyRuleKPIs() {
        return policyRuleKPIs;
    }

    @Override
    public String toString() {
        return String.format(
                "%s:{policyRuleId:\"%s\", %s, policyRulePriority:%d, [%s] [%s]}",
                getClass().getSimpleName(),
                policyRuleId,
                policyRuleState,
                policyRulePriority,
                Util.toString(policyRuleActions),
                Util.toString(policyRuleKPIs));
    }
}
