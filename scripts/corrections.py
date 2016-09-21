#!/usr/bin/env python

from __future__ import unicode_literals

import argparse
import codecs
import sys
import re

RE_LINE = re.compile(r'([^\s]*)\s+(.*)')
RE_TAG = re.compile(r'/(PRE|STM|SUF|ZZZ)\b')

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='corrections.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('original', metavar='<original annotation file>',
            help='File containing annotations')
    add_arg('corrections', metavar='<correction file>',
            help='File containing corrections')
    add_arg('outfile', metavar='<output file>',
            help='File to write the corrected annotations into')

    add_arg('--detag', dest='detag', action='store_true',
            help="detag the corrections")

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def read_annotations(infile):
    with codecs.open(infile, 'r', encoding='utf-8') as fobj:
        for line in fobj:
            line = line.strip()
            if len(line) == 0:
                continue
            m = RE_LINE.match(line)
            if not m:
                print('cant parse {}'.format(line))
                continue
            yield (m.group(1), m.group(2))


def detag(stream):
    for (word, analysis) in stream:
        yield (word, RE_TAG.sub('', analysis))


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)
    corr = read_annotations(args.corrections)
    if args.detag:
        corr = detag(corr)
    corrections = {word: analysis for (word, analysis) in corr}
    unused = set(corrections.keys())
    with codecs.open(args.outfile, 'w', encoding='utf-8') as outfobj:
        for (word, analysis) in read_annotations(args.original):
            if word in corrections:
                try:
                    unused.remove(word)
                except KeyError:
                    pass
                if corrections[word] != analysis:
                    print('Replacing "{}":\t"{}" => "{}"'.format(
                        word, analysis, corrections[word]))
                    analysis = corrections[word]
            outfobj.write('{}\t{}\n'.format(word, analysis))
    if len(unused) > 0:
        print('Unused words:')
        for word in sorted(unused):
            print('{}\t{}'.format(word, corrections[word]))


if __name__ == "__main__":
    main(sys.argv[1:])
