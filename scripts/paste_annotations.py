#!/usr/bin/env python

from __future__ import unicode_literals

import argparse
import codecs
import itertools
import os
import sys

import flatcat
from morphsegannot.tools import tools


def get_argparser():
    parser = argparse.ArgumentParser(
        prog='paste_annotations_single.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('annotfile', metavar='<annotation file>',
            help='File containing all annotations')
    add_arg('wordfile', metavar='<wordfile>',
            help='Words to annotate')
    add_arg('outfile', metavar='<output file>',
            help='File for output')

    add_arg('--detag', dest='detag',
            action='store_true', default=False,
            help='Detag annotations')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    (annots, _) = tools.read_old_annotations(args.annotfile)
    annots = {a.word: a.analysis for a in annots}

    words = tools.read_wordlist(args.wordfile)

    if args.detag:
        func = flatcat.FlatcatModel.detag_word
    else:
        func = lambda x: x

    with codecs.open(args.outfile, 'w', encoding='utf-8') as fobj:
        for word in words:
            if word not in annots:
                print('No annotation for {}'.format(word))
                continue
            # FIXME redundancy
            fobj.write('{}\t{}\n'.format(
                word, 
                tools._format_analysis(
                    func(annots[word]))))


if __name__ == "__main__":
    main(sys.argv[1:])
