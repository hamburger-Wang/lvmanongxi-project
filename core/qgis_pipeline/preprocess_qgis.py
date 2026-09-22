# ==================================================
# preprocess_qgis.py - QGIS 卫星影像预处理（阶段一）
# 作用：把每个时相的 Sentinel-2 单波段影像，用 QGIS 的 GDAL 算法完成
#       重投影到统一坐标系与分辨率 → 合成为多波段影像 → 规则切片
# 运行环境：必须由 QGIS 自带的 Python 执行（bin\python-qgis.bat），
#           因为 qgis.core / processing 只能在 QGIS 环境里导入。
#           本脚本不依赖 h5py，时序堆叠与打包由 build_dataset.py 负责。
# ==================================================
import argparse
import math
import os
import re
import shutil
import sys
import time

DEFAULT_BANDS = "B02,B03,B04,B08,B11,B12"

# QGIS 应用实例必须保持引用，否则被回收后算法注册表会失效
_QGIS_APP = None


def log(msg):
    """输出日志并立即刷新，保证父进程能实时读到"""
    print(msg, flush=True)


def bootstrap_qgis(prefix_path):
    """初始化 QGIS 运行环境并注册 processing 算法提供者

    参数:
        prefix_path: str - QGIS 前缀路径（.../apps/qgis）

    返回:
        QgsApplication - 已初始化的应用实例
    """
    global _QGIS_APP

    # processing 插件位于 python/plugins 下，需手动加入模块搜索路径
    for path in (os.path.join(prefix_path, "python", "plugins"),
                 os.path.join(prefix_path, "python")):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

    from qgis.core import QgsApplication

    # 无 GUI 模式启动（第二个参数 GUIenabled=False）
    QgsApplication.setPrefixPath(prefix_path, True)
    qgis_app = QgsApplication([], False)
    qgis_app.initQgis()
    _QGIS_APP = qgis_app  # 保持引用，避免被垃圾回收

    # 注册 GDAL/原生等算法提供者，否则调用 gdal:* 算法会找不到
    from processing.core.Processing import Processing
    Processing.initialize()

    from qgis.core import Qgis
    log(f"QGIS 版本：{Qgis.version()}")
    log(f"已注册算法数：{len(QgsApplication.processingRegistry().algorithms())}")
    return qgis_app


class AlgorithmRunner:
    """封装 processing.run，失败时抛出带原始报错的异常"""

    def __init__(self):
        from qgis.core import QgsProcessingFeedback
        self._feedback = QgsProcessingFeedback()

    def run(self, alg_id, params):
        """执行算法，失败时抛出异常

        参数:
            alg_id: str - 算法标识，如 gdal:warpreproject
            params: dict - 算法参数
        """
        import processing
        try:
            processing.run(alg_id, params, feedback=self._feedback)
        except Exception as exc:
            raise RuntimeError(f"算法 {alg_id} 执行失败：{exc}") from exc


def find_band_file(folder, band):
    """在目录中查找指定波段的影像文件（大小写不敏感，支持 tif/tiff/jp2）"""
    if not os.path.isdir(folder):
        return None
    for name in os.listdir(folder):
        stem, ext = os.path.splitext(name)
        if stem.upper() == band.upper() and ext.lower() in (".tif", ".tiff", ".jp2"):
            return os.path.join(folder, name)
    return None


def discover_dates(input_dir, bands):
    """发现所有时相及其波段文件

    参数:
        input_dir: str - 输入根目录
        bands: list - 波段名列表

    返回:
        list - [(时相名, {波段: 文件路径})]，按目录名排序
    """
    dates = []
    sub_dirs = sorted(d for d in os.listdir(input_dir)
                      if os.path.isdir(os.path.join(input_dir, d)))
    for name in sub_dirs:
        folder = os.path.join(input_dir, name)
        band_files = {}
        for band in bands:
            path = find_band_file(folder, band)
            if path:
                band_files[band] = path
        missing = [b for b in bands if b not in band_files]
        if not band_files:
            continue
        if missing:
            log(f"⚠️  跳过时相 {name}：缺少波段 {','.join(missing)}")
            continue
        dates.append((name, band_files))

    # 兼容单时相：影像直接放在输入根目录下（不再分时相子目录）
    if not dates:
        band_files = {}
        for band in bands:
            path = find_band_file(input_dir, band)
            if path:
                band_files[band] = path
        if band_files:
            name = os.path.basename(os.path.abspath(input_dir))
            log(f"未发现时相子目录，按单时相处理：{name}")
            dates.append((name, band_files))
    return dates


def compute_aoi(band_files, target_epsg, tile_size, resolution):
    """计算所有影像在目标坐标系下的并集范围，并向外对齐到瓦片网格

    说明：所有时相统一使用该范围输出，可保证各时相切片网格严格对齐，
          这是多时相样本能够逐瓦片对应、堆叠成时序的前提。
          范围向外取整到「瓦片边长×分辨率」的整数倍，可让输出影像的宽高
          恰好是瓦片边长的整数倍，避免 gdal_retile 产生不足边长的边缘瓦片。

    参数:
        band_files: list - 待参与计算的影像路径
        target_epsg: str - 目标坐标系
        tile_size: int - 瓦片边长（像素）
        resolution: float - 目标分辨率（米）

    返回:
        tuple - (QgsRectangle 对齐后的范围, 列数, 行数)
    """
    from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                           QgsProject, QgsRasterLayer, QgsRectangle)

    target_crs = QgsCoordinateReferenceSystem(target_epsg)
    if not target_crs.isValid():
        raise RuntimeError(f"无效的目标坐标系：{target_epsg}")
    transform_ctx = QgsProject.instance().transformContext()

    aoi = QgsRectangle()
    aoi.setNull()
    for path in band_files:
        layer = QgsRasterLayer(path, os.path.basename(path))
        if not layer.isValid():
            raise RuntimeError(f"无法读取影像：{path}")
        extent = layer.extent()
        if layer.crs() != target_crs:
            transform = QgsCoordinateTransform(layer.crs(), target_crs, transform_ctx)
            extent = transform.transformBoundingBox(extent)
        if aoi.isNull():
            aoi = QgsRectangle(extent)
        else:
            aoi.combineExtentWith(extent)

    # 向外对齐到瓦片网格
    step = tile_size * resolution
    x_min = math.floor(aoi.xMinimum() / step) * step
    y_min = math.floor(aoi.yMinimum() / step) * step
    x_max = math.ceil(aoi.xMaximum() / step) * step
    y_max = math.ceil(aoi.yMaximum() / step) * step

    columns = int(round((x_max - x_min) / resolution / tile_size))
    rows = int(round((y_max - y_min) / resolution / tile_size))
    return QgsRectangle(x_min, y_min, x_max, y_max), columns, rows


def process_date(runner, date_name, band_files, bands, args, aoi):
    """处理单个时相：逐波段重投影 → 合成多波段 → 切片

    参数:
        runner: AlgorithmRunner - 算法执行器
        date_name: str - 时相名称（用作中间文件名与切片名前缀）
        band_files: dict - {波段: 文件路径}
        bands: list - 波段顺序
        args: argparse.Namespace - 命令行参数
        aoi: QgsRectangle - 统一输出范围

    返回:
        tuple - (切片输出目录, 该时相切片数量)
    """
    from qgis.core import QgsCoordinateReferenceSystem

    safe_name = re.sub(r"[^0-9A-Za-z_\-]", "_", date_name)
    target_crs = QgsCoordinateReferenceSystem(args.epsg)

    # 1. 逐波段重投影到统一坐标系、分辨率与范围
    warped_paths = []
    for band in bands:
        warped = os.path.join(args.temp_dir, f"{safe_name}_{band}_warp.tif")
        runner.run("gdal:warpreproject", {
            "INPUT": band_files[band],
            "TARGET_CRS": target_crs,
            "RESAMPLING": args.resampling,
            "TARGET_RESOLUTION": args.resolution,
            "TARGET_EXTENT": aoi,
            "TARGET_EXTENT_CRS": target_crs,
            "DATA_TYPE": 0,  # 0 = 沿用输入数据类型（保持 UInt16）
            "NODATA": args.nodata,
            "MULTITHREADING": True,
            "OUTPUT": warped,
        })
        if not os.path.exists(warped):
            raise RuntimeError(f"重投影未生成结果：{band} @ {date_name}")
        warped_paths.append(warped)

    # 2. 合成多波段影像：SEPARATE=True 才是波段堆叠，否则会被当成镶嵌覆盖
    merged = os.path.join(args.temp_dir, f"{safe_name}.tif")
    runner.run("gdal:merge", {
        "INPUT": warped_paths,
        "SEPARATE": True,
        "NODATA_OUTPUT": args.nodata,
        "DATA_TYPE": args.merge_data_type,
        "OUTPUT": merged,
    })
    if not os.path.exists(merged):
        raise RuntimeError(f"多波段合成失败：{date_name}")

    # 3. 规则切片（切片名由输入文件名派生，即 <时相名>_行_列.tif）
    tile_dir = os.path.join(args.tiles_dir, safe_name)
    if os.path.isdir(tile_dir):
        shutil.rmtree(tile_dir)
    # gdal_retile 要求目标目录已存在，否则报 TargetDir does not exist
    os.makedirs(tile_dir, exist_ok=True)
    runner.run("gdal:retile", {
        "INPUT": [merged],
        "TILE_SIZE_X": args.tile_size,
        "TILE_SIZE_Y": args.tile_size,
        "OVERLAP": 0,
        "LEVELS": 1,  # gdal_retile 要求至少 1 级
        "DIR_FOR_ROW": False,
        "DATA_TYPE": args.merge_data_type,
        "OUTPUT": tile_dir,
    })

    # 删除金字塔层级目录，只保留原始分辨率切片
    for name in os.listdir(tile_dir):
        sub = os.path.join(tile_dir, name)
        if os.path.isdir(sub):
            shutil.rmtree(sub, ignore_errors=True)

    tile_count = len([f for f in os.listdir(tile_dir) if f.lower().endswith(".tif")])
    if tile_count == 0:
        raise RuntimeError(f"切片结果为空：{date_name}")

    if not args.keep_temp:
        for path in warped_paths + [merged]:
            try:
                os.remove(path)
            except OSError:
                pass
    return tile_dir, tile_count


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="QGIS 卫星影像预处理（重投影+合成+切片）")
    parser.add_argument("--input-dir", required=True, help="输入根目录（每个时相一个子目录）")
    parser.add_argument("--tiles-dir", required=True, help="GeoTIFF 切片输出目录")
    parser.add_argument("--temp-dir", required=True, help="中间文件目录")
    parser.add_argument("--prefix-path", default=os.environ.get("QGIS_PREFIX_PATH", ""),
                        help="QGIS 前缀路径（.../apps/qgis）")
    parser.add_argument("--epsg", default="EPSG:32650", help="目标坐标系")
    parser.add_argument("--resolution", type=float, default=10.0, help="目标分辨率（米）")
    parser.add_argument("--tile-size", type=int, default=128, help="瓦片边长（像素）")
    parser.add_argument("--bands", default=DEFAULT_BANDS, help="波段顺序，逗号分隔")
    parser.add_argument("--resampling", type=int, default=1, help="重采样方式枚举（0最近邻/1双线性/2三次卷积/5平均）")
    parser.add_argument("--nodata", type=int, default=0, help="无效值填充")
    parser.add_argument("--merge-data-type", type=int, default=2, help="合成输出数据类型枚举（2=UInt16）")
    parser.add_argument("--keep-temp", action="store_true", help="保留中间的重投影与合成文件")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    bands = [b.strip() for b in args.bands.split(",") if b.strip()]
    started = time.time()

    if not args.prefix_path or not os.path.isdir(args.prefix_path):
        log(f"❌ QGIS 前缀路径无效：{args.prefix_path!r}")
        return 1
    if not os.path.isdir(args.input_dir):
        log(f"❌ 输入目录不存在：{args.input_dir}")
        return 1

    os.makedirs(args.temp_dir, exist_ok=True)
    os.makedirs(args.tiles_dir, exist_ok=True)

    log("===== 阶段一：QGIS 重投影 + 波段合成 + 切片 =====")
    bootstrap_qgis(args.prefix_path)
    runner = AlgorithmRunner()

    dates = discover_dates(args.input_dir, bands)
    if not dates:
        log("❌ 未找到任何时相影像，请确认输入目录结构与波段命名")
        return 1
    log(f"共发现 {len(dates)} 个时相：{', '.join(d[0] for d in dates)}")

    all_band_files = [p for _, band_files in dates for p in band_files.values()]
    log("正在计算统一输出范围（各时相共用，保证切片网格对齐）...")
    aoi, columns, rows = compute_aoi(all_band_files, args.epsg,
                                    args.tile_size, args.resolution)
    log(f"输出范围（{args.epsg}）："
        f"x[{aoi.xMinimum():.1f}, {aoi.xMaximum():.1f}] "
        f"y[{aoi.yMinimum():.1f}, {aoi.yMaximum():.1f}]")
    log(f"已对齐到瓦片网格：{columns} 列 × {rows} 行，"
        f"预计每时相 {columns * rows} 张切片")

    total_tiles = 0
    for index, (date_name, band_files) in enumerate(dates, start=1):
        log(f"[{index}/{len(dates)}] 处理时相 {date_name} ...")
        tile_dir, tile_count = process_date(runner, date_name, band_files, bands, args, aoi)
        total_tiles += tile_count
        log(f"[{index}/{len(dates)}] 时相 {date_name} 完成，切片 {tile_count} 张 -> {tile_dir}")

    result = {
        "status": "成功",
        "stage": "preprocess",
        "dates": [d[0] for d in dates],
        "date_count": len(dates),
        "tile_count": total_tiles,
        "tiles_dir": args.tiles_dir,
        "elapsed": round(time.time() - started, 1),
    }
    log(f"✅ 阶段一完成：{len(dates)} 个时相，共 {total_tiles} 张切片，"
        f"耗时 {result['elapsed']} 秒")
    log(f"===RESULT==={result}===END===")
    return 0


if __name__ == "__main__":
    sys.exit(main())


