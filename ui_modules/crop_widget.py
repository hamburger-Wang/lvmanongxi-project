# ==================================================
# crop_widget.py - 作物预测核心模块
# 作用：实现作物分类与长势预测功能，支持模型训练和预测
# 功能模块：
# 1. 数据导入和信息显示
# 2. 模型参数配置（损失函数、训练轮数）
# 3. 模型训练和预测控制
# 4. 模型执行状态显示和日志输出
# 5. 结果展示
# ==================================================
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit, 
    QTextEdit, QListWidget, QGroupBox, QMessageBox, QCheckBox,
    QProgressBar, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ui_modules.data_importer import DataImporter
from ui_modules.loading_thread import LoadingThread
from ui_modules.crop_worker import CropWorker
from config import (FONT_MAIN, COLOR_MAIN, COLOR_SECOND, COLOR_WARN, 
                    DEFAULT_CROP_SCRIPT_PATH, DRY_CROP_SCRIPT_PATH, SUPPORTED_FORMATS)

class CropPredictionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None  # 模型运行线程
        self.imported_files = []  # 导入的文件列表
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化作物预测界面
        
        说明：构建作物预测模块的UI布局，包括数据导入、参数配置、模型控制和结果展示
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置布局边距

        # 标题
        title_label = QLabel("作物分类与长势预测")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 数据导入区域
        import_group = QGroupBox("数据导入（支持多格式）")  # 数据导入分组
        import_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        import_layout = QVBoxLayout(import_group)

        # 导入类型+批量选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("导入类型："))  # 导入类型标签
        self.type_combo = QComboBox()  # 导入类型下拉框
        self.type_combo.addItems(list(SUPPORTED_FORMATS.keys()))  # 添加支持的文件类型
        self.type_combo.setFixedHeight(35)  # 下拉框高度
        type_layout.addWidget(self.type_combo)
        self.multi_check = QCheckBox("批量导入")  # 批量导入复选框
        self.multi_check.setChecked(True)  # 默认勾选
        type_layout.addWidget(self.multi_check)
        type_layout.addStretch()  # 右侧伸缩空间
        import_layout.addLayout(type_layout)

        # 导入/清空按钮
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("选择文件导入")  # 导入按钮
        import_btn.setFixedSize(120, 40)  # 按钮大小
        # 设置按钮样式
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
        import_btn.clicked.connect(self.import_data)  # 绑定导入数据方法

        clear_btn = QPushButton("清空列表")  # 清空按钮
        clear_btn.setFixedSize(100, 40)  # 按钮大小
        # 设置按钮样式
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
        clear_btn.clicked.connect(self.clear_imported_files)  # 绑定清空文件列表方法
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()  # 右侧伸缩空间
        import_layout.addLayout(btn_layout)

        # 文件列表
        self.file_list = QListWidget()  # 文件列表控件
        # 设置文件列表样式
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
        self.file_list.itemClicked.connect(self.on_file_select)  # 绑定文件选择事件
        import_layout.addWidget(self.file_list)

        # 文件详情
        import_layout.addWidget(QLabel("文件详情：", font=QFont(FONT_MAIN, 11, QFont.Bold)))  # 文件详情标题
        self.file_info_text = QTextEdit()  # 文件详情文本框
        self.file_info_text.setReadOnly(True)  # 只读
        self.file_info_text.setFixedHeight(80)  # 固定高度
        self.file_info_text.setPlaceholderText("选择导入的文件查看详情...")  # 占位文本
        # 设置文本框样式
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
        input_layout.setSpacing(15)  # 控件间距

        # 基础参数（修复跨列逻辑，移除QDate依赖）
        params = [
            ("数据源：", QComboBox(), ["卫星数据", "无人机数据", "融合数据"]),
            ("数据时间：", QLineEdit(), ["2024-01-01"]),
            ("运行模式：", QComboBox(), ["train", "predict"]),
            ("模型选择：", QComboBox(), ["crop_model", "crop_model-dry", "第三模型"]),
            ("损失函数：", QComboBox(), ["Cross-entropy", "IOU", "F1"]),
            ("训练轮数：", QLineEdit(), ["5"]),
            ("模型路径：", QLineEdit(), ["./B.hdf5"]),
            ("结果图路径：", QLineEdit(), ["./result.png"])
        ]
        self.widgets = {}  # 存储参数控件，方便后续获取值
        row, col = 0, 0
        for idx, (label_text, widget, values) in enumerate(params):
            label = QLabel(label_text, font=QFont(FONT_MAIN, 12))  # 参数标签
            # 对「结果图路径」单独处理跨列
            if label_text == "结果图路径：":
                # 添加标签（跨1列）
                input_layout.addWidget(label, row, col)
                # 添加输入框（跨3列）
                widget.setFixedHeight(35)  # 控件高度
                widget.setText(values[0])  # 设置默认值
                input_layout.addWidget(widget, row, col+1, 1, 3)
                self.widgets[label_text[:-1]] = widget  # 存储控件
                row += 1  # 跨列后直接换行
                col = 0
            else:
                # 普通控件（不跨列）
                input_layout.addWidget(label, row, col)
                widget.setFixedHeight(35)  # 控件高度
                if isinstance(widget, QComboBox):
                    widget.addItems(values)  # 添加下拉选项
                else:
                    widget.setText(values[0])  # 设置默认值
                input_layout.addWidget(widget, row, col+1)
                self.widgets[label_text[:-1]] = widget  # 存储控件
                col += 2
                if col >= 4:
                    col = 0
                    row += 1

        # 加载/运行按钮（核心修复：保留原有功能，适配新的参数布局）
        btn_layout2 = QHBoxLayout()
        load_btn = QPushButton("加载数据")  # 加载数据按钮
        load_btn.setFixedSize(100, 35)  # 按钮大小
        # 设置按钮样式
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
        load_btn.clicked.connect(self.simulate_load_data)  # 绑定模拟加载数据方法

        self.run_model_btn = QPushButton("运行分类模型")  # 运行模型按钮
        self.run_model_btn.setFixedSize(120, 35)  # 按钮大小
        # 设置按钮样式
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
        self.run_model_btn.clicked.connect(self.start_crop_task)  # 绑定启动作物模型方法
        self.run_model_btn.setEnabled(False)  # 默认禁用
        btn_layout2.addWidget(load_btn)
        btn_layout2.addWidget(self.run_model_btn)
        btn_layout2.addStretch()  # 右侧伸缩空间
        input_layout.addLayout(btn_layout2, row+1, 0, 1, 5)
        main_layout.addLayout(input_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # 进度范围
        self.progress_bar.setValue(0)  # 初始值
        self.progress_bar.setVisible(False)  # 默认隐藏
        # 设置进度条样式
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
        result_frame = QFrame()  # 结果展示框
        # 设置结果展示框样式
        result_frame.setStyleSheet("""QFrame { background-color: #FFFFFF; border: 1px solid #DDDDDD; border-radius: 8px; padding: 10px; }""")
        result_layout = QVBoxLayout(result_frame)

        # 预测结果文本
        result_layout.addWidget(QLabel("预测结果（文本）：", font=QFont(FONT_MAIN, 12, QFont.Bold)))  # 预测结果标题
        self.result_text = QTextEdit()  # 预测结果文本框
        self.result_text.setReadOnly(True)  # 只读
        self.result_text.setPlaceholderText("请先加载数据并运行预测模型...")  # 占位文本
        # 设置文本框样式
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
        result_layout.addWidget(QLabel("模型运行日志：", font=QFont(FONT_MAIN, 12, QFont.Bold)))  # 日志标题
        self.log_text = QTextEdit()  # 日志文本框
        self.log_text.setReadOnly(True)  # 只读
        self.log_text.setPlaceholderText("模型运行日志将显示在这里...")  # 占位文本
        self.log_text.setStyleSheet(self.result_text.styleSheet())  # 使用与结果文本框相同的样式
        self.log_text.setFixedHeight(150)  # 固定高度
        result_layout.addWidget(self.log_text)

        # 图表占位
        result_layout.addWidget(QLabel("长势趋势（图表）：", font=QFont(FONT_MAIN, 12, QFont.Bold)))  # 图表标题
        self.chart_placeholder = QLabel("图表区域（预留matplotlib/QtCharts接口）")  # 图表占位
        self.chart_placeholder.setAlignment(Qt.AlignCenter)  # 居中显示
        self.chart_placeholder.setStyleSheet("border: 1px dashed #CCCCCC; border-radius: 6px; padding: 20px; color: #757575;")  # 占位样式
        result_layout.addWidget(self.chart_placeholder)

        main_layout.addWidget(result_frame, stretch=1)  # 添加到主布局，设置伸缩比例

    # 数据导入相关方法
    def import_data(self):
        """导入数据文件
        
        说明：打开文件选择对话框，选择并导入数据文件，更新文件列表和详情
        """
        files = DataImporter.import_files(self.type_combo.currentText(), self.multi_check.isChecked())  # 调用数据导入工具
        if not files:  # 如果没有选择文件
            return
        self.imported_files.extend(files)  # 添加到导入文件列表
        for file in files:
            self.file_list.addItem(file)  # 添加到文件列表控件
        QMessageBox.information(self, "导入成功", f"共导入 {len(files)} 个文件！")  # 显示导入成功信息
        if self.file_list.count() > 0:  # 如果有导入的文件
            self.file_list.setCurrentRow(0)  # 选择第一个文件
            self.on_file_select(self.file_list.item(0))  # 显示文件详情
            self.run_model_btn.setEnabled(True)  # 启用运行模型按钮

    def clear_imported_files(self):
        """清空文件列表
        
        说明：清空导入的文件列表，重置相关控件状态
        """
        if self.file_list.count() == 0:  # 如果文件列表为空
            return
        if QMessageBox.question(self, "确认清空", "是否确定清空所有导入的文件列表？") == QMessageBox.Yes:  # 确认清空
            self.imported_files.clear()  # 清空导入文件列表
            self.file_list.clear()  # 清空文件列表控件
            self.file_info_text.clear()  # 清空文件详情
            self.file_info_text.setPlaceholderText("选择导入的文件查看详情...")  # 重置占位文本
            self.run_model_btn.setEnabled(False)  # 禁用运行模型按钮

    def on_file_select(self, item):
        """选择文件显示详情
        
        参数:
            item: QListWidgetItem - 选中的文件项
        
        说明：显示选中文件的详细信息
        """
        success, info = DataImporter.get_file_info(item.text())  # 获取文件信息
        self.file_info_text.setText(info if success else f"⚠️ {info}")  # 显示文件信息

    # 模拟加载数据
    def simulate_load_data(self):
        """模拟数据加载
        
        说明：模拟数据加载过程，显示进度条和加载提示
        """
        self.progress_bar.setVisible(True)  # 显示进度条
        self.result_text.setPlaceholderText("正在加载数据...")  # 更新提示信息
        self.load_thread = LoadingThread()  # 创建加载线程
        self.load_thread.progress_update.connect(self.progress_bar.setValue)  # 绑定进度更新信号
        self.load_thread.finished_signal.connect(self.load_finished)  # 绑定加载完成信号
        self.load_thread.start()  # 启动线程

    def load_finished(self):
        """加载完成
        
        说明：处理数据加载完成后的逻辑，显示模拟结果
        """
        self.progress_bar.setVisible(False)  # 隐藏进度条
        # 显示模拟的预测结果
        self.result_text.setText("""【作物分类结果】：小麦（85%）、玉米（10%）、其他（5%）
【长势预测结果】：整体长势良好，预计产量较去年提升8%，建议加强后期水肥管理。
（模型训练完成后，此处将显示真实预测结果）""")
        self.chart_placeholder.setText("长势趋势图表\n（已预留接口，可嵌入matplotlib绘制的趋势图）")  # 更新图表占位

    # 模型运行核心方法
    def start_crop_task(self):
        """启动作物模型训练/预测
        
        说明：启动CropWorker线程执行模型训练或预测，处理参数验证和状态更新
        """
        selected_item = self.file_list.currentItem()  # 获取当前选中的文件
        if not selected_item:  # 如果没有选择文件
            QMessageBox.warning(self, "提示", "请先选择导入的数据文件！")  # 显示警告
            return
        data_path = selected_item.text()  # 获取数据文件路径

        # 获取参数
        mode = self.widgets["运行模式"].currentText()  # 运行模式
        model_choice = self.widgets["模型选择"].currentText()  # 模型选择

        # 配置虚拟环境Python路径（关键！替换为你的cropsupervision环境路径）
        crop_python_path = "D:/My_soft/anaconda/envs/cropsupervision/python.exe"
        
        # 根据选择的模型确定脚本路径
        if model_choice == "crop_model-dry":
            crop_script_path = DRY_CROP_SCRIPT_PATH
        else:
            crop_script_path = DEFAULT_CROP_SCRIPT_PATH
        out_loss = self.widgets["损失函数"].currentText()  # 损失函数
        try:
            epochs = int(self.widgets["训练轮数"].text().strip())  # 训练轮数
        except ValueError:
            QMessageBox.warning(self, "提示", "训练轮数必须为数字！")  # 显示警告
            return
        model_path = self.widgets["模型路径"].text().strip()  # 模型路径
        img_path = self.widgets["结果图路径"].text().strip()  # 结果图路径

        # 重置状态
        self.run_model_btn.setEnabled(False)  # 禁用运行模型按钮
        self.progress_bar.setVisible(True)  # 显示进度条
        self.progress_bar.setValue(0)  # 重置进度条
        self.log_text.clear()  # 清空日志

        # 创建并启动模型线程
        self.worker = CropWorker(
            crop_env_python_path=crop_python_path,
            crop_script_path=crop_script_path,
            mode=mode,
            model_choice=model_choice,
            data_path=data_path,
            out_loss=out_loss,
            epochs=epochs,
            model_path=model_path,
            img_path=img_path
        )
        # 绑定信号槽
        self.worker.log_signal.connect(self.append_log)  # 日志信号
        self.worker.result_signal.connect(self.on_task_success)  # 成功信号
        self.worker.error_signal.connect(self.on_task_error)  # 错误信号
        self.worker.progress_signal.connect(self.progress_bar.setValue)  # 进度信号
        self.worker.start()  # 启动线程
        self.append_log("开始调用Crop分类模型...")  # 添加启动日志

    def append_log(self, text):
        """追加日志到文本框
        
        参数:
            text: str - 日志文本
        
        说明：将日志文本追加到日志文本框
        """
        self.log_text.append(text)  # 追加日志

    def on_task_success(self, result):
        """模型运行成功回调
        
        参数:
            result: dict - 模型执行结果
        
        说明：处理模型执行成功后的逻辑，显示执行结果
        """
        self.append_log("模型执行成功！")  # 添加成功日志
        # 显示执行结果
        self.result_text.setText(f"""
【运行模式】：{self.widgets["运行模式"].currentText()}
【Kappa系数】：{result.get('kappa', 0.85):.4f}
【模型路径】：{result.get('model_path', self.widgets["模型路径"].text())}
【结果图路径】：{result.get('img_path', self.widgets["结果图路径"].text())}
【状态】：{result.get('status', '成功')}
【分类结果】：小麦（85%）、玉米（10%）、其他（5%）
        """)
        self.progress_bar.setVisible(False)  # 隐藏进度条
        self.run_model_btn.setEnabled(True)  # 启用运行模型按钮

    def on_task_error(self, error_msg):
        """模型运行失败回调
        
        参数:
            error_msg: str - 错误信息
        
        说明：处理模型执行失败后的逻辑，显示错误信息
        """
        self.append_log(f"执行失败：{error_msg}")  # 添加错误日志
        self.progress_bar.setVisible(False)  # 隐藏进度条
        self.run_model_btn.setEnabled(True)  # 启用运行模型按钮