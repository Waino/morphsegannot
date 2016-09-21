#!/usr/bin/env python
from __future__ import unicode_literals

import argparse
import codecs
import os
import sys

import flatcat
from morphsegannot.tools import tools, selection

METRICS = {
    'uncertainty': selection.UncertaintyMetric,
    'margin': selection.MarginMetric,
    'logp': selection.LogpMetric,
    'ifsubstrings_norm': 
        lambda: selection.IFSubstringMetric(normalize=True, namesuffix='norm', maxlen=4),
    'ifsubstrings_un': 
        lambda: selection.IFSubstringMetric(normalize=False, namesuffix='un', maxlen=4),
    'ifsubstrings_5n': 
        lambda: selection.IFSubstringMetric(normalize=True, namesuffix='5n', maxlen=5),
    'oneoffboundary': selection.OneOffBoundaryMetric,
    'morphlogp_min':
        lambda: selection.MorphLogpMetric(func=min, namesuffix='min'),
    'category': selection.CategoryMetric,
    'nostm': selection.NoStmMetric,
    }
    # alphabracket no longer supported: needs a separate tool
    #'alphabracket_unnorm': 
    #    lambda: selection.AlphaBracketMetric('unnorm'),
    #'alphabracket_uncert': 
    #    lambda: selection.AlphaBracketMetric('uncert'),
    #'alphabracket_logp': 
    #    lambda: selection.AlphaBracketMetric('logp'),

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='select_for_elicitation.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('iteration', metavar='<iteration>', type=int,
            help='Next iteration number')
    add_arg('metric', metavar='<metric>',
            help='Name of selection metric. '
                 'Alternatives: {}'.format(
                    ' '.join(sorted(METRICS.keys()))))

    add_arg('--model', dest='model',
            metavar='<modelfile>', default=None,
            help='Model file. '
                 'Default "models/p.metric.*.model.tar.gz", '
                 'where "p" is the previous iteration '
                 'and "metric" is the name of the metric.')
    add_arg('--already-selected', dest='oldselected',
            metavar='<file>', default=None,
            help='File containing already selected words. '
                 'Default "annotations/p.train.metric.goldstd.segmentation", '
                 'where p is the previous iteration '
                 'and "metric" is the name of the metric.')
    add_arg('--nonwords', dest='oldnonwords',
            metavar='<file>', default=None,
            help='File containing nonwords, to prevent reselecting them. '
                 'Default "annotations/p.nonword.words", '
                 'where p is the previous iteration.')

    add_arg('-n', dest='num_annots', type=int,
            metavar='<int>', default=50,
            help='Number of words to select. '
                 '(default: %(default)s)')

    add_arg('--pooldir', dest='pooldir',
            metavar='<dir>', default='pools/',
            help='Directory containing training pool')
    add_arg('--outdir', dest='outdir',
            metavar='<output dir>', default='selections/',
            help='Directory to put selections. '
                 '(default: %(default)s)')

    add_arg('--config-corpus', dest='configcorpus',
            metavar='<wordfile>', default=None,
            help='Override the corpus used for configuring the '
                 'selection metric. '
                 'Useful if not all words are in the training pool.')
    add_arg('--old-oracle', dest='oldoracle',
            metavar='<annotfile>', default=None,
            help='Old annotations from the oracle. '
                 'These can be re-selected, but are not re-elicited. '
                 'Useful if restarting the experiment.')
    add_arg('--representative-sampling', dest='representative', type=int,
            metavar='<int>', default=None,
            help='Use representative sampling, '
                 'with this many top words as input. '
                 'default: off. 500 is a decent value.')
    add_arg('--override-metric-out', dest='overridemetric',
            default=None,
            help='Override metric name in output. '
                 'Useful e.g. for separating representative sampling output.')


    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)
    io = flatcat.FlatcatIO(encoding='utf-8')

    prev_iter = args.iteration - 1
    print('Metric: {}, Next iteration: {}, Previous iteration: {}'.format(
        args.metric, args.iteration, prev_iter))
    metric = METRICS[args.metric]()

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    # Guessing filenames

    model_filename = args.model
    if model_filename is None:
        print('Trying to guess model file...')
        for filename in os.listdir('models'):
            if not filename.startswith(
                    '{}.flatcat.{}.'.format(prev_iter, args.metric)):
                continue
            if not filename.endswith('.model.tar.gz'):
                continue
            if model_filename is not None:
                raise Exception(
                    'Both "{}" and "{}" match the model pattern'.format(
                        model_filename, filename))
            model_filename = os.path.join(args.modeldir, filename)
        if model_filename is None:
            raise Exception('Model not found')
        print('... guessing "{}"'.format(model_filename))

    nonword_filename = args.oldnonwords
    if nonword_filename is None:
        nonword_filename = os.path.join(
            'annotations',
            '{}.nonword.words'.format(prev_iter))
        print('Nonword file not specified, guessing "{}"'.format(
            nonword_filename))
    if not os.path.exists(nonword_filename):
        print('Nonword file ({}) not found, '
              'assuming all words are valid'.format(
            nonword_filename))
        nonword_filename = None

    oldselected_filename = args.oldselected
    if oldselected_filename is None:
        oldselected_filename = os.path.join(
            'annotations',
            '{}.train.{}.annotated.words'.format(
                prev_iter, args.metric))
        print('Previously selected word file not specified, '
              'guessing "{}"'.format(
            oldselected_filename))
    if not os.path.exists(oldselected_filename):
        print('Previously selected word file ({}) not found, '
              'assuming no selections have been made'.format(
            oldselected_filename))
        oldselected_filename = None

    if args.oldoracle is not None:
        if not os.path.exists(args.oldoracle):
            raise Exception('Old oracle file "{}" not found'.format(
                args.oldoracle))

    if args.overridemetric is not None:
        metric_out = args.overridemetric
    else:
        metric_out = args.metric

    selection_filename = os.path.join(
        args.outdir,
        '{}.train.{}.all.selected'.format(args.iteration, metric_out))
    scores_filename = os.path.join(
        args.outdir,
        '{}.train.{}.all.scores'.format(args.iteration, metric_out))
    unseen_filename = os.path.join(
        args.outdir,
        '{}.train.{}.unseen.selected'.format(args.iteration, metric_out))
    prediction_filename = os.path.join(
        args.outdir,
        '{}.train.{}.unseen.predictions'.format(args.iteration, metric_out))

    # load, initialize, read

    print('Loading model...')
    model = io.read_tarball_model_file(model_filename)
    print('...done')
    model.initialize_hmm()  # FIXME: automate


    if oldselected_filename is not None:
        seen = set(tools.read_wordlist(oldselected_filename))
    else:
        seen = set()

    if nonword_filename is not None:
        nonwords = tools.read_wordlist(nonword_filename)
    else:
        nonwords = []
    seen.update(nonwords)

    if args.oldoracle is not None:
        oracle = set(tools.read_wordlist(args.oldoracle))
    else:
        oracle = set()

    trainpool = next(tools.get_pools(['train'], args.pooldir))

    # already selected words (incl nonwords) cannot be reselected
    trainpool = tools.filter_pool(trainpool, seen)


    # perform selection
    selector = selection.Selector(
        metric, model,
        progress=flatcat.utils._generator_progress)
    if args.configcorpus is not None:
        print('Configuring metric with "{}"'.format(args.configcorpus))
        selector.configure(
            tools.read_wordlist(args.configcorpus),
            seen=seen)
    print('Performing ranking...')
    ranked = selector.rank(trainpool, seen=seen, n=args.num_annots)
    print('...done')

    # write scores (debug)
    selection.write_scores(ranked, scores_filename)

    # apply representative sampling, if needed
    if args.representative is not None and args.representative > 0:
        print('Performing representative sampling...')
        from morphsegannot.tools import representative
        truncated = [item.word for item in ranked[:args.representative]]
        selected = representative.representative_sampling(
            truncated, args.num_annots)
    else:
        selected = [item.word for item in ranked[:args.num_annots]]

    # write
    with codecs.open(selection_filename, 'w', encoding='utf-8') as selfobj:
        with codecs.open(unseen_filename, 'w', encoding='utf-8') as unfobj:
            with codecs.open(prediction_filename, 'w', encoding='utf-8') as prfobj:
                for word in selected:
                    selfobj.write('{}\n'.format(word))
                    if word not in oracle:
                        unfobj.write('{}\n'.format(word))
                        (morphs, _) = model.viterbi_segment(word)
                        prfobj.write('{}\t{}\n'.format(
                            word, ' + '.join(morphs)))
                        

if __name__ == "__main__":
    main(sys.argv[1:])
