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
    start_year = db.execute('SELECT MAX(t) FROM summary').next()[0] - T_YEAR * (YEARS - 1)
    summarize_overall(db, start_year)
    summarize_by_serotype(db, start_year)
    summarize_by_ageclass(db, start_year)

def summarize_overall(db, start_year):
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
    summarize_frac_resistant_by_ageclass(db, start_year)
    summarize_prevalence_by_ageclass(db, start_year)
    
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
            tmp_prev_age_avg.prev AS prevalence
        FROM
            jobs, tmp_frac_res_age_avg, tmp_prev_age_avg
        WHERE
            jobs.job_id = tmp_frac_res_age_avg.job_id AND jobs.job_id = tmp_prev_age_avg.job_id
            AND tmp_frac_res_age_avg.ageclass = tmp_prev_age_avg.ageclass
    ''')

def summarize_frac_resistant_by_ageclass(db, start_year):
    # Number of colonizations over time
    db.execute('''
        CREATE TEMP TABLE tmp_n_col_age AS
        SELECT
            job_id, t, ageclass,
            SUM(n_colonizations) AS n_col
        FROM
            counts_by_ageclass_treatment_strain
        WHERE
            t >= ?
        GROUP BY job_id, t, ageclass
    ''', [start_year])
    
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

if __name__ == '__main__':
    main()
