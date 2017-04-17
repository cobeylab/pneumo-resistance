Summary
=======
This model explicitly represents the host-level colonization dynamics of multiple strains of pneumococcus.
There are `n_serotypes` different serotypes; for each serotype, there are two strains: antibiotic-sensitive (resistance class 0) and antibiotic-resistant (resistance class 1).
Hosts receive antibiotic treatments through their lifetime, sampled based on an empirical distribution of treatment rates at different ages.
Transmission and clearance dynamics depend on the age, current treatment status, past colonization history, and current set of colonizations, which may include multiple colonizations by the same strain, in hosts.

The simulation is structured using an event queue and proceeds by repeatedly removing the next event from the queue and executing it.

For the sake of simplicity, the model is implemented in Python. Parameters and model state listed here match usage in the code. 


Running the Model
=================
For flexibility, model parameters can be loaded from a static parameters file or via standard input in JSON format; from a Python module defining the parameters as variables, where they can be generated programmatically; or by writing a separate main script that initializes a `pyresistance.Model` object programmatically.

The `example` directory includes a Python module `parameters.py` defining parameters as variables, as well as a directory `burnin_replicate` showing how to perform many jobs on a cluster, including burn-in jobs that serve as the starting point for replicates.
For more information about running replicates, see `README.md` in `example/burnin_replicate`.

To run from a Python module `parameters.py`, simply do this:
```{sh}
[...]/pyresistance.py parameters.py
```

and similarly, from a static `parameters.json` file:
```{sh}
[...]/pyresistance.py parameters.json
```

Parameters
==========
See the comments in `example/parameters.py` for a description of all model parameters.

Model State
===========
Model state is determined by the following components:
* `hosts`: a list of Host objects (see Host State).
* `event_queue`: a priority heap of future events in the simulation, represented as function objects that can be called to execute a change in simulation state, whose priority is the simulation time of the event. Events at the same time are additionally prioritized by the order in which they are added to the queue.

For efficiency, two arrays summarizing host state are also kept up to date throughout the simulation:
* `n_hosts_by_age`: a `n_ages`-length vector where `n_hosts_by_age[i]` is the number of hosts whose age is `i`.
* `colonizations_by_age`: a three-dimensional array of size `n_ages X n_serotypes X 2`, where `colonizations_by_age[i,j,k]` is the number of colonizations in hosts of age `i` by serotype `j`, resistance class `k`.

The time `t` is implied by the time assigned to the current event being executed. The meaning of one unit of time is determined by the values of simulation parameters; the age of hosts is determined by `t_year`, so if `t_year` is 365, and simulation parameters are set accordingly, one unit of time can be thought of as one day.


Host State
==========
Hosts are characterized by the following attributes:
* `birth_time, death_time`: the time of the host's birth and death.
* `age`: the age of the host, in years, kept equal to `floor((t - birth_time)/t_year)`.
* `colonizations`: a two-dimensional array of size `n_serotypes X 2`, where `colonizations[i,j]` is the number of active colonizations by serotype `i`, resistance class `j`.
* `past_colonizations`: a two-dimensional array of size `n_serotypes X 2`, where `past_colonizations[i,j]` is the number of past (cleared) colonizations by serotype `i`, resistance class `j`.
* `treatment_times`: a two-dimensional array of size `n_treatments X 2`, where `n_treatments` is the number of treatments received by the host; `treatment_times[i,0]` is the start time for the treatment; and `treatment_times[i,1]` is the end time. See Treatment Schedule.
* `in_treatment`: `True` if the host is currently receiving an antibiotic treatment; `False` otherwise. (This attribute is implied by `treatment_times`.)


Model Initialization
====================
1. Add `n_hosts` Host objects to the `hosts` list, each with a randomly drawn lifetime. Set the birth time so that `-demographic_burnin_time` is uniformly randomly located within their lifetime. This is done to create a distribution of ages before demographic burnin. (See Host Lifetimes, Host Initialization, and Demographic Burnin.)
2. Simulate birth and death until `t = 0` to reach an initial age distribution.
3. Create initial colonizations in hosts. (See Initial Colonization.)
4. Add a periodic colonization-dynamics event to the event queue, to execute every `colonization_timestep` units of time. See Colonization Event.
5. Repeat until `t = t_end`:
    a. Set `t, event_function` equal to the next time and event function object on the event queue.
    b. Call `event_function`.

Colonization Events
===================
Colonization events are executed every `colonization_timestep`:
```{python}
event colonization_event:
    for serotype_id = 0 to n_serotypes - 1:
        for resistant = 0, 1:
            for age = 0 to n_ages - 1:
                colonization_rate = 0
                for age_j = 0 to n_ages - 1:
                    colonization_rate += alpha[age, age_j] * colonizations_by_age[age_j] / n_hosts_by_age[age_j]
                colonization_rate *= beta
                if resistant:
                    colonization_rate *= resistance_cost_via_transmission
                colonization_rate += immigration_rate
                colonization_rate *= n_hosts_by_age[age]
                n_hosts_to_colonize = draw_poisson(colonization_rate)
                for i = 0 to n_hosts_to_colonize - 1:
                    host = draw_random host_with_age(age)
                    with probability p_colonization(host, serotype_id, resistant):
                        colonize_host(host, serotype_id, resistant)
```

The probability of colonization is given by:
```{python}
function get_p_colonization(host, serotype_id, resistant):
    if sum(host.colonizations) == 0:
        omega = 0.0
    else:
        omega = mu_max * (1.0 - min_serotype_rank(host) / (n_serotypes - 1))
    p_colonization = 1 - omega
    if host.past_colonizations[serotype_id,:].sum() > 0:
        p_colonization *= 1 - p.sigma
    return p_colonization
```
where `min_serotype_rank(host)` is the minimum rank of serotypes currently colonizing the host, where the rank of a serotype `i` is given by `gamma[i]`, where the highest `gamma[i]` is given rank 0 and the lowest `gamma[i]` is given rank `n_serotypes - 1`.

When a host `host` is colonized, the following happens:
```{python}
function colonize_host(host, serotype_id, resistant):
    host.colonizations[serotype_id, resistant] += 1
    
    event_queue.add(
        make_clearance_event(host, serotype_id, resistant),
        draw_clearance_time(host, serotype_id, resistant)
    )
```

```{python}
function draw_clearance_time(host, serotype_id, resistant):
    if host.in_treatment:
        if resistant:
            mean_duration = gamma_treated_resistant
        else:
            mean_duration = gamma_treated_sensitive
    else:
        mean_duration = kappa + (gamma[serotype_id] - kappa) * exp(-epsilon * sum(host.past_colonizations))
        if resistant:
            mean_duration *= xi
    return draw_exponential(mean=mean_duration)
```

Host Initialization
===================

1. Draw `lifetime` from empirical lifetime distribution (see Host Lifetimes).
2. Set `death_time = birth_time + lifetime`.
3. Set `age = 0`.
4. Set `colonizations[i,j] = 0, past_colonizations[i,j] = 0` for all `i, j`.
5. Add aging events to the event queue at times `age = birth_time + age * t_year`. When executed, aging events set `age = age + 1`.
6. Add a death/rebirth event on the event queue at `death_time`. When executed, that event will reinitialize the host and remove all old events associated with the host from the event queue.
7. Add events corresponding to starting and stopping each treatment (see Treatment Events).


Treatment Events
================
When treatment is activated or deactivated for a host, `in_treatment` is set accordingly. Additionally, since treatment affects clearance rates, all clearance times are re-drawn when treatment status changes.


Clearance Events
================
When colonizations are cleared, the corresponding counts are simply reduced by one.


Host Lifetimes
==============
Host lifetimes are drawn from the empirical distribution given by `lifetime_distribution`. The probability that a host dies at age `i` is equal to `lifetime_distribution[i] / sum(lifetime_distribution)`. The actual death time is drawn uniformly randomly within the year given by the chosen age.


Initial Colonization
====================
Each host has an (approximately) `init_p_host_colonized` probability of being colonized by any strain, with each serotype being equally likely, and the probability of a resistant strain given by `init_p_resistant`. These are approximate because the number of colonizations is set to be at least 1 for each serotype/resistance class.


Treatment Schedules
===================
The number of treatments at each age is drawn according to `mean_n_treatments_per_age`. Treatment times are drawn uniformly randomly in each year, conditional on there being at least a `min_time_between_treatments` delay between treatments.


Outputs
=======
The output database contains three tables, each of which begins with a `job_id` column used to indicate, e.g., different runs in a parameter sweep that are writing to the same database file; and a `t` column containing the simulation time.


`counts_by_age_treatment`
-------------------------
This table contains the number of colonized hosts, the number of total colonizations, and the number of hosts colonized simultaneously by sensitive and resistant strains, for hosts in each particular age class/treatment status.

Columns:
```
job_id
t
age
in_treatment
n_hosts
n_colonized
n_colonizations
n_colonized_by_sensitive_and_resistant
```

`counts_by_age_treatment_strain`
--------------------------------
This table contains the number of hosts, and the number of total colonizations, for hosts in each particular age class/treatment status, for each strain.

Columns:
```
job_id
t
age
in_treatment
serotype_id
resistant
n_colonized
n_colonizations
```

`counts_by_age_treatment_n_colonizations`
-----------------------------------------
This table contains the number of hosts hosts by number of colonizations, in each age/treatment status. At each output time, there will be one row for each age/treatment status/number of colonizations, up to the maximum number of colonizations across hosts at that time.

Columns:
```
job_id
t
age
in_treatment
n_colonizations
n_hosts
```
