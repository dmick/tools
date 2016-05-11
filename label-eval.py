#!/usr/bin/env python

import ast
import pprint
import re
import sys

class UnsafeNodeType(Exception):
    ''' Unsafe node type found '''

    def __init__(self, nodetype):
        self.nodetype = nodetype

    def __str__(self):
        return self.__class__.__name__ + ': ' + self.nodetype

class myvisitor(ast.NodeVisitor):
    '''
    Collect all the Name nodes from an ast tree into self.names
    Also, raise UnsafeNodeType if anything but boolean expression node
    types are found in the expression.
    '''

    # allow nodes only of these ast class types
    ALLOWED_TYPES = [
        'Module',
        'Expr',
        'BoolOp',
        'UnaryOp',
        'Name',
        'Load',
        'And',
        'Or',
        'Not',
    ]

    def __init__(self):
        ast.NodeVisitor.__init__(self)
        self.names = set()

    def visit_Name(self, node):
        name = node.id
        self.names.add(name)

    def generic_visit(self, node):
        # filter every node through ALLOWED_TYPES
        if node.__class__.__name__ not in myvisitor.ALLOWED_TYPES:
            raise UnsafeNodeType(node.__class__.__name__)
        ast.NodeVisitor.generic_visit(self, node)


def pythonize_boolean(expr):
    ''' Translate a boolean expression from C-like operators to Python'''

    replacements = {
        '\s*&&\s*': ' and ',
        '\s*\|\|\s*': ' or ',
        '\s*!\s*': ' not ',
    }

    for search, repl in replacements.iteritems():
        expr = re.sub(search, repl, expr)
    # strip in case an operator was first on the line, otherwise
    # parse will throw IndentationError
    return expr.strip()


def validate_and_parse(expr):
    '''
    Parse to collect names mentioned in expr.  Only allow
    expressions with terminals mentioned in myvisitor()
    (for safety).
    '''
    tree=ast.parse(expr)
    visitor = myvisitor()
    visitor.visit(tree)
    return visitor.names


def matching_slaves(expr, slaves):
    '''Returns a list of slaves that match expr'''
    # return value
    matching_slaves = list()

    expr = pythonize_boolean(expr)

    # collect all expr's names
    names = validate_and_parse(expr)

    # all the names in expr, initialized to "False"
    symdict = {k: False for k in names}

    for slavename, labels in slaves.iteritems():
        # copy for this particular slave
        localdict = dict(symdict)

        # Note labels supplied by slavename as 'True' in localdict
        # (we could limit this only to labels that already
        # exist in the expression, but there's not much point;
        # if the expression doesn't care it doesn't care in the
        # eval() below either)
        for label in labels:
            localdict[label] = True

        # localdict is now the intersection of labels mentioned in e
        # and labels supplied by slave, with True/False set
        # appropriately for this slave. 
        if eval(expr, globals(), localdict) is True:
            matching_slaves.append(slavename)

    return matching_slaves


slaves = {
    'trusty_small': ['trusty', 'small'],
    'trusty_huge': ['trusty', 'huge'],
    'trusty_amd64_huge': ['trusty', 'amd64', 'huge'],
    'trusty_arm64_huge': ['trusty', 'arm64', 'huge'],
}


def main():
    TESTEXPRS = ['"ABC".tolower()', 'trusty&&!huge', 'trusty', 'trusty && huge', 'trusty && arm64', '!trusty']
    pp = pprint.PrettyPrinter().pprint
    print 'slaves:'
    pp(slaves)
    print

    for e in TESTEXPRS:
        try:
            result = matching_slaves(e, slaves)
        except UnsafeNodeType as exc:
            print e, 'causes', exc
            continue
        print '"%s" matches %s' % (e, result)

if __name__ == '__main__':
    sys.exit(main())

