#!/usr/bin/env python

import os
import sys
import json
import subprocess
from collections import OrderedDict

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

if __name__ == '__main__':
    print 'Environment:'
    print json.dumps(OrderedDict(os.environ), indent = 2)
    
    returncode = subprocess.Popen(
        [
            os.path.join(SCRIPT_DIR, '..', 'src', 'pyresistance.py'),
            'parameters.json'
        ]
    ).wait()
    if returncode != 0:
        sys.stderr.write('pyresistance.py failed with code {}\n'.format(returncode))
        sys.exit(returncode)
    
    returncode = subprocess.Popen(
        [
            os.path.join(SCRIPT_DIR, '..', 'src', 'plot_simulation.py'),
            'output_db.sqlite',
            'simulation.png'
        ]
    ).wait()
    if returncode != 0:
        sys.stderr.write('plot_simulation.py failed with code {}\n'.format(returncode))
        sys.exit(returncode)
