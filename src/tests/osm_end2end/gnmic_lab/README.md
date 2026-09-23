# OSM End-to-End gNMI Lab

This folder contains an isolated Containerlab scenario and direct `gnmic`
helpers to validate cEOS OpenConfig behavior without involving TeraFlowSDN.

The objective is to determine which OpenConfig payloads correctly configure:

- untagged routed access ports
- tagged routed access ports
- inter-router L3 links

and to inspect the resulting EOS CLI configuration.

The current verified findings are tracked in [REPORT.md](./REPORT.md).

Typical workflow:

```bash
cd ~/tfs-ctrl
src/tests/osm_end2end/gnmic_lab/run-lab.sh deploy
src/tests/osm_end2end/gnmic_lab/run-lab.sh baseline
src/tests/osm_end2end/gnmic_lab/run-lab.sh experiment-tagged-subif125
src/tests/osm_end2end/gnmic_lab/run-lab.sh destroy
```

Results are written under `src/tests/osm_end2end/gnmic_lab/results/`.

Useful experiment actions:

- `experiment-untagged`
- `experiment-tagged-subif125`
- `experiment-tagged-subif0-and-125`
- `experiment-tagged-subif0-then-125`
- `experiment-tagged-subif0-vlan125`
- `experiment-tagged-cli-baseline-and-capture`
- `experiment-tagged-replace-inferred`
