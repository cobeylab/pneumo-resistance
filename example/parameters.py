import os
import numpy
import json

### MODEL PARAMETERS ###

# Transmission model: either 'independent' or 'cotransmission'.
# 'independent': colonizations are transmitted between hosts independently of one another.
# 'cotransmission': transmissions are attempted for all colonizations simultaneously
# between chosen source and target host.
transmission_model = 'independent'

# Transmission scaling: either 'by_host' or 'by_colonization'.
# 'by_colonization': a host with n colonizations is n times as infectious as a host with 1
# colonization
# 'by_host': a host with n colonizations is equally infectious to a host with 1
# colonization, so each individual colonization is 1/n times as infectious.
# Currently, transmission_model = 'independent' requires
# transmission_scaling = 'by_colonization'; 'cotransmission' allows either.
transmission_scaling = 'by_colonization'

# The time between years; ages are defined by this number.
t_year = 365.0

# The amount of simulation time before `t = 0`, during which only birth/death processes
# will be modeled.
# At time t = 0, initial infections happen and infection dynamics begin.
demographic_burnin_time = 300 * t_year

# Duration of epidemiological simulation (after demographic burnin, starts at t = 0)
t_end = 300 * t_year

# Timestep between colonization events (assuming use_exact_simulation = False)
colonization_event_timestep = 1.0

# How often to run verification code ensuring consistency of counts, etc.
verification_timestep = t_year

# Probability of host being immune to each strain
p_init_immune = 0.5

# The number of hosts.
n_hosts = 10000

# The number of serotypes.
n_serotypes = 25

# The number of ages, defined by t_year.
# Age classes start at 0, so the maximum age is `n_ages - 1`.
n_ages = 111

# Number of immigration events (treated the same as a contact) per host per unit time
# The probability per unit time of a host receiving a colonization, above probability
# from within-population contacts, for any serotype
# (NOTE: in an earlier version, was per-STRAIN, including sensitive and resistant strains
# of each serotype) The total immigration rate is thus `n_serotypes * immigration_rate`.
immigration_rate = 0.000001 # Per serotype

# Model for probability of an immigrant colonization being resistant
# 'constant' : constant probability equal to p_immigration_resistant
# 'fraction_resistant_global' : probability equal to fraction of resistant colonizations
# 'fraction_resistant_by_serotype' : probability equal to fraction resistant, by serotype;
# bounded by p_immigration_resistant_bounds
# 'history_by_serotype': probability equal to the fraction of resistant colonizations in
# a per-serotype resistance history that includes the last resistance_history_length
# colonizations for that serotype
immigration_resistance_model = 'constant'

# Min, max probability of an immigrant colonization being resistant, used as bounds
# under fraction_resistant_global, fraction_resistant_by_serotype, and history_by_serotype
p_immigration_resistant_bounds = [0.01, 0.99]

# Length of resistance history for history_by_serotype model
resistance_history_length = 500

# Constant probability of immigration being resistant for 'constant' model.
# Also used as fallback probability in case of no colonizations for
# 'fraction_resistant_global' and 'fraction_resistant_by_serotype' models,
# and in the case of no history for 'history_by_serotype' model
p_immigration_resistant = 0.1

# Probability of being colonized by each serotype at t = 0.
init_prob_host_colonized = (0.02 * numpy.ones(n_serotypes, dtype=float)).tolist()

# Probability that an initial colonization is a resistant strain
init_prob_resistant = 0.5

# The contact rate for hosts (see Colonization Events):  # of contacts per host per unit
# time.
beta = 0.0453208

# Minimum mean carriage duration:
# The mean time to clearance for a sensitive strain for an untreated host with an
# infinite number of past colonizations.
kappa = 25.0

# Ratio of clearance time of a resistant strain to a sensitive strain:
# xi < 1 implies a cost of resistance in untreated hosts
xi = 1.0

# Coefficient governing how clearance time in untreated hosts changes with number of
# past colonizations
epsilon = 0.25

# The reduction in colonization probability due to past colonization by the colonizing
# strain (specific immunity)
# (See readme for calculation for probability of colonization.)
sigma = 0.3

# The maximum reduction in colonization probability due to any strain
# (generalized immunity)
# (See the calculation for probability of colonization.)
mu_max = 0.25

# Mean carriage duration for each serotype in the absence of past colonizations
# in untreated hosts
# A list of length `n_serotypes`, where `gamma[i]` is the mean time to clearance for
# an untreated host with no past colonizations.
# If set to 'empirical_usa', then values are loaded from gamma_empirical_usa.json
gamma = 'empirical_usa'

# Mean carriage duration for sensitive strains in treated hosts
gamma_treated_sensitive = 4.0

# Ratio of mean carriage duration (resistant to sensitive) in treated hosts
# gamma_treated_resistant == gamma_treated_sensitive * gamma_treated_ratio_resistant_to_sensitive
gamma_treated_ratio_resistant_to_sensitive = 5.0

# The ratio of the probability of colonization of resistant strains to sensitive strains.
# Cost of resistance via force of infection: if < 1, resistant strains
# have lower transmission rates
ratio_foi_resistant_to_sensitive = 1.0

# Multiplier applied to mean_n_treatments_per_age: modulates treatment rates for all ages
treatment_multiplier = 0.0

# Distribution of lifetimes: list of relative probabilities (weights) of different ages
# of death.  Need not add up to one.
# Specifically, `lifetime_distribution[i]` is the weight that a lifetime will be in
# the range `[i * t_year, (i + 1) * t_year]`.
# Actual lifetime is drawn uniformly randomly within the year, which is chosen
# proportional to these weights.
# If set to 'empirical_usa', defaults to parameters/lifetime_distribution_empirical_usa.json
# is used.
lifetime_distribution = 'empirical_usa'

# List containing the mean number of antibiotic treatments per year for each age class
# (adjusted treatment_multiplier below)
# If set to 'empirical_usa', defaults to
# parameters/mean_n_treatments_per_age_empirical_usa.json
# which contains empirical data from the United States
mean_n_treatments_per_age = 'empirical_usa'

# The minimum delay between the end of one treatment and the start of the next.
min_time_between_treatments = 1.5

# The mean duration of treatments.
treatment_duration_mean = 10.0

# The standard deviation of treatment durations.
treatment_duration_sd = 3.0

# If use_random_mixing is True, then hosts of all age classes are treated equally in
# calculating the force of infection--that is, each host is equally likely to contact
# each other host.
use_random_mixing = True

# If use_random_mixing is False, alpha determines a contact weight matrix for age classes,
# so that alpha[i][j] is the fraction of contacts that an individual from age class i
# receives from age class j.
# Note that if use_random_mixing = False, the probability of a contact from different age
# classes becomes independent of the actual number of people in that age class.
# If set to 'polymod', then values are loaded from
# parameters/alpha_polymod.json
# Can also be set to a list of lists; inner lists represent rows in the matrix
# If smaller than n_ages by n_ages, contacts between to/from older people are assumed
# to be zero.
# alpha = 'polymod'
alpha = None


### OUTPUT PARAMETERS ###

# Sample output database
db_filename = 'output_db.sqlite'

# Whether to overwrite database if already present
overwrite_db = False

# How often to write output to the database.
output_timestep = t_year

output_ageclasses = [
    5, # age < 5
    15 # 5 <= age < 20 
    # implied class for age >= 20
]
# output_ageclasses = [] implies a single age class for all ages

enable_output_by_age = False

### SIMULATION ALGORITHM PARAMETERS ###

# If an integer, used as seed. If None, generates one randomly using the
# OS-provided random number generator
random_seed = None

# If True, use a calendar queue for events, where future events are put
# into fixed-size buckets of time.
# If False, a priority heap is used, which uses a predictable smaller amount of memory
# but will run slower than a calendar queue with appropriately sized buckets.
use_calendar_queue = True

# The minimum time discretization used for a calendar queue.
# The actual bucket width is adaptively set to
# min(queue_min_bucket_width, 2 * [average interval between events]).
# The maximum number of buckets used at runtime will be
# 2 * min_bucket_width * [time horizon of simulation].
# Since death events are added only after the final birthday event, the time horizon will
# typically be only on the order of one year.
# This minimum can be used to limit memory usage, but if it's too high it may slow
# things down.
queue_min_bucket_width = 1e-3

# If True, colonization events will take place one at a time rather than at discrete
# timesteps.
use_exact_simulation = False

# For use_exact_simulation = True:
# Every rate_bound_timestep, an upper bound for contact events will be calculated
# for each serotype/strain. Rejection is used to filter actual contact events for randomly
# chosen hosts.
rate_bound_timestep = 1.0
