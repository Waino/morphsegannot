#!/usr/bin/env python

import argparse
import collections
import os
import re
import sys

from morphsegannot.tools import tools, selection

def main(num_annots):
    # This tool just runs IFSubstrings on stdin
    # with selected words printed on stdout
    metric = selection.IFSubstringMetric(normalize=True, namesuffix='5n', maxlen=5)

    words = [line.strip() for line in sys.stdin]

    selector = selection.Selector(metric, model=None)
    ranked = selector.rank(words, seen=None, n=num_annots)

    selected = [item.word for item in ranked[:num_annots]]
    for word in selected:
        print(word)


if __name__ == "__main__":
    main(sys.argv[1])   # number of words to select
