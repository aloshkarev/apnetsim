from logging import basicConfig, exception, DEBUG
from os import system as sh, path, devnull
from re import search
from subprocess import check_output as co, PIPE, Popen, call, CalledProcessError
from time import sleep

from apns.log import debug, info, error


class WifiEmu(object):
    """Loads aprf_drv module"""

    prefix = ""
    wemu_ids = []
    externally_managed = False
    devices_created_dynamically = False
    phyWlans = None

    def __init__(self, on_the_fly=False, **params):
        if on_the_fly:
            self.configNodeOnTheFly(**params)
        else:
            self.start(**params)

    def get_wlan_list(self, phys, **params):
        if 'docker' in params:
            wlan_list = []
            for phy in range(len(phys)):
                wlan_list.append('wlan{}'.format(phy))
        else:
            wlan_list = self.get_wlan_iface()
        return wlan_list

    def get_wemu_list(self, node):
        cmd = 'find /sys/kernel/debug/ieee80211 -name wemu | grep %s ' \
               '| cut -d/ -f 6 | sort' % node.name
        return cmd

    def configPhys(self, node, **params):
        phys = self.get_intf_list(self.get_wemu_list(node))  # gets virtual and phy interfaces
        WifiEmu.phyWlans=phys
        wlan_list = self.get_wlan_list(phys, **params)  # gets wlan list
        self.assign_iface(node, phys, wlan_list, (len(phys) - 1), **params)

    def start(self, nodes, nradios, alt_module, board_module, rec_rssi, **params):
        """Starts environment
        :param nodes: list of wireless nodes
        :param nradios: number of wifi radios
        :param alt_module: dir of a aprf_drv alternative module
        :params rec_rssi: if we set rssi to aprf_drv
        """
        if rec_rssi:
            self.add_phy_id(nodes)

        cmd = 'iw dev 2>&1 | grep Interface | awk \'{print $2}\''
        WifiEmu.phyWlans = self.get_intf_list(cmd)  # gets physical wlan(s)
        self.load_module(nradios, nodes, alt_module, board_module, **params)  # loads wifi module
        for node in nodes:
            phys = self.get_intf_list(self.get_wemu_list(node))  # gets virtual and phy interfaces
            wlan_list = self.get_wlan_list(phys, **params)  # gets wlan list
            self.assign_iface(node, phys, wlan_list, **params)

    @staticmethod
    def create_static_radios(nradios, alt_module, modprobe):
        # Useful for kernel <= 3.13.x
        if nradios == 0: nradios = 1
        if alt_module:
            sh('insmod {} radios={}'.format(alt_module, nradios))
        else:
            sh('{}={}'.format(modprobe, nradios))

    def load_module(self, nradios, nodes, alt_module, board_module, **params):
        """Load WiFi Module
        nradios: number of wifi radios
        nodes: list of nodes
        alt_module: dir of a aprf_drv alternative module
        """
        debug('Loading %s board module\n' % board_module)
        sh('modprobe mac80211 >/dev/null 2>&1')
        debug('Loading %s virtual wifi interfaces\n' % nradios)
        if not self.externally_managed:
            modprobe = 'modprobe aprf_drv radios'
            if alt_module:
                debug('using alt module %s\n' % alt_module)
                output = sh('insmod {} radios=0 >/dev/null 2>&1'.format(alt_module))
            else:
                output = sh('{}=0 >/dev/null 2>&1'.format(modprobe))

            if output == 0:
                self.__create_wemu_mgmt_devices(nradios, nodes, **params)
            else:
                self.create_static_radios(nradios, alt_module, modprobe)
        else:
            self.devices_created_dynamically = True
            self.__create_wemu_mgmt_devices(nradios, nodes, **params)

    def configNodeOnTheFly(self, node):
        for wlan in range(len(node.params['wlan'])):
            self.create_wemu(node)
        self.configPhys(node)

    def get_phys(self, node):
        # generate prefix
        num = 0
        numokay = False
        self.prefix = ""
        phys = co(self.get_wemu_list(node), shell=True).decode('utf-8').split("\n")
        while not numokay:
            self.prefix = "%swlan%d" % (node.name, num)  # Add PID to mn-devicenames
            numokay = True
            for phy in phys:
                if phy.startswith(self.prefix):
                    num += 1
                    numokay = False
                    break
        return num

    def create_wemu(self, node):
        self.get_phys(node)
        p = Popen(["aprf_ctrl", "-c", "-t", "-n", self.prefix],
                  stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=-1)
        output, err_out = p.communicate()
        if p.returncode == 0:
            m = search("ID (\d+)", output.decode())
            debug("create_wemu: Created aprf_drv device with ID %s\n" % m.group(1))
            WifiEmu.wemu_ids.append(m.group(1))
        else:
            error("\nError on creating aprf_drv device "
                  "with name {}".format(self.prefix))
            error("\nOutput: {}".format(output))
            error("\nError: {}".format(err_out))

    def __create_wemu_mgmt_devices(self, nradios, nodes, **params):

        if 'docker' in params:
            num = self.get_phys(nodes)
            self.docker_config(nradios=nradios, nodes=nodes, num=num, **params)
        else:
            try:
                for node in nodes:
                    for n in range(nradios):
                        self.create_wemu(n, node)
            except:
                info("Warning!\n")

    @staticmethod
    def get_intf_list(cmd):
        """Gets all phys after starting the wireless module"""
        phy = co(cmd, shell=True).decode('utf-8').split("\n")
        phy.pop()
        phy.sort(key=len, reverse=False)
        return phy

    @classmethod
    def load_ifb(cls, wlans):
        debug('\nLoading IFB: modprobe ifb numifbs={}'.format(wlans))
        sh('modprobe ifb numifbs={}'.format(wlans))

    def docker_config(self, nradios=0, nodes=None, dir='~/',
                      ip='172.17.0.1', num=0, **params):

        file = self.prefix + 'docker-mn-wifi.sh'
        if path.isfile(file):
            sh('rm {}'.format(file))
        sh("echo '#!/bin/sh' >> {}".format(file))
        sh("echo 'pid=$(sudo -S docker inspect -f '{{.State.Pid}}' "
           "{})' >> {}".format(params['container'], file))
        sh("echo 'sudo -S mkdir -p /var/run/netns' >> {}".format(file))
        sh("echo 'sudo -S ln -s /proc/$pid/ns/net/ /var/run/netns/$pid' >> {}".format(file))

        radios = []
        nodes_ = ''
        phys_ = ''
        for node in nodes:
            nodes_ += node.name + ' '
            radios.append(nodes.index(node))

        for radio in range(nradios):
            sh("echo 'sudo -S aprf_ctrl -c -n %s%s' >> %s" %
               (self.prefix, "%01d" % radio, file))
            if radio in radios:
                radio_id = self.prefix + "%01d" % radio
                phys_ += radio_id + ' '
        sh("echo 'nodes=({})' >> {}".format(nodes_, file))
        sh("echo 'phys=({})' >> {}".format(phys_, file))
        sh("echo 'j=0' >> {}".format(file))
        sh("echo 'for i in ${phys[@]}' >> %s" % file)
        sh("echo 'do' >> %s" % file)
        sh("echo '    pid=$(ps -aux | grep \"${nodes[$j]}\" | grep -v 'hostapd' "
           "| awk \"{print \$2}\" | awk \"NR>=%s&&NR<=%s\")' "
           ">> %s" % (num + 1, num + 1, file))
        sh("echo '    sudo iw phy $i set netns $pid' >> %s" % file)
        sh("echo '    j=$((j+1))' >> {}".format(file))
        sh("echo 'done' >> {}".format(file))
        sh("scp %s %s@%s:%s" % (file, params['ssh_user'], ip, dir))
        sh("ssh %s@%s \'chmod +x %s%s; %s%s\'" %
           (params['ssh_user'], ip, dir, file, dir, file))

    @staticmethod
    def rename(node, wintf, newname):
        node.cmd('ip link set {} down'.format(wintf))
        node.cmd('ip link set {} name {}'.format(wintf, newname))
        node.cmd('ip link set {} up'.format(newname))

    def add_phy_id(self, nodes):
        id = 0
        for node in nodes:
            node.phyid = []
            for _ in range(1, len(node.params['wlan'])):
                node.phyid.append(id)
                id += 1

    def assign_iface(self, node, phys, wlan_list, id=0, **params):
        """Assign virtual interfaces for nodes
        nodes: list of nodes
        """
        from apns.node import AP
        log_filename = '/tmp/mn-wifi-hw.log'
        self.logging_to_file(log_filename)
        try:
            pids = co(['pgrep', '-f', 'NetworkManager'])
        except CalledProcessError:
            pids = ''
        try:
            for wlan in range(len(node.params['wlan'])):
                f = open(devnull, 'w')
                if isinstance(node, AP) and not node.inNamespace:
                    if 'docker' not in params:
                        rfkill = co(
                            'rfkill list | grep %s | awk \'{print $1}\''
                            '| tr -d ":"' % phys[0],
                            shell=True).decode('utf-8').split('\n')
                        debug('assign_iface: rfkill unblock {}\n'.format(rfkill[0]))
                        sh('rfkill unblock {}'.format(rfkill[0]))
                        sh('iw phy {} set netns {}'.format(phys[0], node.pid))
                    self.rename(node, wlan_list[0], node.params['wlan'][wlan])
                else:
                    if 'docker' not in params:
                        rfkill = co(
                            'rfkill list | grep %s | awk \'{print $1}\''
                            '| tr -d ":"' % phys[0],
                            shell=True).decode('utf-8').split('\n')
                        debug('assign_iface: rfkill unblock {}\n'.format(rfkill[0]))
                        sh('rfkill unblock {}'.format(rfkill[0]))
                        sh('iw phy {} set netns {}'.format(phys[0], node.pid))
                    self.rename(node, wlan_list[0], node.params['wlan'][wlan])
                wlan_list.pop(0)
                phys.pop(0)
        except:
            exception("Warning:")
            info("Warning! Error when loading aprf_drv. "
                 "Please run sudo 'mn -c' before running your code.\n")
            info("Further information available at {}.\n".format(log_filename))
            exit(1)

    def logging_to_file(self, filename):
        basicConfig(filename=filename, filemode='a', level=DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', )

    @staticmethod
    def get_wlan_iface():
        """Build a new wlan list removing the physical wlan"""
        wlan_list = []
        iface_list = co("iw dev 2>&1 | grep Interface | awk '{print $2}'",
                        shell=True).decode('utf-8').split('\n')
        for iface in iface_list:
            if iface and iface not in WifiEmu.phyWlans:
                wlan_list.append(iface)
        wlan_list = sorted(wlan_list)
        wlan_list.sort(key=len, reverse=False)
        return wlan_list
