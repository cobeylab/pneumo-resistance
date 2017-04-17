#!/usr/bin/env python

import os
import sys
import subprocess

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

def main():
    if len(sys.argv) != 2:
        sys.stderr.write('Usage: ./submit.py <model-letter-prefix>\n')
        sys.exit(1)
    prefix = sys.argv[1]
    
    if not os.path.exists(os.path.join(SCRIPT_DIR, 'runr_db.sqlite')):
        subprocess.Popen('runr init', cwd = SCRIPT_DIR, shell = True).wait()
    
    if not os.path.exists(os.path.join(SCRIPT_DIR, 'runr_output')):
        os.makedirs(os.path.join(SCRIPT_DIR, 'runr_output'))
    
    subprocess.Popen(
        'runr add run_job.sh jobs/{}*/*/*'.format(prefix),
        cwd = SCRIPT_DIR,
        shell = True
    ).wait()
    
    env = dict(os.environ)
    env['PYRESISTANCE'] = os.path.join(SCRIPT_DIR, 'pyresistance')
    subprocess.Popen(
        'sbatch runr_go.sbatch',
        cwd = SCRIPT_DIR,
        env = env,
        shell = True
    ).wait()

if __name__ == '__main__':
    main()
