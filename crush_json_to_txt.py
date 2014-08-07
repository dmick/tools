#!/usr/bin/env python
'''
Translate 'ceph osd crush dump' output into a crushmap text file
suitable for compilation with crushtool -c.

Invoke with the name of the crush dump output file; output comes
to stdout.
'''

import json
import sys

# for sorting, to identify leaf buckets
deviceids = []

def print_tunables(m):
    for k,v in m['tunables'].iteritems():
        print 'tunable %s %d' % (k, v)
    print


def print_devices(crushmap):
    print '# devices'
    for d in crushmap['devices']:
        print 'device %d %s' % (d['id'], d['name'])
    global deviceids
    deviceids.append(d['id'])
    print


def print_types(crushmap):
    print '# types'
    for t in crushmap['types']:
        print 'type %d %s' % (t['type_id'], t['name'])
    print


def add_item_names(crushmap, itemname):
    ''' accumulate bucket/device item id/name mappings from m['buckets'] '''
    for bucket in crushmap['buckets']:
        itemname[bucket['id']] = bucket['name']
    for d in crushmap['devices']:
        itemname[d['id']] = d['name']


def print_buckets(crushmap, itemname):

    hash_str_to_id = {
        'rjenkins1': 0,
    }

    def scale(w):
        return float(w) / 65536.0

    def bucket_compare(a, b):
        ''' compare for bucket topological sort '''

        def alldevs(deps):
            # nodes with only dev dependents sort later
            global deviceids
            return all([i in deviceids for i in deps])

        adeps = [item['id'] for item in a['items']]
        bdeps = [item['id'] for item in b['items']]
        if a['id'] in bdeps:
            # b depends on a: a < b
            return -1
        if b['id'] in adeps:
            # a depends on b: a > b
            return 1
        if alldevs(adeps) and not alldevs(bdeps):
            # a is a leaf, b is not, a < b
            return -1
        if alldevs(bdeps) and not alldevs(adeps):
            # b is a leaf, a is not, a > b
            return 1
        # neither or both nodes are leaves, and neither depends on the other
        # ...order by id
        return cmp(a['id'], b['id'])

    print '# buckets'
    # sort in id numerical order so there are no forward id references
    for b in sorted(crushmap['buckets'], cmp=bucket_compare):
        print '%s %s {' % (b['type_name'], b['name'])
        print '\tid %d\t\t# do not change unnecessarily' % b['id']
        print '\t# weight %.3f' % scale(b['weight'])
        print '\talg %s' % b['alg']
        print '\thash %d\t# %s' % (hash_str_to_id[b['hash']], b['hash'])
        for item in sorted(b['items'], key=lambda item: item['pos']):
            print '\titem %s weight %.3f' % (
                itemname[item['id']],
                scale(item['weight']),
            )
        print '}'
    print


def print_rules(crushmap, itemname):
    rule_id_to_str = {
        1: 'replicated',
        2: 'raid4',
        3: 'erasure',
    }

    step_op_to_fmtstr = {
        'noop': 'noop',
        'take': 'take {item}',
        'emit': 'emit',
        'choose_firstn': 'choose firstn {num} type {type}',
        'choose_indep': 'choose indep {num} type {type}',
        'chooseleaf_firstn': 'chooseleaf firstn {num} type {type}',
        'chooseleaf_indep': 'chooseleaf indep {num} type {type}',
        'set_choose_tries': 'set choose tries {num}',
        'set_chooseleaf_tries': 'set chooseleaf tries {num}',
    }

    print '# rules'
    for r in crushmap['rules']:
        print 'rule %s {' % r['rule_name']
        print '\truleset %d' % r['ruleset']
        print '\ttype %s' % rule_id_to_str[r['type']]
        print '\tmin_size %d' % r['min_size']
        print '\tmax_size %d' % r['max_size']
        for step in r['steps']:
            # translate item id to name
            if 'item' in step:
                step['item'] = itemname[step['item']]
            opfmt = step_op_to_fmtstr[step['op']]
            print '\tstep', opfmt.format(**step)
        print '}'
    print


def main():
    # error checking!
    crushmap = json.load(open(sys.argv[1]))
    itemname = {}
    add_item_names(crushmap, itemname)

    print '# begin crush map'

    print_tunables(crushmap)
    print_devices(crushmap)
    print_types(crushmap)
    print_buckets(crushmap, itemname)
    print_rules(crushmap, itemname)

    print '# end crush map'
    return 0


if __name__ == '__main__':
    sys.exit(main())
