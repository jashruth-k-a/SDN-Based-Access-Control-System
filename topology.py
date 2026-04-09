#!/usr/bin/env python3
"""
SDN Access Control System - Mininet Topology
4 hosts, 1 switch
h1, h2 = authorized (whitelisted)
h3, h4 = unauthorized
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def create_topology():
    setLogLevel('info')

    net = Mininet(controller=RemoteController, switch=OVSSwitch)

    info('*** Adding controller\n')
    c0 = net.addController('c0', ip='127.0.0.1', port=6633)

    info('*** Adding switch\n')
    s1 = net.addSwitch('s1')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4', mac='00:00:00:00:00:04')

    info('*** Adding links\n')
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)
    net.addLink(h4, s1)

    info('*** Starting network\n')
    net.start()

    info('\n*** Hosts configured:\n')
    info('  h1 - 10.0.0.1 (AUTHORIZED)\n')
    info('  h2 - 10.0.0.2 (AUTHORIZED)\n')
    info('  h3 - 10.0.0.3 (UNAUTHORIZED)\n')
    info('  h4 - 10.0.0.4 (UNAUTHORIZED)\n')

    info('\n*** Opening Mininet CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    create_topology()