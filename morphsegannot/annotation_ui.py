# doesn't work in uwsgi for some bizarre reason:
#from __future__ import unicode_literals

import codecs
import datetime
import hashlib
import json
import os

from bottle import Bottle, auth_basic, request, run, static_file

app = Bottle()

package_dir = os.path.dirname(os.path.dirname(__file__))
root_dir = os.path.dirname(package_dir)

real_static_dir = package_dir + u'/html/'
print(real_static_dir)
real_data_dir = root_dir + u'/data/'
input_dir = real_data_dir + u'input/'
output_dir = real_data_dir + u'output/'
user_dir = output_dir + u'users/'

config_file = u'{}config.json'.format(real_data_dir)
context_file = u'{}contexts.json'.format(input_dir)

log_file = u'{}{}.log'.format(
    output_dir,
    datetime.datetime.now().strftime(u'%Y%m%d_%H%M%S'))
logfobj = codecs.open(log_file, u'a', encoding=u'utf-8')

default_context_len = 30

###
# XXX Hardcoded username and password
# (these are placeholders, replace them)
USERNAME = u'username'
PASSWD = u'password'

### Annotator objects

class AnnotatorFactory(object):
    def __init__(self, conf):
        self.annotators = {}
        self.config = conf

    def login(self, email, ip, char_width=default_context_len):
        uid = hashlib.md5(email.encode(u'utf-8')).hexdigest()
        if uid not in self.annotators:
            self.annotators[uid] = Annotator(email, uid, self.config)
            with codecs.open(u'{}{}'.format(user_dir, uid), u'a') as userfobj:
                dt = datetime.datetime.now().strftime(u'%Y-%m-%d-%H:%M:%S')
                userfobj.write(u'{}\t{}\t{}\t{}\n'.format(uid, email, dt, ip))
        self.annotators[uid].set_width(char_width)
        return self.annotators[uid]

    def get(self, uid, ip):
        if uid not in self.annotators:
            log(ip, uid, u'AnnotatorFactory', u'User not logged in')
            raise Exception(u'User not logged in {}'.format(uid))
        return self.annotators[uid]

    def reload(self, conf):
        self.config = conf
        self.annotators = {uid: Annotator(a.email, a.uid, conf)
                           for (uid, a) in self.annotators.items()}


class Annotator(object):
    def __init__(self, email, uid, conf):
        self.email = email
        self.uid = uid
        self.width = default_context_len

        if email in conf[u'annotators']:
            self.config = conf[u'annotators'][email]
        else:
            self.config = conf[u'annotators'][u'_default']

        # outfiles
        self.annots_file = u'{}annotations_{}_{}.txt'.format(
            output_dir, uid, self.config[u'iter'])
        self.annotcontext_file = u'{}annotation_contexts_{}_{}.txt'.format(
            output_dir, uid, self.config[u'iter'])

        self.seen_earlier = set(self.read_annotations(
            u'{}{}'.format(input_dir, self.config[u'seen_words_file'])))
        self.seen_now = set(self.read_annotations(self.annots_file))

        self.annotsfobj = None
        self.annotcontextfobj = None

    def _ensure(self):
        if self.annotsfobj is None:
            self.annotsfobj = codecs.open(
                self.annots_file, u'a', encoding=u'utf-8')
        if self.annotcontextfobj is None:
            self.annotcontextfobj = codecs.open(
                self.annotcontext_file, u'a', encoding=u'utf-8')

    def read_annotations(self, filename):
        out = set()
        if os.path.exists(filename):
            with codecs.open(filename, u'r', encoding=u'utf-8') as fobj:
                for line in fobj:
                    line = line.strip()
                    parts = line.split(u'\t')
                    out.add(parts[0])
        return out

    def get_words(self):
        out = []
        for (name, truncate, suggest, filename) in self.config[u'words']:
            filename = u'{}{}'.format(input_dir, filename)
            words = read_words(filename,
                               self.seen_earlier,
                               self.seen_now,
                               segmentations,
                               truncate=truncate)
            out.append((name, suggest, words))
        return {u'words': out}
        

    def write_annotation(self, word, analysis, matches=None):
        self._ensure()
        self.annotsfobj.write(u'{}\t{}'.format(word, analysis))
        if matches is None:
            self.annotsfobj.write(u'\tEval')
        elif matches:
            self.annotsfobj.write(u'\tPredicted')
        else:
            self.annotsfobj.write(u'\tModified')
        self.annotsfobj.write(u'\n')
        self.annotsfobj.flush()
        self.seen_now.add(word)

    def write_annotcontexts(self, word, segmented, context_ids):
        self._ensure()
        for cid in context_ids:
            if cid not in contexts_by_id:
                log(u'-', u'-', u'writer',
                    u'No context found for id {}'.format(cid))
                continue
            (left, right) = contexts_by_id[cid]
            self.annotcontextfobj.write(u'{} [{}] {}\n'.format(
                u' '.join(left),
                segmented,
                u' '.join(right)))
            self.annotcontextfobj.flush()

    def write_nonword(self, word):
        self._ensure()
        self.annotsfobj.write(u'{}\t!\tNonword\n'.format(word))
        self.annotsfobj.flush()
        self.seen_now.add(word)

    def stats(self):
        return {
            u'uid': self.uid,
            u'iteration': self.config[u'iter'] + 1,  # 1-based indexing
            u'annotated': len(self.seen_now)
            }

    def set_width(self, width):
        self.width = width


def get_config():
    configfobj = codecs.open(config_file, u'r', encoding=u'utf-8')
    config = json.load(configfobj)
    assert u'context_file' in config
    assert u'annotators' in config
    users = config[u'annotators']
    assert u'_default' in users
    for (email, conf) in users.items():
        assert u'words' in conf, email
        assert u'seen_words_file' in conf, email
        assert u'iter' in conf, email
    return config

def check_pw(username, pw):
    if username != USERNAME:
        return False
    if pw != PASSWD:
        return False
    return True

def boundaries_to_seg(word, boundaries):
    boundaries = list(boundaries)
    boundaries.append(True)
    out = []
    cur = []
    for (letter, boundary) in zip(word, boundaries):
        cur.append(letter)
        if boundary:
            out.append(u''.join(cur))
            cur = []
    return out

def log(ip, uid, handle, message):
    dt = datetime.datetime.now().strftime(u'%Y-%m-%d-%H:%M:%S')
    logstr = u'[{}, {}, {}] {}: {}\n'.format(dt, ip, uid, handle, message)
    #print(logstr)
    logfobj.write(logstr)
    logfobj.flush()


##########
# ROUTES #
##########
#
# Statics

@app.route(u'/')
@auth_basic(check_pw)
def htmlpage():
    return static_file(u'index.html', root=real_static_dir)

@app.route(u'/doc.html')
# no auth!
def docpage():
    log(request.remote_addr, u'-', u'docpage', u'-')
    return static_file(u'doc.html', root=real_static_dir)

@app.route(u'/images/<image>')
# no auth!
def imagefile(image):
    return static_file(image, root=os.path.join(real_static_dir, u'images'))

@app.route(u'/js/<filename>')
@auth_basic(check_pw)
def jsfile(filename):
    return static_file(filename, root=os.path.join(real_static_dir, u'js'))

@app.route(u'/css/<filename>')
@auth_basic(check_pw)
def cssfile(filename):
    return static_file(filename, root=os.path.join(real_static_dir, u'css'))

# backend -> frontend

@app.get(u'/user/<email>')
@auth_basic(check_pw)
def get_user(email):
    width = request.query.get(u'width')
    char_width = max(8, int(int(width) * 0.02))
    annotator = annotators.login(
        email,
        request.remote_addr,
        char_width=char_width)
    log(request.remote_addr, annotator.uid, u'login', email)
    return annotator.stats()

@app.get(u'/words/<uid>')
@auth_basic(check_pw)
def get_words(uid):
    annotator = annotators.get(uid, request.remote_addr)
    return annotator.get_words()


@app.get(u'/word/<word>')
@auth_basic(check_pw)
def get_word(word):
    word = word.decode(u'utf-8')
    seg = segmentations.get(word, [word])
    boundaries = []
    for morph in seg:
        boundaries.extend((len(morph) - 1) * [False])
        boundaries.append(True)
    # Remove the last superfluous boundary
    boundaries.pop()
    assert len(boundaries) == len(word) - 1

    uid = request.query.get(u'uid')
    context_len = annotators.get(uid, request.remote_addr).width

    truncated = []
    for c in contexts_by_word.get(word, [[(u'',), (u'',), u'0']]):
        left, right, context_id = c
        left = list(left)
        right = list(right)
        if len(left) > 0:
            tleft = left.pop()
        else:
            tleft = u''
        while len(left) > 0:
            if (len(tleft) + len(left[-1])) > context_len:
                tleft = u'...' + tleft
                break
            tleft = u' '.join((left.pop(), tleft))
        if len(right) > 0:
            tright = right.pop(0)
        else:
            tright = u''
        while len(right) > 0:
            if (len(tright) + len(right[0])) > context_len:
                tright += u'...'
                break
            tright = u' '.join((tright, right.pop(0)))
        truncated.append([tleft, tright, context_id])

    return {u'word': word,
            u'boundaries': boundaries,
            u'contexts': truncated}

# frontend -> backend

@app.post(u'/log/<handle>')
@auth_basic(check_pw)
def log_endpoint(handle):
    log(request.remote_addr,
        request.forms.get(u'uid').decode(u'utf-8'),
        handle.decode(u'utf-8'),
        request.forms.get(u'message').decode(u'utf-8'))

@app.post(u'/word/<word>')
@auth_basic(check_pw)
def word_endpoint(word):
    word = word.decode(u'utf-8')
    uid = request.forms.get(u'uid').decode(u'utf-8')
    boundaries = json.loads(request.forms.get(u'boundaries'))
    tags = json.loads(request.forms.get(u'tags'))
    context_ids = json.loads(request.forms.get(u'contexts'))
    log(request.remote_addr,
        uid,
        u'word',
        (word, boundaries, tags, context_ids))
    context_ids = [cid for (cid, val) in context_ids.items() if val]

    annotator = annotators.get(uid, request.remote_addr)

    segmented = boundaries_to_seg(word, boundaries)
    if len(segmented) != len(tags):
        log(request.remote_addr, uid, u'morph-tag mismatch',
            (segmented, tags))
    analysis = u' '.join(
        u'{}/{}'.format(morph, tag)
        for (morph, tag) in zip(segmented, tags))

    predicted = segmentations.get(word, None)
    if predicted is not None:
        matches = (segmented == predicted)
    else:
        matches = None
    annotator.write_annotation(word, analysis, matches)
    annotator.write_annotcontexts(word, analysis, context_ids)

@app.post(u'/nonword/<word>')
@auth_basic(check_pw)
def nonword(word):
    word = word.decode(u'utf-8')
    uid = request.forms.get(u'uid').decode(u'utf-8')
    log(request.remote_addr, uid, u'nonword', word)

    annotator = annotators.get(uid, request.remote_addr)
    annotator.write_nonword(word)

@app.post(u'/skip/<word>')
@auth_basic(check_pw)
def skip(word):
    word = word.decode(u'utf-8')
    uid = request.forms.get(u'uid').decode(u'utf-8')
    log(request.remote_addr, uid, u'skip', word)

@app.post(u'/sense/<context>')
@auth_basic(check_pw)
def sense(context):
    context = context.decode(u'utf-8')
    uid = request.forms.get(u'uid').decode(u'utf-8')
    log(request.remote_addr, uid, u'sense', context)

@app.post(u'/b2seg/<word>')
@auth_basic(check_pw)
def b2seg(word):
    """Hack to get log for intermediary result,
    and not to have to do as much string manipulation in js"""
    word = word.decode(u'utf-8')
    uid = request.forms.get(u'uid').decode(u'utf-8')
    boundaries = json.loads(request.forms.get(u'boundaries'))
    context_ids = json.loads(request.forms.get(u'contexts'))
    log(request.remote_addr, uid, u'b2seg', (word, boundaries, context_ids))
    segmented = boundaries_to_seg(word, boundaries)
    return {u'word': word,
            u'segmented': segmented}

# Admin
# FIXME: unRestfully a get. Fix when implementing admin UI
@app.get(u'/reload')
@auth_basic(check_pw)
def reload():
    """Reload the config"""
    global config, contexts_by_word, contexts_by_id
    config = get_config()
    annotators.reload(config)
    contexts_by_word, contexts_by_id = read_contexts(config[u'context_file'])
    return "Config reloaded <br/><br/> {}".format(config)


def read_words(infile,
               seen_earlier,
               seen_now,
               segmentations,
               truncate=-1):
    words = []
    with codecs.open(infile, u'r', encoding=u'utf-8') as fobj:
        for line in fobj:
            line = line.strip()
            if len(line) == 0 or line.startswith(u'#'):
                continue
            parts = line.split(u'\t')
            word = parts[0]
            if word in seen_earlier:
                # don't reduce the number of words to collect in this iter
                continue
            if word in seen_now:
                # allow continuing in new session without
                # having to annotate full number again
                truncate -= 1
                continue
            words.append(word)
            if len(parts) >= 2:
                morphs = parts[1].split(u' + ')
                segmentations[word] = morphs
            if len(words) == truncate:
                break
    return words

def read_contexts(infile):
    infile = u'{}{}'.format(input_dir, infile)
    with codecs.open(infile, u'r', encoding=u'utf-8') as fobj:
        contexts_by_word = json.load(fobj)
    contexts_by_id = {}
    for (word, contexts) in contexts_by_word.items():
        for (left, right, cid) in contexts:
            contexts_by_id[cid] = (left, right)
    return contexts_by_word, contexts_by_id

def mkdirs():
    dirs = [output_dir, user_dir]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

# Some globals
if __name__ == "__main__":

    config = None
    annotators = None

    segmentations = {}
    contexts_by_word = None
    contexts_by_id = {}

    # FIXME: this should be run once on app init
    config = get_config()
    annotators = AnnotatorFactory(config)
    contexts_by_word, contexts_by_id = read_contexts(config[u'context_file'])
    mkdirs()

    run(app, host="0.0.0.0", port=8080)
