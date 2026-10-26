import json
from pathlib import Path
workflow=json.loads(Path("workflows/intake.json").read_text())
assert not workflow["active"]
nodes=workflow["nodes"]
assert len({n["id"] for n in nodes})==len(nodes)
names={n["name"] for n in nodes}
assert names=={"Incoming request","Execute operation","Return result"}
assert nodes[0]["parameters"]["authentication"]=="headerAuth"
assert nodes[1]["parameters"]["genericAuthType"]=="httpHeaderAuth"
assert nodes[1]["parameters"]["options"]["timeout"]==60000
for source, connections in workflow["connections"].items():
    assert source in names
    for group in connections["main"]:
        assert all(target["node"] in names for target in group)
print("Workflow structure OK; runtime import requires configured n8n credentials")
