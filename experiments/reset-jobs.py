#!/usr/bin/env python

import os
import sys
import sqlite3

def main():
    os.chdir(os.path.dirname(__file__))
    
    print('This script will remove any output files for jobs marked "running", "canceled",\nor "failed" and set their state to "waiting".')
    print('Make sure no jobs or workers are running!\nAre you sure you want to continue deleting files and resetting jobs?')
    answer = raw_input('type yes or no: ')
    if answer != 'yes':
        print('Wait until nothing is happening before running this script.\n')
        sys.exit(1)
    
    if not os.path.exists('runr_db.sqlite'):
        print('Error: runr_db.sqlite could not be found. This script assumes runr_db.sqlite is in the same directory as this script.')
        sys.exit(1)
    
    count = 0
    with open('reset-jobs.log', 'a') as logfile:
        with sqlite3.connect('runr_db.sqlite') as db:
            for working_dir, status in db.execute(
                'SELECT working_dir, status FROM jobs WHERE status = "running" OR status = "failed" or status = "canceled"'
            ):
                log(logfile, '{}\t{}'.format(status, working_dir))
                remove_file(working_dir, 'stdout.txt')
                remove_file(working_dir, 'output_db.sqlite')
                
                db.execute(
                    'UPDATE jobs SET status = "waiting", worker_id = NULL WHERE working_dir = ?',
                    [working_dir]
                )
                
                count += 1
    print('{} files reset.'.format(count))

def log(logfile, line):
    sys.stdout.write('{}\n'.format(line))
    logfile.write('{}\n'.format(line))

def remove_file(working_dir, filename):
    path = os.path.join(working_dir, filename)
    if os.path.exists(path):
        os.remove(path)

if __name__ == '__main__':
    main()
