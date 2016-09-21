from __future__ import unicode_literals

import argparse
import codecs
import itertools
import sys

import tools

def roundrobin(*iterables):
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
    # Recipe credited to George Sakkis
    pending = len(iterables)
    nexts = itertools.cycle(iter(it).next for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = itertools.cycle(itertools.islice(nexts, pending))

def unique_everseen(iterable, key=None):
    "List unique elements, preserving order. Remember all elements ever seen."
    # unique_everseen('AAAABBBCCDAABBB') --> A B C D
    # unique_everseen('ABBCcAD', str.lower) --> A B C D
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in itertools.ifilterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element


### Command line interface:
#
def get_argparser():
    parser = argparse.ArgumentParser(
        prog='roundrobin.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('infiles', metavar='<infile>', nargs='+',
            help='File containing pre-ranked words')
    add_arg('--outfile', dest='outfile', metavar='<outfile>',
            default='roundrobin.selected',
            help='File to write selection into')

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

    inputs = [tools.read_wordlist(infile)
              for infile in args.infiles]

    combined = unique_everseen(roundrobin(*inputs))

    selected = itertools.islice(combined, 0, args.num_annots)

    with codecs.open(args.outfile, 'w', encoding='utf-8') as fobj:
        for word in selected:
            fobj.write('{}\n'.format(word))

if __name__ == "__main__":
    main(sys.argv[1:])

