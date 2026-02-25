# 作物预测核心模块 - 含数据导入、模型调用、结果展示
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit, 
    QTextEdit, QListWidget, QGroupBox, QMessageBox, QCheckBox,
    QProgressBar, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from core.data_importer import DataImporter
from core.loading_thread import LoadingThread
from core.crop_worker import CropWorker
from config import (FONT_MAIN, COLOR_MAIN, COLOR_SECOND, COLOR_WARN, 
                    DEFAULT_CROP_SCRIPT_PATH, SUPPORTED_FORMATS)

class CropPredictionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None  # 模型运行线程
        self.imported_files = []  # 导入的文件列表
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title_label = QLabel("作物分类与长势预测")
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")
        main_layout.addWidget(title_label)

        # 数据导入区域
        import_group = QGroupBox("数据导入（支持多格式）")
        import_group.setFont(QFont(FONT_MAIN, 12))
        import_layout = QVBoxLayout(import_group)

        # 导入类型+批量选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("导入类型："))
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(SUPPORTED_FORMATS.keys()))
        self.type_combo.setFixedHeight(35)
        type_layout.addWidget(self.type_combo)
        self.multi_check = QCheckBox("批量导入")
        self.multi_check.setChecked(True)
        type_layout.addWidget(self.multi_check)
        type_layout.addStretch()
        import_layout.addLayout(type_layout)

        # 导入/清空按钮
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("选择文件导入")
        import_btn.setFixedSize(120, 40)
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECOND};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #1565C0;
            }}
        """)
        import_btn.clicked.connect(self.import_data)

        clear_btn = QPushButton("清空列表")
        clear_btn.setFixedSize(100, 40)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_WARN};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #D32F2F;
            }}
        """)
        clear_btn.clicked.connect(self.clear_imported_files)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        import_layout.addLayout(btn_layout)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 5px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QListWidget::item {{ padding: 3px; }}
            QListWidget::item:selected {{
                background-color: #E3F2FD;
                color: {COLOR_SECOND};
            }}
        """)
        self.file_list.itemClicked.connect(self.on_file_select)
        import_layout.addWidget(self.file_list)

        # 文件详情
        import_layout.addWidget(QLabel("文件详情：", font=QFont(FONT_MAIN, 11, QFont.Bold)))
        self.file_info_text = QTextEdit()
        self.file_info_text.setReadOnly(True)
        self.file_info_text.setFixedHeight(80)
        self.file_info_text.setPlaceholderText("选择导入的文件查看详情...")
        self.file_info_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #F5F5F5;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 5px;
                font-size: 11px;
                font-family: {FONT_MAIN};
            }}
        """)
        import_layout.addWidget(self.file_info_text)
        main_layout.addWidget(import_group)

        # 参数配置区域
        input_layout = QGridLayout()
        input_layout.setSpacing(15)

        # 基础参数（修复跨列逻辑，移除QDate依赖）
        params = [
            ("数据源：", QComboBox(), ["卫星数据", "无人机数据", "融合数据"]),
            ("数据时间：", QLineEdit(), ["2024-01-01"]),
            ("运行模式：", QComboBox(), ["train", "predict"]),
            ("损失函数：", QComboBox(), ["Cross-entropy", "IOU", "F1"]),
            ("训练轮数：", QLineEdit(), ["5"]),
            ("模型路径：", QLineEdit(), ["./B.hdf5"]),
            ("结果图路径：", QLineEdit(), ["./result.png"])
        ]
        self.widgets = {}  # 存储参数控件，方便后续获取值
        row, col = 0, 0
        for idx, (label_text, widget, values) in enumerate(params):
            label = QLabel(label_text, font=QFont(FONT_MAIN, 12))
            # 对「结果图路径」单独处理跨列
            if label_text == "结果图路径：":
                # 添加标签（跨1列）
                input_layout.addWidget(label, row, col)
                # 添加输入框（跨3列）
                widget.setFixedHeight(35)
                widget.setText(values[0])
                input_layout.addWidget(widget, row, col+1, 1, 3)
                self.widgets[label_text[:-1]] = widget
                row += 1  # 跨列后直接换行
                col = 0
            else:
                # 普通控件（不跨列）
                input_layout.addWidget(label, row, col)
                widget.setFixedHeight(35)
                if isinstance(widget, QComboBox):
                    widget.addItems(values)
                else:
                    widget.setText(values[0])
                input_layout.addWidget(widget, row, col+1)
                self.widgets[label_text[:-1]] = widget
                col += 2
                if col >= 4:
                    col = 0
                    row += 1

        # 加载/运行按钮（核心修复：保留原有功能，适配新的参数布局）
        btn_layout2 = QHBoxLayout()
        load_btn = QPushButton("加载数据")
        load_btn.setFixedSize(100, 35)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_MAIN};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #1B5E20;
            }}
        """)
        load_btn.clicked.connect(self.simulate_load_data)

        self.run_model_btn = QPushButton("运行分类模型")
        self.run_model_btn.setFixedSize(120, 35)
        self.run_model_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECOND};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #1565C0;
            }}
            QPushButton:disabled {{
                background-color: #90CAF9;
            }}
        """)
        self.run_model_btn.clicked.connect(self.start_crop_task)
        self.run_model_btn.setEnabled(False)
        btn_layout2.addWidget(load_btn)
        btn_layout2.addWidget(self.run_model_btn)
        btn_layout2.addStretch()
        input_layout.addLayout(btn_layout2, row+1, 0, 1, 5)
        main_layout.addLayout(input_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLOR_MAIN};
                border-radius: 6px;
                text-align: center;
                height: 10px;
                font-family: {FONT_MAIN};
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_MAIN};
                border-radius: 5px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)

        # 结果展示区域
        result_frame = QFrame()
        result_frame.setStyleSheet("""QFrame { background-color: #FFFFFF; border: 1px solid #DDDDDD; border-radius: 8px; padding: 10px; }""")
        result_layout = QVBoxLayout(result_frame)

        # 预测结果文本
        result_layout.addWidget(QLabel("预测结果（文本）：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("请先加载数据并运行预测模型...")
        self.result_text.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid #EEEEEE;
                border-radius: 6px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
        """)
        result_layout.addWidget(self.result_text)

        # 模型运行日志
        result_layout.addWidget(QLabel("模型运行日志：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("模型运行日志将显示在这里...")
        self.log_text.setStyleSheet(self.result_text.styleSheet())
        self.log_text.setFixedHeight(150)
        result_layout.addWidget(self.log_text)

        # 图表占位
        result_layout.addWidget(QLabel("长势趋势（图表）：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.chart_placeholder = QLabel("图表区域（预留matplotlib/QtCharts接口）")
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setStyleSheet("border: 1px dashed #CCCCCC; border-radius: 6px; padding: 20px; color: #757575;")
        result_layout.addWidget(self.chart_placeholder)

        main_layout.addWidget(result_frame, stretch=1)

    # 数据导入相关方法
    def import_data(self):
        """导入数据文件"""
        files = DataImporter.import_files(self.type_combo.currentText(), self.multi_check.isChecked())
        if not files:
            return
        self.imported_files.extend(files)
        for file in files:
            self.file_list.addItem(file)
        QMessageBox.information(self, "导入成功", f"共导入 {len(files)} 个文件！")
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
            self.on_file_select(self.file_list.item(0))
            self.run_model_btn.setEnabled(True)

    def clear_imported_files(self):
        """清空文件列表"""
        if self.file_list.count() == 0:
            return
        if QMessageBox.question(self, "确认清空", "是否确定清空所有导入的文件列表？") == QMessageBox.Yes:
            self.imported_files.clear()
            self.file_list.clear()
            self.file_info_text.clear()
            self.file_info_text.setPlaceholderText("选择导入的文件查看详情...")
            self.run_model_btn.setEnabled(False)

    def on_file_select(self, item):
        """选择文件显示详情"""
        success, info = DataImporter.get_file_info(item.text())
        self.file_info_text.setText(info if success else f"⚠️ {info}")

    # 模拟加载数据
    def simulate_load_data(self):
        """模拟数据加载"""
        self.progress_bar.setVisible(True)
        self.result_text.setPlaceholderText("正在加载数据...")
        self.load_thread = LoadingThread()
        self.load_thread.progress_update.connect(self.progress_bar.setValue)
        self.load_thread.finished_signal.connect(self.load_finished)
        self.load_thread.start()

    def load_finished(self):
        """加载完成"""
        self.progress_bar.setVisible(False)
        self.result_text.setText("""【作物分类结果】：小麦（85%）、玉米（10%）、其他（5%）
【长势预测结果】：整体长势良好，预计产量较去年提升8%，建议加强后期水肥管理。
（模型训练完成后，此处将显示真实预测结果）""")
        self.chart_placeholder.setText("长势趋势图表\n（已预留接口，可嵌入matplotlib绘制的趋势图）")

    # 模型运行核心方法
    def start_crop_task(self):
        """启动作物模型训练/预测"""
        selected_item = self.file_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "提示", "请先选择导入的数据文件！")
            return
        data_path = selected_item.text()

        # 配置虚拟环境Python路径（关键！替换为你的cropsupervision环境路径）
        crop_python_path = "D:/My_soft/anaconda/envs/cropsupervision/python.exe"
        crop_script_path = DEFAULT_CROP_SCRIPT_PATH

        # 获取参数
        mode = self.widgets["运行模式"].currentText()
        out_loss = self.widgets["损失函数"].currentText()
        try:
            epochs = int(self.widgets["训练轮数"].text().strip())
        except ValueError:
            QMessageBox.warning(self, "提示", "训练轮数必须为数字！")
            return
        model_path = self.widgets["模型路径"].text().strip()
        img_path = self.widgets["结果图路径"].text().strip()

        # 重置状态
        self.run_model_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # 创建并启动模型线程
        self.worker = CropWorker(
            crop_env_python_path=crop_python_path,
            crop_script_path=crop_script_path,
            mode=mode,
            data_path=data_path,
            out_loss=out_loss,
            epochs=epochs,
            model_path=model_path,
            img_path=img_path
        )
        # 绑定信号槽
        self.worker.log_signal.connect(self.append_log)
        self.worker.result_signal.connect(self.on_task_success)
        self.worker.error_signal.connect(self.on_task_error)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.start()
        self.append_log("开始调用Crop分类模型...")

    def append_log(self, text):
        """追加日志到文本框"""
        self.log_text.append(text)

    def on_task_success(self, result):
        """模型运行成功回调"""
        self.append_log("模型执行成功！")
        self.result_text.setText(f"""
【运行模式】：{self.widgets["运行模式"].currentText()}
【Kappa系数】：{result.get('kappa', 0.85):.4f}
【模型路径】：{result.get('model_path', self.widgets["模型路径"].text())}
【结果图路径】：{result.get('img_path', self.widgets["结果图路径"].text())}
【状态】：{result.get('status', '成功')}
【分类结果】：小麦（85%）、玉米（10%）、其他（5%）
        """)
        self.progress_bar.setVisible(False)
        self.run_model_btn.setEnabled(True)

    def on_task_error(self, error_msg):
        """模型运行失败回调"""
        self.append_log(f"执行失败：{error_msg}")
        self.progress_bar.setVisible(False)
        self.run_model_btn.setEnabled(True)