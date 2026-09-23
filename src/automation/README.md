# ETSI TFS Automation Service

The Automation service exposes a gPRC API with the following methods:
- ZSMCreate
- ZSMDelete
- ZSMGetById
- ZSMGetByService

To Invoke this API follow the steps below:

## Install grpcurl

```bash
curl -sSL "https://github.com/fullstorydev/grpcurl/releases/download/v1.8.7/grpcurl_1.8.7_linux_x86_64.tar.gz" | sudo tar -xz -C /usr/local/bin
```

## Fetch available methods around Automation

```bash
cd ~/tfs-ctrl/
grpcurl -import-path ./proto -proto automation.proto list
grpcurl -import-path ./proto -proto automation.proto describe automation.AutomationService
grpcurl -import-path ./proto -proto automation.proto describe automation.AutomationService.ZSMCreate
```

## Try an example ZSMCreate

TFS tests are now augmented with a new Automation example that shows the way to trigger a ZSM loop creaiton.
The following script invokes Automation on top of a specific example topology.

```bash
bash src/tests/automation/run_test_automation.sh
```

More details are provided in `src/tests/automation/README.md`

## Important Services

WebUI

```
http://10.10.10.41/webui/
```

Grafana

```
http://10.10.10.41/grafana
```

Prometheus

```
http://10.10.10.41:30090/
```

## Check Kafka topics

The following commands may help you debug a closed loop that involves Telemetry, Analytics, Policy, all managed by Automation.
Kafka is a key element for Automation as the KPIs managed by Analyzer create alarms that propagate to Policy via a dedicated Kafka topic.
Checking this topic is key for ensuring proper communication between Analytics and Policy.

Get all pods in Kafka namespace:

```bash
kubectl get pods -n kafka

NAME                            READY   STATUS    RESTARTS       AGE
kafka-0                         1/1     Running   2 (90d ago)    104d
kafka-broker-5f9656cc68-d8fzz   1/1     Running   13 (44h ago)   429d
zookeeper-8664c6774d-nvbgg      1/1     Running   6 (90d ago)    429d
```

Query Kafka from within the Kafka broker's pod:

```bash
kubectl exec -it kafka-0 -n kafka -- \
  kafka-consumer-groups.sh \
  --bootstrap-server kafka-service.kafka.svc.cluster.local:9092 \
  --list

Output>
    backend
    KpiValueWriter
    analytics-backend
    policy
```

Now let's see the consumer groups.

```bash
kubectl exec -it kafka-0 -n kafka -- \
    kafka-consumer-groups.sh \
    --bootstrap-server kafka-service.kafka.svc.cluster.local:9092 \
    --list

Output>
    backend
    KpiValueWriter
    analytics-backend
    policy
```

Let's describe the policy group:

```bash
kubectl exec -it kafka-0 -n kafka -- \
    kafka-consumer-groups.sh \
    --bootstrap-server kafka-service.kafka.svc.cluster.local:9092 \
    --describe \
    --group policy

Output>
GROUP  TOPIC  PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID  HOST  CLIENT-ID
policy topic_alarms   0  40              41              1    kafka-consumer-topic_alarms-c8f09ac5-8c44-42ec-a13b-1af2c47fb86c /10.1.181.228   kafka-consumer-topic_alarms
```
