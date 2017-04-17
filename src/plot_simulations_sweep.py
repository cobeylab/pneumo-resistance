#!/usr/bin/env python

import argparse
import os
import sys
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('jobs_dir', metavar='<jobs-directory>')
parser.add_argument('--db-filename', metavar='<db-filename>', default='output_db.sqlite')
parser.add_argument('--plot-filename', metavar='<plot-filename>', default='sim.png')

args = parser.parse_args()

exec_path = os.path.join(SCRIPT_DIR, 'plot_simulation.py')

for subdir in os.listdir(args.jobs_dir):
    job_dir = os.path.join(args.jobs_dir, subdir)
    db_path = os.path.join(job_dir, args.db_filename)
    if os.path.exists(db_path):
        sys.stderr.write('Plotting {}\n'.format(job_dir))
        plot_path = os.path.join(job_dir, args.plot_filename)
        proc = subprocess.Popen([exec_path, db_path, plot_path])
        proc.wait()
