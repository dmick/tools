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

class Include(object):
    def __init__(self, t, l):
        # PyYAML wants the ':' in the tag; no one else does
        self.t = t.replace(':', '')
        self.l = l

    def __repr__(self):
        return f'{self.t}: {self.l}'

# apparently this is never called.  ?  not sure how I'd get the tag
# anyway
#def include_representer(dumper, data):
#    return dumper.represent_sequence('<tag here>', data)

def include_constructor(loader, node):

    # it feels dirty using ScalarNode and SequenceNode but...

    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value=loader.construct_sequence(node)
    return Include(node.tag, value)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--json', action='store_true', help="output json")
    ap.add_argument('infile', nargs='*',  help="input filename (stdin if not supplied")
    return ap.parse_args()

# for json encoding of the Include type.  Just convert it to
# a dict with tag and value (value can be a string or a list of strings)
# the base JSONEncoder can handle a dict

class IncludeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Include):
            return {obj.t : obj.l}
        return super().default(obj)

custom_types = [
    'include',
    'include-raw',
    'include-raw-escape',
    'include-raw-expand',
    'include-raw-verbatim',
    'include-jinja2'
]

def main():
    args = parse_args()
    for t in custom_types:
        # note the tag must include the ':' here.  It's removed when
        # __init__()ing an Include type
        yaml.add_constructor(f'!{t}:', include_constructor, Loader=yaml.SafeLoader)
    # yaml.add_representer(Include, include_representer)
    if args.infile:
        data = yaml.safe_load(open(args.infile[0], 'rb'))
    else:
        data = yaml.safe_load(sys.stdin)

    if args.json:
        print(json.dumps(data, indent=2, cls=IncludeEncoder))
    else:
        pprint.pprint(data)


if __name__ == '__main__':
    sys.exit(main())
