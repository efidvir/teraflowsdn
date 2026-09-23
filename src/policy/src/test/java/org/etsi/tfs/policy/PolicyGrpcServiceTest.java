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

import context.ContextOuterClass;
import io.quarkus.grpc.GrpcClient;
import io.quarkus.test.junit.QuarkusTest;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.jboss.logging.Logger;
import org.junit.jupiter.api.Test;
import policy.Policy;
import policy.PolicyService;

@QuarkusTest
class PolicyGrpcServiceTest {
    private static final Logger LOGGER = Logger.getLogger(PolicyGrpcServiceTest.class);

    @GrpcClient PolicyService client;

    @Test
    void shouldGetPolicyService() throws ExecutionException, InterruptedException, TimeoutException {
        CompletableFuture<String> message = new CompletableFuture<>();

        final var uuid =
                ContextOuterClass.Uuid.newBuilder()
                        .setUuid(UUID.fromString("0f14d0ab-9608-7862-a9e4-5ed26688389b").toString())
                        .build();
        final var policyRuleId = Policy.PolicyRuleId.newBuilder().setUuid(uuid).build();

        client
                .getPolicyService(policyRuleId)
                .subscribe()
                .with(
                        policyRuleService -> {
                            LOGGER.infof(
                                    "Getting policy with ID: %s",
                                    policyRuleService.getPolicyRuleBasic().getPolicyRuleId().getUuid());
                            message.complete(
                                    policyRuleService.getPolicyRuleBasic().getPolicyRuleId().getUuid().getUuid());
                        });

        assertThat(message.get(5, TimeUnit.SECONDS)).isEqualTo(policyRuleId.getUuid().getUuid());
    }

    @Test
    void shouldGetPolicyDevice() throws ExecutionException, InterruptedException, TimeoutException {
        CompletableFuture<String> message = new CompletableFuture<>();

        final var uuid =
                ContextOuterClass.Uuid.newBuilder()
                        .setUuid(UUID.fromString("0f14d0ab-9608-7862-a9e4-5ed26688389b").toString())
                        .build();
        final var policyRuleId = Policy.PolicyRuleId.newBuilder().setUuid(uuid).build();

        client
                .getPolicyDevice(policyRuleId)
                .subscribe()
                .with(
                        policyRuleService -> {
                            LOGGER.infof(
                                    "Getting policy with ID: %s",
                                    policyRuleService.getPolicyRuleBasic().getPolicyRuleId().getUuid());
                            message.complete(
                                    policyRuleService.getPolicyRuleBasic().getPolicyRuleId().getUuid().getUuid());
                        });

        assertThat(message.get(5, TimeUnit.SECONDS)).isEqualTo(policyRuleId.getUuid().getUuid());
    }

    @Test
    void shouldGetPolicyByServiceId()
            throws ExecutionException, InterruptedException, TimeoutException {

        CompletableFuture<String> message = new CompletableFuture<>();

        final var uuid =
                ContextOuterClass.Uuid.newBuilder()
                        .setUuid(UUID.fromString("0f14d0ab-9608-7862-a9e4-5ed26688389b").toString())
                        .build();
        final var serviceId = ContextOuterClass.ServiceId.newBuilder().setServiceUuid(uuid).build();

        client
                .getPolicyByServiceId(serviceId)
                .subscribe()
                .with(
                        policyRuleList -> {
                            LOGGER.infof("Getting policyRuleList with ID: %s", policyRuleList);
                            message.complete(policyRuleList.toString());
                        });

        assertThat(message.get(5, TimeUnit.SECONDS)).isEmpty();
    }
}
