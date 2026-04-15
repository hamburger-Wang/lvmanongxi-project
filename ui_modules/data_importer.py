# ==================================================
# data_importer.py - 数据导入工具类
# 作用：实现多格式文件的解析和文件选择功能，无UI依赖
# 功能模块：
# 1. 多格式文件解析（HDF5、TIFF、IMG、NPY、CSV、JSON、NPZ、TXT）
# 2. 文件信息提取和展示
# 3. 文件选择对话框集成
# ==================================================
import os
import json
import numpy as np
import h5py
import pandas as pd
import tifffile
from PySide6.QtWidgets import QFileDialog

class DataImporter:
    @staticmethod
    def get_file_info(file_path):
        """解析导入文件的基本信息（兼容TIFF/IMG/HDF5等，无GDAL依赖）
        
        参数:
            file_path: str - 文件路径
        
        返回:
            tuple - (success, info)，success为布尔值表示解析是否成功，info为文件信息字符串
        """
        try:
            file_name = os.path.basename(file_path)  # 获取文件名
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            file_type = os.path.splitext(file_path)[1].lower()  # 获取文件扩展名
            info = f"文件名：{file_name} | 大小：{file_size:.2f}MB | 格式：{file_type}"

            # 解析不同格式的详细信息
            if file_type in [".hdf5", ".h5"]:  # HDF5格式
                with h5py.File(file_path, "r") as f:
                    keys = list(f.keys())  # 获取HDF5文件中的键
                    shape = f[keys[0]].shape if keys else "空文件"  # 获取数据形状
                    info += f"\nHDF5内容：{keys} | 数据形状：{shape}"
            elif file_type in [".tiff", ".tif", ".img"]:  # TIFF/IMG格式
                with tifffile.TiffFile(file_path) as tif:
                    pages = len(tif.pages)  # 获取影像页数/波段数
                    shape = tif.pages[0].shape if pages > 0 else "空影像"  # 获取数据形状
                    dtype = tif.pages[0].dtype if pages > 0 else "未知"  # 获取数据类型
                    info += f"\n影像页数/波段数：{pages} | 数据形状：{shape} | 数据类型：{dtype}"
            elif file_type == ".npy":  # NPY格式
                arr = np.load(file_path, allow_pickle=True)  # 加载NumPy数组
                info += f"\n数组形状：{arr.shape} | 数据类型：{arr.dtype}"
            elif file_type == ".csv":  # CSV格式
                df = pd.read_csv(file_path, nrows=5)  # 读取前5行
                info += f"\n列名：{list(df.columns)} | 前5行行数：{len(df)}"
            elif file_type == ".json":  # JSON格式
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)  # 加载JSON数据
                info += f"\nJSON类型：{type(data).__name__} | 键数/长度：{len(data)}"
            elif file_type == ".npz":  # NPZ格式
                with np.load(file_path, allow_pickle=True) as npz:  # 加载NPZ文件
                    keys = list(npz.keys())  # 获取包含的数组名
                    info += f"\nNPZ包含数组：{keys} | 数组数量：{len(keys)}"
            elif file_type == ".txt":  # TXT格式
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[:5]  # 读取前5行
                info += f"\n文本行数（前5行）：{len(lines)} | 编码：UTF-8"
            
            return True, info  # 返回成功标志和文件信息
        except Exception as e:
            return False, f"解析文件失败：{str(e)}"  # 返回失败标志和错误信息

    @staticmethod
    def import_files(file_type="卫星影像", multi_select=True):
        """打开文件选择对话框导入数据，返回文件路径列表
        
        参数:
            file_type: str - 文件类型，对应SUPPORTED_FORMATS中的键
            multi_select: bool - 是否支持多选
        
        返回:
            list - 选中的文件路径列表
        """
        from config import SUPPORTED_FORMATS  # 导入支持的文件格式
        formats = SUPPORTED_FORMATS.get(file_type, ["*.*"])  # 获取对应文件类型的格式列表
        file_filter = f"{file_type} ({' '.join(formats)})"  # 构建文件过滤器
        
        if multi_select:  # 多选模式
            files, _ = QFileDialog.getOpenFileNames(None, f"导入{file_type}", "", file_filter)
        else:  # 单选模式
            file_path, _ = QFileDialog.getOpenFileName(None, f"导入{file_type}", "", file_filter)
            files = [file_path] if file_path else []
        
        return files  # 返回选中的文件路径列表