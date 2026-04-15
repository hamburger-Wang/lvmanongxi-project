# ==================================================
# crop_classification_widget.py - 作物分类模块
# 作用：实现作物分类功能，支持不同模型的分类预测
# 功能模块：
# 1. 数据导入和信息显示
# 2. 模型参数配置（模型选择、损失函数、训练轮数）
# 3. 模型训练和预测控制
# 4. 模型执行状态显示和日志输出
# 5. 分类结果展示
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
import os

class CropClassificationWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None  # 模型运行线程
        self.imported_files = []  # 导入的文件列表
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化作物分类界面
        
        说明：构建作物分类模块的UI布局，包括数据导入、参数配置、模型控制和结果展示
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置布局边距

        # 标题
        title_label = QLabel("作物分类")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 数据导入区域
        import_group = QGroupBox("数据导入（支持多格式）")  # 数据导入分组
        import_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        import_layout = QVBoxLayout(import_group)

        # 导入类型+批量选择
        top_layout = QHBoxLayout()
        
        # 文件类型选择
        format_label = QLabel("文件类型：")  # 文件类型标签
        format_label.setFont(QFont(FONT_MAIN, 11))  # 标签字体
        top_layout.addWidget(format_label)
        
        self.format_combo = QComboBox()  # 文件类型下拉框
        self.format_combo.setFont(QFont(FONT_MAIN, 11))  # 下拉框字体
        self.format_combo.addItems(list(SUPPORTED_FORMATS.keys()))  # 添加文件类型选项
        top_layout.addWidget(self.format_combo)
        
        # 批量选择按钮
        batch_btn = QPushButton("批量选择")  # 批量选择按钮
        batch_btn.setFont(QFont(FONT_MAIN, 11))  # 按钮字体
        batch_btn.setStyleSheet(f"background-color: {COLOR_SECOND}; color: white; padding: 5px 10px;")  # 按钮样式
        batch_btn.clicked.connect(self.batch_import_files)  # 绑定点击事件
        top_layout.addWidget(batch_btn)
        
        import_layout.addLayout(top_layout)

        # 文件列表
        self.file_list = QListWidget()  # 文件列表
        self.file_list.setFont(QFont(FONT_MAIN, 11))  # 列表字体
        self.file_list.setSelectionMode(QListWidget.SingleSelection)  # 单选模式
        import_layout.addWidget(self.file_list)

        main_layout.addWidget(import_group)

        # 参数配置区域
        param_group = QGroupBox("分类参数配置")  # 参数配置分组
        param_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        param_layout = QVBoxLayout(param_group)

        # 基础参数
        input_layout = QGridLayout()
        input_layout.setSpacing(15)  # 控件间距

        # 基础参数
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
            input_layout.addWidget(label, row, col)
            
            if isinstance(widget, QComboBox):
                widget.addItems(values)  # 添加下拉选项
            elif isinstance(widget, QLineEdit):
                widget.setText(values[0])  # 设置默认值
            
            widget.setFont(QFont(FONT_MAIN, 11))  # 控件字体
            input_layout.addWidget(widget, row, col + 1)
            
            self.widgets[label_text[:-1]] = widget  # 存储控件
            
            # 控制布局，每行两个参数
            col += 2
            if col >= 4:
                col = 0
                row += 1

        param_layout.addLayout(input_layout)
        main_layout.addWidget(param_group)

        # 模型控制区域
        control_group = QGroupBox("模型控制")  # 模型控制分组
        control_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        control_layout = QHBoxLayout(control_group)

        # 运行模型按钮
        self.run_model_btn = QPushButton("运行分类模型")  # 运行模型按钮
        self.run_model_btn.setFont(QFont(FONT_MAIN, 12))  # 按钮字体
        self.run_model_btn.setStyleSheet(f"background-color: {COLOR_MAIN}; color: white; padding: 8px 16px;")  # 按钮样式
        self.run_model_btn.clicked.connect(self.start_crop_task)  # 绑定点击事件
        control_layout.addWidget(self.run_model_btn)

        # 停止按钮
        self.stop_model_btn = QPushButton("停止")  # 停止按钮
        self.stop_model_btn.setFont(QFont(FONT_MAIN, 12))  # 按钮字体
        self.stop_model_btn.setStyleSheet(f"background-color: {COLOR_WARN}; color: white; padding: 8px 16px;")  # 按钮样式
        self.stop_model_btn.clicked.connect(self.stop_crop_task)  # 绑定点击事件
        self.stop_model_btn.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.stop_model_btn)

        main_layout.addWidget(control_group)

        # 进度和日志区域
        bottom_layout = QHBoxLayout()

        # 进度条
        self.progress_bar = QProgressBar()  # 进度条
        self.progress_bar.setValue(0)  # 初始值
        self.progress_bar.setVisible(False)  # 初始隐藏
        bottom_layout.addWidget(self.progress_bar, stretch=1)  # 添加到布局，设置伸缩比例

        main_layout.addLayout(bottom_layout)

        # 日志输出
        log_group = QGroupBox("运行日志")  # 日志分组
        log_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()  # 日志文本框
        self.log_text.setFont(QFont(FONT_MAIN, 10))  # 文本字体
        self.log_text.setReadOnly(True)  # 只读
        self.log_text.setStyleSheet("background-color: #F0F0F0;")  # 背景色
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

    def batch_import_files(self):
        """批量导入文件
        
        说明：打开文件选择对话框，支持批量选择文件，显示在文件列表中
        """
        # 获取当前选择的文件类型
        format_key = self.format_combo.currentText()
        filters = SUPPORTED_FORMATS.get(format_key, ["*.*"])
        
        # 构建文件过滤器
        filter_str = ";;".join([f"{format_key} ({' '.join(filters)})"])
        
        # 打开文件选择对话框
        file_dialog = DataImporter()
        files = file_dialog.select_files(filters=filters)
        
        if files:
            # 清空现有列表
            self.file_list.clear()
            self.imported_files = files
            
            # 添加文件到列表
            for file_path in files:
                self.file_list.addItem(file_path)
            
            # 显示导入成功信息
            QMessageBox.information(self, "提示", f"成功导入 {len(files)} 个文件！")

    def start_crop_task(self):
        """启动作物分类任务
        
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
        self.stop_model_btn.setEnabled(True)  # 启用停止按钮
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
        self.append_log("开始调用作物分类模型...")  # 添加启动日志

    def stop_crop_task(self):
        """停止作物分类任务
        
        说明：停止正在运行的CropWorker线程
        """
        if self.worker and self.worker.isRunning():
            self.worker.stop()  # 停止线程
            self.append_log("正在停止模型运行...")  # 添加停止日志

    def append_log(self, text):
        """追加日志到文本框
        
        参数:
            text: str - 日志文本
        """
        self.log_text.append(text)  # 追加文本
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())  # 滚动到底部

    def on_task_success(self, result):
        """任务成功处理
        
        参数:
            result: dict - 任务执行结果
        """
        self.append_log(f"任务执行成功！状态: {result.get('status')}")  # 添加成功日志
        if "kappa" in result:
            self.append_log(f"Kappa系数: {result['kappa']:.3f}")  # 添加kappa系数
        if "class_ratio" in result:
            self.append_log("分类比例:")  # 添加分类比例
            for crop, ratio in result['class_ratio'].items():
                self.append_log(f"  {crop}: {ratio:.2%}")
        self.append_log(f"模型保存路径: {result.get('model_path')}")  # 添加模型路径
        self.append_log(f"结果图保存路径: {result.get('img_path')}")  # 添加结果图路径
        
        # 恢复状态
        self.run_model_btn.setEnabled(True)  # 启用运行模型按钮
        self.stop_model_btn.setEnabled(False)  # 禁用停止按钮
        self.progress_bar.setValue(100)  # 设置进度条为100%

    def on_task_error(self, error_msg):
        """任务错误处理
        
        参数:
            error_msg: str - 错误信息
        """
        self.append_log(f"任务执行失败: {error_msg}")  # 添加错误日志
        
        # 恢复状态
        self.run_model_btn.setEnabled(True)  # 启用运行模型按钮
        self.stop_model_btn.setEnabled(False)  # 禁用停止按钮
