#!/usr/bin/env python

import os
import sys
import sqlite3
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('in_filename', metavar = '<input-database-filename>')

    args = parser.parse_args()
    
    in_filename = args.in_filename
    out_filename = os.path.splitext(in_filename)[0] + '-summaries.sqlite'

    if not os.path.exists(in_filename):
        sys.stdout.write('{} does not exist; aborting.\n'.format(in_filename))
        sys.exit(1)
    if os.path.exists(out_filename):
        sys.stdout.write('{} already exists; aborting.\n'.format(out_filename))
        sys.exit(1)
    
    with sqlite3.connect(out_filename) as db:
        db.execute('ATTACH ? AS indb;', [in_filename])
        db.execute('CREATE TABLE summary_overall AS SELECT * FROM indb.summary_overall;')
        db.execute('CREATE TABLE summary_by_serotype AS SELECT * FROM indb.summary_by_serotype;')
        db.execute('CREATE TABLE summary_by_ageclass AS SELECT * FROM indb.summary_by_ageclass;')

if __name__ == '__main__':
    main()
