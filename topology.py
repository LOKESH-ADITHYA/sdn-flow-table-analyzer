#!/usr/bin/env python3
"""
topology.py
Multi-Switch Mininet Topology for Task 8 – Flow Table Analyzer

Topology:
          h1        h2
           \        /
            s1----s2
           /        \
          h3        h4

  s1 (dpid=1) <--> s2 (dpid=2)  (core link)
  h1, h3 behind s1  |  h2, h4 behind s2

Run:
  sudo python3 topology.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def build_topology():
    setLogLevel('info')

    net = Mininet(controller=RemoteController,
                  switch=OVSSwitch,
                  link=TCLink,
                  autoSetMacs=True)

    info("*** Adding remote controller (Ryu on 127.0.0.1:6633)\n")
    c0 = net.addController('c0',
                            controller=RemoteController,
                            ip='127.0.0.1',
                            port=6633)

    info("*** Adding switches\n")
    s1 = net.addSwitch('s1', dpid='0000000000000001')
    s2 = net.addSwitch('s2', dpid='0000000000000002')

    info("*** Adding hosts\n")
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')

    info("*** Adding links\n")
    # Host–switch links (100 Mbps)
    net.addLink(h1, s1, bw=100)
    net.addLink(h3, s1, bw=100)
    net.addLink(h2, s2, bw=100)
    net.addLink(h4, s2, bw=100)
    # Core inter-switch link (1 Gbps)
    net.addLink(s1, s2, bw=1000)

    info("*** Starting network\n")
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])

    # Force OpenFlow 1.3
    for sw in [s1, s2]:
        sw.cmd('ovs-vsctl set bridge {} protocols=OpenFlow13'.format(sw.name))

    info("\n*** Topology ready:\n")
    info("    h1 (10.0.0.1) --- s1 --- s2 --- h2 (10.0.0.2)\n")
    info("    h3 (10.0.0.3) ---/          \\--- h4 (10.0.0.4)\n\n")
    info("*** Test scenarios:\n")
    info("    Scenario 1 (Connectivity): h1 pingall\n")
    info("    Scenario 2 (Traffic + flow stats): iperf h1 h2\n")
    info("    Scenario 3 (View live flow tables):\n")
    info("      ovs-ofctl -O OpenFlow13 dump-flows s1\n")
    info("      ovs-ofctl -O OpenFlow13 dump-flows s2\n\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    build_topology()
