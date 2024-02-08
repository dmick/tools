#!/usr/bin/python3

import argparse
import os
import sys
import re
import requests


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-l', '--list', action='store_true', help="Output comma-separated list of nodes")
    ap.add_argument('-o', '--offline', action='store_true', help="Print offline hosts as well (marked OFFLINE)")
    ap.add_argument('-O', '--onlyoffline', action='store_true', help="Print only offline hosts")
    ap.add_argument('-t', '--tags', nargs='*', help="tags to search for (any present)")
    ap.add_argument('-T', '--alltags', nargs='*', help="tags to search for (all present)")
    ap.add_argument('-n', '--negative', action='store_true', help="negate -t or -T (none of these tags present or these specific tags not present together")
    ap.add_argument('-d', '--delimiter', help="char to separate tags in output", default=',')
    ap.add_argument('-g', '--group', action="store_true", help="format for jenkins group vars")

    return ap.parse_args()


def intersection(list1, list2):
   '''
   list1 is a list of REs; search for a full match for each RE
   in each member of list2, and return the members that match
   (fully)

   >>> intersection(['foo', 'bar'], ['foobar', 'foobaz'])
   []
   >>> intersection(['foo.*', 'bar'], ['foobar', 'foobaz'])
   ['foobar', 'foobaz']
   >>> intersection(['.*baz', '.*bar'], ['foobar', 'foobaz'])
   ['foobar', 'foobaz']
   '''
   return [l2 for l2 in list2 if [l1 for l1 in list1 if re.fullmatch(l1, l2)]] 


def one_for_one(list1, list2):
    '''
    Does list1 of patterns match list2 in at least one match per 
    pattern?
    '''
    for pat in list1:
        count = len([l2 for l2 in list2 if re.fullmatch(pat, l2)])
        if count < 1:
            return False
    return True


def expand_csv_to_list(l):
    newl = l
    if l and len(l) == 1 and ',' in l[0]:
        newl = l[0].split(',')
    return newl


def main():
    host = os.environ.get('JENKINS_HOST', 'jenkins.ceph.com')

    args = parse_args()
    res = requests.get(f'https://{host}/computer/api/json')
    res.raise_for_status()
    nodes = res.json()
    hosts = []
    for host in nodes['computer']:
        if host['_class'] != 'hudson.slaves.SlaveComputer':
            continue
        if not (args.offline or args.onlyoffline or args.group) and host['offline']:
            continue
        if args.onlyoffline and not host['offline']:
            continue

        tags = list()
        for d in host['assignedLabels']:
            tags.extend([v for k,v in d.items()])
        tags = sorted(tags)

        args.tags = expand_csv_to_list(args.tags)
        args.alltags = expand_csv_to_list(args.alltags)

        if not args.negative:
            # skip if tags don't contain any of the requested tags
            if args.tags and not intersection(args.tags, tags):
                continue

            # skip if tags don't contain all of the requested tags
            if args.alltags:
                i = intersection(args.alltags, tags)
                if not one_for_one(args.alltags, i):
                    continue
        else:
            # skip if tags contain any of the requested tags
            if args.tags and intersection(args.tags, tags):
                continue

            # skip if tags contain all of the requested tags
            if args.alltags:
                i = intersection(args.alltags, tags)
                if one_for_one(args.alltags, i):
                    continue


        name = host['displayName']
        # don't output the IP addr
        if '+' in name:
            name = name[name.index('+')+1:]

        hosts.append({"name": name, "offline": host['offline'], "tags": tags})

    if args.list:
        print(args.delimiter.join([host['name'] for host in hosts]))
    elif args.group:
        for host in hosts:
            name = host["name"] if '.' in host["name"] else f'{host["name"]}.front.sepia.ceph.com'
            tags = host["tags"]
            print(f'{name}: \"{" ".join(tags)}\"')
    else:
        for host in hosts:
            print(f'{host["name"]}: {args.delimiter.join(host["tags"])} {"OFFLINE" if host["offline"] else ""}')


if __name__ == "__main__":
    sys.exit(main())
