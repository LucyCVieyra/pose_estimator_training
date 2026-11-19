# Model Summary

## 1. Architecture

**Backbone:** An ImageNet-pretrained ResNet-18 with its final `fc` layer removed. The convolutional feature extractor is retained, including ResNet's native global average pooling, and produces a **512-dimensional** feature vector for each image.

**Regression head (MLP):**

```text
Input (512)
  -> Linear(512, 256) -> ReLU
  -> Dropout(0.5)
  -> Linear(256, 128) -> ReLU
  -> Linear(128, 7)      # linear output; no activation
```

- The network produces **7** outputs: 3 position values and 4 orientation values (a quaternion).
- Dropout (0.5) is the only explicit regularization in the head; the head does not contain BatchNorm layers.

---

## 2. Network input

| Attribute | Configuration |
|---|---|
| Source | RGB image from the drone's front-facing camera |
| Resize | 224 × 224 pixels |
| Normalization | ImageNet mean and standard deviation: `mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]` |
| Color channels | RGB (the inference node explicitly converts BGR to RGB before creating a PIL image) |
| Training augmentation | ColorJitter (brightness, contrast, saturation, and hue), GaussianBlur, additive Gaussian noise, and RandomErasing |
| Inference/validation augmentation | None; only resizing and normalization (`eval_transform`) are applied |

---

## 3. Network output

A 7-value vector: `[x, y, z, q0, q1, q2, q3]`.

**Position (`x`, `y`, `z`):**

- The network predicts values normalized to **[-1, 1]**.
- Min-max normalization uses the room's physical boundaries:
  - x: [-1.25, 8.75] m
  - y: [-8.0, 2.0] m
  - z: [0.1347, 4.3449] m
- Denormalization: `pos = (pos_norm + 1) / 2 * (POS_MAX - POS_MIN) + POS_MIN`.

**Orientation (quaternion, `q0`, `q1`, `q2`, `q3`):**

- The network produces four raw values that are not guaranteed to have unit norm.
- They are normalized to unit length **after** inference: `q = q / ||q||`.
- The confirmed ordering is `q0=x`, `q1=y`, `q2=z`, `q3=w`, matching the ROS 2 `geometry_msgs/Quaternion` convention.

---

## 4. Loss function

```text
loss = t_loss + BETA_ROT * q_loss        (BETA_ROT = 10.0)
```

- `t_loss`: MSE between the predicted and ground-truth positions (both normalized).
- `q_loss`: MSE between the normalized predicted quaternion and the ground-truth quaternion.
- **Quaternion double-cover handling:** Before computing MSE, the ground-truth quaternion's sign is aligned with the predicted quaternion:
  ```text
  dot = q_pred · q_gt
  q_gt_aligned = -q_gt if dot < 0; otherwise q_gt
  ```
  This prevents a geometrically correct prediction from being penalized as incorrect merely because it lies in the opposite hemisphere of quaternion space. The quaternions `q` and `-q` represent the same rotation.

---

## 5. Training procedure

| Component | Configuration |
|---|---|
| Optimizer | Adam, `lr=1e-4`, `weight_decay=1e-4` |
| Scheduler | `ReduceLROnPlateau` (factor 0.5, patience 3 epochs) |
| Mixed precision | Enabled (`torch.autocast` + `GradScaler`) to reduce memory use on GPUs with 4 GB of VRAM |
| Batch size | 8 |
| Maximum epochs | 60 |
| Early stopping | Patience of 20 epochs without an improvement in validation loss |
| Sampling | `WeightedRandomSampler` weights samples inversely to `route_type` frequency to balance trajectory categories (A: Sweep, B: Around obstacles, C: Through obstacles, D: Room perimeter, E: Random) |
| Checkpointing | Separate `last` and `best` checkpoints are saved. `last` supports resuming and includes the optimizer, scheduler, scaler, and patience counter; `best` stores the best validation-loss model and is used for final evaluation. |

**Dataset:** The original CSV contains Euler angles (RPY), which are converted to quaternions `(w, x, y, z)` using `scipy.spatial.transform.Rotation.from_euler('xyz', ...)`. This conversion was verified against the ROS 2 convention.

---

## 6. Evaluation

- The **best** checkpoint, rather than the most recent checkpoint, is loaded for test evaluation.
- **Translation error:** The L2 distance between predicted and ground-truth positions, in meters and evaluated in denormalized space.
- **Rotation error:** The geodesic angle between quaternions, in degrees; this differs from the training MSE:
  ```text
  angle = 2 * arccos(|q1_norm · q2_norm|)
  ```
- Results are broken down by `route_type` to identify systematic performance issues for specific trajectory categories.

**Best results to date: Training 6 and Training 7.**

---

## 7. Training-to-inference consistency (ROS 2)

The `nn_pose_estimator.py` node mirrors the training pipeline's:

- `PoseNetLight` architecture.
- `eval_transform` (without augmentation).
- Spatial normalization constants (`X/Y/Z_MIN/MAX`).
- Quaternion ordering and mapping to `geometry_msgs/Quaternion`.
- BGR-to-RGB conversion before passing the image to PIL/torchvision.

---

## 8. Potential improvements

Areas for further investigation:

1. Replace quaternion MSE with a direct geodesic loss, which may better reflect the angular error reported during evaluation.
2. Learn `BETA_ROT` using uncertainty weighting instead of keeping it fixed at 10.0.
3. Decouple or throttle inference in the ROS 2 node relative to the incoming image rate.