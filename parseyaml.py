#!/usr/bin/python3
import argparse
import json
import sys
import yaml
import pprint

# it seems as though this method only allows mapping types.  If it can
# do sequence types I haven't figured out how.
'''
class IncludeRaw(yaml.YAMLObject):
    yaml_tag = u'!include-raw-escape:'

    def __init__(self, data):
        self.list = data

    def __repr__(self):
        return f'!include-raw-escape: {self.list}'

'''

# stuff for yaml encoding, to handle !include-raw-*

class IncludeRaw(object):
    def __init__(self, t, l):
        self.t = t
        self.l = l

    def __repr__(self):
        return f'{self.t.replace('!','')} {self.l}'

# apparently this is never called.  ?
#def include_raw_representer(dumper, data):
#    return dumper.represent_sequence('AAAAAAAAAAAA !include-raw-escape:', data)

def include_raw_constructor(loader, node):
    breakpoint()
    value = loader.construct_sequence(node)
    return IncludeRaw(node.tag, value)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--json', action='store_true', help="output json")
    ap.add_argument('infile', nargs='*',  help="input filename (stdin if not supplied")
    return ap.parse_args()

# for json encoding of the IncludeRaw type

class IncludeRawEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, IncludeRaw):
            return str(obj)
        return super().default(obj)

def main():
    args = parse_args()
    yaml.add_constructor('!include-raw:', include_raw_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor('!include-raw-escape:', include_raw_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor('!include-raw-verbatim:', include_raw_constructor, Loader=yaml.SafeLoader)
    # yaml.add_representer(IncludeRaw, include_raw_representer)
    if args.infile:
        data = yaml.safe_load(open(args.infile[0], 'rb'))
    else:
        data = yaml.safe_load(sys.stdin)

    if args.json:
        print(json.dumps(data, indent=2, cls=IncludeRawEncoder))
    else:
        pprint.pprint(data)


if __name__ == '__main__':
    sys.exit(main())
