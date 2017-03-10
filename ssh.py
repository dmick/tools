#!/usr/bin/env python

import os
import logging
import paramiko
import socket
import sys
import time


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def ssh_cmd(host, cmd):

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        user, host = host.split('@')
    except ValueError:
        user = None

    try:
        client.connect(host, username=user, timeout=15)
    except paramiko.SSHException:
        log.error("Can't connect to %s", host)
        return
    except socket.error as v:
        log.error("Can't connect to %s: %s", host, v)
        return

    try:
        _, out, err = client.exec_command(cmd)
    except paramiko.SSHException:
        log.exception("Paramiko SSH error contacting %s", host)
        return
    start = time.time()
    while not out.channel.exit_status_ready():
        log.info('waiting for exit, elapsed: %4.2f', time.time() - start)
        time.sleep(0.5)
    rc = out.channel.recv_exit_status()
    if rc != 0:
        log.error("return code: %s", rc)
        log.error("stderr: %s", err.read())
        return

    out = out.read()
    log.info(out)

if __name__ == '__main__':
    ssh_cmd(sys.argv[1], ' '.join(sys.argv[2:]))
