# advice_widget.py 顶部正确导入
from PySide6.QtWidgets import (
    QWidget, QLabel, QTextEdit, QComboBox, QPushButton, 
    QProgressBar, QMessageBox, QVBoxLayout, QHBoxLayout  # 布局类移到QtWidgets
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt  # 仅保留Qt枚举
from core.loading_thread import LoadingThread
from config import FONT_MAIN, COLOR_MAIN

class FarmingAdviceWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title_label = QLabel("农业种植建议")
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")
        main_layout.addWidget(title_label)

        # 输入区域
        input_layout = QVBoxLayout()

        # 常见问题下拉框
        self.question_combo = QComboBox()
        self.question_combo.addItems([
            "请选择常见问题（可选）",
            "小麦倒伏如何防治？",
            "玉米干旱期水肥管理建议",
            "如何识别作物病虫害？",
            "不同区域种植作物推荐"
        ])
        self.question_combo.setFixedHeight(35)
        self.question_combo.currentTextChanged.connect(self.on_question_select)
        input_layout.addWidget(self.question_combo)

        # 自定义问题
        input_layout.addWidget(QLabel("自定义问题：", font=QFont(FONT_MAIN, 12)))
        self.question_edit = QTextEdit()
        self.question_edit.setPlaceholderText("请输入您想要咨询的农业种植问题...")
        self.question_edit.setFixedHeight(80)
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
        self.generate_btn = QPushButton("生成种植建议")
        self.generate_btn.setFixedSize(120, 40)
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
        self.generate_btn.clicked.connect(self.simulate_generate_advice)
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

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
        input_layout.addWidget(self.progress_bar)
        main_layout.addLayout(input_layout)

        # 结果展示
        main_layout.addWidget(QLabel("AI种植建议：", font=QFont(FONT_MAIN, 12, QFont.Bold)))
        self.advice_edit = QTextEdit()
        self.advice_edit.setPlaceholderText("暂无种植建议，请输入问题并点击生成按钮...")
        self.advice_edit.setReadOnly(True)
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
        main_layout.addWidget(self.advice_edit, stretch=1)

    def on_question_select(self, text):
        """选择常见问题"""
        if text != "请选择常见问题（可选）":
            self.question_edit.setText(text)

    def simulate_generate_advice(self):
        """模拟生成种植建议"""
        question = self.question_edit.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "提示", "请输入咨询的问题！")
            return
        self.progress_bar.setVisible(True)
        self.generate_btn.setDisabled(True)
        self.advice_edit.setPlaceholderText("AI正在分析您的问题，请稍候...")
        self.load_thread = LoadingThread()
        self.load_thread.progress_update.connect(self.progress_bar.setValue)
        self.load_thread.finished_signal.connect(self.generate_finished)
        self.load_thread.start()

    def generate_finished(self):
        """生成完成"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setDisabled(False)
        self.advice_edit.setText("""【AI种植建议】
基于您的问题和当前农业大数据分析，给出以下建议：

1. 基础管理：根据当前区域的土壤墒情和气候条件，建议每7-10天灌溉一次，每亩施用复合肥20-25公斤。
2. 病虫害防治：近期该区域易发生蚜虫、红蜘蛛等虫害，建议使用生物农药进行防治，避免化学农药残留。
3. 后期管理：根据作物长势预测结果，建议在灌浆期加强田间巡查，及时清除杂草和病株。

（已预留AI大模型接口，后续将接入真实的智能建议生成功能）""")