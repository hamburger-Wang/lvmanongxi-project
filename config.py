# ==================================================
# config.py - 全局配置文件
# 作用：统一管理应用的所有常量、路径和格式配置
# 特点：集中式配置，便于统一修改和维护
# ==================================================
import glob
import os
from pathlib import Path

# 项目根目录。QGIS 预处理脚本、默认数据目录均以此为基准。
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

# QGIS 卫星影像预处理配置。QGIS 自带 PyQt6，不能与 PySide6 共进程，
# 因此实际预处理由 QGIS 自带 Python 在独立子进程中执行。
def _detect_qgis_root() -> str:
    env_root = os.environ.get("QGIS_ROOT", "").strip()
    if env_root and os.path.isdir(env_root):
        return env_root

    candidates: list[str] = []
    for pattern in (r"C:\Program Files\QGIS *", r"C:\OSGeo4W\apps\qgis*"):
        candidates.extend(path for path in glob.glob(pattern) if os.path.isdir(path))
    if not candidates:
        return ""

    def version_key(path: str) -> tuple[int, ...]:
        parts = os.path.basename(path).replace("QGIS", "").strip().split(".")
        return tuple(int(part) if part.isdigit() else 0 for part in parts) or (0,)

    return max(candidates, key=version_key)


QGIS_ROOT = _detect_qgis_root()
QGIS_PYTHON = os.path.join(QGIS_ROOT, "bin", "python-qgis.bat") if QGIS_ROOT else ""
QGIS_PREFIX_PATH = os.path.join(QGIS_ROOT, "apps", "qgis") if QGIS_ROOT else ""

GIS_PIPELINE_DIR = BASE_DIR / "core" / "qgis_pipeline"
GIS_PREPROCESS_SCRIPT = GIS_PIPELINE_DIR / "preprocess_qgis.py"
GIS_DATASET_SCRIPT = GIS_PIPELINE_DIR / "build_dataset.py"
GIS_WORK_DIR = BASE_DIR / "gis_data"
GIS_DEFAULT_INPUT_DIR = GIS_WORK_DIR / "input"
GIS_DEFAULT_TILES_DIR = GIS_WORK_DIR / "tiles"
GIS_DEFAULT_TEMP_DIR = GIS_WORK_DIR / "temp"
GIS_DEFAULT_H5_DIR = GIS_WORK_DIR / "dataset"
GIS_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]
GIS_TARGET_EPSG = "EPSG:32650"
GIS_TARGET_RES = 10.0
GIS_TILE_SIZE = 128
GIS_MAX_SAMPLES = 300
GIS_RESAMPLING_OPTIONS = {
    "最近邻（Nearest）": 0,
    "双线性（Bilinear）": 1,
    "三次卷积（Cubic）": 2,
    "平均值（Average）": 5,
}
GIS_DEFAULT_RESAMPLING = "双线性（Bilinear）"
