from __future__ import unicode_literals

import os
import time

from glob import glob
from subprocess import Popen, PIPE, check_output as co, CalledProcessError
from time import sleep

from apns.log import info
from apns.term import cleanUpScreens
from apns.util import decode
from apns.wmediumdConnector import w_server

SAP_PREFIX = 'sap.'


class Cleanup(object):
    """Wrapper for cleanup()"""
    socket_port = 0
    plot = None
    callbacks = []

    @classmethod
    def sh(cls, cmd):
        """Print a command and send it to the shell"""
        result = Popen(['/bin/sh', '-c', cmd], stdout=PIPE).communicate()[0]
        return decode(result)

    @classmethod
    def killprocs(cls, pattern):
        """Reliably terminate processes matching a pattern (including args)"""
        cls.sh('pkill -9 -f {}'.format(pattern))
        # Make sure they are gone
        while True:
            try:
                pids = co(['pgrep', '-f', pattern])
            except CalledProcessError:
                pids = ''
            if pids:
                cls.sh('pkill -9 -f {}'.format(pattern))
                sleep(.5)
            else:
                break

    @classmethod
    def module_loaded(cls, module):
        """Checks if module is loaded"""
        lsmod_proc = Popen(['lsmod'], stdout=PIPE)
        grep_proc = Popen(['grep', module], stdin=lsmod_proc.stdout, stdout=PIPE)
        grep_proc.communicate()  # Block until finished
        return grep_proc.returncode == 0

    @classmethod
    def kill_mod(cls, module):
        if cls.module_loaded(module):
            info("--- Remove module {}\n".format(module))
            os.system('rmmod {}'.format(module))

    @classmethod
    def kill_mod_proc(cls):
        if cls.plot:
            cls.plot.close_plot()

        w_server.disconnect()
        cls.sh('pkill wmediumd')
        sleep(0.1)

        info("\n--- Remove Wi-Fi interfaces\n")
        phy = co('find /sys/kernel/debug/ieee80211 -name wemu | cut -d/ -f 6 | sort',
                 shell=True).decode('utf-8').split("\n")
        phy.pop()
        phy.sort(key=len, reverse=False)

        for phydev in phy:
            p = Popen(["aprf_ctrl", "-x", phydev], stdin=PIPE,
                          stdout=PIPE, stderr=PIPE, bufsize=-1)
            output, err_out = p.communicate()

        cls.kill_mod('aprf_drv')

        if glob('*.apconf'):
            os.system('rm *.apconf')
        if glob('*.staconf'):
            os.system('rm *.staconf')
        if glob('*wifiDirect.conf'):
            os.system('rm *wifiDirect.conf')
        if glob('*.nodeParams'):
            os.system('rm *.nodeParams')

        if cls.socket_port:
            info('\n--- Done\n')
            cls.os.system('fuser -k %s/tcp >/dev/null 2>&1' % cls.socket_port)

    @classmethod
    def cleanup(cls):
        """Clean up junk which might be left over from old runs;
           do fast stuff before slow dp and link removal!"""
        cls.sh("docker stop -t 10 $( docker ps --filter 'label=com.mn_docker' -a -q)")

        if glob('*-mn-telemetry.txt'):
            os.system('rm *-mn-telemetry.txt')

        info("--- Stop controllers/ofprotocols/ofdatapaths\n")
        zombies = ('controller ofprotocol ofdatapath'
                   'ovs-openflowd ovs-controller'
                   'ovs-testcontroller mnexec')
        # Note: real zombie processes can't actually be killed, since they
        # are already (un)dead. Then again,
        # you can't connect to them either, so they're mostly harmless.
        # Send SIGTERM first to give processes a chance to shutdown cleanly.
        os.system('killall ' + zombies + ' 2> /dev/null')
        time.sleep(1)
        os.system('killall -9 ' + zombies + ' 2> /dev/null')

        # And kill off sudo mnexec
        os.system('pkill -9 -f "sudo mnexec"')

        info("--- Removing temporary files from /tmp\n")
        os.system('rm -f /tmp/vconn* /tmp/vlogs* /tmp/*.out /tmp/*.log /tmp/mn_wmd_config*')

        info("--- Removing old X11 tunnels\n")
        cleanUpScreens()

        info("--- Removing excess kernel datapaths\n")
        dps = cls.sh("ps ax | egrep -o 'dp[0-9]+' | sed 's/dp/nl:/'").splitlines()
        for dp in dps:
            if dp:
                cls.sh('dpctl deldp ' + dp)

        info("--- Removing OVS datapaths\n")
        dps = cls.sh("ovs-vsctl --timeout=1 list-br").strip().splitlines()
        if dps:
            os.system("ovs-vsctl " + " -- ".join("--if-exists del-br " + dp
                                                 for dp in dps if dp))
        # And in case the above didn't work...
        dps = cls.sh("ovs-vsctl --timeout=1 list-br").strip().splitlines()
        for dp in dps:
            os.system('ovs-vsctl del-br ' + dp)

        info("--- Killing stale node processes\n")
        cls.killprocs('mn:')

        info("--- Shutting down stale tunnels\n")
        cls.killprocs('Tunnel=Ethernet')
        cls.killprocs('.ssh/mn')
        os.system('rm -f ~/.ssh/mn/*')

        # Call any additional cleanup code if necessary
        for callback in cls.callbacks:
            callback()

        # mn_docker should also cleanup pending Docker
        cls.sh("docker rm -f $( docker ps --filter 'label=com.mn_docker' -a -q)")

        cls.kill_mod_proc()

        info("--- Done.\n")

    @classmethod
    def addCleanupCallback(cls, callback):
        """Add cleanup callback"""
        if callback not in cls.callbacks:
            cls.callbacks.append(callback)

cleanup = Cleanup.cleanup
addCleanupCallback = Cleanup.addCleanupCallback
