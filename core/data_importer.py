# 数据导入工具类 - 多格式文件解析、文件选择，无UI依赖
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
        """解析导入文件的基本信息（兼容TIFF/IMG/HDF5等，无GDAL依赖）"""
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            file_type = os.path.splitext(file_path)[1].lower()
            info = f"文件名：{file_name} | 大小：{file_size:.2f}MB | 格式：{file_type}"

            # 解析不同格式的详细信息
            if file_type in [".hdf5", ".h5"]:
                with h5py.File(file_path, "r") as f:
                    keys = list(f.keys())
                    shape = f[keys[0]].shape if keys else "空文件"
                    info += f"\nHDF5内容：{keys} | 数据形状：{shape}"
            elif file_type in [".tiff", ".tif", ".img"]:
                with tifffile.TiffFile(file_path) as tif:
                    pages = len(tif.pages)
                    shape = tif.pages[0].shape if pages > 0 else "空影像"
                    dtype = tif.pages[0].dtype if pages > 0 else "未知"
                    info += f"\n影像页数/波段数：{pages} | 数据形状：{shape} | 数据类型：{dtype}"
            elif file_type == ".npy":
                arr = np.load(file_path, allow_pickle=True)
                info += f"\n数组形状：{arr.shape} | 数据类型：{arr.dtype}"
            elif file_type == ".csv":
                df = pd.read_csv(file_path, nrows=5)
                info += f"\n列名：{list(df.columns)} | 前5行行数：{len(df)}"
            elif file_type == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                info += f"\nJSON类型：{type(data).__name__} | 键数/长度：{len(data)}"
            elif file_type == ".npz":
                with np.load(file_path, allow_pickle=True) as npz:
                    keys = list(npz.keys())
                    info += f"\nNPZ包含数组：{keys} | 数组数量：{len(keys)}"
            elif file_type == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[:5]
                info += f"\n文本行数（前5行）：{len(lines)} | 编码：UTF-8"
            
            return True, info
        except Exception as e:
            return False, f"解析文件失败：{str(e)}"

    @staticmethod
    def import_files(file_type="卫星影像", multi_select=True):
        """打开文件选择对话框导入数据，返回文件路径列表"""
        from config import SUPPORTED_FORMATS
        formats = SUPPORTED_FORMATS.get(file_type, ["*.*"])
        file_filter = f"{file_type} ({' '.join(formats)})"
        
        if multi_select:
            files, _ = QFileDialog.getOpenFileNames(None, f"导入{file_type}", "", file_filter)
        else:
            file_path, _ = QFileDialog.getOpenFileName(None, f"导入{file_type}", "", file_filter)
            files = [file_path] if file_path else []
        
        return files