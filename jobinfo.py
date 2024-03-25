#!/home/dmick/v/bin/python3 
import argparse
import datetime
fromtimestamp=datetime.datetime.fromtimestamp
import jenkins
import json
import os
import re
import sys

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", "--json", action='store_true', help="Output json")
    ap.add_argument("-P", "--allparams", action='store_true', help="Output all job parameters")
    ap.add_argument('jobre', type=str, nargs="?", default='^ceph-dev-new$', help="regexp to match job name")
    return ap.parse_args() 

def to_minsec(ms):
    totalsec = ms // 1000
    h = totalsec // 3600
    m = (totalsec - (h * 3600)) // 60
    s = totalsec - (h * 3600) - (m * 60)
    return f'{h:02d}:{m:02d}:{s:02d}'

def decruft(reason):
    '''
    Remove some cruft from lines like:
    GitHub pull request #54725 of commit 75e88727ef2bfd13bfcad68c6e60db6bf9d73364, no merge conflicts.
    '''
    cruftsubs = [
        ('GitHub pull request ', 'PR'),
        ('of commit ', ''),
        (', no merge conflicts.', ''),
        ('build number ', '#'),
    ]
    for s,r in cruftsubs:
        reason = re.sub(s, r, reason)
    return reason


def output(name, buildnum, reason, paramdict, timestr, bi, returndict=False):
    if returndict:
        outdict = {
            "buildnum": buildnum,
            "reason": reason,
            "params": paramdict,
            "started": timestr,
            "building": bi["building"],
        }
        if bi["building"]:
            outdict.update(dict(
                estimatedDuration=to_minsec(bi["estimatedDuration"])
            ))
        else:
            outdict.update(dict(
                buildtime=to_minsec(bi['duration']),
                result=bi['result'],
            ))
        return outdict

    nltab = "\n\t"
    print(f'#{buildnum}: {reason}{nltab}{nltab.join(paramdict.values())}{nltab}started: {timestr} ', end='')
    if bi['building']:
        print(f'still building, est duration {to_minsec(bi["estimatedDuration"])}')
    else: 
        print(f'took {to_minsec(bi["duration"])} {bi["result"]}')


def main():
    jenkins_user=os.environ.get('JENKINS_USER')
    jenkins_token=os.environ.get('JENKINS_TOKEN')
    j=jenkins.Jenkins('https://jenkins.ceph.com', jenkins_user, jenkins_token)

    args = parse_args()

    # jobinfo = j.get_job_info_regex(args.jobre)
    # get_job_info_regex doesn't allow passing "fetch_all_builds", so
    # recreate it here
    joblist = j.get_all_jobs()
    jobinfo = list()
    for job in joblist:
        if re.search(args.jobre, job['name']):
            jobinfo.append(j.get_job_info(job['name'], fetch_all_builds=True))


    for ji in jobinfo:
        name=ji['name']
        if args.json:
            outdict = dict(name=name, builds=list())
        for build in ji['builds']:
            buildnum = build['number']
            bi = j.get_build_info(name, buildnum)
            '''
            example CauseAction in actions[]:
            {'_class': 'hudson.model.CauseAction',
             'causes': [{'_class': 'org.jenkinsci.plugins.ghprb.GhprbCause',
                 'shortDescription': 'GitHub pull request #56203 of commit '
                                     'ab4c5daead7f26d41028625453d50bb58d3b02be,'
                                     ' no merge conflicts.'}]}
            '''
            reason = "??"
            paramnames = list()
            paramdict=dict()
            for act in bi['actions']:
                cls = act.get('_class', None)
                if cls == 'hudson.model.CauseAction':
                    if len(act['causes']) > 1:
                        print(f'{name} #{buildnum} has more than one cause?', file=sys.stderr)
                    reason = act['causes'][0]['shortDescription']
                if cls and cls.endswith('ParametersAction'):
                    params = act['parameters']
                    pois = ['BRANCH', 'ARCHS', 'DISTROS', 'FLAVOR']
                    for param in params:
                        paramnames.append(param['name'])
                        if args.allparams or param['name'] in pois:
                            paramdict[param['name']] = param['value']
            reason = decruft(reason)
            timestr = fromtimestamp(bi['timestamp'] / 1000).strftime('%d %b %H:%M:%S')
            if args.json:
                outdict['builds'].append(output(name, buildnum, reason, paramdict, timestr, bi, returndict=True))
            else:
                output(name, buildnum, reason, paramdict, timestr, bi, returndict=False)
    if args.json:
        print(json.dumps(outdict))

if __name__ == "__main__":
    sys.exit(main())
