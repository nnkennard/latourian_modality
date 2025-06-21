# Latourian Modality (at scale)

## Setup

```
conda create --name latmod_env python=3.12
conda activate latmod_env
python -m pip install ipykernel
python -m ipykernel install --user --name latmod_env --display-name="Latourian Modality"
python -m pip install openreview-py
python -m pip install pikepdf
conda install yapf # Not pip! I don't know why
wget https://raw.githubusercontent.com/cascremers/pdfdiff/refs/heads/master/pdfdiff.py
```
