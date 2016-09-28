'''
jenkins_api.py: read Jenkins build artifacts using jenkinsapi

This is meant to replace the older method of sftp/searching.  It's still
not perfect; jenkinsapi doesn't necessarily give access to everything
we'd like, but it should be at least as good, while being less
sensitive to the exact structure of the Jenkins filesystem, and
also adding the capability to get all files for a specific job, whether
or not they are package files.

fetch_job_output(url, jobname, distrover=None, archs=None, branch=None,
onlypkgs=True, path='.') is the entry point.  Its strategy: Look for
builds of 'jobname' at 'url' which match arch, dist, and branch
(if given, or DEFAULT_ARCHES, any dist, and any branch if not).
If a build matches, check if it was successful.  If so, fetch
the artifacts from the build, possibly only the packages
(if onlypkgs is True), using http, and store them in 'path'.
If no suitable artifacts are found, raise an exception.

There is a test main program for experimentation.
'''
import getpass
import logging
import os
import re
import requests
import shutil
import time

from jenkinsapi.constants import STATUS_SUCCESS
from jenkinsapi.jenkins import Jenkins

log = logging.getLogger(__name__)
# shaddap, you
logging.getLogger('requests.packages.urllib3.connectionpool').\
    setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').\
    setLevel(logging.WARNING)

JENKINS_USER = os.environ.get('JENKINS_API_USER') or getpass.getuser()
JENKINS_PASS = os.environ.get('JENKINS_API_TOKEN')

# these will appear in the environment of matrix jobs; they are
# labels of the axes of multiple-configuration setups.  It would
# certainly be nice if they were single values and not lists.
ARCHTAGS = ['Arch', 'arch']
DISTTAGS = ['dist', 'Dist', 'Distro']

# if no arch is specified, accept either of these
DEFAULT_ARCHES = ['x86_64', 'noarch']


def jenkins_url(host):
    return 'http://{0}'.format(host)


def _filter_archs(artifacts, archs=None):
    '''
    Return a subset of 'artifacts' containing only those who match an
    arch in 'archs'.  'match' means: appears after ARCHTAG in the URL,
    or, if 'noarch' is in archs, whose URL doesn't mention any ARCHTAG,
    implying they are noarch.

    :param artifacts: full list of artifacts
    :param archs: arch values to search for (default to DEFAULT_ARCHS)
    :return: filtered list of artifacts
    '''
    # have all artifacts; filter for arch by looking in url path
    if archs is None:
        archs = DEFAULT_ARCHES
    filtered = []
    for arch in archs:
        for archtag in ARCHTAGS:
            filtered.extend([a for a in artifacts
                             if '{}={}'.format(archtag, arch) in a.url])
            log.debug('filter arches: archtag %s: list now %s',
                      archtag, filtered)
        if arch == 'noarch':
            # add any artifacts that have no {ARCHTAGS}= in their URLs at all
            noarch_arts = [a for a in artifacts
                           if not any([t + '=' in a.url for t in ARCHTAGS])]
            log.debug('_filter_archs: adding noarch artifacts %s', noarch_arts)
            filtered.extend(noarch_arts)

    log.debug('_filter_archs: returning %s', filtered)
    return filtered


def _successful(build):
    return build.get_status() == STATUS_SUCCESS


def _set_branch(build):
    '''
    See if build has a BRANCH parameter; set an attribute
    '''
    build.branch = None
    if 'parameters' not in build.get_actions():
        return
    for paramdict in build.get_actions()['parameters']:
        if paramdict['name'] == 'BRANCH' or paramdict['name'] == 'DESCRIPTION_SETTER_DESCRIPTION':
            build.branch = paramdict['value']
            log.debug('%s: branch %s', build.lname, build.branch)
            return


def _get_build_envvars(build):
    '''
    Return a dict of var:value for the 'injected environment variables',
    if present (and an empty dict if not)
    '''
    envvars = dict()
    try:
        resp = requests.get(
            build._data['url'] + 'injectedEnvVars/export',
            headers={'Accept': 'application/json'},
        )
        resp.raise_for_status()
        # {['envVars']['envVar'][{'name': 'value':}]}? seriously?
        for vardict in resp.json()['envVars']['envVar']:
            envvars[vardict['name']] = vardict['value']
    except:
        pass
    return envvars


def _match_env(build):
    '''
    Look for all the permutations of arch and dist envvars; return
    a tuple of arch, dist where each is a match or None
    '''
    env = _get_build_envvars(build)
    for archtag in ARCHTAGS:
        buildarch = env.get(archtag, None)
        if buildarch:
            break
    for disttag in DISTTAGS:
        builddist = env.get(disttag, None)
        if builddist:
            break
    return buildarch, builddist


def _match_gitbuilder_name(name):
    '''
    This is a horrible hack to attempt to extract a build arch and
    build dist from the only piece of information we have: the
    name of the gitbuilder slave the build ran on (for, say,
    radosgw-agent builds).  *Really* need to get metainfo tags on
    builds.  Return a tuple as above: (arch, dist) where either may be None
    '''
    dists = set([
        'rhel6', 'rhel7', 'centos6', 'centos7', 'precise', 'trusty', 'wheezy'
    ])
    archs = set(['amd64', 'i386'])
    archmap = {'amd64': 'x86_64'}

    builddist = buildarch = None

    # first translate rhel6-4 to rhel6.4 (et. al.) for all the dists
    # that end in a digit
    for distmajor in [d for d in dists if re.match('\w+\d$', d)]:
        mo = re.search(distmajor + '-(\d)', name)
        if mo:
            # at this point we've found builddist
            builddist = distmajor + '.' + mo.group(1)

    for namepiece in name.split('-'):
        if not builddist and namepiece in dists:
            builddist = namepiece
        elif namepiece in archs:
            buildarch = archmap.get(namepiece, namepiece)
    return buildarch, builddist


def _has_arch_distrover(build, arch, distrover, is_matrix):
    '''
    Return True if build is for arch/distrover, somewhat heuristically
    '''
    # first, look at the env vars DIST and ARCH
    build.arch, build.dist = _match_env(build)
    if build.dist and build.arch:
        log.debug('%s: from env: %s:%s', build.lname, build.arch, build.dist)
    else:
        buildsplit = str(build).split()
        if is_matrix:
            # 'jobname Unicodechar label[,label...] #buildno'
            # this might not be super-robust.
            if len(buildsplit) == 4:
                name, _, archdist, number = buildsplit
            archsplit = archdist.split(',')
            if len(archsplit) == 2:
                if build.arch is None:
                    build.arch = archsplit[0]
                if build.dist is None:
                    build.dist = archsplit[1]
            elif build._data['builtOn'].startswith('gitbuilder-'):
                build.arch, build.dist = \
                    _match_gitbuilder_name(build._data['builtOn'])
            log.debug('%s: matrix build %s:%s', build.lname, build.arch, build.dist)
        else:
            # Not a matrix build.  uhhh...do what we can to infer it
            if len(buildsplit) == 2:
                name, number = str(build).split()
                # does it look like this is a calamari build?
                mo = re.match('calamari-\w+-(\w+)', name)
                if mo:
                    build.dist = mo.groups()[0]
                    build.arch = 'x86_64'
                    log.debug('%s: calamari build %s:%s',
                              build.lname, build.arch, build.dist)
    # I'm out of ideas
    if not (build.dist and build.arch):
        log.debug('%s: no dist/arch found', build.lname)
        return False

    # allow arch or distrover to be None, and not affect the match if so
    retval = True
    if arch:
        retval = (build.arch == arch)
    if distrover:
        retval = retval and (
            # some ceph builds use <dist>-pbuild as DIST.  IWBNI
            # we could always put the real dist, say, in the environment.
            build.dist == distrover or build.dist == distrover + '-pbuild'
        )

    return retval


def _build_matches(build, arch, distrover, branch, is_matrix=False):
    '''
    Return True if this build matches arch/distrover/optional branch
    Comparison changes for matrix builds vs. non-matrix builds
    '''
    return (
        _has_arch_distrover(build, arch, distrover, is_matrix) and
        (branch is None or build.branch == branch)
    )


def _matching_builds(url, jobname, arch, distrover, branch=None):
    '''
    Iterator: return builds of jobname, in newest-first order, that
    match arch/distrover/optional branch (if there are any).
    '''
    job = Jenkins(
        url,
        username=JENKINS_USER,
        password=JENKINS_PASS,
    )[jobname]
    # get_build_ids() returns in newest-to-oldest order
    for buildno in job.get_build_ids():
        build = job.get_build(buildno)
        build.lname = str(build).decode('utf-8', 'ignore')
        _set_branch(build)
        # set dist and arch later in the horrible _has_arch_distrover

        # if it's a matrix build, search the runs; if not, search parent.
        for run in build.get_matrix_runs():
            run.lname = str(run).decode('utf-8', 'ignore')
            _set_branch(run)
            if _build_matches(run, arch, distrover, branch, is_matrix=True):
                yield run
        else:
            if _build_matches(build, arch, distrover, branch, is_matrix=False):
                yield build

    raise StopIteration


def _find_matching_good_build(url, jobname, arch, distrover, branch=None):
    '''
    Return _matching_builds() filtering for successful builds
    '''
    for build in _matching_builds(url, jobname, arch, distrover, branch):
        if _successful(build):
            tag=None
            for disttag in DISTTAGS:
                val = _get_build_envvars(build).get(disttag, None)
                if val:
                    tag = disttag
                    break
            log.info(
                "%s %s=%s",
                str(build).decode('utf-8'), tag, val
            )
            yield build
        log.debug('%s: not successful', build.lname)
    raise StopIteration


def _get_job_artifacts(host, jobname, distrover=None, arch=None, branch=None,
                       limit=None, onlypkgs=True, path='.', match_jobname=False):
    url = jenkins_url(host)

    all_artifacts = []
    discovered = {}
    for build in _find_matching_good_build(url, jobname, arch, distrover, branch):
        buildkey = (build.arch, build.dist, build.branch)
        if buildkey in discovered:
            log.debug(
                '{}, {}, {}: skipping #{}, already have #{}'.format(
                    build.arch, build.dist, build.branch, build.buildno,
                    discovered[buildkey].buildno
                )
            )
            continue

        discovered[buildkey] = build

        log.info('FOUND %s branch %s built %s', build.lname, build.branch,
                 time.ctime(build._data['timestamp'] / 1000))
        artifacts = [a for a in build.get_artifacts()]
        if onlypkgs:
            artifacts = [a for a in artifacts if a.url.endswith('rpm') or a.url.endswith('deb')]
        artifacts = _filter_archs(artifacts, ('x86_64', 'noarch'))
        if match_jobname:
            artifacts = [a for a in artifacts if a.filename.startswith(jobname)]
        all_artifacts.extend(artifacts)
        # if we got anything, and we've completely specified, we can
        # be done now
        if all_artifacts and distrover and arch and branch:
            break
        if limit is not None and len(discovered) == int(limit):
            break
    return all_artifacts


def fetch_job_output(host, jobname, distrover=None, arch='x86_64', branch=None,
                     onlypkgs=True, path='.', match_jobname=False):
    '''
    Get latest packages from build artifacts from jobname for distrover;
    store at path.  Raise exception if a suitable build is not found.
    :param host: Jenkins server (anonymous API access assumed)
    :param jobname: name of Jenkins job
    :param distrover: distro and version: centos6.4, trusty, etc.
           If distrover is none, don't try filtering for it, and fetch
           all artifacts.  This is to handle Jenkins jobs that don't
           have multiconfiguration, but imply distroversion by the
           job name
    :param arch: architecture
    :param onlypkgs: if true, return only 'rpm' or 'deb' files
    :param path: local path to store package files
    :return: disttype (debian or rpm)
    '''
    log.info("get_job_output(%s, %s, %s, %s, %s)",
             host, jobname, distrover, arch, path)
    requests_getargs = {
        'allow_redirects': True,
        'stream': True,
    }
    artifacts = _get_job_artifacts(host, jobname, distrover, arch,
                                   branch, onlypkgs, path, match_jobname=match_jobname)
    if not artifacts:
        msg = ('Job {jobname} for {distrover}, {arch}, {branch} '
               'not found on {host}').format(
                   jobname=jobname,
                   distrover=distrover,
                   arch=arch,
                   branch=branch,
                   host=host
        )
        raise RuntimeError(msg)

    disttype = 'debian'
    for a in artifacts:
        log.debug('Fetch %s', a.url)
        response = requests.get(a.url, **requests_getargs)
        response.raise_for_status()
        with open(os.path.join(path, a.filename), 'w') as f:
            shutil.copyfileobj(response.raw, f)
        if a.url.endswith('rpm'):
            disttype = 'rpm'

    return disttype


docstr = '''
Usage: {progname} [--host JENKINS] --jobname JOBNAME [--arch ARCH] [--distrover DISTROVER]
       [--branch BRANCH] [--limit LIMIT] [--onlypkgs] (--path OUTPUT | --list) [--verbose]

Get packages from Jenkins server

Options:
  --host, -h JENKINS         Jenkins host
                             [default: jenkins.ceph.com]
  --jobname, -j JOBNAME      Jenkins job name
  --arch, -a ARCH            Architecture [default: x86_64]
  --distrover, -d DISTROVER  Distro and version
  --branch, -b BRANCH        Branch to fetch (value of build param BRANCH)
  --limit, -L LIMIT          Limit number of good builds (useful for speedier listing)
  --onlypkgs                 Fetch only rpm/deb [default: False]
  --list, -l                 List artifact urls, do not retrieve
  --path, -p OUTPUT          Output path for retrieved artifacts [default: .]
  --verbose, -v              Show all your work
'''


def main():
    import docopt
    import os
    import sys
    logging.basicConfig(level=logging.INFO)

    global docstr
    docstr = docstr.format(progname=sys.argv[0].split(os.sep)[-1])
    args = docopt.docopt(docstr)
    args = {k.replace('--', ''): v for k, v in args.iteritems()}
    if args['verbose']:
        log.setLevel(logging.DEBUG)
    args.pop('verbose')
    do_list = args.pop('list')
    if do_list:
        for a in _get_job_artifacts(**args):
            print a.url
        sys.exit(0)
    fetch_job_output(**args)

if __name__ == '__main__':
    main()
