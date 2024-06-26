#!/usr/bin/python

"""
Simple example of sending output to multiple files and
monitoring them
"""

from select import poll, POLLIN
from subprocess import Popen, PIPE
from time import time

from apns.log import setLogLevel
from apns.net import Wmnet
from apns.topo import SingleSwitchTopo


def monitorFiles(outfiles, seconds, timeoutms):
    "Monitor set of files and return [(host, line)...]"
    devnull = open('/dev/null', 'w')
    tails, fdToFile, fdToHost = {}, {}, {}
    for h, outfile in list(outfiles.items()):
        tail = Popen(['tail', '-f', outfile],
                     stdout=PIPE, stderr=devnull)
        fd = tail.stdout.fileno()
        tails[h] = tail
        fdToFile[fd] = tail.stdout
        fdToHost[fd] = h
    # Prepare to poll output files
    readable = poll()
    for t in list(tails.values()):
        readable.register(t.stdout.fileno(), POLLIN)
    # Run until a set number of seconds have elapsed
    endTime = time() + seconds
    while time() < endTime:
        fdlist = readable.poll(timeoutms)
        if fdlist:
            for fd, _flags in fdlist:
                f = fdToFile[fd]
                host = fdToHost[fd]
                # Wait for a line of output
                line = f.readline().strip()
                yield host, line
        else:
            # If we timed out, return nothing
            yield None, ''
    for t in list(tails.values()):
        t.terminate()
    devnull.close()  # Not really necessary


def monitorTest(N=3, seconds=3):
    "Run pings and monitor multiple hosts"
    topo = SingleSwitchTopo(N)
    net = Wmnet(topo)
    net.start()
    hosts = net.hosts
    print("Starting test...")
    server = hosts[0]
    outfiles, errfiles = {}, {}
    for h in hosts:
        # Create and/or erase output files
        outfiles[h] = '/tmp/%s.out' % h.name
        errfiles[h] = '/tmp/%s.err' % h.name
        h.cmd('echo >', outfiles[h])
        h.cmd('echo >', errfiles[h])
        # Start pings
        h.cmdPrint('ping', server.IP(),
                   '>', outfiles[h],
                   '2>', errfiles[h],
                   '&')
    print(("Monitoring output for", seconds, "seconds"))
    for h, line in monitorFiles(outfiles, seconds, timeoutms=500):
        if h:
            print(('%s: %s' % (h.name, line)))
    for h in hosts:
        h.cmd('kill %ping')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    monitorTest()
