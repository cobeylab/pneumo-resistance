#!/usr/bin/env python

import os
import sys
import sqlite3

YEARS = 50
N_SEROTYPES = 25
T_YEAR = 365
N_AGECLASSES = 3
N_HOSTS = 100000

def main():
    db_filename = sys.argv[1]
    
    with sqlite3.connect(db_filename) as db:
        create_indexes(db)
        summarize(db)

def create_indexes(db):
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_index ON counts_by_ageclass_treatment
        (job_id, t, ageclass, in_treatment)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_n_colonizations_index ON counts_by_ageclass_treatment_n_colonizations
        (job_id, t, ageclass, in_treatment, n_colonizations)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_strain_index ON counts_by_ageclass_treatment_strain
        (job_id, t, ageclass, in_treatment, serotype_id, resistant)
    ''')

def summarize(db):
    print('summarize()')
    
    start_year = db.execute('SELECT MAX(t) FROM summary').next()[0] - T_YEAR * (YEARS - 1)
    summarize_overall(db, start_year)
    summarize_by_serotype(db, start_year)
    summarize_by_ageclass(db, start_year)
    summarize_by_serotype_ageclass(db, start_year)

def summarize_overall(db, start_year):
    print('summarize_overall()')
    
    summarize_frac_resistant_overall(db, start_year)
    summarize_prevalence_overall(db, start_year)
    
    db.execute('DROP TABLE IF EXISTS summary_overall')
    db.execute('''
        CREATE TABLE summary_overall AS
        SELECT
            jobs.job_id,
            jobs.cost,
            jobs.treatment_multiplier,
            jobs.gamma_treated_ratio_resistant_to_sensitive,
            tmp_frac_res_avg.frac_res AS frac_resistant,
            tmp_prev_avg.prev AS prevalence
        FROM
            jobs, tmp_frac_res_avg, tmp_prev_avg
        WHERE
            jobs.job_id = tmp_frac_res_avg.job_id AND jobs.job_id = tmp_prev_avg.job_id
    ''')
    

def summarize_frac_resistant_overall(db, start_year):
    print('summarize_frac_resistant_overall()')
    
    # Number of colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col AS
        SELECT
            job_id, t,
            SUM(n_colonizations) AS n_col
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t
    ''', [start_year])
    
    # Number of resistant colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col_res AS
        SELECT
            job_id, t,
            SUM(n_colonizations) AS n_col_res
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ? AND resistant = 1
        GROUP BY job_id, t
    ''', [start_year])
    
    # Fraction resistant over time
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res AS
        SELECT
            tmp_n_col.job_id AS job_id, tmp_n_col.t AS t,
            tmp_n_col_res.n_col_res * 1.0 / tmp_n_col.n_col AS frac_res
        FROM
            tmp_n_col, tmp_n_col_res
        WHERE
            tmp_n_col.job_id = tmp_n_col_res.job_id AND tmp_n_col.t = tmp_n_col_res.t
        GROUP BY tmp_n_col.job_id, tmp_n_col.t
    ''')
    
    # Average fraction resistant over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_avg AS
        SELECT job_id, AVG(frac_res) AS frac_res FROM tmp_frac_res GROUP BY job_id
    ''')

def summarize_prevalence_overall(db, start_year):
    print('summarize_prevalence_overall()')
    
    # Prevalence over time
    db.execute('''
        CREATE TEMP TABLE tmp_prev AS
        SELECT
            job_id, t, SUM(n_hosts) * 1.0 / ? AS prev
        FROM
            counts_by_ageclass_treatment_n_colonizations
        WHERE
            t >= ? AND n_colonizations >= 1
        GROUP BY job_id, t
    ''', [N_HOSTS, start_year])
    
    # Average prevalence over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_prev_avg AS
        SELECT job_id, AVG(prev) AS prev FROM tmp_prev GROUP BY job_id
    ''')

def summarize_by_serotype(db, start_year):
    print('summarize_by_serotype()')
    
    summarize_frac_resistant_by_serotype(db, start_year)
    summarize_prevalence_by_serotype(db, start_year)
    
    db.execute('DROP TABLE IF EXISTS summary_by_serotype')
    db.execute('''
        CREATE TABLE summary_by_serotype AS
        SELECT
            jobs.job_id,
            jobs.cost,
            jobs.treatment_multiplier,
            jobs.gamma_treated_ratio_resistant_to_sensitive,
            tmp_frac_res_sero_avg.serotype_id AS serotype_id,
            tmp_frac_res_sero_avg.frac_res AS frac_resistant,
            tmp_prev_sero_avg.prev AS prevalence
        FROM
            jobs, tmp_frac_res_sero_avg, tmp_prev_sero_avg
        WHERE
            jobs.job_id = tmp_frac_res_sero_avg.job_id AND jobs.job_id = tmp_prev_sero_avg.job_id
            AND tmp_frac_res_sero_avg.serotype_id = tmp_prev_sero_avg.serotype_id
    ''')

def summarize_frac_resistant_by_serotype(db, start_year):
    print('summarize_frac_resistant_by_serotype()')
    
    # Number of colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col_sero AS
        SELECT
            job_id, t, serotype_id,
            SUM(n_colonizations) AS n_col
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t, serotype_id
    ''', [start_year])
    
    # Number of resistant colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col_res_sero AS
        SELECT
            job_id, t, serotype_id,
            SUM(n_colonizations) AS n_col_res
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ? AND resistant = 1
        GROUP BY job_id, t, serotype_id
    ''', [start_year])
    
    # Fraction resistant over time
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_sero AS
        SELECT
            tmp_n_col_sero.job_id AS job_id, tmp_n_col_sero.t AS t,
            tmp_n_col_sero.serotype_id AS serotype_id,
            tmp_n_col_res_sero.n_col_res * 1.0 / tmp_n_col_sero.n_col AS frac_res
        FROM
            tmp_n_col_sero, tmp_n_col_res_sero
        WHERE
            tmp_n_col_sero.job_id = tmp_n_col_res_sero.job_id
            AND tmp_n_col_sero.t = tmp_n_col_res_sero.t
            AND tmp_n_col_sero.serotype_id = tmp_n_col_res_sero.serotype_id
        GROUP BY tmp_n_col_sero.job_id, tmp_n_col_sero.t, tmp_n_col_sero.serotype_id
    ''')
    
    # Average fraction resistant over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_sero_avg AS
        SELECT job_id, serotype_id, AVG(frac_res) AS frac_res FROM tmp_frac_res_sero
        GROUP BY job_id, serotype_id
    ''')

def summarize_prevalence_by_serotype(db, start_year):
    print('summarize_prevalence_by_serotype()')
    
    # Prevalence over time
    db.execute('''
        CREATE TEMP TABLE tmp_prev_sero AS
        SELECT
            job_id, t, serotype_id, SUM(n_colonized) * 1.0 / ? AS prev
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t, serotype_id
    ''', [N_HOSTS, start_year])
    
    # Average prevalence over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_prev_sero_avg AS
        SELECT job_id, serotype_id, AVG(prev) AS prev FROM tmp_prev_sero
        GROUP BY job_id, serotype_id
    ''')

def summarize_by_ageclass(db, start_year):
    print('summarize_prevalence_by_serotype')
    
    summarize_frac_resistant_by_ageclass(db, start_year)
    summarize_prevalence_by_ageclass(db, start_year)
    summarize_prevalence_by_ageclass_resistant(db, start_year)
    
    db.execute('DROP TABLE IF EXISTS summary_by_ageclass')
    db.execute('''
        CREATE TABLE summary_by_ageclass AS
        SELECT
            jobs.job_id,
            jobs.cost,
            jobs.treatment_multiplier,
            jobs.gamma_treated_ratio_resistant_to_sensitive,
            tmp_frac_res_age_avg.ageclass AS ageclass,
            tmp_frac_res_age_avg.frac_res AS frac_resistant,
            tmp_prev_age_avg.prev AS prevalence,
            tmp_prev_sens_res_age_avg.prev_sens AS prev_sens,
            tmp_prev_sens_res_age_avg.prev_res AS prev_res
        FROM
            jobs, tmp_frac_res_age_avg, tmp_prev_age_avg, tmp_prev_sens_res_age_avg
        WHERE
            jobs.job_id = tmp_frac_res_age_avg.job_id AND jobs.job_id = tmp_prev_age_avg.job_id
            AND jobs.job_id = tmp_prev_sens_res_age_avg.job_id
            AND tmp_frac_res_age_avg.ageclass = tmp_prev_age_avg.ageclass
            AND tmp_prev_sens_res_age_avg.ageclass = tmp_prev_age_avg.ageclass
    ''')

def create_tmp_n_col_age(db, start_year):
    # Number of colonizations over time by ageclass
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_n_col_age AS
        SELECT
            job_id, t, ageclass,
            SUM(n_colonizations) AS n_col
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t, ageclass
    ''', [start_year])

def create_tmp_n_col_age_total(db, start_year):
    # Number of colonizations total over last 50 years by ageclass
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_n_col_age_total AS
        SELECT
            job_id, ageclass,
            SUM(n_colonizations) AS n_col
        FROM
            tmp_n_col_age
        GROUP BY job_id, ageclass
    ''', [start_year])

def summarize_frac_resistant_by_ageclass(db, start_year):
    print('summarize_frac_resistant_by_ageclass')
    
    create_tmp_n_col_age(db, start_year)
    
    # Number of resistant colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col_res_age AS
        SELECT
            job_id, t, ageclass,
            SUM(n_colonizations) AS n_col_res
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ? AND resistant = 1
        GROUP BY job_id, t, ageclass
    ''', [start_year])
    
    # Fraction resistant over time
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_age AS
        SELECT
            tmp_n_col_age.job_id AS job_id, tmp_n_col_age.t AS t,
            tmp_n_col_age.ageclass AS ageclass,
            tmp_n_col_res_age.n_col_res * 1.0 / tmp_n_col_age.n_col AS frac_res
        FROM
            tmp_n_col_age, tmp_n_col_res_age
        WHERE
            tmp_n_col_age.job_id = tmp_n_col_res_age.job_id
            AND tmp_n_col_age.t = tmp_n_col_res_age.t
            AND tmp_n_col_age.ageclass = tmp_n_col_res_age.ageclass
        GROUP BY tmp_n_col_age.job_id, tmp_n_col_age.t, tmp_n_col_age.ageclass
    ''')
    
    # Average fraction resistant over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_age_avg AS
        SELECT job_id, ageclass, AVG(frac_res) AS frac_res FROM tmp_frac_res_age
        GROUP BY job_id, ageclass
    ''')

def summarize_prevalence_by_ageclass(db, start_year):
    print('summarize_prevalence_by_ageclass')
    
    # Prevalence over time
    db.execute('''
        CREATE TEMP TABLE tmp_prev_age AS
        SELECT
            job_id, t, ageclass, SUM(n_colonized) * 1.0 / SUM(n_hosts) AS prev
        FROM
            counts_by_ageclass_treatment
        WHERE
            t >= ?
        GROUP BY job_id, t, ageclass
    ''', [start_year])
    
    # Average prevalence over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_prev_age_avg AS
        SELECT job_id, ageclass, AVG(prev) AS prev FROM tmp_prev_age
        GROUP BY job_id, ageclass
    ''')

def summarize_prevalence_by_ageclass_resistant(db, start_year):
    print('summarize_prevalence_by_ageclass_resistant')
    
    # No. hosts, no. colonized and no. colonized by sensitive and resistant over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_age AS
        SELECT
            job_id, t, ageclass,
            SUM(n_hosts) AS n_hosts,
            SUM(n_colonized) AS n_colonized,
            SUM(n_colonized_by_sensitive_and_resistant) as n_colonized_sandr
        FROM
            counts_by_ageclass_treatment
        WHERE
            t >= ?
        GROUP BY job_id, t, ageclass
    ''', [start_year])
    
    # Estimate of prevalence of sensitive & resistant strains over time
    # [n_colonized - n_colonized_sandr] * frac_res + n_colonized_sandr
    db.execute('''
        CREATE TEMP TABLE tmp_prev_sens_res_age AS
        SELECT
            tmp_n_age.job_id AS job_id,
            tmp_n_age.t AS t,
            tmp_n_age.ageclass AS ageclass,
            ((n_colonized - n_colonized_sandr) * (1.0 - frac_res) + n_colonized_sandr) / n_hosts AS prev_sens,
            ((n_colonized - n_colonized_sandr) * frac_res + n_colonized_sandr) / n_hosts AS prev_res
        FROM
            tmp_n_age, tmp_frac_res_age
        WHERE
            tmp_n_age.job_id = tmp_frac_res_age.job_id
            AND tmp_n_age.t = tmp_frac_res_age.t
            AND tmp_n_age.ageclass = tmp_frac_res_age.ageclass
    ''')
    
    
    # Average prevalence over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_prev_sens_res_age_avg AS
        SELECT
            job_id, ageclass,
            AVG(prev_sens) AS prev_sens,
            AVG(prev_res) AS prev_res
        FROM tmp_prev_sens_res_age
        GROUP BY job_id, ageclass
    ''')

def summarize_by_serotype_ageclass(db, start_year):
    print('summarize_by_serotype_ageclass()')
    
    create_tmp_frac_res_sero_age_avg(db, start_year)
    create_tmp_n_col_sero_age_total(db, start_year)
    create_tmp_freq_sero_age_avg(db, start_year)
    
    db.execute('DROP TABLE IF EXISTS summary_by_serotype_ageclass')
    db.execute('''
        CREATE TABLE summary_by_serotype_ageclass AS
        SELECT
            jobs.job_id AS job_id,
            jobs.cost AS cost,
            jobs.treatment_multiplier AS treatment_multiplier,
            jobs.gamma_treated_ratio_resistant_to_sensitive,
            tmp_frac_res_sero_age_avg.serotype_id AS serotype_id,
            tmp_frac_res_sero_age_avg.ageclass AS ageclass,
            tmp_frac_res_sero_age_avg.frac_res AS frac_resistant,
            tmp_freq_sero_age_avg.freq AS freq_avg,
            tmp_n_col_sero_age_total.n_col AS n_colonizations_total
        FROM
            jobs, tmp_frac_res_sero_age_avg, tmp_n_col_sero_age_total, tmp_freq_sero_age_avg
        WHERE
            jobs.job_id = tmp_frac_res_sero_age_avg.job_id AND
            jobs.job_id = tmp_n_col_sero_age_total.job_id AND
            jobs.job_id = tmp_freq_sero_age_avg.job_id AND
            
            tmp_frac_res_sero_age_avg.serotype_id = tmp_n_col_sero_age_total.serotype_id AND
            tmp_frac_res_sero_age_avg.serotype_id = tmp_freq_sero_age_avg.serotype_id AND
            
            tmp_frac_res_sero_age_avg.ageclass = tmp_n_col_sero_age_total.ageclass AND
            tmp_frac_res_sero_age_avg.ageclass = tmp_freq_sero_age_avg.ageclass
            
    ''')

def create_tmp_frac_res_sero_age_avg(db, start_year):
    print('create_tmp_frac_res_sero_age_avg()')
    
    create_tmp_n_col_sero_age(db, start_year)
    create_tmp_n_col_res_sero_age(db, start_year)
    
    # Fraction resistant over time
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_sero_age AS
        SELECT
            tmp_n_col_sero_age.job_id AS job_id, tmp_n_col_sero_age.t AS t,
            tmp_n_col_sero_age.serotype_id AS serotype_id,
            tmp_n_col_sero_age.ageclass AS ageclass,
            tmp_n_col_res_sero_age.n_col_res * 1.0 / tmp_n_col_sero_age.n_col AS frac_res
        FROM
            tmp_n_col_sero_age, tmp_n_col_res_sero_age
        WHERE
            tmp_n_col_sero_age.job_id = tmp_n_col_res_sero_age.job_id
            AND tmp_n_col_sero_age.t = tmp_n_col_res_sero_age.t
            AND tmp_n_col_sero_age.serotype_id = tmp_n_col_res_sero_age.serotype_id
            AND tmp_n_col_sero_age.ageclass = tmp_n_col_res_sero_age.ageclass
        GROUP BY tmp_n_col_sero_age.job_id, tmp_n_col_sero_age.t, tmp_n_col_sero_age.serotype_id, tmp_n_col_sero_age.ageclass
    ''')
    
    # Average fraction resistant over last YEARS years
    db.execute('''
        CREATE TEMP TABLE tmp_frac_res_sero_age_avg AS
        SELECT job_id, serotype_id, ageclass, AVG(frac_res) AS frac_res FROM tmp_frac_res_sero_age
        GROUP BY job_id, serotype_id, ageclass
    ''')

def create_tmp_n_col_sero_age_total(db, start_year):
    print('create_tmp_n_col_sero_age_total()')
    
    create_tmp_n_col_sero_age(db, start_year)
    
    # Number of colonizations total over last 50 years by ageclass
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_n_col_sero_age_total AS
        SELECT
            job_id, serotype_id, ageclass,
            SUM(n_col) AS n_col
        FROM
            tmp_n_col_sero_age
        GROUP BY job_id, serotype_id, ageclass
    ''')

def create_tmp_freq_sero_age_avg(db, start_year):
    print('create_tmp_freq_sero_age_avg()')
    
    create_tmp_freq_sero_age(db, start_year)
    
    # Average frequency over last 50 years by serotype, ageclass
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_freq_sero_age_avg AS
        SELECT
            job_id, serotype_id, ageclass,
            AVG(freq) AS freq
        FROM
            tmp_freq_sero_age
        GROUP BY job_id, serotype_id, ageclass
    ''')
    
    c = db.execute('SELECT * FROM tmp_freq_sero_age_avg')
    print c.description
    for row in db.execute('SELECT * FROM tmp_freq_sero_age_avg'):
        print row

def create_tmp_freq_sero_age(db, start_year):
    print('create_tmp_freq_sero_age()')
    
    create_tmp_n_col_age(db, start_year)
    
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_freq_sero_age AS
        SELECT
            tmp_n_col_age.job_id AS job_id,
            tmp_n_col_age.t AS t,
            serotype_id AS serotype_id,
            tmp_n_col_age.ageclass AS ageclass,
            SUM(counts_by_ageclass_treatment_strain.n_colonizations) * 1.0 / tmp_n_col_age.n_col AS freq
        FROM
            counts_by_ageclass_treatment_strain, tmp_n_col_age
        WHERE
            counts_by_ageclass_treatment_strain.t >= ? AND
            counts_by_ageclass_treatment_strain.job_id = tmp_n_col_age.job_id AND
            counts_by_ageclass_treatment_strain.ageclass = tmp_n_col_age.ageclass AND
            counts_by_ageclass_treatment_strain.t = tmp_n_col_age.t
        GROUP BY tmp_n_col_age.job_id, tmp_n_col_age.t, serotype_id, tmp_n_col_age.ageclass
    ''', [start_year])


def create_tmp_n_col_sero_age(db, start_year):
    # Number of colonizations over time
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_n_col_sero_age AS
        SELECT
            job_id, t, serotype_id, ageclass,
            SUM(n_colonizations) AS n_col
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t, serotype_id, ageclass
    ''', [start_year])

def create_tmp_n_col_res_sero_age(db, start_year):
    # Number of resistant colonizations over time
    db.execute('''
        CREATE TEMP TABLE IF NOT EXISTS tmp_n_col_res_sero_age AS
        SELECT
            job_id, t, serotype_id, ageclass,
            SUM(n_colonizations) AS n_col_res
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ? AND resistant = 1
        GROUP BY job_id, t, serotype_id, ageclass
    ''', [start_year])

if __name__ == '__main__':
    main()
