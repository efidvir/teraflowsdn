# RESTCONF/SIMAP Datastore

This component implements a basic RESTCONF datastore that can load, potentially, any YANG data model.
In this case, it is prepared to load a SIMAP datastore based on IETF Network Topology + custom SIMAP Telemetry extensions.


## Build the RESTCONF/SIMAP Datastore Docker image
```bash
./build.sh
```

## Deploy the RESTCONF/SIMAP Datastore
```bash
./deploy.sh
```

## Run the RESTCONF/SIMAP Client for testing:
```bash
./run_client.sh
```

## Destroy the RESTCONF/SIMAP Datastore
```bash
./destroy.sh
```
