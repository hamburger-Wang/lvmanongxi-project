# ==================================================
# build_dataset.py - 时序堆叠与数据集打包（阶段二）
# 作用：把阶段一产出的各时相切片，按地理位置对齐堆叠成时序样本
#       (N, H, W, T, C)，并流式写入 HDF5 数据集与标签表
# 运行环境：项目自身 Python（依赖 rasterio + h5py，QGIS 环境不带 h5py）
# ==================================================
import argparse
import os
import re
import sys
import time

import h5py
import numpy as np
import rasterio

TILE_NAME_PATTERN = re.compile(r"_(\d+)_(\d+)$")


def log(msg):
    """输出日志并立即刷新，保证父进程能实时读到"""
    print(msg, flush=True)


def scan_tile_positions(tiles_dir):
    """扫描各时相切片目录，建立 时相 -> {(行号, 列号): 文件路径} 索引

    参数:
        tiles_dir: str - 阶段一输出的切片根目录

    返回:
        tuple - (时相列表, 索引字典)，时相按目录名排序
    """
    dates = sorted(d for d in os.listdir(tiles_dir)
                   if os.path.isdir(os.path.join(tiles_dir, d)))
    if not dates:
        raise RuntimeError(f"切片目录下没有时相子目录：{tiles_dir}")

    index = {}
    for date in dates:
        date_dir = os.path.join(tiles_dir, date)
        positions = {}
        for name in os.listdir(date_dir):
            if not name.lower().endswith(".tif"):
                continue
            matched = TILE_NAME_PATTERN.search(os.path.splitext(name)[0])
            if not matched:
                raise RuntimeError(
                    f"切片命名不符合 <时相>_行_列.tif 规则：{name}，"
                    f"请确认该目录由 preprocess_qgis.py 生成"
                )
            positions[(int(matched.group(1)), int(matched.group(2)))] = \
                os.path.join(date_dir, name)
        if not positions:
            raise RuntimeError(f"时相 {date} 没有任何切片")
        index[date] = positions
        log(f"  时相 {date}：{len(positions)} 张切片")
    return dates, index


def read_reference(dates, index):
    """读取参考切片，确定样本的形状、波段数与数据类型，并校验各时相一致

    返回:
        tuple - (高度, 宽度, 波段数, 数据类型)
    """
    first_path = next(iter(index[dates[0]].values()))
    with rasterio.open(first_path) as src:
        height, width, band_count = src.height, src.width, src.count
        dtype = src.dtypes[0]

    log(f"参考切片：{os.path.basename(first_path)} "
        f"{band_count} 波段 {width}x{height} {dtype}")
    for date in dates:
        sample_path = next(iter(index[date].values()))
        with rasterio.open(sample_path) as src:
            if (src.height, src.width, src.count, src.dtypes[0]) != \
                    (height, width, band_count, dtype):
                raise RuntimeError(
                    f"时相 {date} 的切片规格与参考不一致，无法堆叠："
                    f"{src.count}波段 {src.width}x{src.height} {src.dtypes[0]}"
                )
    return height, width, band_count, dtype


def tile_bounds(path):
    """读取切片的地理范围，返回 (左上角x, 左上角y)"""
    with rasterio.open(path) as src:
        return round(src.bounds.left, 3), round(src.bounds.top, 3)


def build_dataset(tiles_dir, out_h5_dir, max_samples, dataset_name):
    """堆叠时序并写出 HDF5 数据集与标签表

    参数:
        tiles_dir: str - 切片根目录
        out_h5_dir: str - 数据集输出目录
        max_samples: int - 最大样本数（0 表示不限制）
        dataset_name: str - HDF5 中的数据集名称

    返回:
        dict - 结果摘要
    """
    log("===== 阶段二：多时相堆叠 + HDF5 打包 =====")
    log(f"扫描切片目录：{tiles_dir}")
    dates, index = scan_tile_positions(tiles_dir)
    time_len = len(dates)
    height, width, band_count, dtype = read_reference(dates, index)

    # 只保留在所有时相中都存在的位置，保证每个样本的时序完整
    common = set(index[dates[0]])
    for date in dates[1:]:
        common &= set(index[date])
    positions = sorted(common)
    if not positions:
        raise RuntimeError("没有任何位置在所有时相中都存在，无法构成时序样本")

    dropped = len(index[dates[0]]) - len(positions)
    log(f"共有位置 {len(index[dates[0]])} 个，完整时序位置 {len(positions)} 个"
        + (f"（丢弃 {dropped} 个时序不完整的位置）" if dropped else ""))
    sample_count = len(positions)

    os.makedirs(out_h5_dir, exist_ok=True)
    h5_path = os.path.join(out_h5_dir, "data.h5")
    label_path = os.path.join(out_h5_dir, "label.csv")

    np_dtype = np.dtype(dtype)
    estimated_gb = sample_count * height * width * time_len * band_count * np_dtype.itemsize / 1024 ** 3
    log(f"候选样本上限：{sample_count} 个，形状 ({height}, {width}, {time_len}, {band_count})，"
        f"类型 {dtype}，最多占用 {estimated_gb:.2f} GB")

    with h5py.File(h5_path, "w") as h5_file:
        # 先按候选数分配，写入过程中跳过全无效的位置，最后收缩到实际样本数
        dataset = h5_file.create_dataset(
            dataset_name,
            shape=(sample_count, height, width, time_len, band_count),
            maxshape=(None, height, width, time_len, band_count),
            dtype=np_dtype,
            chunks=(1, height, width, time_len, band_count),  # 每个样本一个分块，便于流式写入
        )
        h5_file.attrs["bands"] = ",".join([f"band_{i}" for i in range(band_count)])
        h5_file.attrs["dates"] = ",".join(dates)
        h5_file.attrs["time_len"] = time_len

        labels = []
        written = 0
        blank = 0
        for processed, (row, col) in enumerate(positions, start=1):
            # 逐时相读取切片，先攒够一个样本的时序（内存占用约 T×C×H×W 个像元）
            series = []
            for date in dates:
                with rasterio.open(index[date][(row, col)]) as src:
                    arr = src.read()  # (波段, 高, 宽)
                # (波段, 高, 宽) -> (高, 宽, 波段)
                series.append(np.transpose(arr, (1, 2, 0)))

            # 完全无有效像元的位置（重投影产生的边角空白瓦片）不写入训练集
            if not any(item.any() for item in series):
                blank += 1
                continue

            for time_index, item in enumerate(series):
                dataset[written, :, :, time_index, :] = item

            left, top = tile_bounds(index[dates[0]][(row, col)])
            labels.append({"sample_id": written, "row": row, "col": col, "x": left, "y": top})
            written += 1

            if processed % 20 == 0 or processed == sample_count:
                log(f"[{processed}/{sample_count}] 已处理位置，写入 {written} 个样本")

            if max_samples and written >= max_samples:
                log(f"已达到样本数上限 {max_samples}，提前结束扫描")
                break

        dataset.resize((written, height, width, time_len, band_count))
        sample_count = written

    if blank:
        log(f"已跳过 {blank} 个全无效（无任何有效像元）的位置")

    with open(label_path, "w", encoding="utf-8") as handle:
        handle.write("sample_id,row,col,x,y\n")
        for item in labels:
            handle.write(f"{item['sample_id']},{item['row']},{item['col']},{item['x']},{item['y']}\n")

    actual_size = os.path.getsize(h5_path) / 1024 ** 3
    log(f"✅ 数据集已保存：{h5_path}（{actual_size:.2f} GB）")
    log(f"✅ 标签表已保存：{label_path}（{sample_count} 行）")

    return {
        "status": "成功",
        "stage": "dataset",
        "h5_path": h5_path,
        "label_path": label_path,
        "sample_count": sample_count,
        "time_len": time_len,
        "band_count": band_count,
        "tile_size": height,
        "dtype": str(dtype),
        "h5_size_gb": round(actual_size, 3),
        "dates": dates,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="多时相堆叠并打包 HDF5 数据集")
    parser.add_argument("--tiles-dir", required=True, help="阶段一输出的切片根目录")
    parser.add_argument("--out-dir", required=True, help="HDF5 与标签表输出目录")
    parser.add_argument("--max-samples", type=int, default=0, help="最大样本数，0 表示不限制")
    parser.add_argument("--dataset-name", default="data", help="HDF5 数据集名称")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    started = time.time()
    try:
        result = build_dataset(args.tiles_dir, args.out_dir, args.max_samples, args.dataset_name)
    except Exception as exc:
        log(f"❌ 阶段二失败：{exc}")
        return 1
    result["elapsed"] = round(time.time() - started, 1)
    log(f"✅ 阶段二完成，耗时 {result['elapsed']} 秒")
    log(f"===RESULT==={result}===END===")
    return 0


if __name__ == "__main__":
    sys.exit(main())


