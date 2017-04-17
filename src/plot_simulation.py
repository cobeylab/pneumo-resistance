#!/usr/bin/env python

import os
import sys
import argparse
import sqlite3
import json
import numpy
import matplotlib
matplotlib.use('Agg')
matplotlib.rc('font', size=10)
import matplotlib.pyplot as pyplot

def main():
    parser = argparse.ArgumentParser(
        description='Plots output from a single pyresistance simulation.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'db_filename', metavar='<output-database>',
        help='SQLite database of output from simulation.'
    )
    parser.add_argument(
        'plot_filename', metavar='<plot-filename>',
        help='Filename for generated plot.'
    )
    parser.add_argument(
        '--job-id', metavar='<job-id>', type=int, default=None,
        help='Job ID, needed if the database contains multiple runs.'
    )
    parser.add_argument(
        '--n-average-years', metavar='<n-years>', type=float, default=50.0,
        help='Number of years to average over (for averaging plots).'
    )
    parser.add_argument(
        '--n-timeseries-years', metavar='<n-years>', type=float, default=50.0,
        help='Number of years to use for time-series plots.'
    )
    parser.add_argument(
        '--end-year', metavar='<end-year>', type=float, default=None,
        help='Final time used for all plots; if unspecified the final time of the simulation will be used.'
    )
    args = parser.parse_args()
    
    with sqlite3.connect(args.db_filename) as db:
        plot_all(db, args.job_id, args.plot_filename, args.n_average_years, args.n_timeseries_years, args.end_year)


def plot_all(db, job_id, plot_filename, n_average_years, n_timeseries_years, end_year):
    p = get_parameters(db, job_id)
    
    # Get age classes & construct age-class labels
    n_ageclasses = get_n_ageclasses(p)
    ageclass_labels = make_ageclass_labels(p)
    
    # Set up plot
    n_cols = 3
    n_rows = 4 + 5 # p.n_serotypes
    pyplot.figure(figsize=[6 * n_cols, 4 * n_rows])
    
    # Get times to use for plots
    if end_year is None:
        ts, t_indices = get_times(db, job_id)
        end_time = ts[-1]
    else:
        end_time = end_year * p.t_year
    start_time_avg = end_time - n_average_years * p.t_year
    start_time_ts = end_time - n_timeseries_years * p.t_year
    
    # Age distribution over time
    pyplot.subplot(n_rows, n_cols, 1)
    plot_age_distribution_over_time(db, p, job_id, t_start=start_time_ts, t_end=end_time)
    
    # Fraction colonized over time
    pyplot.subplot(n_rows, n_cols, 2)
    plot_fraction_colonized_over_time(db, p, job_id, t_start=start_time_ts, t_end=end_time)
    
    # Fraction prevalence over time
    pyplot.subplot(n_rows, n_cols, 3)
    plot_fraction_prevalence_over_time(db, p, job_id, t_start=start_time_ts, t_end=end_time)
    
    # Fraction of total prevalence, by age class, averaged over time
    pyplot.subplot(n_rows, n_cols, 4)
    plot_mean_fraction_prevalence_by_age(db, p, job_id, t_start=start_time_avg, t_end=end_time)
    
    # Fraction colonized, by # colonizations, averaged over time
    pyplot.subplot(n_rows, n_cols, 5)
    plot_fraction_colonized_by_n_colonizations(db, p, job_id, t_start=start_time_avg, t_end=end_time)
    
    # Fraction resistant, by age class, averaged over time
    pyplot.subplot(n_rows, n_cols, 6)
    plot_fraction_resistant_by_age(db, p, job_id, t_start=start_time_avg, t_end=end_time)
    
    # Number resistant, by age class, averaged over time
    pyplot.subplot(n_rows, n_cols, 7)
    plot_number_resistant_by_age(db, p, job_id, t_start=start_time_avg, t_end=end_time)
    
    # Fraction resistant, by serotype, averaged over time, for first 5 age classes
    for ageclass in range(min(5, n_ageclasses)):
        pyplot.subplot(n_rows, n_cols, 8 + ageclass)
        plot_fraction_resistant_by_serotype(db, p, job_id, ageclass, ageclass_labels[ageclass], t_start=start_time_avg, t_end=end_time)
    
    # Plots for the top 5 serotypes
    for serotype_id in range(5):
        # Fraction colonized, by age class, over time
        pyplot.subplot(n_rows, n_cols, 3 * serotype_id + 13)
        plot_fraction_colonized_by_age_over_time(db, p, job_id, serotype_id, t_start=start_time_ts, t_end=end_time)
        
        # Number colonized, by age class, over time
        pyplot.subplot(n_rows, n_cols, 3 * serotype_id + 14)
        plot_number_colonized_by_age_over_time(db, p, job_id, serotype_id, t_start=start_time_ts, t_end=end_time)
        
        # Fraction resistant, by age class, over time
        pyplot.subplot(n_rows, n_cols, 3 * serotype_id + 15)
        plot_fraction_resistant_by_age_over_time(db, p, job_id, serotype_id, t_start=start_time_ts, t_end=end_time)
    
    pyplot.savefig(plot_filename)


### INDIVIDUAL PLOTTING FUNCTIONS ###

def plot_age_distribution_over_time(db, p, job_id, t_start=None, t_end=None):
    print('plot_age_distribution_over_time')
    
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_ageclasses = get_n_ageclasses(p)
    n_hosts_by_ageclass = numpy.zeros((n_ageclasses, len(ts)), dtype=float)
    for row in db.execute(
        'SELECT t, ageclass, n_hosts FROM counts_by_ageclass_treatment {}'.format(
            'WHERE job_id = ?' if job_id is not None else ''
        ), [job_id] if job_id is not None else []
    ):
        try:
            n_hosts_by_ageclass[row[1], t_indices[row[0]]] += row[2]
        except:
            pass
    
    plot_stacked_area(
        numpy.array(ts) / p.t_year,
        n_hosts_by_ageclass,
        colors=get_colors(n_ageclasses),
        labels=make_ageclass_labels(p)
    )
    
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Number of people')

def plot_fraction_colonized_over_time(db, p, job_id, t_start=None, t_end=None):
    print('plot_fraction_colonized_over_time')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    colors = get_colors(p.n_serotypes)
    
    for serotype_id in range(p.n_serotypes):
        frac_colonized = numpy.zeros(len(ts), dtype=float)
        for row in db.execute(
            'SELECT t, n_colonized FROM counts_by_ageclass_treatment_strain WHERE {} serotype_id = ?'.format(
                'job_id = ? AND' if job_id is not None else ''
            ),
            [job_id, serotype_id] if job_id is not None else [serotype_id]
        ):
            try:
                frac_colonized[t_indices[row[0]]] += row[1]
            except:
                pass
        frac_colonized /= p.n_hosts
        pyplot.plot(ts / p.t_year, frac_colonized, color=colors[serotype_id,:])
    
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Fraction of people\ncolonized with serotype')

def plot_fraction_prevalence_over_time(db, p, job_id, t_start=None, t_end=None):
    print('plot_fraction_prevalence_over_time')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    colors = get_colors(p.n_serotypes)
    
    frac_colonizations_by_serotype = numpy.zeros((p.n_serotypes, len(ts)), dtype=float)
    for row in db.execute(
        'SELECT t, serotype_id, n_colonizations FROM counts_by_ageclass_treatment_strain {}'.format(
            'WHERE job_id = ?' if job_id is not None else ''
        ),
        [job_id] if job_id is not None else []
    ):
        t, serotype_id, n_colonizations = row
        try:
            ti = t_indices[t]
            frac_colonizations_by_serotype[serotype_id, ti] += n_colonizations
        except:
            pass
    
    for ti, t in enumerate(ts):
        frac_colonizations_by_serotype[:,ti] /= max(1.0, frac_colonizations_by_serotype[:,ti].sum())
    
    plot_stacked_area(
        ts / p.t_year,
        frac_colonizations_by_serotype,
        colors=get_colors(p.n_serotypes),
        labels=None
    )
    
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Fraction of total\npneumococcal prevalence')

def get_frac_col_by_ageclass_serotype(db, p, job_id, t):
    n_ageclasses = get_n_ageclasses(p)
    
    frac_col_by_ageclass_serotype = numpy.zeros((n_ageclasses, p.n_serotypes), dtype=float)
    for ageclass, serotype_id, n_colonizations in db.execute(
        '''
            SELECT ageclass, serotype_id, n_colonizations FROM counts_by_ageclass_treatment_strain
            WHERE {} t = ?;
        '''.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, t] if job_id is not None else [t]
    ):
        frac_col_by_ageclass_serotype[ageclass, serotype_id] += n_colonizations
    
    for i in range(n_ageclasses):
        frac_col_by_ageclass_serotype[i,:] /= max(1.0, frac_col_by_ageclass_serotype[i,:].sum())
    
    return frac_col_by_ageclass_serotype

def plot_mean_fraction_prevalence_by_age(db, p, job_id, t_start=None, t_end=None):
    print('plot_mean_fraction_prevalence_by_age')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_ageclasses = get_n_ageclasses(p)
    mean_frac_col_by_ageclass_serotype = numpy.zeros((n_ageclasses, p.n_serotypes), dtype=float)
    for t in ts:
        mean_frac_col_by_ageclass_serotype += get_frac_col_by_ageclass_serotype(db, p, job_id, t)
    mean_frac_col_by_ageclass_serotype /= len(ts)
    
    plot_stacked_bar(
        make_ageclass_labels(p),
        mean_frac_col_by_ageclass_serotype,
        colors=get_colors(p.n_serotypes)
    )

def get_fraction_colonized_by_n_colonizations(db, p, job_id, max_n_col, t):
    n_hosts_by_n_colonizations = numpy.zeros(max_n_col, dtype=float)
    for n_col, n_hosts in db.execute(
        'SELECT n_colonizations, n_hosts FROM counts_by_ageclass_treatment_n_colonizations WHERE {} t = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, t] if job_id is not None else [t]
    ):
        if n_col > 0:
            n_hosts_by_n_colonizations[n_col - 1] += n_hosts
    
    return n_hosts_by_n_colonizations / n_hosts_by_n_colonizations.sum()
    

def plot_fraction_colonized_by_n_colonizations(db, p, job_id, t_start=None, t_end=None):
    print('plot_fraction_colonized_by_n_colonizations')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    max_n_col = db.execute(
        '''
            SELECT MAX(n_colonizations) FROM counts_by_ageclass_treatment_n_colonizations
            WHERE {} t >= ? and t <= ?
        '''.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, ts[0], ts[-1]] if job_id is not None else [ts[0], ts[-1]]
    ).next()[0]
    
    mean_frac_col = numpy.zeros(max_n_col, dtype=float)
    for t in ts:
        mean_frac_col += get_fraction_colonized_by_n_colonizations(db, p, job_id, max_n_col, t)
    mean_frac_col /= len(ts)
    
    pyplot.bar(range(1, max_n_col + 1), mean_frac_col, align='center')
    
    pyplot.xticks(numpy.arange(max_n_col + 1))
    pyplot.xlabel('Pneumococcal colonizations per person')
    pyplot.ylabel('Fraction of colonized people\nat end of simulation')
    pyplot.ylim([0, 1])

def get_n_hosts_by_age(db, p, job_id, ts, t_indices):
    n_hosts_by_age = numpy.zeros((p.n_ages, len(ts)), dtype=float)
    for t, age, n_hosts in db.execute(
        'SELECT t, age, n_hosts FROM counts_by_age_treatment '.format(
            'WHERE job_id = ?' if job_id is not None else ''
        ),
        [job_id] if job_id is not None else []
    ):
        try:
            n_hosts_by_age[age, t_indices[t]] += n_hosts
        except:
            pass
    
    return n_hosts_by_age

def get_n_hosts_by_ageclass(db, p, job_id, ts, t_indices):
    n_ageclasses = get_n_ageclasses(p)
    
    n_hosts_by_ageclass = numpy.zeros((n_ageclasses, len(ts)), dtype=float)
    for t, ageclass, n_hosts in db.execute(
        'SELECT t, ageclass, n_hosts FROM counts_by_ageclass_treatment {}'.format(
            'WHERE job_id = ?' if job_id is not None else ''
        ),
        [job_id] if job_id is not None else []
    ):
        try:
            n_hosts_by_ageclass[ageclass, t_indices[t]] += n_hosts
        except:
            pass
    
    return n_hosts_by_ageclass

def get_n_colonized_by_age(db, p, job_id, ts, t_indices, serotype_id):
    n_colonized_by_age = numpy.zeros((p.n_ages, len(ts)), dtype=float)
    for t, age, n_colonized in db.execute(
        'SELECT t, age, n_colonized FROM counts_by_age_treatment_strain WHERE {} serotype_id = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, serotype_id] if job_id is not None else [serotype_id]
    ):
        try:
            n_colonized_by_age[age, t_indices[t]] += n_colonized
        except:
            pass
    
    return n_colonized_by_age

def get_n_colonized_by_ageclass(db, p, job_id, ts, t_indices, serotype_id):
    n_ageclasses = get_n_ageclasses(p)
    n_colonized_by_ageclass = numpy.zeros((n_ageclasses, len(ts)), dtype=float)
    for t, ageclass, n_colonized in db.execute(
        'SELECT t, ageclass, n_colonized FROM counts_by_ageclass_treatment_strain WHERE {} serotype_id = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, serotype_id] if job_id is not None else [serotype_id]
    ):
        try:
            n_colonized_by_ageclass[ageclass, t_indices[t]] += n_colonized
        except:
            pass
    
    return n_colonized_by_ageclass

def plot_fraction_colonized_by_age_over_time(db, p, job_id, serotype_id, t_start=None, t_end=None):
    n_ageclasses = get_n_ageclasses(p)
    
    print('plot_fraction_colonized_by_n_colonizations({0})'.format(serotype_id))
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_hosts_by_ageclass = get_n_hosts_by_ageclass(db, p, job_id, ts, t_indices)
    n_colonized_by_ageclass = get_n_colonized_by_ageclass(db, p, job_id, ts, t_indices, serotype_id)
    
    colors = get_colors(n_ageclasses)
    for i in range(n_ageclasses):
        pyplot.plot(ts / p.t_year, n_colonized_by_ageclass[i,:] / n_hosts_by_ageclass[i,:], c=colors[i,:])
    pyplot.legend(make_ageclass_labels(p))
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Serotype {0}:\nFraction colonized'.format(serotype_id))

def plot_number_colonized_by_age_over_time(db, p, job_id, serotype_id, t_start=None, t_end=None):
    print('plot_number_colonized_by_age_over_time({0})'.format(serotype_id))
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_ageclasses = get_n_ageclasses(p)
    
    n_colonized_by_ageclass = get_n_colonized_by_ageclass(db, p, job_id, ts, t_indices, serotype_id)
    
    colors = get_colors(n_ageclasses)
    for i in range(n_ageclasses):
        pyplot.plot(ts / p.t_year, n_colonized_by_ageclass[i,:], c=colors[i,:])
    pyplot.legend(make_ageclass_labels(p))
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Number of people colonized'.format(serotype_id))

def get_n_colonizations_by_age(db, p, job_id, ts, t_indices, serotype_id, resistant):
    n_cols_by_age = numpy.zeros((p.n_ages, len(ts)), dtype=float)
    for t, age, n_colonizations in db.execute(
        'SELECT t, age, n_colonized FROM counts_by_age_treatment_strain WHERE {} serotype_id = ? AND resistant = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, serotype_id, resistant] if job_id is not None else [serotype_id, resistant]
    ):
        try:
            n_cols_by_age[age, t_indices[t]] += n_colonizations
        except:
            pass
    
    return n_cols_by_age

def get_n_colonizations_by_ageclass(db, p, job_id, ts, t_indices, serotype_id, resistant):
    n_ageclasses = get_n_ageclasses(p)
    
    n_cols_by_ageclass = numpy.zeros((n_ageclasses, len(ts)), dtype=float)
    for t, ageclass, n_colonizations in db.execute(
        'SELECT t, ageclass, n_colonized FROM counts_by_ageclass_treatment_strain WHERE {} serotype_id = ? AND resistant = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, serotype_id, resistant] if job_id is not None else [serotype_id, resistant]
    ):
        try:
            n_cols_by_ageclass[ageclass, t_indices[t]] += n_colonizations
        except:
            pass
    
    return n_cols_by_ageclass

def plot_fraction_resistant_by_age_over_time(db, p, job_id, serotype_id, t_start=None, t_end=None):
    n_ageclasses = get_n_ageclasses(p)
    
    print('plot_fraction_resistant_by_age_over_time({0})'.format(serotype_id))
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_cols_by_ageclass_sensitive = get_n_colonizations_by_ageclass(db, p, job_id, ts, t_indices, serotype_id, 0)
    n_cols_by_ageclass_resistant = get_n_colonizations_by_ageclass(db, p, job_id, ts, t_indices, serotype_id, 1)
    
    frac_resistant_by_ageclass = n_cols_by_ageclass_resistant / numpy.maximum(1.0,
        n_cols_by_ageclass_sensitive + n_cols_by_ageclass_resistant
    )
    
    colors = get_colors(n_ageclasses)
    for i in range(n_ageclasses):
        pyplot.plot(ts / p.t_year, frac_resistant_by_ageclass[i,:], c=colors[i,:])
    pyplot.legend(make_ageclass_labels(p))
    pyplot.xlabel('Time (y)')
    pyplot.ylabel('Serotype {0}:\nFraction of colonizations resistant'.format(serotype_id))
    pyplot.ylim([0, 1])

def get_frac_resistant_by_ageclass(db, p, job_id, t):
    n_ageclasses = get_n_ageclasses(p)
    
    n_col_by_ageclass_resistance = numpy.zeros((n_ageclasses, 2), dtype=float)
    for ageclass, n_colonizations, resistant in db.execute(
        'SELECT ageclass, n_colonizations, resistant FROM counts_by_ageclass_treatment_strain WHERE {} t = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, t] if job_id is not None else [t]
    ):
        n_col_by_ageclass_resistance[ageclass, resistant] += n_colonizations
    
    return n_col_by_ageclass_resistance[:,1] / (n_col_by_ageclass_resistance.sum(axis=1))

def plot_fraction_resistant_by_age(db, p, job_id, t_start=None, t_end=None):
    print('plot_fraction_resistant_by_age')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_ageclasses = get_n_ageclasses(p)
    
    mean_frac_resistant_by_ageclass = numpy.zeros(n_ageclasses, dtype=float)
    valid_ts = numpy.zeros(n_ageclasses, dtype=float)
    for t in ts:
        frac_res_t = get_frac_resistant_by_ageclass(db, p, job_id, t)
        valid = numpy.logical_not(numpy.logical_or(
            numpy.isinf(frac_res_t), numpy.isnan(frac_res_t)
        ))
        valid_ts += valid
        mean_frac_resistant_by_ageclass += frac_res_t * valid
    mean_frac_resistant_by_ageclass /= valid_ts
    
    pyplot.bar(range(n_ageclasses), mean_frac_resistant_by_ageclass, align='center')
    pyplot.xticks(range(n_ageclasses), make_ageclass_labels(p))
    pyplot.ylabel('Mean fraction of colonizations\nresistant by age')
    pyplot.ylim([0, 1])

def get_n_col_by_ageclass_resistance(db, p, job_id, t):
    n_ageclasses = get_n_ageclasses(p)
    
    n_col_by_ageclass_resistance = numpy.zeros((n_ageclasses, 2), dtype=float)
    for ageclass, n_colonizations, resistant in db.execute(
        'SELECT ageclass, n_colonizations, resistant FROM counts_by_ageclass_treatment_strain WHERE {} t = ?'.format(
            'job_id = ? AND' if job_id is not None else ''
        ),
        [job_id, t] if job_id is not None else [t]
    ):
        n_col_by_ageclass_resistance[ageclass, resistant] += n_colonizations
    
    return n_col_by_ageclass_resistance
    
def plot_number_resistant_by_age(db, p, job_id, t_start=None, t_end=None):
    print('plot_number_resistant_by_age')
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    n_ageclasses = get_n_ageclasses(p)
    
    mean_n_col_by_ageclass_resistance = numpy.zeros((n_ageclasses,2), dtype=float)
    for t in ts:
        mean_n_col_by_ageclass_resistance += get_n_col_by_ageclass_resistance(db, p, job_id, t)
    mean_n_col_by_ageclass_resistance /= len(ts)
    
    pyplot.bar(numpy.arange(n_ageclasses) - 0.2, mean_n_col_by_ageclass_resistance[:,0], width=0.4, color='red', align='center')
    pyplot.bar(numpy.arange(n_ageclasses) + 0.2, mean_n_col_by_ageclass_resistance[:,1], width=0.4, color='blue', align='center')
    pyplot.xticks(range(n_ageclasses), make_ageclass_labels(p))
    pyplot.legend(['sensitive', 'resistant'])
    pyplot.ylabel('Mean number of colonizations\nby age, resistance')
    
def plot_fraction_resistant_by_serotype(db, p, job_id, ageclass, ageclass_label, t_start=None, t_end=None):
    print('plot_fraction_resistant_by_serotype({0})'.format(ageclass_label))
    ts, t_indices = get_times(db, job_id, t_start=t_start, t_end=t_end)
    
    def get_frac_resistant(t):
        n_by_serotype_resistant = numpy.zeros((p.n_serotypes, 2), dtype=float)
        for n_colonizations, serotype_id, resistant in db.execute(
            '''
                SELECT n_colonizations, serotype_id, resistant
                FROM counts_by_ageclass_treatment_strain
                WHERE {} t = ? AND ageclass = ?
            '''.format(
                'job_id = ? AND' if job_id is not None else ''
            ),
            [job_id, t, ageclass] if job_id is not None else [t, ageclass]
        ):
            n_by_serotype_resistant[serotype_id, resistant] += n_colonizations
        return n_by_serotype_resistant[:,1] / n_by_serotype_resistant.sum(axis=1)
    
    mean_frac_resistant = numpy.zeros(p.n_serotypes, dtype=float)
    valid_ts = numpy.zeros(p.n_serotypes, dtype=float)
    for t in ts:
        mean_frac_resistant_t = get_frac_resistant(t)
        valid = numpy.logical_not(numpy.logical_or(
            numpy.isinf(mean_frac_resistant_t),
            numpy.isnan(mean_frac_resistant_t)
        ))
        mean_frac_resistant_t[numpy.logical_not(valid)] = 0
        valid_ts += valid
        mean_frac_resistant += mean_frac_resistant_t * valid
    
    mean_frac_resistant /= valid_ts
    
    pyplot.bar(numpy.arange(p.n_serotypes), mean_frac_resistant, align='center')
    
    pyplot.xlabel('Serotype (in order of fitness)')
    pyplot.ylabel('Mean fraction resistant')
    pyplot.ylim([0, 1])
    pyplot.title(ageclass_label)


### REUSABLE PLOTTING FUNCTIONS ###

def plot_stacked_area(x, y, colors=None, labels=None):
    y_cumsum = numpy.cumsum(y, axis=0)
    patches = []
    pyplot.fill_between(x, 0, y_cumsum[0,:], facecolor=colors[0,:])
    
    if labels is not None:
        patches.append(matplotlib.patches.Rectangle((0, 0), 1, 1, color=colors[0,:], label=labels[0]))
    for i in range(1, y.shape[0]):
        pyplot.fill_between(x, y_cumsum[i-1,:], y_cumsum[i,:], facecolor=colors[i,:])
        if labels is not None:
            patches.append(matplotlib.patches.Rectangle((0, 0), 1, 1, color=colors[i,:], label=labels[i]))
    
    if labels is not None:
        pyplot.legend(patches, labels)

def plot_stacked_bar(xlabels, y, colors=None):
    nx, ny = y.shape
    
    assert len(xlabels) == nx
    assert colors.shape[0] == ny
    
    y_cumsum = numpy.cumsum(y, axis=1)
    
    pyplot.bar(range(nx), y[:,0], align='center', color=colors[0,:])
    for i in range(1, ny):
        pyplot.bar(range(nx), y[:,i], align='center', color=colors[i,:], bottom=y_cumsum[:,i-1])
    
    pyplot.xticks(range(5), xlabels)


### UTILITY FUNCTIONS ###

def get_n_ageclasses(p):
    ageclasses = numpy.array(p.output_ageclasses)
    if ageclasses.sum() < p.n_ages:
        return ageclasses.shape[0] + 1
    else:
        assert ageclasses.sum() == p.n_ages
        return ageclasses.shape[0]

def make_ageclass_labels(p):
    sizes = list(p.output_ageclasses)
    if sum(p.output_ageclasses) < p.n_ages:
        sizes.append(p.n_ages - sum(p.output_ageclasses))
    
    labels = []
    age = 0
    for ageclass, size in enumerate(sizes):
        labels.append('{0} - {1}'.format(age, age + size))
        age += size
    
    return labels

def get_times(db, job_id, t_start = None, t_end = None):
    ts = [
        row[0] for row in db.execute(
            'SELECT DISTINCT t FROM counts_by_ageclass_treatment {}'.format(
                'WHERE job_id = ?' if job_id is not None else ''
            ), 
            [job_id] if job_id is not None else []
        )
        if (t_start is None or row[0] >= t_start) and (t_end is None or row[0] <= t_end)
    ]
    t_indices = dict([(t, i) for i, t in enumerate(ts)])
    
    return numpy.array(ts), t_indices

def get_colors(n_colors, cmap_name='Spectral'):
    cmap = matplotlib.cm.get_cmap(cmap_name)
    colors = numpy.zeros((n_colors, 3), dtype=float)
    for i in range(n_colors):
        if i == 0:
            color = numpy.array(cmap(i))
        else:
            color = numpy.array(cmap(float(i) / (n_colors - 1)))
        colors[i,:] = color[:3]
    return colors


### PARAMETER LOADING FROM DATABASE ###

class Parameters(object):
    def __init__(self, d):
        for k, v in d.iteritems():
            setattr(self, k, v)

def get_parameters(db, job_id):
    return Parameters(json.loads(db.execute(
        'SELECT parameters FROM parameters {}'.format(
            'WHERE job_id = ?' if job_id is not None else ''
        ), [job_id] if job_id is not None else []
    ).next()[0]))

if __name__ == '__main__':
    main()
