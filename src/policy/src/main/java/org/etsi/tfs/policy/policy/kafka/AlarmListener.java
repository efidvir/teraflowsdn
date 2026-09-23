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

package org.etsi.tfs.policy.policy.kafka;

import io.smallrye.reactive.messaging.annotations.Blocking;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.etsi.tfs.policy.policy.CommonPolicyServiceImpl;
import org.etsi.tfs.policy.policy.model.AlarmTopicDTO;
import org.jboss.logging.Logger;

@ApplicationScoped
public class AlarmListener {
    private final CommonPolicyServiceImpl commonPolicyServiceImpl;

    private final Logger logger = Logger.getLogger(AlarmListener.class);
    public static final String ALARM_TOPIC = "topic_alarms";

    @Inject
    public AlarmListener(CommonPolicyServiceImpl commonPolicyServiceImpl) {
        logger.info("Alarm listener initialized");
        this.commonPolicyServiceImpl = commonPolicyServiceImpl;
    }

    @Incoming(ALARM_TOPIC)
    @Blocking
    public void receiveAlarm(AlarmTopicDTO alarmTopicDto) {
        logger.infof("Received message from Analytics service:\n %s", alarmTopicDto.toString());
        if (alarmTopicDto.isValid() && alarmTopicDto.isTriggered()) {
            logger.info("************************** Alarm **************************");
            logger.infof("Alarm for kpiId: %s", alarmTopicDto.getKpiId());
            logger.infof("Alarm value: %.2f", alarmTopicDto.getValue());
            logger.infof("Alarm value low  threshold: %s", alarmTopicDto.getValueThresholdLow());
            logger.infof("Alarm value high threshold: %s", alarmTopicDto.getValueThresholdHigh());
            commonPolicyServiceImpl.applyActionServiceBasedOnKpiId(alarmTopicDto.getKpiId());
            logger.info("***********************************************************");
        } else {
            logger.warnf("Invalid alarm message: %s", alarmTopicDto);
        }
    }
}
