#!/usr/bin/env python

import json
import itertools
import argparse
import importlib
import shutil
import os
import sys
import multiprocessing
import subprocess
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(SCRIPT_DIR)
import sqlite3
from time import gmtime, strftime

def main():
    with open('chunk_spec.json') as f:
        spec = json.load(f)
    
    pool = multiprocessing.Pool(spec['n_processes'])
    results = pool.map(run, spec['job_ids'])
#     for job_id in spec['job_ids']:
#         pool.apply_async(run, [job_id])
    pool.close()
    pool.join()

def get_time_str():
    return strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())

def run(job_id):
    with open('chunk_spec.json') as f:
        spec = json.load(f)

    exec_path = os.path.join(SCRIPT_DIR, 'pyresistance.py')

    job_dir = os.path.join(spec['tmp_dir'], 'jobs', '{0}'.format(job_id))

    sys.stderr.write('{0}\n'.format(get_time_str()))
    sys.stderr.write('Job {0} starting\n'.format(job_id))

    stdout = open(os.path.join(job_dir, 'stdout.txt'), 'w')
    stderr = open(os.path.join(job_dir, 'stderr.txt'), 'w')
    
    if spec['dry']:
        args = [exec_path, '--dry', 'params.json']
    else:
        args = [exec_path, 'params.json']
    proc = subprocess.Popen(
        args,
        stdout=stdout,
        stderr=stderr,
        cwd=job_dir
    )
    result = proc.wait()
    sys.stderr.write('{0}\n'.format(get_time_str()))
    if result != 0:
        sys.stderr.write('Job {0} failed. Aborting.\n'.format(job_id))
        raise Exception('Failed job')
    else:
        sys.stderr.write('Job {0} done\n'.format(job_id))
    
    return job_id

if __name__ == '__main__':
    main()
