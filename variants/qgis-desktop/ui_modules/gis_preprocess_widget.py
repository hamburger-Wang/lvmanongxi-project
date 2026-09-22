# ==================================================
# gis_preprocess_widget.py - 卫星影像预处理模块
# 作用：用 QGIS 完成卫星影像的重投影、波段合成与切片，
#       再按时相堆叠成时序数据集（HDF5），供作物分类模型使用
# 功能模块：
# 1. 输入/输出目录选择
# 2. 预处理参数配置（坐标系、分辨率、瓦片大小、重采样）
# 3. 两阶段流程的异步执行与停止
# 4. 实时日志、进度与结果摘要展示
# ==================================================
import os
import sys

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit,
    QTextEdit, QGroupBox, QMessageBox, QProgressBar,
    QGridLayout, QVBoxLayout, QHBoxLayout, QFileDialog
)
from PySide6.QtGui import QFont

from ui_modules.gis_worker import GisPreprocessWorker
from config import (
    FONT_MAIN, COLOR_MAIN, COLOR_SECOND, COLOR_WARN,
    QGIS_PYTHON, QGIS_PREFIX_PATH,
    GIS_PREPROCESS_SCRIPT, GIS_DATASET_SCRIPT,
    GIS_DEFAULT_INPUT_DIR, GIS_DEFAULT_TILES_DIR, GIS_DEFAULT_TEMP_DIR, GIS_DEFAULT_H5_DIR,
    GIS_TARGET_EPSG, GIS_TARGET_RES, GIS_TILE_SIZE, GIS_MAX_SAMPLES,
    GIS_RESAMPLING_OPTIONS, GIS_DEFAULT_RESAMPLING
)


class GisPreprocessWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None  # 预处理线程
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化影像预处理界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 布局边距

        # 标题
        title_label = QLabel("卫星影像预处理（QGIS）")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 目录配置区域
        dir_group = QGroupBox("目录配置")  # 目录配置分组
        dir_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        dir_layout = QGridLayout(dir_group)
        dir_layout.setSpacing(10)  # 控件间距

        # 输入影像目录
        dir_layout.addWidget(QLabel("输入影像目录：", font=QFont(FONT_MAIN, 11)), 0, 0)
        self.input_dir_edit = QLineEdit(str(GIS_DEFAULT_INPUT_DIR))  # 输入目录
        self.input_dir_edit.setFixedHeight(32)  # 控件高度
        dir_layout.addWidget(self.input_dir_edit, 0, 1)
        input_btn = self._make_button("浏览", COLOR_SECOND)  # 浏览按钮
        input_btn.clicked.connect(self.choose_input_dir)  # 绑定选择输入目录
        dir_layout.addWidget(input_btn, 0, 2)

        # 输出目录
        dir_layout.addWidget(QLabel("输出根目录：", font=QFont(FONT_MAIN, 11)), 1, 0)
        self.output_dir_edit = QLineEdit(str(GIS_DEFAULT_TILES_DIR.parent))  # 输出目录
        self.output_dir_edit.setFixedHeight(32)  # 控件高度
        dir_layout.addWidget(self.output_dir_edit, 1, 1)
        output_btn = self._make_button("浏览", COLOR_SECOND)  # 浏览按钮
        output_btn.clicked.connect(self.choose_output_dir)  # 绑定选择输出目录
        dir_layout.addWidget(output_btn, 1, 2)

        # 目录结构说明
        tip_label = QLabel(
            "输入目录结构要求：每个时相一个子目录，子目录内放该时相的各波段影像，"
            "命名为 B02.tif、B03.tif …（波段名大小写不敏感）\n"
            "例如：input/20240101/B02.tif、input/20240101/B03.tif …"
        )
        tip_label.setFont(QFont(FONT_MAIN, 10))  # 说明字体
        tip_label.setStyleSheet("color: #757575;")  # 说明颜色
        tip_label.setWordWrap(True)  # 自动换行
        dir_layout.addWidget(tip_label, 2, 0, 1, 3)

        main_layout.addWidget(dir_group)

        # 参数配置区域
        param_group = QGroupBox("预处理参数")  # 参数配置分组
        param_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        param_layout = QGridLayout(param_group)
        param_layout.setSpacing(10)  # 控件间距

        self.epsg_edit = QLineEdit(GIS_TARGET_EPSG)  # 目标坐标系
        self.resolution_edit = QLineEdit(str(GIS_TARGET_RES))  # 目标分辨率
        self.tile_size_edit = QLineEdit(str(GIS_TILE_SIZE))  # 瓦片边长
        self.max_samples_edit = QLineEdit(str(GIS_MAX_SAMPLES))  # 最大样本数
        self.resampling_combo = QComboBox()  # 重采样方式
        self.resampling_combo.addItems(list(GIS_RESAMPLING_OPTIONS.keys()))  # 重采样选项
        self.resampling_combo.setCurrentText(GIS_DEFAULT_RESAMPLING)  # 默认重采样

        fields = [
            ("目标坐标系：", self.epsg_edit),
            ("分辨率（米）：", self.resolution_edit),
            ("瓦片大小（像素）：", self.tile_size_edit),
            ("重采样方式：", self.resampling_combo),
            ("最大样本数：", self.max_samples_edit),
        ]
        for index, (label_text, widget) in enumerate(fields):
            row, col = divmod(index, 2)
            param_layout.addWidget(QLabel(label_text, font=QFont(FONT_MAIN, 11)), row, col * 2)
            widget.setFixedHeight(32)  # 控件高度
            param_layout.addWidget(widget, row, col * 2 + 1)
        param_layout.setColumnStretch(4, 1)  # 右侧留白

        main_layout.addWidget(param_group)

        # 控制按钮区域
        control_layout = QHBoxLayout()
        self.run_btn = self._make_button("开始预处理", COLOR_MAIN)  # 运行按钮
        self.run_btn.setFixedSize(120, 38)
        self.run_btn.clicked.connect(self.start_preprocess)  # 绑定启动方法
        self.stop_btn = self._make_button("停止", COLOR_WARN)  # 停止按钮
        self.stop_btn.setFixedSize(90, 38)
        self.stop_btn.clicked.connect(self.stop_preprocess)  # 绑定停止方法
        self.stop_btn.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()  # 右侧伸缩空间
        main_layout.addLayout(control_layout)

        # 进度条
        self.progress_bar = QProgressBar()  # 进度条
        self.progress_bar.setRange(0, 100)  # 进度范围
        self.progress_bar.setValue(0)  # 初始值
        self.progress_bar.setVisible(False)  # 初始隐藏
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLOR_MAIN};
                border-radius: 6px;
                text-align: center;
                height: 12px;
                font-family: {FONT_MAIN};
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_MAIN};
                border-radius: 5px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)

        # 结果摘要
        main_layout.addWidget(QLabel("结果摘要：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.result_text = QTextEdit()  # 结果文本框
        self.result_text.setReadOnly(True)  # 只读
        self.result_text.setFixedHeight(90)  # 固定高度
        self.result_text.setPlaceholderText("预处理完成后，此处显示数据集形状与输出路径...")  # 占位文本
        self.result_text.setStyleSheet(self._text_style())  # 文本框样式
        main_layout.addWidget(self.result_text)

        # 运行日志
        main_layout.addWidget(QLabel("运行日志：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.log_text = QTextEdit()  # 日志文本框
        self.log_text.setReadOnly(True)  # 只读
        self.log_text.setPlaceholderText("预处理日志将显示在这里...")  # 占位文本
        self.log_text.setStyleSheet(self._text_style())  # 文本框样式
        main_layout.addWidget(self.log_text, stretch=1)  # 占据剩余空间

        self.check_qgis_env()  # 启动时检查 QGIS 环境

    def _make_button(self, text, color):
        """创建统一样式的按钮"""
        button = QPushButton(text)
        button.setFixedHeight(32)  # 按钮高度
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-family: {FONT_MAIN};
                padding: 0 12px;
            }}
            QPushButton:hover {{ background-color: #455A64; }}
            QPushButton:disabled {{ background-color: #BDBDBD; }}
        """)
        return button

    @staticmethod
    def _text_style():
        """结果/日志文本框的统一样式"""
        return f"""
            QTextEdit {{
                background-color: #F5F5F5;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 5px;
                font-size: 11px;
                font-family: {FONT_MAIN};
            }}
        """

    def check_qgis_env(self):
        """检查 QGIS 环境是否可用，并输出提示信息"""
        self.append_log("===== 卫星影像预处理（QGIS）=====")
        if QGIS_PYTHON and os.path.exists(QGIS_PYTHON):
            self.append_log(f"✅ 已找到 QGIS：{QGIS_PYTHON}")
        else:
            self.append_log("⚠️ 未找到 QGIS 启动器（python-qgis.bat），"
                            "请安装 QGIS 或设置环境变量 QGIS_ROOT 后重启应用")
        self.append_log(f"阶段一脚本：{GIS_PREPROCESS_SCRIPT}")
        self.append_log(f"阶段二脚本：{GIS_DATASET_SCRIPT}")

    # 目录选择相关方法
    def choose_input_dir(self):
        """选择输入影像根目录"""
        selected = QFileDialog.getExistingDirectory(self, "选择输入影像目录",
                                                    self.input_dir_edit.text())
        if selected:
            self.input_dir_edit.setText(selected)

    def choose_output_dir(self):
        """选择输出根目录"""
        selected = QFileDialog.getExistingDirectory(self, "选择输出根目录",
                                                    self.output_dir_edit.text())
        if selected:
            self.output_dir_edit.setText(selected)

    # 参数校验与执行
    def _collect_params(self):
        """读取并校验界面参数

        返回:
            dict - 参数字典；校验失败返回 None
        """
        input_dir = self.input_dir_edit.text().strip()
        if not input_dir or not os.path.isdir(input_dir):
            QMessageBox.warning(self, "提示", "请选择有效的输入影像目录！")
            return None

        output_root = self.output_dir_edit.text().strip()
        if not output_root:
            QMessageBox.warning(self, "提示", "请选择输出根目录！")
            return None

        epsg = self.epsg_edit.text().strip()
        if not epsg:
            QMessageBox.warning(self, "提示", "目标坐标系不能为空！")
            return None

        try:
            resolution = float(self.resolution_edit.text().strip())
            tile_size = int(self.tile_size_edit.text().strip())
            max_samples = int(self.max_samples_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "提示", "分辨率、瓦片大小、最大样本数必须为数字！")
            return None
        if resolution <= 0 or tile_size <= 0 or max_samples < 0:
            QMessageBox.warning(self, "提示", "分辨率与瓦片大小需为正数，样本数不能为负！")
            return None

        return {
            "input_dir": input_dir,
            "tiles_dir": os.path.join(output_root, "tiles"),
            "temp_dir": os.path.join(output_root, "temp"),
            "h5_dir": os.path.join(output_root, "dataset"),
            "epsg": epsg,
            "resolution": resolution,
            "tile_size": tile_size,
            "resampling": GIS_RESAMPLING_OPTIONS.get(
                self.resampling_combo.currentText(), 1),
            "max_samples": max_samples,
        }

    def start_preprocess(self):
        """启动预处理流程"""
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "提示", "预处理正在运行中，请稍候...")
            return
        if not os.path.exists(QGIS_PYTHON):
            QMessageBox.warning(
                self, "提示",
                "未找到 QGIS 启动器（python-qgis.bat）。\n"
                "请安装 QGIS，或设置环境变量 QGIS_ROOT 指向 QGIS 安装目录后重启应用。"
            )
            return

        params = self._collect_params()
        if params is None:
            return
        if not os.path.exists(GIS_PREPROCESS_SCRIPT) or not os.path.exists(GIS_DATASET_SCRIPT):
            QMessageBox.warning(self, "提示", "预处理脚本缺失，请检查 core/qgis_pipeline 目录！")
            return

        # 重置界面状态
        self.run_btn.setEnabled(False)  # 禁用运行按钮
        self.stop_btn.setEnabled(True)  # 启用停止按钮
        self.progress_bar.setVisible(True)  # 显示进度条
        self.progress_bar.setValue(0)  # 重置进度
        self.log_text.clear()  # 清空日志
        self.result_text.clear()  # 清空结果

        # 创建并启动线程
        self.worker = GisPreprocessWorker(
            qgis_python=QGIS_PYTHON,
            qgis_prefix=QGIS_PREFIX_PATH,
            preprocess_script=str(GIS_PREPROCESS_SCRIPT),
            dataset_script=str(GIS_DATASET_SCRIPT),
            python_exe=sys.executable,  # 阶段二使用当前项目的 Python
            input_dir=params["input_dir"],
            tiles_dir=params["tiles_dir"],
            temp_dir=params["temp_dir"],
            h5_dir=params["h5_dir"],
            epsg=params["epsg"],
            resolution=params["resolution"],
            tile_size=params["tile_size"],
            resampling=params["resampling"],
            max_samples=params["max_samples"],
        )
        self.worker.log_signal.connect(self.append_log)  # 日志信号
        self.worker.result_signal.connect(self.on_success)  # 成功信号
        self.worker.error_signal.connect(self.on_error)  # 错误信号
        self.worker.progress_signal.connect(self.progress_bar.setValue)  # 进度信号
        self.worker.start()  # 启动线程

    def stop_preprocess(self):
        """停止预处理流程"""
        if self.worker is not None and self.worker.isRunning():
            self.append_log("正在停止预处理...")
            self.worker.stop()  # 结束子进程

    def append_log(self, text):
        """追加日志到文本框

        参数:
            text: str - 日志文本
        """
        self.log_text.append(text)  # 追加文本
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum())  # 滚动到底部

    def on_success(self, result):
        """预处理成功回调

        参数:
            result: dict - 结果摘要
        """
        self.append_log("✅ 预处理全部完成！")
        self.result_text.setText(
            f"【时相数量】：{result.get('date_count', '-')}\n"
            f"【切片总数】：{result.get('tile_count', '-')}\n"
            f"【样本形状】：({result.get('sample_count', '-')}, "
            f"{result.get('tile_size', '-')}, {result.get('tile_size', '-')}, "
            f"{result.get('time_len', '-')}, {result.get('band_count', '-')})\n"
            f"【数据类型】：{result.get('dtype', '-')}　"
            f"【数据集大小】：{result.get('h5_size_gb', '-')} GB\n"
            f"【HDF5 路径】：{result.get('h5_path', '-')}\n"
            f"【标签表路径】：{result.get('label_path', '-')}"
        )
        self._reset_buttons()

    def on_error(self, error_msg):
        """预处理失败回调

        参数:
            error_msg: str - 错误信息
        """
        self.append_log(f"❌ 执行失败：{error_msg}")
        self.result_text.setText(f"执行失败：{error_msg}")
        self._reset_buttons()

    def _reset_buttons(self):
        """恢复按钮可用状态并隐藏进度条"""
        self.progress_bar.setVisible(False)  # 隐藏进度条
        self.run_btn.setEnabled(True)  # 启用运行按钮
        self.stop_btn.setEnabled(False)  # 禁用停止按钮

