# Pose Estimator Training

This repository contains successive versions of a drone pose-estimation training pipeline. The local training scripts use a camera image to predict the drone's 3D position and orientation.

## Repository versions

### Original `v03` training pipeline

The original pipeline trained on consecutive images from multiple trajectories generated in the first Gazebo world version.

- Dataset: [dataset_1](https://drive.google.com/drive/folders/18E6CwBWxQE8mEu-caHqZziRyw9V66Dnz?usp=drive_link)

### `cats_pose_local_v01.py`

The first local adaptation of the training pipeline, intended to run on a PC with a CUDA-capable GPU. It trains for up to 40 epochs and does not use early stopping.

- Dataset: [dataset_3](https://drive.google.com/drive/folders/1aC88Jw-UjBabNftDLtgXRgOiWB-Vtail?usp=sharing)
- Results: [Training_1](https://drive.google.com/drive/folders/1XDXkbwspKQHqVHVUJ29evWNVljqU4s2z?usp=sharing)

### `cats_pose_local_v02.py`

An updated local training version with early stopping. Training can run for up to 60 epochs and stops after 20 consecutive epochs without an improvement in validation loss.

- Dataset: [dataset_3](https://drive.google.com/drive/folders/1aC88Jw-UjBabNftDLtgXRgOiWB-Vtail?usp=sharing)
- Results: [Training_2](https://drive.google.com/drive/folders/14LZavmovI7NraTS6kjBR9xoDMwbPwgHR?usp=sharing), [Training_3](https://drive.google.com/drive/folders/1nu5ekLi5kluL0sJZ7Bjt-GBd0IfLt1hN?usp=sharing), [Training_4](https://drive.google.com/drive/folders/1Sr8Ttur5_uFQZyEsflKti51RcKg1kCzR?usp=sharing), [Training_5](https://drive.google.com/drive/folders/1ewrllXZi3eiVN9k8CrWhQonGz3rCCyZw?usp=sharing), [Training_6](https://drive.google.com/drive/folders/164uxdK9WPAO-kv82qX1zH_Nsbn6MmPSz?usp=sharing), [Training_7](https://drive.google.com/drive/folders/1dsIeWo_s-UE0xioFk1gP5EjsFaByHf1H?usp=sharing)

The best reported training runs are [Training_6](https://drive.google.com/drive/folders/164uxdK9WPAO-kv82qX1zH_Nsbn6MmPSz?usp=sharing) and [Training_7](https://drive.google.com/drive/folders/1dsIeWo_s-UE0xioFk1gP5EjsFaByHf1H?usp=sharing).

## Requirements

- Windows PC; a CUDA-capable NVIDIA GPU is recommended. The scripts also select CPU automatically if CUDA is unavailable, although training will be slower.
- Anaconda or Miniconda.
- Python 3.10, as used in the existing environment setup instructions.
- PyTorch and a compatible `torchvision` build. Select the PyTorch installation command that matches the machine's CUDA setup using the official [PyTorch installation guide](https://pytorch.org/get-started/locally/).
- `numpy`, `pandas`, and `Pillow`.

Install the Python packages in the `pose_estimator_env` environment. After installing the appropriate PyTorch/`torchvision` build, the remaining packages can be installed with:

```text
python -m pip install numpy pandas Pillow
```

## Environment setup

Open Anaconda Prompt and create the environment:

```text
conda create -n pose_estimator_env python=3.10
conda activate pose_estimator_env
python --version
```

In Anaconda Prompt, navigate to the repository root directory—the location where the training scripts are stored. Use the directory chosen for your own installation; no fixed project location is required. Activate the environment in each new prompt before running a training script:

```text
conda activate pose_estimator_env
```

## Configure dataset and output paths

Before running either local training script, edit `training_paths.yaml` and provide these three paths:

```yaml
training_paths:
  DATASET_ROOT: "path to the dataset root directory"
  LOGS_ROOT: "path to the directory for training outputs"
  CSV_PATH: "path to the dataset CSV file"
```

`DATASET_ROOT` is the root directory used to resolve image paths listed in the CSV. `LOGS_ROOT` is where the run-specific output directory is created. `CSV_PATH` points directly to the CSV file and may be outside `DATASET_ROOT`.

On startup, a script reads `training_paths.yaml`. If the file or any required value is missing or empty, it prompts for the missing path or paths and saves the values back to the YAML file. Absolute paths are recommended. Relative paths are resolved relative to the directory containing `training_paths.yaml`. Keep `path_config.py` and `training_paths.yaml` alongside the training scripts.

## Run training

From the activated `pose_estimator_env` environment and the repository directory, run one of the following:

```text
python cats_pose_local_v01.py
```

or:

```text
python cats_pose_local_v02.py
```

The scripts create separate run folders under `LOGS_ROOT`: `Training_1` for version 01 and `Training_4` for version 02. Each run folder contains the training log and a `checkpoints` directory. The scripts append console output to the corresponding log and save both a resumable last checkpoint and the best validation checkpoint.

## Dataset format

The CSV file must contain the following columns:

```text
image_path, x, y, z, q0, q1, q2, q3, route_type, trajectory_id, split
```

- `image_path` identifies an image relative to `DATASET_ROOT`.
- `x`, `y`, `z` are position coordinates in meters.
- `q0`, `q1`, `q2`, `q3` are quaternion components in the order expected by the training pipeline.
- `route_type` identifies the trajectory category.
- `trajectory_id` identifies the trajectory.
- `split` must identify each row as `train`, `valid`, or `test`.

The training scripts expect examples for all three splits. The training loader balances `route_type` values using weighted sampling.

## Model architecture

The network, `PoseNetLight`, uses an ImageNet-pretrained ResNet-18 as its visual backbone. The final ResNet classification layer is removed; the convolutional feature extractor and global average pooling produce a 512-dimensional feature vector. A regression head maps this representation to the pose:

```text
512 features
  -> Linear(512, 256) -> ReLU -> Dropout(0.5)
  -> Linear(256, 128) -> ReLU
  -> Linear(128, 7)
```

The seven outputs represent `[x, y, z, q0, q1, q2, q3]`. Position is min-max normalized to `[-1, 1]` using the room limits in the scripts and converted back to meters for evaluation. The quaternion outputs are normalized to unit length for loss calculation and evaluation.

The quaternion component convention documented for the ROS 2 pipeline is `q0=x`, `q1=y`, `q2=z`, and `q3=w`.

Input images are converted to RGB, resized to 224 × 224 pixels, converted to tensors, and normalized with ImageNet channel statistics. During training, both versions apply color jitter, Gaussian blur, additive Gaussian noise, and random erasing. Validation and test processing use resizing and normalization only.

## Training and evaluation details

Both scripts use Adam (`lr=1e-4`, `weight_decay=1e-4`), a `ReduceLROnPlateau` scheduler (factor 0.5, patience 3), batch size 8, and mixed precision when CUDA is available. The loss is the position MSE plus 10 times the quaternion MSE. Version 02 aligns the signs of the predicted and ground-truth quaternions before computing quaternion MSE, accounting for the fact that `q` and `-q` represent the same rotation.

| Setting | Version 01 | Version 02 |
|---|---:|---:|
| Maximum epochs | 40 | 60 |
| Early stopping | No | Patience of 20 epochs without validation-loss improvement |
| Quaternion sign alignment in loss | No | Yes |

After training, the best validation checkpoint is loaded for test evaluation. Translation error is the Euclidean distance between predicted and ground-truth positions in meters. Rotation error is the angular distance between normalized quaternions in degrees. Metrics are reported globally and by route type.

For further details about the network, loss, evaluation, and consistency with the ROS 2 inference node, see `model_summary.md`.

