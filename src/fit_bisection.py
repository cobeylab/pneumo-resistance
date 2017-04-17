#!/usr/bin/env python

import numpy
import random
import scipy.stats
import json
import itertools
import argparse
import importlib
import shutil
import os
import sys
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.join(SCRIPT_DIR, 'shpool'))
import shpool
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as pyplot

def median_from_pdf(vals, pdf):
    cdf = numpy.cumsum(pdf)
    
    left = numpy.nonzero(cdf < 0.5)[0][-1]
    right = numpy.nonzero(cdf >= 0.5)[0][0]
    
    return vals[left] + (vals[right] - vals[left]) * (0.5 - cdf[left]) / (cdf[right] - cdf[left])

def run_iteration(pool, fit_module, param_val):
    n_runs = fit_module.n_runs
    
    def generate_run_args():
        const_params = fit_module.get_constant_parameters()
        
        for i in range(n_runs):
            params = dict(const_params)
            params[fit_module.param_name] = param_val
            print json.dumps(params)
            yield json.dumps(params)
    
    model_script_filename = os.path.join(SCRIPT_DIR, 'pyresistance.py')
    call_id, n_runs = pool.run_many(
        ['pypy', model_script_filename],
        generate_run_args()
    )
    
    func_values = numpy.zeros(n_runs, dtype=float)
    for i in range(n_runs):
        call_id, chunk_id, job_id, job_dir, stdoutdata, exception = pool.next_result()
        if exception is not None:
            sys.stderr.write('job {0} caused exception in shpool:\n'.format(job_id))
            sys.stderr.write(exception)
            sys.stderr.write('\nAborting sweep. You may need to clean up running processes or jobs.\n')
            return None
        
        run_db_filename = os.path.join(job_dir, 'output_db.sqlite')
        if not os.path.exists(run_db_filename):
            sys.stderr.write('No output db. Aborting.\n')
            return None
        with sqlite3.connect(run_db_filename) as run_db:
            func_values[i] = fit_module.target_function(run_db, param_val)
        
        if not fit_module.keep_files:
            shutil.rmtree(job_dir)
    
    if not fit_module.keep_files:
        shutil.rmtree(os.path.join(fit_module.tmp_dir, '{0}'.format(call_id)))
    
    return func_values

def run_fit(fit_module):
    pool = shpool.ShellPool(
        processes=fit_module.processes,
        chunksize=fit_module.chunksize,
        shell=fit_module.shell,
        preamble=fit_module.preamble,
        tmp_dir=fit_module.tmp_dir,
        wait_before_polling=fit_module.wait_before_polling,
        polling_rate=fit_module.polling_rate,
        keep_files=True # Need to process database output before deleting files
    )
    
    job_id = 0
    
    if os.path.exists(fit_module.db_filename):
        if fit_module.overwrite:
            os.remove(fit_module.db_filename)
        else:
            sys.stderr.write('Database present. Aborting.\n')
            sys.exit(1)
    
    db = sqlite3.connect(fit_module.db_filename)
    db.execute('CREATE TABLE runs (iteration INTEGER, param_val REAL, func_val REAL)')
    db.execute('CREATE TABLE means (iteration INTEGER, param_val REAL, func_mean REAL)')
    
    const_params = fit_module.get_constant_parameters()
    
    param_name = fit_module.param_name
    param_range = fit_module.param_range
    target_value = fit_module.target_value
    n_iter = fit_module.n_iterations
    n_runs = fit_module.n_runs
    n_points_pdf = fit_module.n_points_pdf
    
    # Parameter values and density for PDF in target range
    param_vals = numpy.linspace(param_range[0], param_range[1], n_points_pdf)
    param_pdf = numpy.ones(n_points_pdf, dtype=float) / n_points_pdf
    
    for i in range(fit_module.n_iterations):
        param_median = median_from_pdf(param_vals, param_pdf)
        func_vals = run_iteration(pool, fit_module, param_median)
        
        for func_val in func_vals:
            db.execute('INSERT INTO runs VALUES (?,?,?)', [i, param_median, func_val])
        db.execute('INSERT INTO means VALUES (?,?,?)', [i, param_median, func_val.mean()])
        db.commit()
        
        # Sample variance of data
        var_data = numpy.var(func_vals, ddof=1)
        
        # Cheating Bayesian posterior with known variance and infinite-variance prior
        mu_func = func_vals.mean()
        sigma_func = numpy.sqrt(var_data / n_runs)
        
        # Probability that the target value is less than the mean of the samples
        p_target_less = scipy.stats.norm.cdf(mu_func, loc=target_value, scale=sigma_func)
        
        print mu_func, sigma_func, p_target_less
        
        # Update distribution
        less_indices = numpy.nonzero(param_vals < param_median)[0]
        param_pdf[less_indices] *= p_target_less
        
        gt_indices = numpy.nonzero(param_vals >= param_median)[0]
        param_pdf[gt_indices] *= (1.0 - p_target_less)
        
        param_pdf /= param_pdf.sum()
        
        fig = pyplot.figure()
        pyplot.plot(param_vals, param_pdf)
        pyplot.savefig('param_pdf_{0}.png'.format(i))
        pyplot.close(fig)
    
    pool.finish()
    db.close()

def main():
    parser = argparse.ArgumentParser(
        description='Fit pyresistance model',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'fit_module_filename',
        metavar='<fit-script>', type=str,
        help='''
            A Python source file (module) containing fit configuration.
        '''
    )
    args = parser.parse_args()
    
    sys.path.append(os.path.dirname(args.fit_module_filename))
    fit_module = importlib.import_module(os.path.splitext(os.path.basename(args.fit_module_filename))[0])
    
    if os.path.exists(fit_module.db_filename):
        if fit_module.overwrite:
            os.remove(fit_module.db_filename)
        else:
            sys.stderr.write('Output database already exists. Remove first or use --overwrite.')
            sys.exit(1)
    run_fit(fit_module)

if __name__ == '__main__':
    main()
