#! /usr/bin/env python

import docopt
import os
import json
import logging
import paramiko
import socket
import subprocess
import sys
import yaml


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

def do_daemon_command(host, osdlist, cmd):
    '''
    Do a 'ceph osd daemon' command on host for each osd in osdlist
    'cmd' is the command to execute (less the ceph osd daemon <osd.n>)
    If 'host' contains an '@', it will be split into user and host

    Prints one line per osd including name as given and either
    a list of key/values (if the command returns a JSON map) or the
    output of the command directly if not formatted as JSON    
    '''

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    user, host = host.split('@')
    if not host:
        host = user
        user = None
    try:
        client.connect(host, username=user, timeout=15)
    except paramiko.SSHException:
        log.error("Can't connect to %s", host)
        return
    except socket.error, v:
        log.error("Can't connect to %s: %s", host, v)
        return

    for o in sorted(osdlist):
        try:
            command = ('sudo ceph daemon {osd} {cmd}'.format(osd=o, cmd=cmd))
            # print command

            _, out, err = client.exec_command(command)
        except paramiko.SSHException:
            log.exception("Paramiko SSH error contacting %s", host)
            return
        rc = out.channel.recv_exit_status()
        if rc != 0:
            log.error("return code: %s", rc)
            log.error("stderr: %s", err.read())
            return

        out = out.read()
        print o,
        try:
            out = json.loads(out)
            for k, v in out.iteritems():
                print "%s: %s" % (k, v)
        except ValueError:
            print out


def get_osd_tree(conf):
    ''' Get host/osd map from ceph.conf in 'conf' '''
    p = subprocess.Popen(
        args='ceph -c {conf} osd tree -f json'.format(conf=conf).split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # json response contains:
    #[nodes]: array of crush nodes, 'id', 'type' 'osd' or 'host'
    # if 'host', 'children' are child ids
    # make a dict of osds[host] = [osd.n, osd.m, ..]
    out, err = p.communicate()
    if p.returncode != 0:
        log.error('return code %d', p.returncode)
        log.error('stderr: %s', err)
        return {}
    return json.loads(out)


def get_host_and_osd_list(nodes):
    '''
    Parse JSON containing the output of osd dump's 'nodes' item:
    An array of crush nodes, 'id', 'type' 'osd' or 'host'
    If type is 'host', 'children' are child ids of osds
    
    Return a dict of osds[host] = [osd.n, osd.m, ..]
    '''
    host_to_osds = dict()
    for n in nodes:
        if n['type'] == 'host':
            # accumulate the ids first
            host_to_osds[n['name']] = list(n['children'])
        elif n['type'] == 'osd':
            # find id in hosts_to_osds osdlists, reset id to name
            for host, osdlist in host_to_osds.iteritems():
                if n['id'] in osdlist:
                    ind = host_to_osds[host].index(n['id'])
                    host_to_osds[host][ind] = n['name']

    return host_to_osds


docstr = '''
Execute a Ceph osd daemon command on every OSD in a cluster with
one connection to each OSD host.

Usage:
    osd_daemon_cmd [-c CONF] [-u USER] [-f FILE] (COMMAND | -k KEY)

Options:
   -c CONF   ceph.conf file to use [default: ./ceph.conf]
   -u USER   user to connect with ssh
   -f FILE   get names and osds from yaml
   COMMAND   command other than "config get" to execute
   -k KEY    config key to retrieve with config get <key>

Notes:
    k KEY and COMMAND are mutually exclusive.

    The format of FILE is a mapping of hostname to a list of osd names on
    that host, in the form 'osd.nn'
'''


def main():
    args = docopt.docopt(docstr)
    if args['-f']:
        host_to_osds = yaml.load(open(args['-f']))
    else:
        tree = get_osd_tree(args['-c'])['nodes']
        host_to_osds = get_host_and_osd_list(tree)

    if args['-k']:
        command = 'config get {key}'.format(key=args['-k'])
    else:
        command = args['COMMAND']

    for host, osdlist in host_to_osds.iteritems():
        print "%s:" % host
        if args['-u']:
            host = args['-u'] + '@' + host
        do_daemon_command(host, osdlist, command)


if __name__ == '__main__':
    sys.exit(main())
