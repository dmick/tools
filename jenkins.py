#!/usr/bin/env python
import logging
import os
import requests
import sys


'''
https://{server}/job/{jobname}/api/json

['builds']:  array of dicts
  ['number']: buildnum
  ['url']: https://{server}/job/{jobname}/{buildnum}


https://{server}/job/{jobname}/{buildnum}/api/json

['result']: 'SUCCESS' etc.
['id']: '<buildnum>'
['builtON']: slave name
['actions']['parameters']: array of dicts
    if ['actions']['class'] is for ghprb:
    name: 'ghprbActualCommit', 'value': <sha1>
    name: 'ghrpbActualCommitAuthorEmail', value: <ghemail>
    name: 'ghrpbPullAuthorLogin', value: <ghusername>
    name: 'ghprbPullLink', value: <PR url>
    name: 'ghprbLongDescription', value: <PR description>
    name: 'ghprbPullTitle', value: PR title
'''

SERVER = 'jenkins.ceph.com'
WHITELIST = '~/.jenkins.whitelist'

JOB_TEMPLATE = 'https://{server}/job/{jobname}/api/json'
BUILD_TEMPLATE = 'https://{server}/job/{jobname}/{buildnum}/api/json'
PARAMS_OF_INTEREST = [
    'ghprbActualCommit',
    'ghrpbActualCommitAuthorEmail',
    'ghrpbPullAuthorLogin',
    'ghprbPullLink',
    'ghprbLongDescription',
    'ghprbPullTitle',
]


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# We don't need to see log entries for each connection opened
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(
    logging.WARN)
# if requests doesn't bundle it, shut it up anyway
logging.getLogger('urllib3.connectionpool').setLevel(
    logging.WARN)


def fetch_job(server, job):
    r = requests.get(JOB_TEMPLATE.format(server=server, jobname=job))
    r.raise_for_status()
    job = r.json()
    return dict(builds=job['builds'])


def fetch_build(server, job, build):
    r = requests.get(BUILD_TEMPLATE.format(server=server, jobname=job, buildnum=build))
    r.raise_for_status()
    build = r.json()
    if build['building']:
        return dict(building=True, id=build['id'], result='IN_PROGRESS')

    retdict = dict(
        building=False,
        result=build['result'],
        id=build['id'],
        builtOn=build['builtOn'],
    )
    for action in build['actions']:
        if '_class' not in action:
            continue
        if 'GhprbParametersAction' not in action['_class']:
            continue
        for param in action['parameters']:
            if param['name'] in PARAMS_OF_INTEREST:
                retdict[param['name']] = param['value']
    return retdict


def read_whitelist(wlpath):
    # format: jobname buildid
    whitelist = []
    for l in open(wlpath, 'r'):
        whitelist.append(tuple(l.split()))
    return whitelist


def valid_buildinfo(jobinfo):
    if 'buildinfo' not in jobinfo:
        return None
    buildinfo = jobinfo['buildinfo']
    if buildinfo['result'] == 'IN_PROGRESS':
        return None
    return buildinfo


def main(args):
    job = {}
    if len(args) < 2:
        jobnames = ['ceph-pull-requests', 'ceph-pull-requests-arm64']
    else:
        jobnames = args[1:]

    # snarf the whitelist file
    whitelist = read_whitelist(
        os.path.expanduser(WHITELIST)
    )
    # slurp it all up
    for jobname in jobnames:
        count = 0
        job[jobname] = fetch_job(SERVER, jobname)
        for jobbuildinfo in job[jobname]['builds']:
            buildnum = jobbuildinfo['number']
            buildinfo = fetch_build(SERVER, jobname, buildnum)
            jobbuildinfo['buildinfo'] = fetch_build(SERVER, jobname, buildnum)
            log.debug('%s %s %s' % (jobname, buildinfo['id'], buildinfo['result']))
            count += 1
        log.debug('fetched %d builds from %s ' % (count, jobname))

    firstjobname = jobnames[0]
    for firstjobinfo in job[firstjobname]['builds']:
        firstbuildinfo = valid_buildinfo(firstjobinfo)
        if not firstbuildinfo:
            continue
        firstbuildnum = firstbuildinfo['id']
        if (firstjobname, firstbuildnum) in whitelist:
            log.debug('whitelisted %s #%s, skipping' % (firstjobname, firstbuildnum))
            continue
        for jobname in jobnames[1:]:
            for jobinfo in job[jobname]['builds']:
                buildinfo = valid_buildinfo(jobinfo)
                if not buildinfo:
                    continue
                buildnum = buildinfo['id']
                if (jobname, buildnum) in whitelist:
                    log.debug('whitelisted %s #%s, skipping' % (jobname, buildnum))
                    continue
                log.debug("comparing %s:%s and %s:%s" % (
                    firstjobname, firstbuildnum,
                    jobname, buildnum
                ))
                if firstbuildinfo['ghprbActualCommit'] == buildinfo['ghprbActualCommit']:
                    if firstbuildinfo['result'] == 'SUCCESS' and buildinfo['result'] != 'SUCCESS':
                        log.warning(
                            '{sha1:.8s}:: {job1} #{build1}: {res1}   {jobn} #{buildn}: {resn}'.format(
                                sha1=firstbuildinfo['ghprbActualCommit'],
                                job1=firstjobname,
                                build1=firstbuildnum,
                                res1=firstbuildinfo['result'],
                                jobn=jobname,
                                buildn=buildnum,
                                resn=buildinfo['result']
                            )
                        )


if __name__ == '__main__':
    sys.exit(main(sys.argv))
