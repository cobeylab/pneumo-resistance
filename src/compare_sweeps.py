#!/usr/bin/env python

from collections import OrderedDict
import json
import itertools
import argparse
import subprocess
import importlib
import shutil
import os
import sys
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(SCRIPT_DIR)
import sqlite3
from math import floor, ceil
from time import strftime, gmtime
import numpy
import scipy.stats

def main():
    parser = argparse.ArgumentParser(
        description='Compare distribution of statistics from sweep databases with matching parameters in order to catch intended/unintended behavior changes.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'comp_module_filename', metavar='<comparison-script>', type=str,
        help='''A Python source file (module) specifying what to compare.'''
    )
    args = parser.parse_args()
    
    comp_module_dir = os.path.abspath(os.path.dirname(args.comp_module_filename))
    sys.path.append(comp_module_dir)
    comp_module = importlib.import_module(os.path.splitext(os.path.basename(args.comp_module_filename))[0])
    os.chdir(comp_module_dir)
    
    for db_filename in comp_module.db_filenames:
        if not os.path.exists(db_filename):
            sys.stderr.write('Database {0} does not exist; quitting.\n'.format(db_filename))
            sys.exit(1)
    
    if not hasattr(comp_module, 'statistic_functions'):
        sys.stderr.write('No statistic_functions specified; nothing to do.\n')
        sys.exit(1)
    
    for i, db_filename_1 in enumerate(comp_module.db_filenames):
        for j, db_filename_2 in enumerate(comp_module.db_filenames):
            if j > i:
                compare_databases(comp_module, db_filename_1, db_filename_2)
    
    if not hasattr(comp_module, 'match_columns'):
        sys.stderr.write('No match_columns specified; assuming all jobs are replicates with the same parameters.\n')
    
def compare_databases(comp_module, db_filename_1, db_filename_2):
    sys.stdout.write('Comparing {0} to {1}...\n'.format(db_filename_1, db_filename_2))
    
    db1 = sqlite3.connect(db_filename_1)
    db2 = sqlite3.connect(db_filename_2)
    
    match_columns = comp_module.match_columns
    match_query = 'SELECT DISTINCT {0} FROM jobs'.format(', '.join(match_columns))
    match_vals_1 = [tuple(row) for row in db1.execute(match_query)]
    match_vals_2_set = set([tuple(row) for row in db2.execute(match_query)])
    
    match_vals_both = [x for x in match_vals_1 if x in match_vals_2_set]
    sys.stderr.write('Found {0} sets of parameter values common to both databases.\n'.format(len(match_vals_both)))
    if len(match_vals_1) != len(match_vals_both):
        sys.stderr.write(
            'Warning: some sets of parameter values were not present in both databases.\n' +
            '{0} contains {1} sets\n'.format(db_filename_1, len(match_vals_1)) +
            '{0} contains {1} sets\n'.format(db_filename_2, len(match_vals_2_set))
        )
    
    sys.stdout.write('\n')
    
    job_id_query = 'SELECT job_id FROM jobs WHERE {0}'.format(
        ' AND '.join(['{0} = ?'.format(match_column) for match_column in match_columns])
    )
    for match_vals in match_vals_both:
        match_dict = OrderedDict(zip(match_columns, match_vals))
        sys.stdout.write('Comparing statistics for {0}:\n'.format(json.dumps(match_dict, indent=2)))
        job_ids_1 = [x[0] for x in db1.execute(job_id_query, match_vals)]
        job_ids_2 = [x[0] for x in db2.execute(job_id_query, match_vals)]
        
        compare_jobs(comp_module, db1, db2, job_ids_1, job_ids_2)
        
        sys.stdout.write('\n')
    
    db1.close()
    db2.close()

def compare_jobs(comp_module, db1, db2, job_ids_1, job_ids_2):
    for stat_func in comp_module.statistic_functions:
        sys.stdout.write('  {0}:\n'.format(stat_func.__name__))
        compare_stat(stat_func, db1, db2, job_ids_1, job_ids_2)

def compare_stat(stat_func, db1, db2, job_ids_1, job_ids_2):
    stats1 = [stat_func(db1, job_id) for job_id in job_ids_1]
    stats2 = [stat_func(db2, job_id) for job_id in job_ids_2]
    
    sys.stdout.write('    means: {0:.6g}, {1:.6g}\n'.format(numpy.mean(stats1), numpy.mean(stats2)))
    sys.stdout.write('    stddevs: {0:.6g}, {1:.6g}\n'.format(numpy.std(stats1), numpy.std(stats2)))
    sys.stdout.write('    medians: {0:.6g}, {1:.6g}\n'.format(numpy.median(stats1), numpy.median(stats2)))
    
    ks_stat, p_val = scipy.stats.ks_2samp(stats1, stats2)
    sys.stdout.write('    K-S test: p-value = {0} (statistic = {1})\n'.format(ks_stat, p_val))

if __name__ == '__main__':
    main()
