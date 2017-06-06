# Setting up a parameter sweep

## PyPy Setup

The simulation code was built and run using PyPy 4.0.1 and the corresponding NumPy-via-PyPy release.
Here's how to install, briefly, on Unix-y systems:

* [Download PyPy 4.0.1 here](https://bitbucket.org/pypy/pypy/downloads/).
* Ensure that `pypy` is in your `$PATH` environment variable, so that `which pypy` points to the right place.
* [Download and unpack NumPy-via-PyPy for PyPy 4.0.1](https://bitbucket.org/pypy/numpy/downloads/?tab=tags)

Then set up NumPy in PyPy via:

```
cd pypy-numpy-0208abed8c7e
pypy setup.py install
```

Newer versions may work, as may the now-recommended C-extension method for using NumPy in PyPy, but they have not been tested.

If you don't want to set up PyPy, you can run `pyresistance.py` using Anaconda Python, e.g., via

```sh
python <path-to-repo>/src/pyresistance.py parameters.json
```

but simulations will take significantly longer.

## Anaconda Setup

To run the sweep-generating, database-gathering and summary scripts, you'll need the [Anaconda Python 2.7 distribution](https://www.continuum.io/downloads).
Set your `$PATH` so that `which python` points to Anaconda's copy of `python`.

## Setting up and running a sweep

First, get the code and move it into an experiment directory:

```{sh}
mkdir 2015-11-09-sweep
cd 2015-11-09-sweep
git clone https://github.com/cobeylab/pneumo-resistance.git
cp pneumo-resistance/example/sweep/* .
```

Then, modify the parameter values/sweep in `generate_sweep_jobs.py` to match the experiment.

Finally, run the script to generate a bunch of directories for runs:

```sh
./generate_sweep_jobs.py
```

which will generate a directory hierarchy, e.g.,

```sh
jobs/
    treat=0.0-cost=0.90-ratio=1.0/
        00/
            parameters.json
        01/
            parameters.json
        ...
```

These jobs can be run individually, e.g.:

```sh
cd jobs/treat=0.0-cost=0.90-ratio=1.0/00
<path-to-repo>/src/pyresistance.py parameters.json
```

or, if you didn't install PyPy,

```sh
cd jobs/treat=0.0-cost=0.90-ratio=1.0/00
python <path-to-repo>/src/pyresistance.py parameters.json
```

To actually run a sweep, you'll want to submit many jobs to your cluster system via a script that iterates through all the directories or submits an array job.


## Gather databases and generate summaries

After all jobs have run, run `gather.py` to combine all the jobs into a single database:

```sh
./gather.py jobs sweep_db.sqlite
```

(This will produce a very large file and take a while.)

You can run `summarize_sweep.py` to add summary tables to the database:

```sh
./summarize_sweep.py sweep_db.sqlite
```

You can then extract a small-ish SQLite file, `sweep_db-summaries.sqlite`, containing only summary data:

```sh
./extract_summaries.py sweep_db.sqlite
```
