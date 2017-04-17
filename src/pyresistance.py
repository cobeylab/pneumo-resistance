#!/usr/bin/env pypy

import argparse
import os
import sys
import sqlite3
SCRIPT_DIR = os.path.dirname(__file__)
import json
import random
from discretedist import DiscreteDistribution
from calqueue import CalendarQueue
from heapqueue import HeapQueue
import numpy
import time
import inspect
import importlib
import resource
from StringIO import StringIO
import pickle
import npybuffer
from collections import OrderedDict
from collections import deque

### GLOBAL SWITCHES FOR DEBUGGING MODES ###

# Set to True to log every event to stderr
TRACE_EVENTS = False

# Set to True to log every function call to stderr
TRACE_CALLS = False

# Tolerance for verifying, e.g., age classes (so that 1 - EPS is considered valid for age class 1)
EPS = 1e-12


### MAIN FUNCTION ###

def main():
    '''Parses command-line arguments; loads parameters; runs model.
    '''
    if TRACE_CALLS:
        print_call('main')

    parser = argparse.ArgumentParser(
        description='Run pneumo resistance model.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--dry', action='store_true'
    )
    parser.add_argument(
        'params_filename', metavar='<parameters-file>', type=str, default=None, nargs='?',
        help='''
            Either a file containing a JSON-encoded dictionary of parameters,
            or a Python module file containing parameters as variables.
            If not present, reads a JSON-encoded parameters dictionary from standard input.
        '''
    )
    args = parser.parse_args()

    if args.params_filename is None:
        # Read from stdin
        params = Parameters(json.load(sys.stdin, object_pairs_hook=OrderedDict))
    else:
        # Read from file
        # Load Python module to use as parameters object
        if args.params_filename.endswith('.py'):
            # Load Python module defining parameters
            sys.path.append(os.path.dirname(args.params_filename))
            params = importlib.import_module(os.path.splitext(os.path.basename(args.params_filename))[0])
        elif args.params_filename.endswith('.json'):
            with open(args.params_filename) as f:
                params = Parameters(json.load(f, object_pairs_hook=OrderedDict))
        else:
            assert False

    model = Model(params, args.dry)
    model.run()


### MODEL CLASS ###

class Model(object):
    def __init__(self, parameters, dry):
        '''Initialize model state.

        :param parameters: Object whose attributes are used as model parameters.
        :param dry: If dry == True, then the simulation does nothing except set up an empty database and write out parameters.
        :return:
        '''
        if TRACE_CALLS:
            print_call('Model.__init__', parameters, dry)

        self.dry = dry

        self.p = parameters
        p = self.p
        
        self.set_up_parameters() # Some parameters need post-processing (e.g., loading 'alpha_polymod')

        self.init_database()
        
        if dry:
            return
        
        # Event queue for all simulation events.
        # Original implementation based on indexed priority heap;
        # new implementation an adaptive "calendar queue".
        # Indexed priority heap is somewhat more predictable w.r.t. memory but slower.
        if hasattr(p, 'use_calendar_queue'):
            use_calendar_queue = p.use_calendar_queue
        else:
            use_calendar_queue = True
        
        if use_calendar_queue:
            self.event_queue = CalendarQueue(
                t_min=-(p.demographic_burnin_time + p.n_ages * p.t_year),
                bucket_width=1.0,
                min_bucket_width=p.queue_min_bucket_width
            )
        else:
            self.event_queue = HeapQueue()
        self.event_count = 0
        self.event_counts = [0]

        # Track time and memory usage
        self.walltimes = [time.time()]
        self.memusages = [get_memusage()]

        # Random number generator
        self.rng = numpy.random.RandomState(p.random_seed)
        
        # Lifetime distribution: draws years according to weights in p.lifetime_distribution;
        # draws lifetime uniformly randomly within years.
        self.lifetime_dist = DiscreteDistribution(
            self.rng,
            p.lifetime_distribution
        )
        
        # Tracking of host/colonization counts
        self.n_hosts_by_age = numpy.zeros(p.n_ages, dtype=int)
        self.n_hosts_by_age[0] = p.n_hosts
        self.colonizations_by_age = numpy.zeros((p.n_ages, p.n_serotypes, 2), dtype=int)

        self.hosts_by_age = []
        for i in range(p.n_ages):
            self.hosts_by_age.append([])
        for i in range(p.n_hosts):
            self.hosts_by_age[0].append(i)
        
        # Set up colonization resistance history if history_by_serotype model being used
        if p.immigration_resistance_model == 'history_by_serotype':
            self.resistance_history = []
            for i in range(p.n_serotypes):
                self.resistance_history.append(deque())
            assert hasattr(p, 'resistance_history_length')
        else:
            self.resistance_history = None
        
        # Initialize hosts with birthday at t = -demographic_burnin_time - uniform(0, lifetime).
        # That way, there will be somewhat of a spread of ages even before burnin.
        if p.load_hosts_from_checkpoint:
            self.initialize_hosts_from_checkpoint()
        else:
            self.initialize_hosts()

        if p.load_hosts_from_checkpoint:
            self.event_queue.add(self.initialize_loaded_host_colonizations, 0.0)
        else:
            self.event_queue.add(self.initialize_colonizations_and_immunity, 0.0)

        # Verification events: do some sanity checks on counts, etc. in order to catch new bugs
        self.event_queue.add(self.verify, -p.demographic_burnin_time)

        self.event_queue.add(self.write_output, p.output_start)

        if p.checkpoint_start is not None:
            assert p.checkpoint_start >= 0.0
            self.event_queue.add(self.write_checkpoint, p.checkpoint_start)

    def initialize_hosts_from_checkpoint(self):
        p = self.p

        assert p.demographic_burnin_time == 0.0
        if not os.path.exists(p.checkpoint_load_path):
            sys.stderr.write('Checkpoint file does not exist; aborting.\n')
            sys.exit(1)
        checkpoint_db = sqlite3.connect(p.checkpoint_load_path)

        t_offset = checkpoint_db.execute('SELECT t FROM meta').next()[0]

        self.hosts = []
        for i, row in enumerate(checkpoint_db.execute('SELECT * FROM hosts')):
            assert i < p.n_hosts

            birth_time, lifetime, colonizations, past_colonizations, treatment_times = row

            colonizations = npybuffer.npy_buffer_to_ndarray(colonizations)
            self.colonizations_by_age[0] += colonizations
            past_colonizations = npybuffer.npy_buffer_to_ndarray(past_colonizations)
            if treatment_times is not None:
                treatment_times = npybuffer.npy_buffer_to_ndarray(treatment_times)
                treatment_times -= t_offset

            birth_time -= t_offset

            host = Host(
                i, birth_time, lifetime, self,
                treatment_times=treatment_times, colonizations=colonizations, past_colonizations=past_colonizations
            )
            self.hosts.append(host)
        checkpoint_db.close()
        assert len(self.hosts) == p.n_hosts

    def initialize_hosts(self):
        p = self.p
        self.hosts = []
        for i in xrange(p.n_hosts):
            lifetime = self.draw_host_lifetime()
            birth_time = -p.demographic_burnin_time - self.rng.uniform(0, lifetime)

            host = Host(i, birth_time, lifetime, self)
            self.hosts.append(host)

    ### SIMULATION CODE ###
    # (also see HOST CLASS below)

    def run(self):
        '''Run model until t_end by repeatedly removing events.'''
        if TRACE_CALLS:
            print_call('Model.run', self)

        if self.dry:
            return

        event_queue = self.event_queue
        p = self.p

        while event_queue.size > 0:
            event_function, t = event_queue.pop()
            self.event_count += 1

            if t > p.t_end:
                break

            # Call the event function to execute a state change.
            # Event function is given access to the current time, the model object,
            # the event queue, and a reference to itself, via function arguments.
            # Additional state (e.g., relevant host ID) can be captured via named
            # arguments with default values in the definition of the function
            # or by using a bound object method where state is stored in the object.
            if TRACE_EVENTS:
                sys.stderr.write('t = {0}\n'.format(t))
                print_call(event_function, t, self, event_queue, event_function)
            event_function(t, self, event_queue, event_function)
    
    def get_fraction_resistant(self):
        n_colonizations = float(self.colonizations_by_age.sum())
        n_resistant = float(self.colonizations_by_age[:,:,1].sum())
        
        if n_colonizations == 0:
            return None
        return n_resistant / n_colonizations
    
    def get_fraction_resistant_for_serotype(self, serotype_id):
        n_colonizations = float(self.colonizations_by_age[:,serotype_id,:].sum())
        n_resistant = float(self.colonizations_by_age[:,serotype_id,1].sum())
        
        if n_colonizations == 0:
            return None
        return n_resistant / n_colonizations
    
    def get_fraction_resistant_history_for_serotype(self, serotype_id):
        if len(self.resistance_history[serotype_id]) == 0:
            return None
        
        frac_resistant_history = sum(self.resistance_history[serotype_id]) / float(len(self.resistance_history[serotype_id]))
        return frac_resistant_history
    
    def do_colonizations_cotransmission(self, t, *args):
        '''Perform colonizations for this timestep (cotransmission model).
        :param t: The current simulation time.
        :param args: Unused arguments passed in by the event queue loop.
        '''
        if TRACE_CALLS:
            print_call('Model.do_colonizations_cotransmission', self, t, *args)

        p = self.p
        
        if p.use_random_mixing:
            self.do_colonizations_cotransmission_random_mixing(t)
        else:
            self.do_colonizations_cotransmission_age_assortative(t)
        self.do_immigration_cotransmission(t)
        
        next_time = t + p.colonization_event_timestep
        if next_time < self.p.t_end:
            self.event_queue.add(self.do_colonizations_cotransmission, next_time)
    
    def do_colonizations_cotransmission_random_mixing(self, t):
        choice_time = 0.0

        p = self.p
        rng = self.rng

        assert p.ratio_foi_resistant_to_sensitive <= 1.0
        
        p_ir_by_serotype = self.get_p_immigration_resistant_by_serotype(t)
        
        col_rate = p.beta
        
        n_contacts = rng.poisson(col_rate * p.colonization_event_timestep * p.n_hosts)
        for i in range(n_contacts):
            target_index = rng.randint(p.n_hosts)
            source_index = rng.randint(p.n_hosts - 1)
            if source_index >= target_index:
                source_index += 1
            
            target_host = self.hosts[target_index]
            source_host = self.hosts[source_index]

            self.do_single_cotransmission(source_host, target_host, t)

    def do_colonizations_cotransmission_age_assortative(self, t):
        p = self.p
        rng = self.rng

        assert p.ratio_foi_resistant_to_sensitive <= 1.0
        p_ir_by_serotype = self.get_p_immigration_resistant_by_serotype(t)

        col_rate = p.beta

        #print self.n_hosts_by_age

        n_contacts = rng.poisson(col_rate * p.colonization_event_timestep * p.n_hosts)
        for i in range(n_contacts):
            target_index = rng.randint(p.n_hosts)
            target_host = self.hosts[target_index]
            if self.no_transmission[target_host.age]:
                continue

            # Choose source so that P(source age = j) = alpha[i, j] for target age i
            while True:
                source_age = randint_weighted(rng, p.n_ages, p = p.alpha[target_host.age,:])
                if self.n_hosts_by_age[source_age] == 0:
                    continue
                source_index = self.hosts_by_age[source_age][rng.randint(len(self.hosts_by_age[source_age]))]
                if source_index == target_index:
                    continue
                source_host = self.hosts[source_index]
                break

            self.do_single_cotransmission(source_host, target_host, t)


    def do_single_cotransmission(self, source_host, target_host, t):
        p = self.p
        rng = self.rng

        n_source_col = source_host.colonizations.sum()
        if n_source_col == 0:
            pass
        else:
            serotype_id_vec, resistant_vec = source_host.colonizations.nonzero()

            # Pre-calculate colonization probabilities
            p_col_vec = numpy.zeros(serotype_id_vec.shape[0])
            for i in range(serotype_id_vec.shape[0]):
                p_col_vec[i] = target_host.get_prob_colonization(serotype_id_vec[i], resistant_vec[i], self)
                if resistant_vec[i]:
                    p_col_vec[i] *= p.ratio_foi_resistant_to_sensitive
                if p.transmission_scaling == 'by_host':
                    p_col_vec[i] /= n_source_col

            # Receive colonizations with pre-calculated colonization probabilities
            # (probabilities are constant across a cotransmission event)
            for i in range(serotype_id_vec.shape[0]):
                for j in range(source_host.colonizations[serotype_id_vec[i], resistant_vec[i]]):
                    if rng.rand() < p_col_vec[i]:
                        target_host.receive_colonization(serotype_id_vec[i], resistant_vec[i], t, self)
    
    def do_immigration_cotransmission(self, t):
        p = self.p
        rng = self.rng
        
        p_ir_by_serotype = self.get_p_immigration_resistant_by_serotype(t)
        
        for serotype_id in range(p.n_serotypes):
            for resistant in (0, 1):
                ir = self.get_immigration_rate(resistant, p_ir_by_serotype[serotype_id])
                n_imm = rng.poisson(ir * p.colonization_event_timestep * p.n_hosts)
                for i in range(n_imm):
                    host = self.hosts[rng.randint(p.n_hosts)]
                    p_col = host.get_prob_colonization(serotype_id, resistant, self)
                    if rng.rand() < p_col:
                        host.receive_colonization(serotype_id, resistant, t, self)
    
    def do_colonizations_independent(self, t, *args):
        '''Perform colonizations for this timestep for all strains.
        :param t: The current simulation time.
        :param args: Unused arguments passed in by the event queue loop.
        '''
        if TRACE_CALLS:
            print_call('Model.do_colonizations_independent', self, t, *args)

        p = self.p
        p_ir_by_serotype = self.get_p_immigration_resistant_by_serotype(t)
        
        for serotype_id in range(p.n_serotypes):
            n_col = [None, None]
            for resistant in (0, 1):
                if p.use_random_mixing:
                    n_col[resistant] = self.do_colonizations_for_strain_random_mixing(serotype_id, resistant, p_ir_by_serotype[serotype_id], t)
                else:
                    n_col[resistant] = self.do_colonizations_for_strain(serotype_id, resistant, p_ir_by_serotype[serotype_id], t)
            
            if self.resistance_history is not None:
                new_colonizations_resistant = [0] * n_col[0] + [1] * n_col[1]
                self.rng.shuffle(new_colonizations_resistant)
                for resistant in new_colonizations_resistant:
                    self.record_resistance_history(serotype_id, resistant)

        next_time = t + self.p.colonization_event_timestep
        if next_time < self.p.t_end:
            self.event_queue.add(self.do_colonizations_independent, next_time)

    def record_resistance_history(self, serotype_id, resistant):
        if len(self.resistance_history[serotype_id]) == self.p.resistance_history_length:
            self.resistance_history[serotype_id].popleft()
        self.resistance_history[serotype_id].append(resistant)
    
    def do_colonizations_for_strain_random_mixing(self, serotype_id, resistant, p_immigration_resistant, t):
        '''Perform colonizations for a single strain (random mixing model).
        :param serotype_id: The serotype to perform colonizations for.
        :param resistant: The resistance class to perform colonizations for.
        :param t: Simulation time.
        '''
        if TRACE_CALLS:
            print_call('Model.do_colonizations_for_strain_no_age_assort', self, serotype_id, resistant, t)

        p = self.p
        rng = self.rng
        
        n_col = self.colonizations_by_age[:, serotype_id, resistant].sum()
        col_rate = p.beta * n_col / (p.n_hosts - 1)
        if resistant:
            col_rate *= p.ratio_foi_resistant_to_sensitive

        col_rate += self.get_immigration_rate(resistant, p_immigration_resistant)
        n_attempts = rng.poisson(col_rate * p.colonization_event_timestep * p.n_hosts)
        
        n_colonizations_received = 0
        
        for host_index in rng.choice(p.n_hosts, size=n_attempts):
            host = self.hosts[host_index]
            col_rate_delta = p.beta * host.colonizations[serotype_id, resistant] / (p.n_hosts - 1)
            if resistant:
                col_rate_delta *= p.ratio_foi_resistant_to_sensitive
            col_rate_adjusted = col_rate - col_rate_delta
            prob_colonization = col_rate_adjusted / col_rate * host.get_prob_colonization(serotype_id, resistant, self)
            if rng.rand() < prob_colonization:
                host.receive_colonization(serotype_id, resistant, t, self)
                n_colonizations_received += 1
        
        return n_colonizations_received
    
    def do_colonizations_for_strain(self, serotype_id, resistant, p_immigration_resistant, t):
        '''Perform colonizations for a single strain (age-based mixing model).
        :param serotype_id: The serotype to perform colonizations for.
        :param resistant: The resistance class to perform colonizations for.
        :param t: Simulation time.
        '''
        if TRACE_CALLS:
            print_call('Model.do_colonizations_for_strain', self, serotype_id, resistant, t)

        p = self.p
        rng = self.rng
        
        colonization_rates_by_age = self.get_colonization_rates_by_age(serotype_id, resistant, p_immigration_resistant)
        max_rate = colonization_rates_by_age.max()

        n_colonizations_received = 0
        
        def get_rate_adjusted(host):
            rate_adjusted = colonization_rates_by_age[host.age]
            if self.colonizations_by_age[age, serotype_id, resistant] > 0:
                rate_adjusted -= p.beta * p.alpha[age,age] \
                    * self.colonizations_by_age[age, serotype_id, resistant] \
                    / self.n_hosts_by_age[age]
                if self.n_hosts_by_age[age] > 1:
                    rate_adjusted += p.beta * p.alpha[age,age] * (
                        self.colonizations_by_age[age, serotype_id, resistant]
                        - host.colonizations[serotype_id, resistant]
                    ) / (
                        self.n_hosts_by_age[age] - 1
                    )
            return rate_adjusted
        
        if hasattr(p, 'colonize_host_by_host') and p.colonize_host_by_host:
            for host_index in xrange(p.n_hosts):
                host = self.hosts[host_index]
                age = host.age

                rate_adjusted = get_rate_adjusted(host)
                if rng.rand() < rate_adjusted * host.get_prob_colonization(serotype_id, resistant, self):
                    host.receive_colonization(serotype_id, resistant, t, self)
                    n_colonizations_received += 1

        else:
            n_possible_colonizations = rng.poisson(p.colonization_event_timestep * max_rate * p.n_hosts)
            for host_index in rng.choice(p.n_hosts, size=n_possible_colonizations):
                host = self.hosts[host_index]
                age = host.age

                rate_adjusted = get_rate_adjusted(host)
                
                if rng.rand() < rate_adjusted / max_rate:
                    if rng.rand() < host.get_prob_colonization(serotype_id, resistant, self):
                        host.receive_colonization(serotype_id, resistant, t, self)
                        n_colonizations_received += 1
        
        return n_colonizations_received

    def get_colonization_rates_by_age(self, serotype_id, resistant, p_immigration_resistant):
        '''Get an upper bound on colonization rates for each age class for a particular strain.

        :param serotype_id: The serotype to calculate rates for.
        :param resistant: The resistance class to calculate rates for.
        :return: An n_ages-length one-dimensional array of rates.
        '''
        p = self.p

        rates = numpy.zeros(p.n_ages, dtype=float)

        divisor = numpy.array(numpy.maximum(self.n_hosts_by_age, 1), dtype=float)
        freq = self.colonizations_by_age[:, serotype_id, resistant] / divisor
        for age in range(p.n_ages):
            rates[age] = (freq * p.alpha[age,:]).sum()
        if resistant:
            rates *= p.ratio_foi_resistant_to_sensitive
        rates *= p.beta
        rates += self.get_immigration_rate(resistant, p_immigration_resistant)

        return rates
    
    def get_p_immigration_resistant_bounds(self):
        if hasattr(self.p, 'p_immigration_resistant_bounds'):
            return self.p.p_immigration_resistant_bounds
        return 0.01, 0.99
    
    def get_p_immigration_resistant_by_serotype(self, t):
        p = self.p
        p_ir_lower, p_ir_upper = self.get_p_immigration_resistant_bounds()
        
        p_ir_by_serotype = numpy.zeros(p.n_serotypes, dtype=float)
        
        if p.immigration_resistance_model == 'constant':
            p_ir_by_serotype[:] = p.p_immigration_resistant
        elif p.immigration_resistance_model == 'fraction_resistant_global':
            frac_resistant = self.get_fraction_resistant()
            if frac_resistant is None:
                p_ir_by_serotype[:] = p.p_immigration_resistant
            else:
                p_ir_by_serotype[:] = max(min(frac_resistant, p_ir_upper), p_ir_lower)
        elif p.immigration_resistance_model == 'fraction_resistant_by_serotype':
            for serotype_id in range(p.n_serotypes):
                frac_resistant = self.get_fraction_resistant_for_serotype(serotype_id)
                if frac_resistant is None:
                    p_ir_by_serotype[serotype_id] = p.p_immigration_resistant
                else:
                    p_ir_by_serotype[serotype_id] = max(min(frac_resistant, p_ir_upper), p_ir_lower)
        elif p.immigration_resistance_model == 'history_by_serotype':
            for serotype_id in range(p.n_serotypes):
                frac_resistant = self.get_fraction_resistant_history_for_serotype(serotype_id)
                if frac_resistant is None:
                    p_ir_by_serotype[serotype_id] = p.p_immigration_resistant
                else:
                    p_ir_by_serotype[serotype_id] = max(min(frac_resistant, p_ir_upper), p_ir_lower)
                
                if (t % p.output_timestep) == 0.0:
                    self.db.execute('INSERT INTO immigration_resistance VALUES (?,?,?,?,?)', [
                        t, serotype_id, len(self.resistance_history[serotype_id]),
                        sum(self.resistance_history[serotype_id]), p_ir_by_serotype[serotype_id]
                    ])
        else:
            assert False, 'Invalid immigration resistant model {}'.format(p.immigration_resistance_model)
        
        return p_ir_by_serotype

    def get_immigration_rate(self, resistant, p_immigration_resistant):
        '''Helper function to just calculate the immigration rate.
        :param resistant: Whether or not the strain is resistant.
        :return: The immigration rate, per host, per unit time.
        '''
        immigration_rate = self.p.immigration_rate
        if resistant:
            immigration_rate *= p_immigration_resistant
        else:
            immigration_rate *= 1.0 - p_immigration_resistant
        return immigration_rate
    
    def draw_host_lifetime(self):
        lifetime = self.lifetime_dist.next_continuous() * self.p.t_year
        return lifetime

    def draw_treatment_times(self, birth_time, death_time):
        p = self.p
        rng = self.rng

        lifetime = death_time - birth_time
        lifetime_years = lifetime / p.t_year

        treatment_times = []
        n_ages = int(numpy.floor(lifetime_years))
        for age in range(n_ages):
            mean_n_treatments = p.treatment_multiplier * p.mean_n_treatments_per_age[age]
            if age == n_ages:
                mean_n_treatments *= (lifetime_years - n_ages)
            n_treatments = rng.poisson(mean_n_treatments)

            # Draw treatments with uniform random start times, normally-distributed
            # durations, until there is a delay >= min_time_between_treatments
            # between all of them, including the last one from the previous year.
            done = False
            while not done:
                age_treatment_times = numpy.zeros((n_treatments, 2), dtype=float)
                if n_treatments == 0:
                    done = True
                    break
                age_treatment_times[:,0] = numpy.sort(rng.uniform(
                    birth_time + age * p.t_year,
                    min(death_time, birth_time + (age + 1) * p.t_year),
                    size=n_treatments
                ))
                age_treatment_times[:,1] = age_treatment_times[:,0] + numpy.maximum(
                    rng.normal(p.treatment_duration_mean, p.treatment_duration_sd, size=n_treatments),
                    0.0
                )
                done = True
                # If the start time for the first treatment is too early, we need to redraw.
                if age > 0 and len(treatment_times) > 0:
                    if age_treatment_times[0,0] < treatment_times[-1][1] + p.min_time_between_treatments:
                        done = False
                # If any of the rest of the start times are too early, we need to redraw.
                if done:
                    if numpy.sum(
                        age_treatment_times[1:,0] < age_treatment_times[:-1,1] + p.min_time_between_treatments
                    ) > 0:
                        done = False
            treatment_times += age_treatment_times.tolist()
        return numpy.array(treatment_times)

    def adjust_age_count(self, age, delta):
        '''Adjust the count of number of hosts at a particular age.

        :param age: The age to modify.
        :param delta: The amount to change the count by.
        '''
        self.n_hosts_by_age[age] += delta

    def adjust_colonizations_by_age(self, age, delta_matrix):
        '''Adjust all colonization counts at a particular age.

        :param age: The age to modify.
        :param delta_matrix: A matrix of size (n_serotypes, 2) to change the counts by.
        '''
        self.colonizations_by_age[age] += delta_matrix

    def adjust_colonizations_by_age_strain(self, age, serotype_id, resistant, delta):
        '''Adjust the colonization count for a particular age and strain.

        :param age: The age to modify the counts of.
        :param serotype_id: The serotype_id to modify the counts of.
        :param resistant: The resistance class to modify the counts of.
        :param delta: The amount to change the count by.
        '''
        self.colonizations_by_age[age, serotype_id, resistant] += delta


    ### INITIALIZATION HELPER FUNCTIONS ###

    def initialize_colonizations_and_immunity(self, t, model, event_queue, me):
        '''Initialize colonizations and immunity at t = 0.'''
        if TRACE_CALLS:
            print_call('Model.initialize_colonizations_and_immunity', self, t, *args)

        p = self.p
        rng = self.rng

        for host in self.hosts:
            host.past_colonizations = numpy.array(
                rng.binomial(1, p.p_init_immune, size=(p.n_serotypes, 2))
            , dtype=int)

        for serotype_id in range(p.n_serotypes):
            p_colonization = p.init_prob_host_colonized[serotype_id]
            p_colonization_sensitive = p_colonization * (1.0 - p.init_prob_resistant)
            p_colonization_resistant = p_colonization * p.init_prob_resistant
            for resistant in (0, 1):
                n_colonizations = max(
                    1,
                    rng.binomial(
                        p.n_hosts,
                        p_colonization_resistant if resistant else p_colonization_sensitive
                    )
                )
                for i in range(n_colonizations):
                    host_index = rng.random_integers(0, p.n_hosts - 1)

                    self.hosts[host_index].receive_colonization(
                        serotype_id, resistant, t, self
                    )
        
        self.schedule_do_colonizations()

    def initialize_loaded_host_colonizations(self, t, *args):
        for host in self.hosts:
            host.update_next_clearance(t, self)
        self.schedule_do_colonizations()
    
    def schedule_do_colonizations(self):
        p = self.p
        
        if not hasattr(p, 'transmission_model') or p.transmission_model == 'independent':
            assert not hasattr(p, 'transmission_scaling') or p.transmission_scaling == 'by_colonization'
            self.event_queue.add(self.do_colonizations_independent, 0.0)
        elif p.transmission_model == 'cotransmission':
            self.event_queue.add(self.do_colonizations_cotransmission, 0.0)
        else:
            assert False, 'invalid transmission model {}'.format(p.transmission_model)
        
    
    def load_parameter(self, param_name, make_array=True):
        '''If parameter is set to a string, load from a file; also convert it to a numpy array if requested.'''
        param_value = getattr(self.p, param_name)
        if isinstance(param_value, basestring):
            preset_name = param_value
            with open(os.path.join(SCRIPT_DIR, '..', 'parameters', '{0}_{1}.json'.format(param_name, preset_name))) as f:
                param_value = json.load(f)

        if make_array:
            setattr(self.p, param_name, numpy.array(param_value))
        else:
            setattr(self.p, param_name, param_value)

    def set_up_parameters(self):
        p = self.p

        if not hasattr(p, 'output_start'):
            p.output_start = 0.0

        if not hasattr(p, 'load_hosts_from_checkpoint'):
            p.load_hosts_from_checkpoint = False
        if not hasattr(p, 'checkpoint_save_prefix'):
            p.checkpoint_save_prefix = 'checkpoint_out'
        if not hasattr(p, 'checkpoint_load_path'):
            p.checkpoint_load_path = 'checkpoint_in.sqlite'
        if not hasattr(p, 'checkpoint_start'):
            p.checkpoint_start = None
        if not hasattr(p, 'checkpoint_timestep'):
            p.checkpoint_timestep = None

        if p.load_hosts_from_checkpoint:
            assert p.demographic_burnin_time == 0.0

        # Load alpha and expand/contract if necessary
        if p.alpha is not None:
            self.load_parameter('alpha')
            assert p.alpha.shape[0] == p.alpha.shape[1]
            if p.alpha.shape[0] < p.n_ages:
                alpha_big = numpy.zeros((p.n_ages, p.n_ages), dtype=float)
                alpha_big[:p.alpha.shape[0], :p.alpha.shape[1]] = p.alpha
                p.alpha = alpha_big
            if p.alpha.shape[0] > p.n_ages:
                p.alpha = p.alpha[:p.n_ages, :p.n_ages]

            self.no_transmission = numpy.zeros(p.n_ages, dtype = bool)
            for i in range(p.n_ages):
                p_alpha_sum_i = p.alpha[i,:].sum()
                if p_alpha_sum_i > 0.0:
                    p.alpha[i,:] /= p.alpha[i,:].sum()
                else:
                    self.no_transmission[i] = True

        # Load gamma
        self.load_parameter('gamma')
        assert p.gamma.shape[0] >= p.n_serotypes

        # Load lifetime_distribution
        self.load_parameter('lifetime_distribution')

        # Load mean_n_treatments_per_age
        self.load_parameter('mean_n_treatments_per_age')

        # Set up random seed
        if p.random_seed is None or p.random_seed == 0:
            seed_rng = random.SystemRandom()
            p.random_seed = seed_rng.randint(1, 2**31)

        # Map between ages and output age classes
        if hasattr(p, 'output_ageclasses'):
            self.ageclass_index = numpy.zeros(p.n_ages, dtype=int)
            if len(p.output_ageclasses) == 0:
                self.n_ageclasses = 1
            else:
                age = 0
                for ageclass, size in enumerate(p.output_ageclasses):
                    for i in range(size):
                        self.ageclass_index[age] = ageclass
                        age += 1
                if age < p.n_ages:
                    ageclass += 1
                    while age < p.n_ages:
                        self.ageclass_index[age] = ageclass
                        age += 1
                
                self.n_ageclasses = ageclass + 1
        else:
            self.n_ageclasses = None
            self.ageclass_index = None


    ### VERIFICATION ###

    def verify(self, t, *args):
        for host in self.hosts:
            host.verify(t, self)
        
        self.verify_serotype_ranks()
        self.verify_counts()
        self.event_queue.verify()
        
        next_time = t + self.p.verification_timestep
        if next_time <= self.p.t_end:
            self.event_queue.add(self.verify, t + self.p.verification_timestep)
    
    def verify_serotype_ranks(self):
        p = self.p
        #gamma_sorted = numpy.array(p.gamma)[self.serotype_ranks]
        for i in range(0, p.n_serotypes - 1):
            assert p.gamma[i] >= p.gamma[i+1]
    
    def verify_counts(self):
        p = self.p
        
        assert self.n_hosts_by_age.sum() == p.n_hosts
        
        n_hosts_by_age = numpy.zeros(p.n_ages, dtype=int)
        colonizations_by_age = numpy.zeros((p.n_ages, p.n_serotypes, 2), dtype=int)
        for host in self.hosts:
            n_hosts_by_age[host.age] += 1
            if host.colonizations is not None:
                colonizations_by_age[host.age,:,:] += host.colonizations
        
        assert numpy.array_equal(n_hosts_by_age, self.n_hosts_by_age)
        assert numpy.array_equal(colonizations_by_age, self.colonizations_by_age)


    ### DATABASE SETUP AND OUTPUT ###

    def init_database(self):
        p = self.p
        
        if os.path.exists(p.db_filename):
            if p.overwrite_db:
                os.remove(p.db_filename)
            else:
                sys.stderr.write('{} already exists; aborting.\n'.format(p.db_filename))
                sys.exit(1)
        db = sqlite3.connect(p.db_filename)
        
        if hasattr(p, 'job_info'):
            jobs_colnames = p.job_info.keys()
            db.execute('CREATE TABLE jobs ({})'.format(', '.join(jobs_colnames)))
            db.execute(
                'INSERT INTO jobs VALUES ({})'.format(', '.join(['?'] * len(jobs_colnames))),
                [p.job_info[jobs_colname] for jobs_colname in jobs_colnames]
            )
        
        db.execute('CREATE TABLE parameters (parameters)')
        db.execute('INSERT INTO parameters VALUES (?)', [json.dumps(object_to_json_dict(p), indent=2)])
        
        if p.immigration_resistance_model == 'history_by_serotype':
            db.execute('''CREATE TABLE immigration_resistance
                (t, serotype_id, history_length, n_resistant, p_immigration_resistant)
            ''')
        
        ### OUTPUT DATABASES PRE-STRATIFIED BY MULTIPLE-AGE CLASSES
        if self.ageclass_index is not None:
            db.execute('CREATE TABLE ageclasses (age, ageclass)')
            for age in range(p.n_ages):
                db.execute('INSERT INTO ageclasses VALUES (?,?)', [age, self.ageclass_index[age]])
            
            db.execute('''CREATE TABLE counts_by_ageclass_treatment
                (t, ageclass, in_treatment, n_hosts, n_colonized, n_colonizations, n_colonized_by_sensitive_and_resistant)
            ''')

            db.execute('''CREATE TABLE counts_by_ageclass_treatment_strain
                (t, ageclass, in_treatment, serotype_id, resistant, n_colonized, n_colonizations)
            ''')
            
            db.execute('''CREATE TABLE counts_by_ageclass_treatment_n_colonizations
                (t, ageclass, in_treatment, n_colonizations, n_hosts)
            
            ''')

        ### OUTPUT DATABASES BY EVERY AGE (YEAR)
        if not hasattr(p, 'enable_output_by_age') or p.enable_output_by_age:
            db.execute('''CREATE TABLE counts_by_age_treatment
                (t, age, in_treatment, n_hosts, n_colonized, n_colonizations, n_colonized_by_sensitive_and_resistant)
            ''')

            db.execute('''CREATE TABLE counts_by_age_treatment_strain
                (t, age, in_treatment, serotype_id, resistant, n_colonized, n_colonizations)
            ''')

            db.execute('''CREATE TABLE counts_by_age_treatment_n_colonizations
                (t, age, in_treatment, n_colonizations, n_hosts)
            ''')

        db.execute('''CREATE TABLE summary
            (t, n_colonized, n_colonizations)
        ''')

        db.commit()

        self.db = db
    
    def write_output(self, t, *args):
        p = self.p
        
        if TRACE_CALLS:
            print_call('Model.write_output', self, t, *args)
        
        sys.stderr.write('t = {0}\n'.format(t))

        new_event_count = self.event_count - self.event_counts[-1]
        walltime = time.time()
        memusage = get_memusage()

        delta_memusage = memusage - self.memusages[-1]
        elapsed_walltime = walltime - self.walltimes[-1]

        self.event_counts.append(self.event_count)
        self.walltimes.append(walltime)
        self.memusages.append(memusage)

        sys.stderr.write('time = {0} (change {1})\n'.format(walltime - self.walltimes[0], elapsed_walltime))
        sys.stderr.write('event count = {0} (change {1})\n'.format(self.event_count, new_event_count))
        sys.stderr.write('events per second = {0}\n'.format(new_event_count / elapsed_walltime))
        sys.stderr.write('memory usage: {0} (change {1})\n'.format(
            memusage, delta_memusage
        ))
        sys.stderr.write('total colonizations: {0}\n'.format(self.colonizations_by_age.sum()))

        if not hasattr(p, 'use_calendar_queue') or p.use_calendar_queue:
            sys.stderr.write('event queue bucket width: {0}\n'.format(self.event_queue.bucket_width))
        
        sys.stderr.write('  Writing output to database...\n')
        
        if self.ageclass_index is not None:
            self.write_counts_by_ageclass_treatment(t)
            self.write_counts_by_ageclass_treatment_strain(t)
            self.write_counts_by_ageclass_treatment_n_colonizations(t)
        
        if not hasattr(p, 'enable_output_by_age') or p.enable_output_by_age:
            self.write_counts_by_age_treatment(t)
            self.write_counts_by_age_treatment_strain(t)
            self.write_counts_by_age_treatment_n_colonizations(t)

        self.write_age_distribution(t)
        self.write_summary(t)

        sys.stderr.write('  ...done.\n')
        
        next_time = t + self.p.output_timestep
        if next_time <= self.p.t_end:
            self.event_queue.add(self.write_output, next_time)

    def write_counts_by_age_treatment(self, t):
        p = self.p
        
        n_hosts = numpy.zeros((p.n_ages,2), dtype=int)
        n_colonized = numpy.zeros((p.n_ages,2), dtype=int)
        n_colonizations = numpy.zeros((p.n_ages,2), dtype=int)
        n_colonized_by_s_and_r = numpy.zeros((p.n_ages,2), dtype=int)
        for host in self.hosts:
            n_hosts[host.age, host.in_treatment] += 1
            host_n_col = host.colonizations.sum()
            if host_n_col > 0:
                n_colonized[host.age, host.in_treatment] += 1
            n_colonizations[host.age, host.in_treatment] += host_n_col
            
            if host.colonizations[:,0].sum() > 0 and host.colonizations[:,1].sum() > 0:
                n_colonized_by_s_and_r[host.age, host.in_treatment] += 1
        
        for age in range(p.n_ages):
            assert n_colonizations[age,0] + n_colonizations[age,1] == self.colonizations_by_age[age,:,:].sum()
            for in_treatment in (False, True):
                self.db.execute('INSERT INTO counts_by_age_treatment VALUES (?,?,?,?,?,?,?)',
                    [t, age, in_treatment, n_hosts[age,in_treatment], n_colonized[age,in_treatment], n_colonizations[age,in_treatment], n_colonized_by_s_and_r[age,in_treatment]]
                )
        self.db.commit()
    
    def write_counts_by_ageclass_treatment(self, t):
        p = self.p
        
        n_hosts = numpy.zeros((self.n_ageclasses,2), dtype=int)
        n_colonized = numpy.zeros((self.n_ageclasses,2), dtype=int)
        n_colonizations = numpy.zeros((self.n_ageclasses,2), dtype=int)
        n_colonized_by_s_and_r = numpy.zeros((self.n_ageclasses,2), dtype=int)
        for host in self.hosts:
            ageclass = self.ageclass_index[host.age]
            n_hosts[ageclass, host.in_treatment] += 1
            host_n_col = host.colonizations.sum()
            if host_n_col > 0:
                n_colonized[ageclass, host.in_treatment] += 1
            n_colonizations[ageclass, host.in_treatment] += host_n_col
            
            if host.colonizations[:,0].sum() > 0 and host.colonizations[:,1].sum() > 0:
                n_colonized_by_s_and_r[ageclass, host.in_treatment] += 1
        
        for ageclass in range(self.n_ageclasses):
            for in_treatment in (False, True):
                self.db.execute('INSERT INTO counts_by_ageclass_treatment VALUES (?,?,?,?,?,?,?)',
                    [t, ageclass, in_treatment, n_hosts[ageclass,in_treatment], n_colonized[ageclass,in_treatment], n_colonizations[ageclass,in_treatment], n_colonized_by_s_and_r[ageclass,in_treatment]]
                )
        self.db.commit()
    
    def write_counts_by_age_treatment_strain(self, t):
        p = self.p
        
        n_colonized = numpy.zeros((p.n_ages, 2, p.n_serotypes, 2), dtype=int)
        n_colonizations = numpy.zeros((p.n_ages, 2, p.n_serotypes, 2), dtype=int)
        
        for host in self.hosts:
            n_colonized[host.age, host.in_treatment,:,:] += numpy.array(host.colonizations, dtype=bool)
            n_colonizations[host.age, host.in_treatment,:,:] += host.colonizations
        for age in range(p.n_ages):
            for in_treatment in (False, True):
                for serotype_id in range(p.n_serotypes):
                    for resistant in (False, True):
                        self.db.execute(
                            'INSERT INTO counts_by_age_treatment_strain VALUES (?,?,?,?,?,?,?)',
                            [t, age, in_treatment, serotype_id, resistant, n_colonized[age,in_treatment,serotype_id,resistant], n_colonizations[age,in_treatment,serotype_id,resistant]]
                        )
        self.db.commit()
    
    def write_counts_by_ageclass_treatment_strain(self, t):
        p = self.p
        
        n_colonized = numpy.zeros((self.n_ageclasses, 2, p.n_serotypes, 2), dtype=int)
        n_colonizations = numpy.zeros((self.n_ageclasses, 2, p.n_serotypes, 2), dtype=int)
        
        for host in self.hosts:
            ageclass = self.ageclass_index[host.age]
            n_colonized[ageclass, host.in_treatment,:,:] += numpy.array(host.colonizations, dtype=bool)
            n_colonizations[ageclass, host.in_treatment,:,:] += host.colonizations
        for ageclass in range(self.n_ageclasses):
            for in_treatment in (False, True):
                for serotype_id in range(p.n_serotypes):
                    for resistant in (False, True):
                        self.db.execute('INSERT INTO counts_by_ageclass_treatment_strain VALUES (?,?,?,?,?,?,?)', [
                            t,
                            ageclass,
                            in_treatment,
                            serotype_id,
                            resistant,
                            n_colonized[ageclass,in_treatment,serotype_id,resistant],
                            n_colonizations[ageclass,in_treatment,serotype_id,resistant]
                        ])
        self.db.commit()
    
    def write_counts_by_age_treatment_n_colonizations(self, t):
        p = self.p
        
        max_n_col = 0
        for host in self.hosts:
            host_n_col = int(host.colonizations.sum())
            if host_n_col > max_n_col:
                max_n_col = host_n_col
        
        n_hosts = numpy.zeros((p.n_ages, 2, max_n_col+1), dtype=int)
        for host in self.hosts:
            host_n_col = host.colonizations.sum()
            n_hosts[host.age, host.in_treatment, host_n_col] += 1
        
        for age in range(p.n_ages):
            for in_treatment in (False, True):
                for n_col in range(max_n_col+1):
                    self.db.execute('INSERT INTO counts_by_age_treatment_n_colonizations VALUES (?,?,?,?,?)', [
                        t,
                        age,
                        in_treatment,
                        n_col,
                        n_hosts[age,in_treatment,n_col]
                    ])
        
        self.db.commit()
    
    def write_counts_by_ageclass_treatment_n_colonizations(self, t):
        p = self.p
        
        max_n_col = 0
        for host in self.hosts:
            host_n_col = int(host.colonizations.sum())
            if host_n_col > max_n_col:
                max_n_col = host_n_col
        
        n_hosts = numpy.zeros((self.n_ageclasses, 2, max_n_col+1), dtype=int)
        for host in self.hosts:
            ageclass = self.ageclass_index[host.age]
            host_n_col = host.colonizations.sum()
            n_hosts[ageclass, host.in_treatment, host_n_col] += 1
        
        for ageclass in range(self.n_ageclasses):
            for in_treatment in (False, True):
                for n_col in range(max_n_col+1):
                    self.db.execute('INSERT INTO counts_by_ageclass_treatment_n_colonizations VALUES (?,?,?,?,?)', [
                        t,
                        ageclass,
                        in_treatment,
                        n_col,
                        n_hosts[ageclass,in_treatment,n_col]
                    ])
        
        self.db.commit()
    
    def write_summary(self, t):
        p = self.p
        
        n_colonized = 0
        n_colonizations = 0
        for host in self.hosts:
            host_n_col = host.colonizations.sum()
            n_colonizations += host_n_col
            if host_n_col > 0:
                n_colonized += 1
        
        self.db.execute('INSERT INTO summary VALUES (?,?,?)',
            [t, n_colonized, n_colonizations]
        )
        self.db.commit()

    def write_age_distribution(self, t):
        p = self.p

        self.db.execute('CREATE TABLE IF NOT EXISTS age_distribution (t, age, n_hosts)')
        for age in range(p.n_ages):
            self.db.execute('INSERT INTO age_distribution VALUES (?,?,?)', [t, age, self.n_hosts_by_age[age]])
        self.db.commit()

    def write_checkpoint(self, t, *args):
        p = self.p

        tmp_path = p.checkpoint_save_prefix + '_tmp.sqlite'
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        state_db = sqlite3.connect(tmp_path)

        state_db.execute('CREATE TABLE meta (t, rng)')
        rngfile = StringIO()
        pickle.dump(self.rng, rngfile)
        rngbuf = buffer(rngfile.getvalue())
        rngfile.close()
        state_db.execute('INSERT INTO meta VALUES (?,?)', [t, rngbuf])
        
        state_db.execute('''CREATE TABLE hosts
            (birth_time, lifetime, colonizations, past_colonizations, treatment_times)
        ''')

        for host in self.hosts:
            state_db.execute('INSERT INTO hosts VALUES (?,?,?,?,?)', [
                host.birth_time,
                host.death_time - host.birth_time,
                npybuffer.ndarray_to_npy_buffer(host.colonizations),
                npybuffer.ndarray_to_npy_buffer(host.past_colonizations),
                npybuffer.ndarray_to_npy_buffer(host.treatment_times)
            ])

        state_db.commit()
        state_db.close()

        final_path = p.checkpoint_save_prefix + '.sqlite'
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(tmp_path, final_path)
        
        if p.checkpoint_timestep is not None and p.checkpoint_timestep > 0.0:
            next_time = t + p.checkpoint_timestep
            if next_time <= self.p.t_end:
                self.event_queue.add(self.write_checkpoint, next_time)

    def __str__(self):
        return 'model'


### HOST CLASS ###

class Host(object):
    def __init__(
            self, index, birth_time, lifetime, model,
            treatment_times=None, colonizations=None, past_colonizations=None
    ):
        if TRACE_CALLS:
            print_call('Host.__init__', index, birth_time, lifetime, model)
        
        p = model.p
        event_queue = model.event_queue
        
        self.index = index
        self.age = 0
        self.birth_time = birth_time
        self.death_time = birth_time + lifetime
        
        if lifetime > p.t_year:
            event_queue.add(self.celebrate_birthday, birth_time + p.t_year)
        else:
            event_queue.add(self.reset, self.death_time)
        
        # Colonization/treatment dynamics only happen for t >= 0 (after demographic burnin).
        if self.death_time >= 0:
            # Number of current colonizations for each serotype/resistance class
            if colonizations is not None:
                self.colonizations = colonizations
            else:
                self.colonizations = numpy.zeros((p.n_serotypes, 2), dtype=int)
            
            # Number of past colonizations for each serotype/resistance class
            if past_colonizations is not None:
                self.past_colonizations = past_colonizations
            else:
                self.past_colonizations = numpy.zeros((p.n_serotypes, 2), dtype=int)
            
            # Treatment times: n x 2 array, where n is the total number of treatments;
            # treatment_times[i,0] is the start time, and treatment_times[i,1] is the end time
            if treatment_times is not None:
                self.treatment_times = treatment_times
            else:
                self.treatment_times = model.draw_treatment_times(self.birth_time, self.death_time)

            if self.treatment_times.shape[0] == 0:
                self.in_treatment = False
                self.treatment_times = None
                self.treatment_index = -1
            else:
                # Whether the host is currently in treatment
                self.in_treatment = False
                if self.treatment_times.shape[0] > 0:
                    # If in_treatment = False, this is the index of the treatment to be started next.
                    # If in_treatment = True, this is the treatment that is currently active.
                    self.treatment_index = 0

                    # One treatment event is on the event queue at any time; 
                    # the first one corresponds to starting the first treatment.
                    # When called, step_treatment will schedule its own next invocation.
                    event_queue.add(self.step_treatment, self.treatment_times[0,0])
        else:
            self.colonizations = None
            self.past_colonizations = None
            self.treatment_times = None
            self.in_treatment = False
            self.treatment_index = -1
    
    def reset(self, t, model, event_queue, event_function):
        if TRACE_CALLS:
            print_call('Host.reset', self, t, model, event_queue, event_function)

        if self.colonizations is not None:
            event_queue.remove_if_present(self.clear_colonization)

        model.adjust_age_count(self.age, -1)
        model.hosts_by_age[self.age].remove(self.index)
        
        if self.colonizations is not None:
            model.adjust_colonizations_by_age(self.age, -self.colonizations)
        lifetime = model.draw_host_lifetime()
        model.hosts[self.index] = Host(self.index, t, lifetime, model)
        model.adjust_age_count(0, 1)
        model.hosts_by_age[0].append(self.index)
    
    def celebrate_birthday(self, t, model, event_queue, event_function):
        if TRACE_CALLS:
            print_call('Host.celebrate_birthday', self, t, model, event_queue, event_function)
        
        p = model.p

        # sys.stderr.write('age: {}\n'.format(self.age))
        model.hosts_by_age[self.age].remove(self.index)
        model.adjust_age_count(self.age, -1)
        if self.colonizations is not None:
            model.adjust_colonizations_by_age(self.age, -self.colonizations)
        self.age += 1
        model.adjust_age_count(self.age, 1)
        model.hosts_by_age[self.age].append(self.index)
        if self.colonizations is not None:
            model.adjust_colonizations_by_age(self.age, self.colonizations)
        
        next_birthday = t + model.p.t_year
        if next_birthday < self.death_time:
            event_queue.add(self.celebrate_birthday, next_birthday)
        else:
            event_queue.add(self.reset, self.death_time)
    
    def step_treatment(self, t, model, event_queue, event_function):
        if TRACE_CALLS:
            print_call('Host.step_treatment', self, t, model, event_queue, event_function)
        
        # If currently treating, stop treatment and schedule the next one.
        if self.in_treatment:
            self.in_treatment = False
            self.treatment_index += 1
            if self.treatment_index < self.treatment_times.shape[0]:
                event_queue.add(
                    self.step_treatment,
                    self.treatment_times[self.treatment_index,0]
                )
        # If currently not treating, start treatment and schedule the end of treatment
        else:
            self.in_treatment = True
            end_time = self.treatment_times[self.treatment_index,1]
            if end_time < self.death_time:
                event_queue.add(self.step_treatment, end_time)
        
        self.update_next_clearance(t, model)
    
    def calculate_mean_clearance_duration(self, serotype_id, resistant, model):
        p = model.p
        rng = model.rng
        
        if self.in_treatment:
            if p.treatment_multiplier == 0.0:
                assert False
            
            if resistant:
                mean_duration = p.gamma_treated_sensitive * p.gamma_treated_ratio_resistant_to_sensitive
            else:
                mean_duration = p.gamma_treated_sensitive
        else:
            mean_duration = p.kappa + (p.gamma[serotype_id] - p.kappa) * numpy.exp(-p.epsilon * self.past_colonizations.sum())
            if resistant:
                mean_duration *= p.xi
        
        return mean_duration
    
    def clear_colonization(self, t, model, event_queue, event_function):
        if not t == self.next_clearance_time:
            sys.stderr.write('{}, {}\n'.format(t, self.next_clearance_time))
            sys.stderr.write('{}\n'.format(self.colonizations))
        assert t == self.next_clearance_time
        serotype_id = self.next_clearance_serotype_id
        resistant = self.next_clearance_resistant
        
        self.colonizations[serotype_id, resistant] -= 1
        self.past_colonizations[serotype_id, resistant] += 1
        model.adjust_colonizations_by_age_strain(self.age, serotype_id, resistant, -1)
        
        self.update_next_clearance(t, model)
    
    def get_prob_colonization(self, serotype_id, resistant, model):
        p = model.p
        
        if self.colonizations.sum() == 0:
            omega = 0.0
        else:
            if p.n_serotypes == 1:
                omega = p.mu_max
            else:
                min_serotype_rank = numpy.min(numpy.nonzero(self.colonizations.sum(axis=1))[0])
                omega = p.mu_max * (1.0 - min_serotype_rank / (p.n_serotypes - 1.0))
        
        prob_colonization = 1 - omega
        if self.past_colonizations[serotype_id,:].sum() > 0:
            prob_colonization *= 1 - p.sigma
        
        return prob_colonization
    
    def receive_colonization(self, serotype_id, resistant, t, model):
        self.colonizations[serotype_id, resistant] += 1
        model.adjust_colonizations_by_age_strain(self.age, serotype_id, resistant, 1)
        
        self.update_next_clearance(t, model)
    
    def update_next_clearance(self, t, model):
        '''Updates state for the next clearance event.
        
        Specifically: recalculates clearance rates for all current colonized strains;
        draws the time to the next clearance event;
        chooses which strain will be cleared next;
        and updates the clearance event on the event queue.
        '''
        if TRACE_CALLS:
            print_call('Host.update_next_clearance', self)

        # Don't update before the start of time; that's demographic burnin for checkpoint loading.
        if t < 0.0:
            return

        # Get arrays for serotype_id, resistant corresponding to nonzero entries
        # in colonizations array
        nz_sero, nz_res = numpy.nonzero(self.colonizations)
        
        if nz_sero.shape[0] == 0:
            assert not model.event_queue.contains(self.clear_colonization)
            return
        
        # Calculate clearance rates for all present strains
        rates = numpy.zeros(nz_sero.shape[0])
        for strain_index in range(nz_sero.shape[0]):
            serotype_id = nz_sero[strain_index]
            resistant = nz_res[strain_index]
            
            # rate for this strain = [# colonizations] / [mean duration of one colonization]
            rates[strain_index] = self.colonizations[serotype_id, resistant] / self.calculate_mean_clearance_duration(
                serotype_id, resistant, model
            )
            assert not numpy.isinf(rates[strain_index])
            assert not numpy.isnan(rates[strain_index])
            assert rates[strain_index] > 0.0
        rates_sum = rates.sum()
        
        # Draw clearance time
        self.next_clearance_time = t + model.rng.exponential(scale = 1.0 / rates_sum)
        
        # Choose strain to be cleared
        strain_index = model.rng.choice(nz_sero.shape[0], size=1, p=(rates / rates_sum))
        self.next_clearance_serotype_id = nz_sero[strain_index]
        self.next_clearance_resistant = nz_res[strain_index]
        
        # Update clearance event
        model.event_queue.add_or_update(self.clear_colonization, self.next_clearance_time)

    def verify(self, t, model):
        if TRACE_CALLS:
            print_call('Host.verify', self, t, model)
        p = model.p
        event_queue = model.event_queue
        
        assert t <= self.death_time
        age_lower = int(numpy.floor((t - self.birth_time - EPS) / p.t_year))
        age = int(numpy.floor((t - self.birth_time) / p.t_year))
        age_upper = int(numpy.floor((t - self.birth_time + EPS) / p.t_year))
        assert self.age == age or self.age == age_lower or self.age == age_upper
        
        if self.colonizations is not None:
            for serotype_id in range(p.n_serotypes):
                for resistant in (0, 1):
                    assert self.colonizations[serotype_id, resistant] >= 0
                    assert self.past_colonizations[serotype_id, resistant] >= 0
        
        if self.treatment_times is not None:
            assert self.treatment_index >= 0
            
            for i in range(1, self.treatment_times.shape[0]):
                assert self.treatment_times[i,0] >= self.treatment_times[i-1,1] + p.min_time_between_treatments
            if self.in_treatment:
                assert self.treatment_times[self.treatment_index,0] <= t
                assert self.treatment_times[self.treatment_index,1] >= t
                if self.treatment_times[self.treatment_index,1] < self.death_time:
                    assert event_queue.get_time(self.step_treatment) == self.treatment_times[self.treatment_index,1]
            else:
                if self.treatment_index < self.treatment_times.shape[0]:
                    if self.treatment_index > 0:
                        assert self.treatment_times[self.treatment_index - 1,1] <= t
                    assert self.treatment_times[self.treatment_index,0] >= t
                    assert event_queue.get_time(self.step_treatment) == self.treatment_times[self.treatment_index,0]
    
    def __str__(self):
        return 'hosts[{0}]'.format(self.index)


### UTILITIES ###

def print_call(name, *args):
    '''Prints a function along with its arguments; used to trace all calls in the simulation for debugging purposes.

    :param name:
    :param args:
    :return:
    '''
    sys.stderr.write('{0}({1})\n'.format(name, ', '.join(['{0}'.format(arg) for arg in args])))

def get_memusage():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

def object_to_json_dict(obj):
    d = {}
    for k in dir(obj):
        if not k.startswith('_'):
            v = getattr(obj, k)
            if not (inspect.isroutine(v) or inspect.ismodule(v) or inspect.isclass(v)):
                try:
                    v = v.tolist()
                except:
                    pass
                d[k] = v
    return d

def randint_weighted(rng, n, p):
    pmax = numpy.max(p)
    while True:
        index = rng.randint(n)
        if rng.uniform() < p[index] / pmax:
            return index

class Parameters(object):
    def __init__(self, d):
        for k, v in d.iteritems():
            setattr(self, k, v)

if __name__ == '__main__':
    main()
