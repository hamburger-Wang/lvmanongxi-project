# 全局配置文件 - 所有常量、路径、格式统一在这里定义
import os
from pathlib import Path

# 配置文件根路径
CONFIG_PATH = Path.home() / ".agri_project"
CONFIG_PATH.mkdir(exist_ok=True)
DB_PATH = CONFIG_PATH / "user_data.db"
SETTINGS_PATH = CONFIG_PATH / "app_settings.ini"

# 数据格式配置（支持的文件类型）
SUPPORTED_FORMATS = {
    "卫星影像": ["*.hdf5", "*.h5", "*.tiff", "*.tif", "*.img"],
    "标签数据": ["*.csv", "*.json", "*.txt"],
    "数组数据": ["*.npy", "*.npz"],
    "所有文件": ["*.*"]
}

# 模型脚本路径（自动适配项目根目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CROP_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "crop_model.py")

# 样式常量（可统一修改）
FONT_MAIN = "Microsoft YaHei"
COLOR_MAIN = "#2E7D32"    # 主色（绿色）
COLOR_SECOND = "#1976D2"  # 次色（蓝色）
COLOR_WARN = "#F44336"    # 警告色（红色）
COLOR_ORANGE = "#FF9800"  # 橙色（跳过登录）