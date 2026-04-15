# ==================================================
# advice_widget.py - 农业种植建议模块
# 作用：实现农业种植建议生成功能，支持常见问题选择和自定义问题输入
# 功能模块：
# 1. 常见问题选择下拉框
# 2. 自定义问题输入文本框
# 3. 种植建议生成按钮
# 4. 生成进度显示
# 5. AI种植建议展示
# ==================================================
from PySide6.QtWidgets import (
    QWidget, QLabel, QTextEdit, QComboBox, QPushButton, 
    QProgressBar, QMessageBox, QVBoxLayout, QHBoxLayout  # 布局类移到QtWidgets
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt  # 仅保留Qt枚举
from ui_modules.loading_thread import LoadingThread
from config import FONT_MAIN, COLOR_MAIN

class FarmingAdviceWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化农业种植建议界面
        
        说明：构建农业种植建议模块的UI布局，包括标题、输入区域和结果展示
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置布局边距

        # 标题
        title_label = QLabel("农业种植建议")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 输入区域
        input_layout = QVBoxLayout()

        # 常见问题下拉框
        self.question_combo = QComboBox()  # 常见问题下拉框
        self.question_combo.addItems([
            "请选择常见问题（可选）",
            "小麦倒伏如何防治？",
            "玉米干旱期水肥管理建议",
            "如何识别作物病虫害？",
            "不同区域种植作物推荐"
        ])  # 添加常见问题选项
        self.question_combo.setFixedHeight(35)  # 下拉框高度
        self.question_combo.currentTextChanged.connect(self.on_question_select)  # 绑定选择事件
        input_layout.addWidget(self.question_combo)

        # 自定义问题
        input_layout.addWidget(QLabel("自定义问题：", font=QFont(FONT_MAIN, 12)))  # 自定义问题标签
        self.question_edit = QTextEdit()  # 自定义问题文本框
        self.question_edit.setPlaceholderText("请输入您想要咨询的农业种植问题...")  # 占位文本
        self.question_edit.setFixedHeight(80)  # 固定高度
        # 设置文本框样式
        self.question_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid #EEEEEE;
                border-radius: 6px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
        """)
        input_layout.addWidget(self.question_edit)

        # 生成按钮+进度条
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成种植建议")  # 生成按钮
        self.generate_btn.setFixedSize(120, 40)  # 按钮大小
        # 设置按钮样式
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_MAIN};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #1B5E20;
            }}
            QPushButton:disabled {{
                background-color: #A5D6A7;
            }}
        """)
        self.generate_btn.clicked.connect(self.simulate_generate_advice)  # 绑定生成建议方法
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addStretch()  # 右侧伸缩空间
        input_layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()  # 进度条
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
        input_layout.addWidget(self.progress_bar)
        main_layout.addLayout(input_layout)

        # 结果展示
        main_layout.addWidget(QLabel("AI种植建议：", font=QFont(FONT_MAIN, 12, QFont.Bold)))  # 结果标题
        self.advice_edit = QTextEdit()  # 建议文本框
        self.advice_edit.setPlaceholderText("暂无种植建议，请输入问题并点击生成按钮...")  # 占位文本
        self.advice_edit.setReadOnly(True)  # 只读
        # 设置文本框样式
        self.advice_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
        """)
        main_layout.addWidget(self.advice_edit, stretch=1)  # 添加到主布局，设置伸缩比例

    def on_question_select(self, text):
        """选择常见问题
        
        参数:
            text: str - 选中的问题文本
        
        说明：当选择常见问题时，将问题文本设置到自定义问题输入框
        """
        if text != "请选择常见问题（可选）":  # 如果选择了具体问题
            self.question_edit.setText(text)  # 设置到自定义问题输入框

    def simulate_generate_advice(self):
        """模拟生成种植建议
        
        说明：模拟AI生成种植建议的过程，显示进度条和加载提示
        """
        question = self.question_edit.toPlainText().strip()  # 获取输入的问题
        if not question:  # 如果问题为空
            QMessageBox.warning(self, "提示", "请输入咨询的问题！")  # 显示警告
            return
        self.progress_bar.setVisible(True)  # 显示进度条
        self.generate_btn.setDisabled(True)  # 禁用生成按钮
        self.advice_edit.setPlaceholderText("AI正在分析您的问题，请稍候...")  # 更新提示信息
        self.load_thread = LoadingThread()  # 创建加载线程
        self.load_thread.progress_update.connect(self.progress_bar.setValue)  # 绑定进度更新信号
        self.load_thread.finished_signal.connect(self.generate_finished)  # 绑定生成完成信号
        self.load_thread.start()  # 启动线程

    def generate_finished(self):
        """生成完成
        
        说明：处理种植建议生成完成后的逻辑，显示模拟的AI建议
        """
        self.progress_bar.setVisible(False)  # 隐藏进度条
        self.generate_btn.setDisabled(False)  # 启用生成按钮
        # 显示模拟的AI种植建议
        self.advice_edit.setText("""【AI种植建议】
基于您的问题和当前农业大数据分析，给出以下建议：

1. 基础管理：根据当前区域的土壤墒情和气候条件，建议每7-10天灌溉一次，每亩施用复合肥20-25公斤。
2. 病虫害防治：近期该区域易发生蚜虫、红蜘蛛等虫害，建议使用生物农药进行防治，避免化学农药残留。
3. 后期管理：根据作物长势预测结果，建议在灌浆期加强田间巡查，及时清除杂草和病株。

（已预留AI大模型接口，后续将接入真实的智能建议生成功能）""")