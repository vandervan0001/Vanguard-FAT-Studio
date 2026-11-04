# Public passive PLC laboratory

This bundle has one standard DB and OB1, 75 mapped primitive tags, and no FB,
UDT, customer library, state machine or equipment diagnostic logic. EnableDemo
defaults to FALSE. Only an explicitly isolated virtual copy may set it to TRUE.
Requests pass through EnableDemo and StopHealthy. Speeds/positions use native
LIMIT; three levels use native NORM_X/SCALE_X (0..27648 to 0..100).

FAT Studio supplies simulated requests and feedbacks. The PLC owns all command
outputs. This example is not a production control or safety program.

Import plc/Program_All.scl into a NEW TIA V21 simulation project. Configure an
isolated PLCSIM Advanced CPU and OPC UA server separately. Compile, review and
load with the authorized human engineering workflow. Never import it into an
existing plant project. See docs/DEMO_PLC.md in the source distribution.

tags.csv intentionally leaves addresses and NodeIds empty. Export the compiled
standard DB with Openness WithReadOnly for actual bit offsets; browse the real
OPC UA server, verify its certificate and ApplicationUri, and record each actual
NodeId/type/access. Set a separate local machine target policy before connecting.
demo-lab.json uses FAT Studio's Python demo controller until explicitly remapped.

Verify this bundle with: python -m integrations.demo_plc verify PATH_TO_BUNDLE
No secret, private key or native CPU command is included. No human FAT verdict
is supplied by this example.
