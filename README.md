# Task 8 – Multi-Switch Flow Table Analyzer (SDN Mininet Project)

## Problem Statement

Design and implement an SDN application using **Ryu** controller and **Mininet**
that connects to multiple OpenFlow switches, retrieves their flow tables, and
displays detailed rule information — distinguishing **active** rules (packets
matched) from **unused** rules (zero packet count) — with **dynamic polling**
so the view refreshes automatically.

---

## Topology

```
      h1 (10.0.0.1)        h2 (10.0.0.2)
           |                      |
          s1 (dpid=1) --------- s2 (dpid=2)
           |                      |
      h3 (10.0.0.3)        h4 (10.0.0.4)
```

* **s1, s2** – OVS switches running OpenFlow 1.3  
* **h1–h4** – hosts, all on `10.0.0.0/24`  
* Inter-switch link: 1 Gbps | Host links: 100 Mbps

---

## Features

| Feature | Detail |
|---|---|
| Flow retrieval | `OFPFlowStatsRequest` sent to every switch every 10 s |
| Rule display | Priority, TableID, idle/hard timeouts, packet/byte counts, match fields |
| Active vs Unused | Rule flagged **ACTIVE** if `packet_count > 0`, else **UNUSED** |
| Dynamic updates | Background `hub.spawn` polling thread – no manual trigger needed |
| Learning switch | `packet_in` handler learns MAC→port and installs unicast rules |

---

## Setup & Execution

### Prerequisites

```bash
# Install Ryu
pip install ryu

# Install Mininet (Ubuntu/Debian)
sudo apt-get install mininet

# Verify OVS
ovs-vsctl --version
```

### Step 1 – Start the Ryu Controller

```bash
ryu-manager flow_table_analyzer.py --verbose
```

The controller listens on port **6633** and begins polling connected switches
every 10 seconds.

### Step 2 – Start the Mininet Topology (new terminal)

```bash
sudo python3 topology.py
```

### Step 3 – Run Test Scenarios inside Mininet CLI

**Scenario 1 – Basic connectivity (Allowed traffic)**

```
mininet> pingall
```

Expected: all hosts reachable; flow rules installed on s1 and s2.

**Scenario 2 – Throughput test**

```
mininet> iperf h1 h2
mininet> iperf h3 h4
```

Expected: ~90 Mbps on host links; flow byte/packet counts increase.

**Scenario 3 – Inspect flow tables manually**

```
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2
```

**Scenario 4 – Observe Active vs Unused in controller output**

After `pingall`, the Ryu terminal prints a table like:

```
======================================================================
  FLOW TABLE SNAPSHOT  |  Switch dpid=0000000000000001  |  12:34:56
======================================================================
  Priority   TableID  IdleTO  HardTO   Packets      Bytes  Status    Match
----------------------------------------------------------------------
         1         0      30     120        42       3528  ACTIVE    in_port=1,eth_dst=...
         1         0      30     120         0          0  UNUSED    in_port=2,eth_dst=...
         0         0       0       0        10        420  ACTIVE    
----------------------------------------------------------------------
  Total: 3 rules  |  Active: 2  |  Unused: 1
======================================================================
```

---

## Expected Output

* **Ryu terminal**: flow table snapshots every 10 s per switch, with Active/Unused classification  
* **Mininet CLI**: `pingall` shows 0% packet loss; `iperf` shows TCP throughput  
* **ovs-ofctl**: raw OpenFlow 1.3 flow entries with counters

---

## Performance Metrics

| Metric | How measured | Tool |
|---|---|---|
| Latency | `pingall` RTT | Mininet / ping |
| Throughput | TCP bandwidth | `iperf` |
| Flow table changes | Polling output | Ryu / ovs-ofctl |
| Packet counts | `packet_count` in stats | OFPFlowStatsReply |

---

## File Structure

```
.
├── flow_table_analyzer.py   # Ryu controller (main application)
├── topology.py              # Mininet topology script
└── README.md                # This file
```

---

## References

1. Ryu documentation – https://ryu.readthedocs.io/en/latest/
2. OpenFlow 1.3 specification – https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
3. Mininet documentation – http://mininet.org/
4. OVS OpenFlow tutorial – https://github.com/openvswitch/ovs/blob/main/Documentation/tutorials/openflow-1.0.rst
