#!/bin/sh
#SBATCH --array=1:48
#SBATCH --cpus-per-task=1
#SBATCH --time=36:00:00
#SBATCH --mem-per-cpu=1000
#SBATCH --output=runr_output/%A-%a-stdout.txt
#SBATCH --error=runr_output/%A-%a-stderr.txt
#SBATCH --mail-type=ALL
#SBATCH --mail-user=edbaskerville

srun runr go $SLURM_CPUS_PER_TASK
