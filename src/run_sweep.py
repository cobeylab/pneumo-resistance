#!/usr/bin/env python

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

def get_time_str():
    return strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())

def run_sweep(sweep_module, complete=False, dry=False):
    if os.path.exists(sweep_module.db_filename):
        db = None
    else:
        db = sqlite3.connect(sweep_module.db_filename)
    
    const_params = sweep_module.get_constant_parameters()
    jobs_table_created = False
    
    job_id = 0
    
    # Generate database entries, working directories, and parameter files for each job
    job_ids = []
    for db_col_vals, param_vals in sweep_module.generate_sweep():
        params = dict(const_params)
        for k, v in param_vals:
            params[k] = v
        params['job_id'] = job_id
        
        if db is not None and not jobs_table_created:
            db_cols = [x[0] for x in db_col_vals]
            db.execute(
                'CREATE TABLE jobs (job_id INTEGER, params TEXT, {0})'.format(', '.join(db_cols))
            )
            jobs_table_created = True
        
        db.execute('INSERT INTO jobs VALUES ({0})'.format(
             ','.join(['?'] * (len(db_col_vals) + 2))
        ), [job_id, json.dumps(params, indent=2)] + [x[1] for x in db_col_vals])
        db.commit()
        
        job_dir = os.path.join('tmp_dir', 'jobs', '{0}'.format(job_id))
        if not os.path.exists(job_dir):
            os.makedirs(job_dir)
            with open(os.path.join(job_dir, 'params.json'), 'w') as f:
                json.dump(params, f, indent=2)
                f.write('\n')
            job_ids.append(job_id)
        
        job_id += 1
    
    model_script_filename = os.path.join(SCRIPT_DIR, 'pyresistance.py')
    
    # Submit jobs in chunks
    n_jobs = len(job_ids)
    if n_jobs == 0:
        sys.stderr.write('No jobs to run.\n')
        sys.exit(0)
    
    n_chunks = min(
        int(ceil(n_jobs / float(sweep_module.n_chunk_processes))),
        sweep_module.max_n_chunks
    )
    sys.stderr.write('Splitting {0} jobs into {1} chunks.\n'.format(n_jobs, n_chunks))
    
    chunk_script_filename = os.path.abspath(os.path.join(sweep_module.tmp_dir, 'run_chunk.sh'))
    with open(chunk_script_filename, 'w') as f:
        f.write(sweep_module.preamble)
        f.write('\n\n')
        f.write('{0}\n'.format(os.path.join(SCRIPT_DIR, 'run_chunk.py')))
    
    small_chunk_size = int(floor(n_jobs / float(n_chunks)))
    large_chunk_size = small_chunk_size + 1
    
    n_large_chunks = n_jobs % n_chunks
    n_small_chunks = n_chunks - n_large_chunks
    
    job_index = 0
    chunk_id = 0
    for chunk_id in range(n_chunks):
        chunk_dir = os.path.join(sweep_module.tmp_dir, 'chunks', '{0}'.format(chunk_id))
        if chunk_id < n_small_chunks:
            chunk_job_ids = job_ids[job_index:job_index + small_chunk_size]
            job_index += small_chunk_size
        else:
            chunk_job_ids = job_ids[job_index:job_index + large_chunk_size]
            job_index += large_chunk_size
        
        if os.path.exists(chunk_dir):
            if complete:
                sys.stderr.write('chunks directory must be deleted or renamed before running with --complete.\n')
            else:
                sys.stderr.write('chunk directory already exists; aborting.\n')
            sys.exit(1)
        
        os.makedirs(chunk_dir)
        with open(os.path.join(chunk_dir, 'chunk_spec.json'), 'w') as f:
            json.dump({
                'chunk_id' : chunk_id,
                'n_processes' : sweep_module.n_chunk_processes,
                'tmp_dir' : os.path.abspath(sweep_module.tmp_dir),
                'job_ids' : chunk_job_ids,
                'dry' : dry
            }, f, indent=2)
            f.write('\n')
        
        # Submit chunk
        sys.stderr.write('{0}\n'.format(get_time_str()))
        sys.stderr.write('Submitting chunk {0}\n'.format(chunk_id))
        
        stdout = open(os.path.join(chunk_dir, 'stdout.txt'), 'w')
        stderr = open(os.path.join(chunk_dir, 'stderr.txt'), 'w')
        proc = subprocess.Popen(
            [sweep_module.shell, chunk_script_filename],
            stdout=stdout,
            stderr=stderr,
            cwd=chunk_dir
        )
        result = proc.wait()
        sys.stderr.write('{0}\n'.format(get_time_str()))
        if result != 0:
            sys.stderr.write('Chunk {0} submission failed. Aborting.\n'.format(chunk_id))
            sys.exit(1)
        else:
            sys.stderr.write('Chunk {0} submitted\n'.format(chunk_id))
    
    if db is not None:
        db.close()

def gather_sweep(sweep_module):
    print 'Gathering sweep results...'
    
    if not os.path.exists(sweep_module.db_filename):
        sys.stderr.write('Sweep DB not present! Aborting.\n')
        sys.exit(1)
    
    db = sqlite3.connect(sweep_module.db_filename)
    
    create_index_sql_set = set()

    jobs_info = [row for row in db.execute('SELECT job_id, params FROM jobs')]

    for job_id, params_json in jobs_info:
        job_dir = os.path.join(sweep_module.tmp_dir, 'jobs', '{0}'.format(job_id))
        params = json.loads(params_json)
        job_db_path = os.path.join(job_dir, params['db_filename'])
        if not os.path.exists(job_db_path):
            sys.stderr.write('Database for job ID {0} not present; skipping!\n'.format(job_id))
        else:
            job_db = sqlite3.connect(job_db_path)
            create_index_sql_set.update(gather_job(db, job_id, job_db))
            job_db.close()

    for create_index_sql in create_index_sql_set:
        try:
            db.execute(create_index_sql)
        except Exception as e:
            sys.stderr.write('Warning: could not create index:\n{0}\n'.format(create_index_sql))
    
    db.commit()
    db.close()

def gather_job(db, job_id, job_db):
    sys.stderr.write('Processing output from job_id {0}\n'.format(job_id))
    
    for table_name, create_sql in job_db.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
    ):
        # Try creating table in case it doesn't yet exist
        try:
            db.execute(create_sql)
        except:
            pass
        
        # Insert all rows into master database
        for row in job_db.execute('SELECT * FROM {0}'.format(table_name)):
            db.execute(
                'INSERT INTO {0} VALUES ({1})'.format(
                    table_name,
                    ','.join(['?'] * len(row))
                ), row
            )
        
        db.commit()
    
    # Return indices identified by this job
    create_index_sql_list = []
    for row in job_db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index'"
    ):
        create_index_sql_list.append(row[0])

    return create_index_sql_list

def main():
    parser = argparse.ArgumentParser(
        description='Run sweep of pyresistance model',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--dry', action='store_true')
    parser.add_argument('--complete', action='store_true')
    parser.add_argument('--gather', action='store_true')
    parser.add_argument(
        'sweep_module_filename',
        metavar='<sweep-script>', type=str,
        help='''
            A Python source file (module) containing configuration variables as well as a function
            to generate a sweep.
        '''
    )
    args = parser.parse_args()
    
    sys.path.append(os.path.dirname(args.sweep_module_filename))
    sweep_module = importlib.import_module(os.path.splitext(os.path.basename(args.sweep_module_filename))[0])
    
    if args.gather:
        gather_sweep(sweep_module)
    else:
        if os.path.exists(sweep_module.db_filename):
            if sweep_module.overwrite:
                os.remove(sweep_module.db_filename)
            else:
                sys.stderr.write('Output database already exists. Remove first or use overwrite = True.\n')
                sys.exit(1)
        if args.complete:
            if os.path.exists(os.path.join(sweep_module.tmp_dir, 'chunks')):
                sys.stderr.write('chunks directory must be renamed or deleted before running with --complete.\n')
                sys.exit(1)
            run_sweep(sweep_module, complete=True, dry=args.dry)
        else:
            if os.path.exists(sweep_module.tmp_dir):
                if sweep_module.overwrite:
                    shutil.rmtree(sweep_module.tmp_dir)
                else:
                    sys.stderr.write('Output temporary directory exists. Remove first or use overwrite = True.\n')
                    sys.exit(1)
            run_sweep(sweep_module, dry=args.dry)

if __name__ == '__main__':
    main()
