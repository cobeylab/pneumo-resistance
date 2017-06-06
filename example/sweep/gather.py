#!/usr/bin/env python

import os
import sys
import sqlite3
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root_dir', metavar = '<root-directory>')
    parser.add_argument('out_filename', metavar = '<output-database-filename>')
    parser.add_argument('--source-id', metavar = '<source-id-column-name>', default = 'job_id')
    parser.add_argument('--source-table', metavar = '<source-table-name>', default = 'sources')

    args = parser.parse_args()

    root_dir  = args.root_dir
    out_filename = args.out_filename

    source_id_name = args.source_id
    source_table_name = args.source_table

    if not os.path.exists(root_dir):
        sys.stdout.write('{} does not exist; aborting.\n'.format(root_dir))
        sys.exit(1)

    if os.path.exists(out_filename):
        sys.stdout.write('{} already exists; aborting.\n'.format(out_filename))
        sys.exit(1)

    source_id = 1
    with sqlite3.connect(out_filename) as db:
        db.execute('CREATE TABLE {} ({} INTEGER, filename TEXT);'.format(source_table_name, source_id_name))
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames.sort()
            for filename in filenames:
                if filename.endswith('.sqlite'):
                    process_file(db, os.path.join(dirpath, filename), source_table_name, source_id_name, source_id)
                    source_id += 1

def process_file(db, in_filename, source_table_name, source_id_name, source_id):
    sys.stderr.write('{}\n'.format(in_filename))

    db.execute('ATTACH ? AS indb;', [in_filename])
    db.execute('INSERT INTO {} VALUES (?, ?);'.format(source_table_name), [source_id, in_filename])

    table_names = [name for name, in db.execute("SELECT name FROM indb.sqlite_master WHERE type='table';")]
    for table_name in table_names:
        col_names = [entry[0] for entry in db.execute('SELECT * FROM indb.{}'.format(table_name)).description]
        if source_id_name in col_names:
            sys.stderr.write('{} column already exists; aborting.\n'.format(source_id_name))
            sys.exit(1)
        try:
            db.execute('CREATE TABLE {0} AS SELECT ? AS {1}, * FROM indb.{0}'.format(table_name, source_id_name), [source_id])
        except:
            db.execute('INSERT INTO {0} SELECT ? AS {1}, * FROM indb.{0}'.format(table_name, source_id_name), [source_id])

    db.execute('DETACH indb;')

if __name__ == '__main__':
    main()
