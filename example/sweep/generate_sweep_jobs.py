#!/usr/bin/env python

import os
import sys
import random
from collections import OrderedDict
import numpy
import json

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
RUN_EXEC_PATH = os.path.join(SCRIPT_DIR, 'run_job.sh')
JOBS_DIR = os.path.join(SCRIPT_DIR, 'jobs')
N_REPLICATES = 10

seed_rng = random.SystemRandom()

if os.path.exists(JOBS_DIR):
    sys.stderr.write('{} already exists; aborting\n'.format(JOBS_DIR))
    sys.exit(1)

runmany_info_template = OrderedDict([
    ('executable', RUN_EXEC_PATH),
    ('environment', {'PYRESISTANCE' : os.path.join(SCRIPT_DIR, 'pyresistance')}),
    ('minutes', 600),
    ('megabytes', 6000)
])

def get_constant_parameters():
    n_hosts = 100000
    n_serotypes = 25
    n_ages = 111

    t_year = 365.0

    demographic_burnin_time = 150 * t_year
    t_end = 150 * t_year

    load_hosts_from_checkpoint = False

    beta = 0.0453208

    kappa = 25.0
    xi = 1.0
    epsilon = 0.25
    sigma = 0.3
    mu_max = 0.25
    gamma = 'empirical_usa'
    gamma_treated_sensitive = 4.0
    gamma_treated_ratio_resistant_to_sensitive = 5.0
    ratio_foi_resistant_to_sensitive = 1.0
    treatment_multiplier = 0.0
    immigration_rate = 0.000001
    
    immigration_resistance_model = 'constant'
    p_immigration_resistant_bounds = [0.01, 0.99]
    p_immigration_resistant = 0.1

    p_init_immune = 0.5
    init_prob_host_colonized = (0.02 * numpy.ones(n_serotypes, dtype=float)).tolist()
    init_prob_resistant = 0.5

    lifetime_distribution = 'empirical_usa'
    mean_n_treatments_per_age = 'empirical_usa'
    min_time_between_treatments = 1.5
    treatment_duration_mean = 10.0
    treatment_duration_sd = 3.0

    use_random_mixing = True
    alpha = None

    output_timestep = t_year
    db_filename = 'output_db.sqlite'
    overwrite_db = True

    output_ageclasses = [
        5, # age < 5
        15 # 5 <= age < 20
        # implied class for age >= 20
    ]

    enable_output_by_age = False

    random_seed = None
    use_calendar_queue = True
    queue_min_bucket_width = 5e-4
    colonization_event_timestep = 1.0
    verification_timestep = t_year

    return locals() # Magically returns a dictionary of all the variables defined in this function

def dump_json(obj, filename):
    with open(filename, 'w') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')

for xi in [0.90, 0.92, 0.94, 0.96, 0.98, 1.00]:
    for treatment_multiplier in [0.0, 0.5, 1.0, 1.5]:
        for gamma_treated_ratio_resistant_to_sensitive in [4.0]:
            for replicate_id in range(0, N_REPLICATES):
                job_dir = os.path.join(
                    JOBS_DIR,
                    'xi={:.2f}-treat={:.1f}-ratio={:.1f}'.format(
                        xi, treatment_multiplier, gamma_treated_ratio_resistant_to_sensitive
                    ),
                    '{:02d}'.format(replicate_id)
                )
                sys.stderr.write('{}\n'.format(job_dir))
                os.makedirs(job_dir)
                
                random_seed = seed_rng.randint(1, 2**31-1)
                
                runmany_info = OrderedDict(runmany_info_template)
                runmany_info['job_info'] = OrderedDict([
                    ('xi', xi),
                    ('treatment_multiplier', treatment_multiplier),
                    ('gamma_treated_ratio_resistant_to_sensitive', gamma_treated_ratio_resistant_to_sensitive),
                    ('random_seed', random_seed)
                ])
                
                parameters = get_constant_parameters()
                parameters.update(runmany_info['job_info'])
                parameters['job_info'] = runmany_info['job_info']
                
                dump_json(parameters, os.path.join(job_dir, 'parameters.json'))
                dump_json(runmany_info, os.path.join(job_dir, 'runmany_info.json'))
