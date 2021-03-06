#!/bin/sh

echo SLURM_JOB_ID=$SLURM_JOB_ID
echo SLURM_JOB_NAME=$SLURM_JOB_NAME
echo SLURM_CPUS_ON_NODE=$SLURM_CPUS_ON_NODE
echo SLURM_JOB_NODELIST=$SLURM_JOB_NODELIST
echo SLURM_NODEID=$SLURM_NODEID
echo SLURM_TASK_PID=$SLURM_TASK_PID

${PYRESISTANCE}/pyresistance.py parameters.json
${PYRESISTANCE}/plot_simulation.py output_db.sqlite simulation.png
