# ==================================================
# gis_worker.py - QGIS 预处理运行线程
# 作用：在后台依次执行两个阶段的子进程，实时回传日志与进度，避免界面卡顿
# 说明：QGIS 自带 PyQt6，与项目的 PySide6 无法在同一进程内共存，
#       因此阶段一必须用 QGIS 自带 Python 以子进程方式运行；
#       阶段二需要 h5py/rasterio，用项目自身的 Python 运行。
# ==================================================
import ast
import os
import re
import subprocess
import sys

from PySide6.QtCore import QThread, Signal

# 日志中的 [已完成/总数] 进度标记
PROGRESS_PATTERN = re.compile(r"\[(\d+)/(\d+)\]")


class GisPreprocessWorker(QThread):
    """两阶段卫星影像预处理线程"""

    log_signal = Signal(str)  # 日志信号
    result_signal = Signal(dict)  # 结果信号
    error_signal = Signal(str)  # 错误信号
    progress_signal = Signal(int)  # 进度信号（0-100）

    def __init__(self, qgis_python, qgis_prefix, preprocess_script,
                 dataset_script, python_exe,
                 input_dir, tiles_dir, temp_dir, h5_dir,
                 epsg, resolution, tile_size, resampling, max_samples):
        """初始化线程参数

        参数:
            qgis_python: str - QGIS 启动器路径（python-qgis.bat）
            qgis_prefix: str - QGIS 前缀路径
            preprocess_script: str - 阶段一脚本路径
            dataset_script: str - 阶段二脚本路径
            python_exe: str - 运行阶段二的项目 Python 解释器
            input_dir: str - 输入影像根目录
            tiles_dir: str - GeoTIFF 切片输出目录
            temp_dir: str - 中间文件目录
            h5_dir: str - HDF5 数据集输出目录
            epsg: str - 目标坐标系
            resolution: float - 目标分辨率（米）
            tile_size: int - 瓦片边长（像素）
            resampling: int - 重采样枚举值
            max_samples: int - 最大样本数，0 表示不限制
        """
        super().__init__()
        self.qgis_python = qgis_python
        self.qgis_prefix = qgis_prefix
        self.preprocess_script = preprocess_script
        self.dataset_script = dataset_script
        self.python_exe = python_exe
        self.input_dir = input_dir
        self.tiles_dir = tiles_dir
        self.temp_dir = temp_dir
        self.h5_dir = h5_dir
        self.epsg = epsg
        self.resolution = resolution
        self.tile_size = tile_size
        self.resampling = resampling
        self.max_samples = max_samples
        self.is_running = True  # 线程运行状态
        self._process = None  # 当前子进程
        self._stage_results = []  # 各阶段返回的结果摘要

    def stop(self):
        """请求停止线程并结束当前子进程及其子进程树"""
        self.is_running = False
        process = self._process
        if process is not None and process.poll() is None:
            # python-qgis.bat 会再拉起 python.exe，需连子进程一起结束
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                               capture_output=True)
            except OSError:
                process.terminate()

    def _build_stage1_command(self):
        """构造阶段一命令（QGIS Python 执行）"""
        return [
            self.qgis_python, self.preprocess_script,
            "--input-dir", self.input_dir,
            "--tiles-dir", self.tiles_dir,
            "--temp-dir", self.temp_dir,
            "--prefix-path", self.qgis_prefix,
            "--epsg", self.epsg,
            "--resolution", str(self.resolution),
            "--tile-size", str(self.tile_size),
            "--resampling", str(self.resampling),
        ]

    def _build_stage2_command(self):
        """构造阶段二命令（项目 Python 执行）"""
        return [
            self.python_exe, "-u", self.dataset_script,
            "--tiles-dir", self.tiles_dir,
            "--out-dir", self.h5_dir,
            "--max-samples", str(self.max_samples),
        ]

    def _read_stage_output(self, process, progress_start, progress_end):
        """实时读取子进程输出，解析日志、进度与结果

        参数:
            process: Popen - 子进程
            progress_start: int - 本阶段进度下界
            progress_end: int - 本阶段进度上界

        返回:
            dict - 本阶段解析到的结果（没有则为空字典）
        """
        result = {}
        current_progress = progress_start
        # 以读取到 EOF 为结束条件：子进程退出后管道中可能还有未读完的输出
        # （含 ===RESULT=== 结果行），只看 poll() 会漏读
        while self.is_running:
            line = process.stdout.readline()
            if not line:
                break
            text = line.strip()
            if not text:
                continue
            self.log_signal.emit(text)

            # 解析 [已完成/总数] 换算为本阶段区间内的进度
            matched = PROGRESS_PATTERN.search(text)
            if matched:
                done, total = int(matched.group(1)), int(matched.group(2))
                if total > 0:
                    ratio = min(done / total, 1.0)
                    current_progress = int(progress_start +
                                           ratio * (progress_end - progress_start))
                    self.progress_signal.emit(current_progress)

            # 捕获 ===RESULT===...===END=== 中的结果字典
            if "===RESULT===" in text and "===END===" in text:
                payload = text.split("===RESULT===")[1].split("===END===")[0].strip()
                try:
                    result = ast.literal_eval(payload)
                except (ValueError, SyntaxError) as exc:
                    self.log_signal.emit(f"结果解析失败：{exc}")
        return result

    def _run_stage(self, cmd, progress_start, progress_end, stage_name):
        """执行单个阶段并等待结束

        参数:
            cmd: list - 命令与参数
            progress_start: int - 进度下界
            progress_end: int - 进度上界
            stage_name: str - 阶段名称（用于日志）

        返回:
            dict - 该阶段结果
        """
        self.log_signal.emit(f"执行命令：{' '.join(cmd)}")
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并标准输出与错误，便于统一展示
            text=True,
            bufsize=1,  # 行缓冲，保证实时输出
            universal_newlines=True,
            encoding="utf-8",
            errors="ignore",
        )
        result = self._read_stage_output(self._process, progress_start, progress_end)
        exit_code = self._process.wait()

        if not self.is_running:
            raise RuntimeError(f"{stage_name}已被手动停止")
        if exit_code != 0:
            raise RuntimeError(f"{stage_name}执行失败，退出码：{exit_code}")
        self.progress_signal.emit(progress_end)
        return result

    def run(self):
        """线程主体：依次执行阶段一、阶段二"""
        try:
            if not self.qgis_python or not os.path.exists(self.qgis_python):
                self.error_signal.emit(
                    f"未找到 QGIS 启动器：{self.qgis_python}，"
                    f"请确认已安装 QGIS 或设置环境变量 QGIS_ROOT"
                )
                return
            if not self.python_exe or not os.path.exists(self.python_exe):
                self.python_exe = sys.executable

            # 阶段一占用前 70% 进度，阶段二占用后 30%
            self._stage_results.append(
                self._run_stage(self._build_stage1_command(), 0, 70, "阶段一（QGIS 预处理）"))
            self._stage_results.append(
                self._run_stage(self._build_stage2_command(), 70, 100, "阶段二（数据集打包）"))

            merged = {}
            for stage_result in self._stage_results:
                merged.update(stage_result)
            merged["status"] = "成功"
            self.progress_signal.emit(100)
            self.result_signal.emit(merged)
        except Exception as exc:
            self.error_signal.emit(str(exc))

