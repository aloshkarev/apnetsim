#!/usr/bin/python

from apns.cli import CLI
from apns.log import info, setLogLevel
from apns.net import Wmnet

def topology():
    ap = {}
    sta = {}
    num_of_ap = 125
    num_of_sta = 0

    net = Wmnet(bridge_with="enp3s0", start_ap_id=100)

    info('--- Run docker containers\n')

    ap=net.addAP(position='1,1,0', amount=num_of_ap ,dimage="wifi.eltex.loc:5000/apemu:test")


    for i in range(1, num_of_sta + 1):
        sta[i] = net.addSta(ssid="default-ssid", position='1,1,0')
        info(sta[i].pop().name+" ")
    info('\n')

    # net.plotGraph(max_x=10, max_y=10)
    #
    # net.setMobilityModel(time=10, model='RandomWayPoint', max_x=10, max_y=10,
    #                      min_v=0.5, max_v=0.5, seed=20)

    info('--- Start\n')
    net.start()

    info('--- CLI\n')
    CLI(net)

    info('--- Stop\n')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
