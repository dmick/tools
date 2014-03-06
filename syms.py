#!/usr/bin/env python
# vim: ts=4 sw=4 expandtab
'''
syms.py: take a collection of object files and, for each public symbol,
identify the definer and the users of that symbol (if there are any).
'''

import argparse
import collections
import re
import subprocess

DEFINES = 'ABCDGRSTVW'
USES = 'U'
# -C: demangle C++ symbols
# -f posix: set output format to a more-parseable one
NM_ARGS = ['nm', '-C', '-o', '-f', 'posix']

defines = collections.defaultdict(list)
uses = collections.defaultdict(list)

parser = argparse.ArgumentParser()
parser.add_argument('--definer', nargs='+',
    help='look for symbols defined only in these files')
parser.add_argument('--user', nargs='+',
    help='look for symbols used only by these files')
parser.add_argument('-U', '--used', action='store_true',
    help='show defined-and-used symbols')
parser.add_argument('-u', '--unused', action='store_true',
    help='show defined-but-unused symbols')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('filenames', nargs='*')
args = parser.parse_args()
maxlen = 0

allfiles = args.filenames
if args.definer:
    allfiles += args.definer
if args.user:
    allfiles += args.user

if args.verbose:
    if args.definer: print "definers: ", args.definer
    if args.user: print "users: ", args.user
    print "files to check: ", allfiles

if not args.used and not args.unused:
    print >> sys.stderr, 'Should select either -U or -u'

for name in allfiles:
    nmargs = NM_ARGS[:]
    # use dynamic symbols for .so's
    if '.so' in name:
        nmargs.append('-D')
    nm_output = subprocess.check_output(nmargs + [name])
    for l in nm_output.split('\n'):
        if not l:
            continue
        # try to handle symbols-with-embedded-single-space: change
        # any spaces between () to '_', split, change back.
        groups = re.search('\((.*)\)', l)
        new = None
        if groups:
            if args.verbose:
                print 'replace hack: groups.group(0) {}'.format(groups.group(0))
            orig = groups.group(0)
            new = orig.replace(' ', '_')
            l = l.replace(orig, new)
        words = l.split()
        if new:
            words = [w.replace(new, orig) for w in words]
        if args.verbose:
            print '    l: "{}"\nwords: {}'.format(l, words)
        filename, sym, symtype = words[:3]
        filename = filename.rstrip(':')
        filename_only = filename
        pos = filename.find('[')
        if pos > 0:
            filename_only = filename[:pos]

        if symtype in DEFINES:
            if args.definer and filename_only in args.definer:
                if sym not in defines:
                    defines[sym].append(filename)
        elif symtype in USES:
            if args.user and filename_only in args.user:
                uses[sym].append(filename)

def printsyms(defines, uses, used=True):
    if used:
        fmt = '{sym}\t{defined_in}\t{used_by}'
    else:
        fmt ='{sym}\t{defined_in}\tUNUSED'

    for sym in sorted(defines.iterkeys()) :
        if (used and uses[sym]) or (not used and not uses[sym]):
            print fmt.format(sym=sym,
                             defined_in=defines[sym][0],
                             used_by=','.join(uses[sym])
                            )


if args.used:
    print '\nUSED SYMBOLS: (sym  definer  user)\n'
    printsyms(defines, uses, used=True)

if args.unused:
    print '\nUNUSED SYMBOLS: (sym  definer)\n'
    printsyms(defines, uses, used=False)
