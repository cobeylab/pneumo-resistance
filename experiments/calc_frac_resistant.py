#!/usr/bin/env python

import os
import numpy
import sqlite3
import json
from collections import OrderedDict

N_REPLICATES = 10

def main():
    frac_resistant = None
    for replicate_id in range(N_REPLICATES):
        dir = '{:02d}'.format(replicate_id)
        
        with sqlite3.connect(os.path.join(dir, 'output_db.sqlite')) as db:
            create_indexes(db)
            ts = [row[0] for row in db.execute('SELECT DISTINCT t FROM  counts_by_ageclass_treatment WHERE t > 36500 ORDER BY t')]
            serotype_ids = [row[0] for row in db.execute('SELECT DISTINCT serotype_id FROM counts_by_ageclass_treatment_strain ORDER BY serotype_id')]
            
            if frac_resistant is None:
                frac_resistant = numpy.zeros((N_REPLICATES, len(ts), len(serotype_ids)), dtype=float)
            
            for it, t in enumerate(ts):
                for isero, serotype_id in enumerate(serotype_ids):
                    n_col = db.execute(
                        'SELECT SUM(n_colonizations) FROM counts_by_ageclass_treatment_strain WHERE t = ? AND serotype_id = ?',
                        [t, serotype_id]
                    ).next()[0]
                    if n_col > 0:
                        n_col_res = db.execute(
                            'SELECT SUM(n_colonizations) FROM counts_by_ageclass_treatment_strain WHERE t = ? AND serotype_id = ? AND resistant = 1',
                            [t, serotype_id]
                        ).next()[0]
                        frac_resistant[replicate_id, it, isero] = n_col_res / float(n_col)
                    else:
                        frac_resistant[replicate_id, it, isero] = None
    
    with open('frac_resistant.npy', 'w') as f:
        numpy.save(f, frac_resistant)
    with open('frac_resistant.json', 'w') as f:
        json.dump(frac_resistant.tolist(), f, indent = 2)
        f.write('\n')

def create_indexes(db):
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_index ON counts_by_ageclass_treatment
        (t, ageclass, in_treatment)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_n_colonizations_index ON counts_by_ageclass_treatment_n_colonizations
        (t, ageclass, in_treatment, n_colonizations)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS counts_by_ageclass_treatment_strain_index ON counts_by_ageclass_treatment_strain
        (t, ageclass, in_treatment, n_colonizations, serotype_id, resistant)
    ''')
    db.commit()

if __name__ == '__main__':
    main()
