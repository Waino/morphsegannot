#!/usr/bin/env python

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup

import re
main_py = open('morphsegannot/__init__.py').read()
metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", main_py))

requires = [
        'bottle',
]

setup(name='morphsegannot',
      version=metadata['version'],
      author=metadata['author'],
      author_email='stig-arne.gronroos@aalto.fi',
      #url='',
      description='morphsegannot',
      packages=['morphsegannot', 'morphsegannot.tools'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Scientific/Engineering',
      ],
      license="BSD",
      scripts=[
        'morphsegannot/annotation_ui.py',
        'scripts/make_contexts.py',
        'scripts/process_singleton_iteration.py',
        'scripts/select_for_elicitation.py'
        ],
      install_requires=requires,
      #extras_require={
      #    'docs': [l.strip() for l in open('docs/build_requirements.txt')]
      #}
      )
