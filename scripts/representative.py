#!/usr/bin/env python
from __future__ import unicode_literals

import Levenshtein
import argparse
import codecs
import os
import sys
import numpy as np

from morphsegannot.tools import selection
from morphsegannot.tools import representative
from morphsegannot.tools import tools

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='representative.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('infile', metavar='<infile>',
            help='File containing pre-ranked words')
    add_arg('outfile', metavar='<outfile>',
            help='File to write selection into')

    add_arg('--truncate', dest='num_input', type=int,
        metavar='<int>', default=500,
        help='Number of words of input to read. '
                '(default: %(default)s)')
    add_arg('-n', dest='num_annots', type=int,
        metavar='<int>', default=50,
        help='Number of words to select. '
             '(default: %(default)s)')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    words = tools.read_wordlist(args.infile)

    truncated = []
    while len(truncated) < args.num_input:
        parts = words.next().split('\t', 1)
        truncated.append(parts[0])
    selected = representative.representative_sampling(
        truncated, args.num_annots)

    with codecs.open(args.outfile, 'w', encoding='utf-8') as fobj:
        for word in selected:
            fobj.write('{}\n'.format(word))

if __name__ == "__main__":
    main(sys.argv[1:])

