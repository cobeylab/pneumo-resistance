import os
import numpy
import json

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
