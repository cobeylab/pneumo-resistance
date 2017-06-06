#!/usr/bin/env python

import os
import sys
import random
from collections import OrderedDict
import numpy
import json

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

N_REPLICATES = 20

def main():
    params = get_constant_parameters()
    
    # Use cost = xi (cost in duration)
    generate_sweep_jobs(params, 'jobs', 'xi', [0.90, 0.92, 0.94, 0.96, 0.98, 1.00])
    
    # Alternatively, use cost = ratio_foi_resistant_to_sensitive (cost in duration)
    # generate_sweep_jobs(params, 'jobs', 'ratio_foi_resistant_to_sensitive', [0.90, 0.92, 0.94, 0.96, 0.98, 1.00])

def get_constant_parameters():
    transmission_model = 'independent'
    transmission_scaling = 'by_colonization'

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
    gamma = 'empirical'
    gamma_treated_sensitive = 4.0
    gamma_treated_ratio_resistant_to_sensitive = 5.0
    ratio_foi_resistant_to_sensitive = 1.0
    treatment_multiplier = 1.0

    immigration_rate = 0.000001 / 8.0
    immigration_resistance_model = 'constant'
    p_immigration_resistant = 0.01

    p_init_immune = 0.5
    init_prob_host_colonized = (0.02 * numpy.ones(n_serotypes, dtype=float)).tolist()
    init_prob_resistant = 0.5

    lifetime_distribution = 'empirical_usa'
    mean_n_treatments_per_age = [0.35405] * n_ages
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

    # Only produce output for age clases
    enable_output_by_age = False

    # Internal operation
    use_calendar_queue = True
    queue_min_bucket_width = 5e-4
    colonization_event_timestep = 1.0
    verification_timestep = t_year

    return locals() # Magically returns a dictionary of all the variables defined in this function

def generate_sweep_jobs(model_params, jobs_dirname, cost_param_name, cost_values):
    seed_rng = random.SystemRandom()
    for treatment_multiplier_base in [0.0, 0.5, 1.0, 1.5]:
        treatment_multiplier = treatment_multiplier_base * 10.0 / model_params['treatment_duration_mean']
        for cost_value in cost_values:
            for gamma_treated_ratio_resistant_to_sensitive in [1.0, 2.0, 4.0, 5.0]:
                for replicate_id in range(0, N_REPLICATES):
                    job_dir = os.path.join(
                        jobs_dirname,
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

def dump_json(obj, filename):
    with open(filename, 'w') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')

if __name__ == '__main__':
    main()
