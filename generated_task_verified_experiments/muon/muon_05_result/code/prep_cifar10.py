"""
Convert HuggingFace uoft-cs/cifar10 parquet files to torchvision's CIFAR-10 format
(data_batch_1..5, test_batch) so that `torchvision.datasets.CIFAR10(...)` can read
them offline without re-downloading.

Usage:
    python3 prep_cifar10.py --parquet-dir /tmp/cifar10_smoke --out-dir /home/data/cifar10
"""
import argparse
import io
import os
import pickle
import sys

import numpy as np
import pyarrow.parquet as pq
from PIL import Image


def load_split(parquet_path):
    table = pq.read_table(parquet_path)
    n = table.num_rows
    images = np.empty((n, 32, 32, 3), dtype=np.uint8)
    labels = np.empty(n, dtype=np.int64)
    img_struct = table.column("img").combine_chunks()
    label_col = table.column("label").to_pylist()
    for i in range(n):
        img_bytes = img_struct[i]["bytes"].as_py()
        images[i] = np.asarray(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
        labels[i] = label_col[i]
    return images, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, "cifar-10-batches-py"), exist_ok=True)
    out_dir = os.path.join(args.out_dir, "cifar-10-batches-py")

    for split, n_batches, fname in [
        ("train", 5, ["data_batch_{}".format(i) for i in range(1, 6)]),
        ("test", 1, ["test_batch"]),
    ]:
        parquet_path = os.path.join(args.parquet_dir, f"cifar-{split}.parquet")
        print(f"[convert] reading {parquet_path} ...", flush=True)
        images, labels = load_split(parquet_path)
        n = len(labels)
        assert images.shape == (n, 32, 32, 3), images.shape
        # CIFAR-10 batch layout: flat (n*3072) uint8, in [R plane, G plane, B plane] order
        # i.e. data[i] = [R0..R1023, G0..G1023, B0..B1023]
        flat = images.reshape(n, -1)
        # convert RGB -> RRR...GGG...BBB... (this matches what torchvision's CIFAR10 does)
        flat = np.concatenate([images[..., 0].reshape(n, -1),
                               images[..., 1].reshape(n, -1),
                               images[..., 2].reshape(n, -1)], axis=1)
        assert flat.shape == (n, 3072)
        assert flat.dtype == np.uint8
        # split into batches
        per = n // n_batches
        for b in range(n_batches):
            start = b * per
            end = (b + 1) * per if b < n_batches - 1 else n
            batch = {
                b"batch_label": fname[b].encode(),
                b"labels": labels[start:end].astype(np.uint8).tolist(),
                b"data": flat[start:end],
                b"filenames": [f"img_{i}.png".encode() for i in range(start, end)],
            }
            out_path = os.path.join(out_dir, fname[b])
            with open(out_path, "wb") as f:
                pickle.dump(batch, f, protocol=2)
            print(f"[convert] {split} {fname[b]} rows {start}..{end-1}", flush=True)

    # Write batches.meta
    meta = {
        b"num_cases_per_batch": 10000,
        b"num_vis": 3072,
        b"label_names": [b"airplane", b"automobile", b"bird", b"cat", b"deer",
                         b"dog", b"frog", b"horse", b"ship", b"truck"],
    }
    with open(os.path.join(out_dir, "batches.meta"), "wb") as f:
        pickle.dump(meta, f, protocol=2)
    print(f"[convert] done. Files in {out_dir}")


if __name__ == "__main__":
    main()
