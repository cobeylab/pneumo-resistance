#!/usr/bin/env python
'''
Run this inside a subdirectory (model0-null, etc.) and it will load the base parameters
from this directory, and load the parameters from the first command-line argument,
or from overridden_parameters.py if unspecified.
'''

import importlib
import os
import sys
import random
from collections import OrderedDict
import numpy
import json
import subprocess
import types

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(SCRIPT_DIR)

import base_parameters

RUN_EXEC_PATH = os.path.join(SCRIPT_DIR, 'run_job.sh')
N_REPLICATES = 20

def main():
    if len(sys.argv) > 1:
        overridden_params_filename = sys.argv[1]
    else:
        overridden_params_filename = 'overridden_parameters.py'
    
    if len(sys.argv) > 2:
        suffix = sys.argv[2]
    else:
        suffix = None
        
    
    # Load Python module defining overridden parameters
    sys.path.append(os.path.dirname(overridden_params_filename))
    overridden_params = importlib.import_module(os.path.splitext(os.path.basename(overridden_params_filename))[0])
    
    # Combine base parameters with overridden parameters
    params = module_to_dict(base_parameters)
    print 'base params:'
    print json.dumps(params, indent=2)
    params.update(module_to_dict(overridden_params))
    print 'base+overridden params:'
    print json.dumps(params, indent=2)
    
    # Jobs with cost in duration of carriage
    generate_model_jobs(params, 'cost_duration', suffix, 'xi', [0.90, 0.92, 0.94, 0.96, 0.98, 1.00])
    
    # Jobs with cost in transmission
    generate_model_jobs(params, 'cost_transmission', suffix, 'ratio_foi_resistant_to_sensitive', [0.90, 0.92, 0.94, 0.96, 0.98, 1.00])

def generate_model_jobs(model_params, jobs_dirname, suffix, cost_param_name, cost_values):
    seed_rng = random.SystemRandom()
    for treatment_multiplier_base in [0.0, 0.5, 1.0, 1.5]:
        treatment_multiplier = treatment_multiplier_base * 10.0 / model_params['treatment_duration_mean']
        for cost_value in cost_values:
            for gamma_treated_ratio_resistant_to_sensitive in [1.0, 2.0, 4.0, 5.0]:
                for replicate_id in range(0, N_REPLICATES):
                    job_dir = os.path.join(
                        jobs_dirname + ('' if suffix is None else '-{}'.format(suffix)), 
                        'jobs',
                        'treat={:.1f}-cost={:.2f}-ratio={:.1f}'.format(
                            treatment_multiplier, cost_value, gamma_treated_ratio_resistant_to_sensitive
                        ),
                        '{:02d}'.format(replicate_id)
                    )
                    
                    if os.path.exists(job_dir):
                        sys.stderr.write('{} already exists\n'.format(job_dir))
                    else:
                        sys.stderr.write('{}\n'.format(job_dir))
                        os.makedirs(job_dir)
                
                        random_seed = seed_rng.randint(1, 2**31-1)
                        
                        parameters = OrderedDict(model_params)
                        job_info = OrderedDict([
                            ('cost_param_name', cost_param_name),
                            ('cost', cost_value),
                            (cost_param_name, cost_value),
                            ('treatment_multiplier', treatment_multiplier),
                            ('gamma_treated_ratio_resistant_to_sensitive', gamma_treated_ratio_resistant_to_sensitive),
                            ('random_seed', random_seed)
                        ])
                        parameters.update(job_info)
                        parameters['job_info'] = job_info
                        
                        dump_json(parameters, os.path.join(job_dir, 'parameters.json'))

def module_to_dict(module):
    keys = [k for k in dir(module) if not k.startswith('__') and not isinstance(getattr(module, k), types.ModuleType)]
    return OrderedDict([(k, getattr(module, k)) for k in keys])

def dump_json(obj, filename):
    with open(filename, 'w') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')

if __name__ == '__main__':
    main()
