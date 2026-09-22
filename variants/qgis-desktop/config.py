# ==================================================
# config.py - 全局配置文件
# 作用：统一管理应用的所有常量、路径和格式配置
# 特点：集中式配置，便于统一修改和维护
# ==================================================
import glob
import os
from pathlib import Path

# 项目代码根目录
# 说明：本文件所在目录即项目根目录，供 QGIS 预处理脚本等内部模块定位
BASE_DIR = Path(__file__).resolve().parent

# 配置文件根路径
# 说明：创建用户配置目录，用于存储数据库和设置文件
CONFIG_PATH = Path.home() / ".agri_project"
CONFIG_PATH.mkdir(exist_ok=True)  # 如果目录不存在则创建
DB_PATH = CONFIG_PATH / "user_data.db"  # 用户数据库路径
SETTINGS_PATH = CONFIG_PATH / "app_settings.ini"  # 应用设置文件路径

# 数据格式配置（支持的文件类型）
# 说明：定义不同类型数据支持的文件格式，用于文件选择对话框
SUPPORTED_FORMATS = {
    "卫星影像": ["*.hdf5", "*.h5", "*.tiff", "*.tif", "*.img"],  # 卫星影像文件格式
    "标签数据": ["*.csv", "*.json", "*.txt"],  # 标签和文本数据格式
    "数组数据": ["*.npy", "*.npz"],  # NumPy数组数据格式
    "所有文件": ["*.*"]  # 所有文件类型
}

# 模型脚本路径（自动适配项目根目录）
# 说明：自动计算项目根目录，确保模型脚本路径的正确性
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CROP_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "crop_model.py")  # 默认作物模型脚本路径
DRY_CROP_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "crop_model_dry.py")  # 随机森林模型脚本路径

# 样式常量（可统一修改）
# 说明：定义应用的全局样式，包括字体和颜色
FONT_MAIN = "Microsoft YaHei"  # 主字体
COLOR_MAIN = "#2E7D32"    # 主色（绿色）- 用于主要按钮和标题
COLOR_SECOND = "#1976D2"  # 次色（蓝色）- 用于次要按钮和强调
COLOR_WARN = "#F44336"    # 警告色（红色）- 用于错误提示和删除按钮
COLOR_ORANGE = "#FF9800"  # 橙色 - 用于跳过登录等特殊按钮

# ==================================================
# QGIS 卫星影像预处理配置
# ==================================================
# QGIS 安装根目录
# 说明：QGIS 自带 PyQt6，与本项目的 PySide6 不能同进程共存，
#       因此预处理流程通过子进程调用 QGIS 自带 Python 执行。
#       可设置环境变量 QGIS_ROOT 覆盖，否则自动探测 Program Files 下最高版本。
def _detect_qgis_root():
    env_root = os.environ.get("QGIS_ROOT", "").strip()
    if env_root and os.path.isdir(env_root):
        return env_root
    # 探测常见安装位置下的 QGIS x.y.z 目录，取版本号最大者
    candidates = []
    for pattern in (r"C:\Program Files\QGIS *", r"C:\OSGeo4W\apps\qgis*"):
        candidates.extend(d for d in glob.glob(pattern) if os.path.isdir(d))
    if not candidates:
        return ""
    def _version_key(path):
        tail = os.path.basename(path).replace("QGIS", "").strip()
        parts = tail.split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts) or (0,)
    return max(candidates, key=_version_key)

QGIS_ROOT = _detect_qgis_root()
# QGIS 启动器：内部会配置 GDAL/PROJ/Qt 环境后再调用 Python
QGIS_PYTHON = os.path.join(QGIS_ROOT, "bin", "python-qgis.bat") if QGIS_ROOT else ""
# QGIS 前缀路径，供脚本内 QgsApplication.setPrefixPath 使用
QGIS_PREFIX_PATH = os.path.join(QGIS_ROOT, "apps", "qgis") if QGIS_ROOT else ""

# 预处理脚本位置
GIS_PIPELINE_DIR = BASE_DIR / "core" / "qgis_pipeline"
GIS_PREPROCESS_SCRIPT = GIS_PIPELINE_DIR / "preprocess_qgis.py"  # 阶段一：重投影+合成+切片（QGIS Python）
GIS_DATASET_SCRIPT = GIS_PIPELINE_DIR / "build_dataset.py"  # 阶段二：时序堆叠+H5打包（项目 Python）

# 预处理默认工作目录
GIS_WORK_DIR = BASE_DIR / "gis_data"
GIS_DEFAULT_INPUT_DIR = GIS_WORK_DIR / "input"  # 输入影像根目录（每个时相一个子目录）
GIS_DEFAULT_TILES_DIR = GIS_WORK_DIR / "tiles"  # GeoTIFF 切片输出
GIS_DEFAULT_TEMP_DIR = GIS_WORK_DIR / "temp"  # 重投影/合成的中间文件
GIS_DEFAULT_H5_DIR = GIS_WORK_DIR / "dataset"  # HDF5 数据集输出

# 预处理默认参数
GIS_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]  # 送入模型的波段顺序（蓝/绿/红/近红外/短波红外×2）
GIS_TARGET_EPSG = "EPSG:32650"  # 目标投影：WGS84 / UTM 50N
GIS_TARGET_RES = 10.0  # 统一分辨率（米）
GIS_TILE_SIZE = 128  # 瓦片边长（像素）
GIS_MAX_SAMPLES = 300  # 单次导出的最大样本数，避免数据集过大
# 重采样方式（QGIS gdal:warpreproject 的 RESAMPLING 枚举）
GIS_RESAMPLING_OPTIONS = {
    "最近邻（Nearest）": 0,
    "双线性（Bilinear）": 1,
    "三次卷积（Cubic）": 2,
    "平均值（Average）": 5,
}
GIS_DEFAULT_RESAMPLING = "双线性（Bilinear）"
