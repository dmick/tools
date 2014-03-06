#!/usr/bin/env python
'''
syms.py: take a collection of object files and, for each public symbol,
identify the definer and the users of that symbol (if there are any;
if there are no uses, don't output the symbol unless -U/--unused is 
given.)
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
parser.add_argument('--definer', nargs='+', help='look for symbols defined only in these files')
parser.add_argument('--user', nargs='+', help='look for symbols used only by these files')
parser.add_argument('-u', '--unused', action='store_true', help='show defined-but-unused symbols')
parser.add_argument('filenames', nargs='*')
args = parser.parse_args()
maxlen = 0

allfiles = args.definer + args.user + args.filenames
if args.definer: print "definers: ", args.definer
if args.user: print "users: ", args.user

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
        # any spaces between () to '?', split, change back.
        groups = re.search('\((.*)\)', l)
        new = None
        if groups:
            orig = groups.group(0)
            new = orig.replace(' ', '?')
            l.replace(orig, new)
        words = l.split()
        if new and new in words[0]:
            words[0].replace(new, orig)
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

print 'sym\tdefined in\tused by'
for sym in sorted(defines.iterkeys()):
    if len(defines[sym]) > 1:
        print '*** odd: sym {} multiply defined ***'.format(sym)
    if not uses[sym] and not args.unused:
        continue
    print '{sym:40}\t{defined_in:20}\t{used_by}\t'.format(
        sym=sym,
        defined_in=defines[sym][0],
        used_by=','.join(uses[sym]) if uses[sym] else 'UNUSED'
    )
