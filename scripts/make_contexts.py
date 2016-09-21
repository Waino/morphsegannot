#!/usr/bin/env python

import argparse
import json
import sys

from morphsegannot.tools import tools


def get_argparser():
    parser = argparse.ArgumentParser(
        prog='make_contexts.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('corpusfile', metavar='<corpus file>',
            help='word files')
    add_arg('wordfiles', metavar='<word file>', nargs='+',
            help='word files')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    words = set()
    for word_file in args.wordfiles:
        for word in tools.read_wordlist(word_file):
            words.add(word)

    contexts = tools.get_contexts(words, args.corpusfile)

    print(json.dumps(contexts))


if __name__ == "__main__":
    main(sys.argv[1:])
