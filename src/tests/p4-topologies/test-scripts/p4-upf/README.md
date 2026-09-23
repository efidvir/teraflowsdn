# UPF Test

If you have already deployed your UPF following the instructions provided in `src/tests/p4-sd-fabric-svc-upf/` and you want to perform a quick test without deploying a fully-fledged 5G system, you may execute the script in this folder.
All you need is to tweak the script's initial variables to fit your setup.

## Where to deploy the script

On the network interface that connects the 5G gNB node with the UPF.
Mark this network interface and add its name as a value in variable `GNB_IFACE`.

## What to configure in the script

Apart from the `GNB_IFACE` variable, you need to provide:
- `GNB_IP` and `GNB_MAC` addresses that correspond to the interface `GNB_IFACE`
- `DNN_IP` and `DNN_IP` addresses that correspond to the destination of the packet after traversing the UPF.
- `UPF_IP_LEFT` and `UPF_MAC_LEFT`  addresses that correspond to the interface of the UPF that talks to te gNB
- a `UE_IP` of your choice if the default value in the script is not what you want. The UE is emulated by this script so you may leave the default IP.


## How the script works

The script employs a traffic sniffer on the `GNB_IFACE` with a timeout.
After the sniffer is employed, the script transmits a GTP-U packet towards the DNN, which encapsulates an ICMP echo request from the UE to the DNN host.
This packet has to pass through your UPF and get back once the kernel of the DNN host responds with an ICMP echo reply.
This reply is captured by the script and printed.
