## Setup

First, get the code and move it into an experiment directory:

```{sh}
mkdir 2015-11-09-sweep
cd 2015-11-09-sweep
git clone git@bitbucket.org:cobeylab/pyresistance.git
cp example/sweep/* .
```

## Generate job directories

First, modify the parameter values/sweep in `generate_sweep_jobs.py` to match the experiment. If necessary, also modify time/memory requirements in the `runmany_info_template`.

Then, run the script to generate a bunch of directories for runs:

```{sh}
./generate_sweep_jobs.py
```

which will generate a directory hierarchy, e.g.,

```
jobs/
    xi=0.90-treat=0.0-cost=4.0/
        00/
            parameters.json
            runmany_info.json
        01/
            ...
        ...
```

You might need to make this file executable (`chmod +x generate_sweep_jobs.py`).

Then, try a dry SLURM run via `runmany`:

```{sh}
runmany slurm pneu jobs chunks --chunks 48 --dry
```

and then do the real thing:

```{sh}
rm -r chunks
runmany slurm pneu jobs chunks --chunks 48
```

## Gather database

Run `gather` (in `runmany`) to combine all the jobs into a single database:

```{sh}
gather jobs sweep_db.sqlite
```


## Plot sweep

```{sh}
./plot_sweep.py sweep_db.sqlite
```
