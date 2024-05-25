#!/usr/bin/env python

"""
This example shows how to define multiple mediums.
By default, all interfaces share the same medium and the packet ordering takes into account all of their queues.
This behavior causes throughput to drop every time there is additional network load, even if networks are
independent of each other.

By defining interface sets of each medium, we can isolate packet orderings in the queues.
"""

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet

def topology():
    net = Wmnet(bridge_with="enp3s0")

    info('--- Add APs\n')
    ap1 = net.addAP('ap1',
                             position='337.0,424.0,0')
    ap2 = net.addAP('ap2',
                       position='1368.0,391.0,0')
    ap3 = net.addAP('ap3',
                             position='2368.0,391.0,0')

    info('--- Add hosts/stations\n')
    sta1 = net.addSta('sta1', ip='10.0.0.1', position='192.0,384.0,0')
    sta2 = net.addSta('sta2', ip='10.0.0.2', position='237.0,443.0,0')
    sta3 = net.addSta('sta3', ip='10.0.0.3', position='1493.0,150.0,0')
    sta4 = net.addSta('sta4', ip='10.0.0.4', position='1374.0,656.0,0')
    sta5 = net.addSta('sta5', ip='10.0.0.5', position='2393.0,350.0,0')
    sta6 = net.addSta('sta6', ip='10.0.0.6', position='2374.0,426.0,0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    # Defining 3 mediums for packet ordering
    initial_mediums = ((sta1, sta2, ap1),  # Medium #1
                       (sta3, sta4, ap2),  # Medium #2
                       (sta5,))  # Medium #3
    net.setInitialMediums(initial_mediums)

    info('--- Start\n')
    net.start()

    info('--- Post configure nodes\n')
    # Adding ap3's first interface to medium #3
    ap3.setMediumId(3, intf=None)
    # Adding sta6-wlan0 interface to medium #3
    sta6.getNameToWintf("sta6-wlan0").setMediumId(3)

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('debug')
    topology()
