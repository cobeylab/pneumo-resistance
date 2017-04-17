## Setup

First, get the code and move it into experiment directory:

```{sh}
mkdir 2015-11-09-sweep
cd 2015-11-09-sweep
git clone git@bitbucket.org:cobeylab/pyresistance.git
cp experiments/* .
```

Then, run the following script to create directories for each of the 16 models:

```{sh}
./generate_jobs.py
```

This will create a directory hierarchy of 11,520 runs:

```
jobs/
    a-null-dur/
        treat=0.0-cost=0.90-ratio=4.0/
            00/
            01/
            ...
    a-null-trans/
    b-aam-dur/
    b-aam-trans/
    c-ast-dur/
    c-ast-trans/
    d-std-dur/
    d-std-trans/
    e-aam+ast-dur/
    e-aam+ast-trans/
    f-aam+std-dur/
    f-aam+std-trans/
    g-ast+std-dur/
    g-ast+std-trans/
    h-aam+ast+std-dur/
    h-aam+ast+std-trans/
```

The initial letter corresponds to the model letters in the planning document. The middle part of the name describes the model; the directory name is used to decide what parameters to write out. The final component (`dur` or `trans`) determines whether the model implements cost-of-resistance via infection duration or via transmission rates.

The models:

* `null`: the null model
* `aam`: age-assortative mixing
* `ast`: age-specific treatment
* `std`: shorter treatment duration

## Run jobs one model at a time

## Gather database

## Plot sweep

