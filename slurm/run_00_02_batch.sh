#!/bin/bash
#SBATCH --job-name=latmod_compute
#SBATCH --nodes=1 --ntasks=1
#SBATCH --output=logs/compute_%A_%a.out
#SBATCH --error=logs/compute_%A_%a.err
#SBATCH -p gpu  # Partition
#SBATCH -G 1  # Number of GPUs
#SBATCH --array=0-5
#SBATCH --time=1-00:00:00
#SBATCH --time-min=0-08:00:00

array=( $(seq 2018 2023 ) )

module load conda/latest
conda activate latmod_env
cd /work/pi_mccallum_umass_edu/nnayak_umass_edu/latourian_modality/00_extract_data
python 02_compute.py \
	-d /gypsum/work1/mccallum/nnayak/latmod/\
	-c iclr_${array[$SLURM_ARRAY_TASK_ID]}

