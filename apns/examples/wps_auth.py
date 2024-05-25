#!/usr/bin/env python

"""This example shows how to start AP with wps"""
import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.term import makeTerm


def topology(attack):
    """Create a network."""
    net = Wmnet()

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', encrypt='wpa2')
    sta2 = net.addSta('sta2', encrypt='wpa2')
    ap1 = net.addAP('ap1', ssid="simplewifi", mode="g", channel="1",
                             passwd='123456789a', encrypt='wpa2',
                             failMode="standalone", datapath='user', wps_state='2',
                             config_methods='label display push_button keypad')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)

    info("--- Start\n")
    net.build()
    ap1.start([])

    if attack:
        ap1.cmd('hostapd_cli -i ap1-wlan1 wps_ap_pin set 12345670')
        sta1.cmd('iw dev sta1-wlan0 interface add mon0 type monitor')
        sta1.cmd('ip link set mon0 up')
        makeTerm(sta1)  # reaver -i mon0 -b 02:00:00:00:02:00 -vv
    else:
        ap1.cmd('hostapd_cli -i ap1-wlan1 wps_pin any 12345670')
        sta1.cmd('wpa_cli -i sta1-wlan0 wps_pin 02:00:00:00:02:00 12345670')
        sta2.cmd('wpa_cli -i sta2-wlan0 wps_pin 02:00:00:00:02:00 12345670')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    attack = True if '-a' in sys.argv else False
    topology(attack)
