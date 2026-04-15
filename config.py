# ==================================================
# config.py - 全局配置文件
# 作用：统一管理应用的所有常量、路径和格式配置
# 特点：集中式配置，便于统一修改和维护
# ==================================================
import os
from pathlib import Path

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