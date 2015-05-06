#!/usr/bin/env python

import sys
import os
import subprocess

checked = set()
level = -1
requirements = []
ignore_stop = ['glibc', 'coreutils']

def finddeps(pkglist):
    global checked, level, requirements
    level += 1
    for pkg in pkglist:
        if pkg in checked:
            level -= 1
            return
        checked.add(pkg)
        proc = subprocess.Popen(
            "rpm -q --requires {0} | awk '{{print $1;}}'".format(pkg),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate()
        capabilities = out.split()
        capabilities = set(c for c in capabilities if c != '' and '(' not in c)
        required_by = set()
        for cap in capabilities:
            proc = subprocess.Popen(
                "rpm -q --whatprovides {0} | sed 's/(.*//'".format(cap),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, err = proc.communicate()
            req = out.strip()
            if 'no package provides' in req:
                continue
            required_by.add(req)

        for req in required_by:
            # don't count self
            if req == pkg:
                continue
            # skip already found reqs (only record first requirer)
            if req in (t[1] for t in requirements):
                continue
            # ignore any "ignore_stop" packages and stop recursing
            ignoreit = False
            for ignore in ignore_stop:
                if req.startswith(ignore):
                    ignoreit = True
                    break
            if ignoreit:
                continue

            requirements.append((pkg, req, level))
            finddeps([req])
    level -= 1

finddeps(sys.argv[1:])

for pkg, req, level in requirements:
    print '  ' * level, pkg, '->', req

