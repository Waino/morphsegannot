from __future__ import unicode_literals

import codecs
import collections
import hashlib
import itertools
import json
import os
import unicodedata

import flatcat

Context = collections.namedtuple('Context', ['left', 'word', 'right'])
Pool = collections.namedtuple('Pool', ['id', 'metric', 'words'])
Annotation = collections.namedtuple('Annotation', ['word', 'analysis'])
GroupedAnnotation = collections.namedtuple('GroupedAnnotation',
    ['type', 'id', 'metric', 'word', 'analysis'])
TripleFobj = collections.namedtuple('TripleFobj',
    ['words', 'segmentation', 'tagged'])

# Public functions

def get_contexts(words, corpusfile):
    contexts = _find_contexts(words, corpusfile)
    contexts = sorted(contexts, key=lambda x: x.word)
    grouped_contexts = itertools.groupby(contexts, lambda x: x.word)
    contexts = _remove_redundant(grouped_contexts)
    return contexts


def get_pools(pools,
              pooldir,
              suffix='pool.words'):
    """Gets words in (static) pools"""
    for pool in pools:
        filepath = os.path.join(
            pooldir,
            '{}{}'.format(pool, suffix))
        yield Pool(pool, None, read_wordlist(filepath))


def get_selections(metrics,
                   selectiondir,
                   iteration,
                   pool='train',
                   suffix='selected'):
    for metric in metrics:
        filepath = os.path.join(
            selectiondir,
            '{}.{}.{}.{}'.format(iteration, pool, metric, suffix))
        yield Pool(pool, metric, read_wordlist(filepath))

def all_metrics(selectiondir, iteration=None, pools=None):
    out = []
    for path in os.listdir(selectiondir):
        parts = path.split('.')
        tmp = parts.pop()
        if tmp != 'selected':
            print('not selected: {} {}'.format(tmp, path))
            continue
        tmp = parts.pop(0)
        if (not iteration is None) and (tmp != iteration):
            print('not iter: {} {}'.format(tmp, path))
            continue
        tmp = parts.pop(0)
        if (not pools is None) and (tmp not in pools):
            print('not pool: {} {}'.format(tmp, path))
            continue
        out.append('.'.join(parts))
    return out


def filter_pool(pool, seen):
    # use for removing already selected words before selection
    # and for removing old annots after selection
    key = (pool.id, pool.metric)
    return Pool(pool.id,
                pool.metric,
                [word for word in pool.words
                 if word not in seen])

def combine_pools(id, pools):
    seen = set()
    combined = []
    for pool in pools:
        for word in pool:
            if word in seen:
                continue
            combined.append(word)
            seen.add(word)
    return Pool(pool.id,
                None,
                combined)

# Generic helpers

def read_wordlist(word_file, firstcol=True):
    with codecs.open(word_file, 'r', encoding='utf-8') as fobj:
        for line in fobj:
            line = line.strip()
            if firstcol:
                parts = line.split('\t')
                line = parts[0].strip()
            yield line

def pool_progress(pool):
    return Pool(pool.id, pool.metric,
                 flatcat.utils._generator_progress(pool.words))

# Helpers for contexts

def _read_corpus(corpus_file):
    with codecs.open(corpus_file, 'r', encoding='utf-8') as fobj:
        for line in fobj:
            line = unicodedata.normalize('NFKC', line)
            line = line.strip()
            context_words = line.split(' ')
            yield context_words

def _find_contexts(target_words, corpus_file):
    for context_words in _read_corpus(corpus_file):
        for (i, context_word) in enumerate(context_words):
            if context_word in target_words:
                yield Context(
                    context_words[:i],
                    context_word,
                    context_words[i + 1:])

def _immediate(context):
    if len(context.left) == 0:
        left = None
    else:
        left = context.left[-1]
    if len(context.right) == 0:
        right = None
    else:
        right = context.right[0]
    return (left, right)

def _remove_redundant(grouped_contexts):
    out = collections.defaultdict(list)
    for (word, contexts) in grouped_contexts:
        seen = set()
        for c in contexts:
            imm = _immediate(c)
            if imm in seen:
                # This word has already been seen in this immediate context
                continue
            seen.add(imm)
            left = ' '.join(c.left)
            right = ' '.join(c.right)
            context_id = '-'.join([
                hashlib.md5(left.encode('utf-8')).hexdigest(),
                hashlib.md5(c.word.encode('utf-8')).hexdigest(),
                hashlib.md5(right.encode('utf-8')).hexdigest()])
            out[word].append([c.left, c.right, context_id])
    return out

# Helpers for handling annotations

def read_annotation_log(filename):
    io = flatcat.FlatcatIO(encoding='utf-8')
    out = []
    nonwords = []
    # enforces splitting of hyphens and colons
    fs = flatcat.flatcat.ForceSplitter(':-', None)
    with codecs.open(filename, 'r', encoding='utf-8') as fobj:
        for line in fobj:
            line = line.strip()
            parts = line.split('\t')
            if len(parts) < 3:
                print('Cant parse annotation "{}"'.format(line))
            if parts[2] in ('Eval', 'Modified', 'Predicted'):
                analysis = io.read_annotation(parts[1],
                                              construction_sep=' ',
                                             )[0]
                analysis = fs.enforce_one(analysis)
                out.append(Annotation(parts[0], analysis))
            elif parts[2] == 'Nonword':
                nonwords.append(parts[0])

    # multiple analyses for the same surface word
    # are returned as separate Annotations
    return (out, nonwords)


def read_old_annotations(filename):
    io = flatcat.FlatcatIO(encoding='utf-8')
    out = []
    nonwords = []
    with codecs.open(filename, 'r', encoding='utf-8') as fobj:
        for line in fobj:
            line = line.strip()
            parts = line.split('\t')
            if len(parts) < 2:
                print('Cant parse annotation "{}"'.format(line))
            if parts[1] == '!':
                nonwords.append(parts[0])
            else:
                analysis = io.read_annotation(parts[1],
                                              construction_sep=' ',
                                              analysis_sep=',',
                                             )
                out.append(Annotation(parts[0], analysis))
    return (out, nonwords)


#def combine_multiple_annotators()
def combine_with_old_annotations(pools, old, new, nonwords):
    by_word = {annot.word: annot.analysis
               for annot in old}
    unclaimed_new = set()
    unclaimed_old = set(by_word.keys())
    for annot in new:
        unclaimed_new.add(annot.word)
        if annot.word in by_word:
            if tuple(annot.analysis) == tuple(by_word[annot.word]):
                continue
            print('Changed annotation {} -> {}'.format(
                by_word[annot.word], annot.analysis))
        by_word[annot.word] = annot.analysis
    for pool in pools:
        for word in pool.words:
            try:
                unclaimed_new.remove(word)
            except KeyError:
                pass
            try:
                unclaimed_old.remove(word)
            except KeyError:
                pass
            if word in nonwords:
                continue
            if word in by_word:
                yield GroupedAnnotation('goldstd',
                                        pool.id, pool.metric,
                                        word, by_word[word])
                continue
            yield GroupedAnnotation('unseen',
                                    pool.id, pool.metric,
                                    word, None)
    for word in unclaimed_new:
        yield GroupedAnnotation('unclaimed_new',
                                None, None,
                                word, by_word[word])
    for word in unclaimed_old:
        yield GroupedAnnotation('unclaimed_old',
                                None, None,
                                word, by_word[word])
    for word in nonwords:
        yield GroupedAnnotation('nonword',
                                None, None,
                                word, ('!',))


def combine_single(new, selection, old, old_oracle, nonwords,
                   metric, pool_id='train'):
    by_word = {annot.word: [annot.analysis]
               for annot in old_oracle}
    cur_iter_words = []

    for annot in old:
        cur_iter_words.append(annot.word)
        by_word[annot.word] = annot.analysis
    unclaimed_new = set()
    unclaimed_old = set(by_word.keys())
    for annot in new:
        unclaimed_new.add(annot.word)
        if annot.word in by_word:
            newtmp = tuple(annot.analysis)
            if any(tuple(x) == newtmp
                   for x in by_word[annot.word]):
                # already added
                continue
            by_word[annot.word].append(annot.analysis)
        else:
            by_word[annot.word] = [annot.analysis]
    cur_iter_words.extend(selection)

    for word in cur_iter_words:
        try:
            unclaimed_new.remove(word)
        except KeyError:
            pass
        try:
            unclaimed_old.remove(word)
        except KeyError:
            pass
        if word in nonwords:
            continue
        if word in by_word:
            yield GroupedAnnotation('goldstd',
                                    pool_id, metric,
                                    word, by_word[word])
            continue
        yield GroupedAnnotation('unseen',
                                pool_id, metric,
                                word, None)
    for word in unclaimed_new:
        yield GroupedAnnotation('unclaimed_new',
                                None, None,
                                word, by_word[word])
    for word in unclaimed_old:
        yield GroupedAnnotation('unclaimed_old',
                                None, None,
                                word, by_word[word])
    for word in nonwords:
        yield GroupedAnnotation('nonword',
                                None, None,
                                word, ('!',))


class MultiFileAnnotationWriter(object):
    def __init__(self, prefix, suffix):
        self.prefix = prefix
        self.suffix = suffix

    def write(self, grouped_annotations):
        all_fobj = self._open_one(
            self._make_filename('goldstd', 'all', None)
            + '.tagged')
        single_fobjs = {}
        triple_fobjs = {}
        for ga in grouped_annotations:
            key = (ga.type, ga.id, ga.metric)
            if ga.analysis is None:
                assert key not in triple_fobjs
                if key not in single_fobjs:
                    filename = self._make_filename(*key) + '.words'
                    single_fobjs[key] = self._open_one(filename)
                single_fobjs[key].write('{}\n'.format(ga.word))
            else:   # has analysis
                assert key not in single_fobjs
                if key not in triple_fobjs:
                    filenamebase = self._make_filename(*key)
                    triple_fobjs[key] = self._open_three(filenamebase)
                triple = triple_fobjs[key]
                triple.words.write('{}\n'.format(ga.word))
                triple.segmentation.write('{}\t{}\n'.format(
                    ga.word, _format_analyses(ga.analysis, detag=True)))
                triple.tagged.write('{}\t{}\n'.format(
                    ga.word, _format_analyses(ga.analysis)))
                all_fobj.write('{}\t{}\n'.format(
                    ga.word, _format_analyses(ga.analysis)))
        for fobj in single_fobjs.values():
            fobj.close()
        for triple in triple_fobjs.values():
            for fobj in triple:
                fobj.close()


    @staticmethod
    def _open_one(filename):
        return codecs.open(filename, 'w', encoding='utf-8')

    @classmethod
    def _open_three(cls, filenamebase):
        return TripleFobj(
            cls._open_one(filenamebase + '.words'),
            cls._open_one(filenamebase + '.segmentation'),
            cls._open_one(filenamebase + '.tagged'))

    def _make_filename(self, type, id, metric):
        d = {'prefix': self.prefix,
             'suffix': self.suffix,
             'type': type,
             'id': id,
             'metric': metric}
        if metric is None:
            if id is None:
                template = '{prefix}{type}{suffix}'
            else:
                template = '{prefix}{id}.{type}{suffix}'
        else:
            template = '{prefix}{id}.{metric}.{type}{suffix}'
        return template.format(**d)


def _format_analyses(analyses, detag=False):
    if detag:
        func = flatcat.FlatcatModel.detag_word
    else:
        func = lambda x: x
    return ', '.join(
        _format_analysis(func(analysis))
        for analysis in analyses)


def _format_analysis(analysis):
    try:
        morphs = ['{}/{}'.format(cmorph.morph, cmorph.category)
                for cmorph in analysis]
    except AttributeError:
        morphs = [unicode(morph) for morph in analysis]
    return ' '.join(morphs)
