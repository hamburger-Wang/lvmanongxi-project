# map_widget.py 顶部正确的导入（替换原有导入）
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QProgressBar,
    QVBoxLayout, QHBoxLayout, QSizePolicy  # 布局/尺寸策略归属于QtWidgets
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt  # QtCore只保留Qt枚举（如Qt.AlignCenter）
from core.loading_thread import LoadingThread
from config import FONT_MAIN, COLOR_MAIN

class MapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("农业地图分析")
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 地图控件栏
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        btns = ["放大", "缩小", "切换图层", "刷新数据"]
        for btn_text in btns:
            btn = QPushButton(btn_text)
            btn.setFixedSize(80, 35)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #E8F5E9;
                    color: {COLOR_MAIN};
                    border: 1px solid {COLOR_MAIN};
                    border-radius: 6px;
                    font-size: 12px;
                    font-family: {FONT_MAIN};
                }}
                QPushButton:hover {{
                    background-color: #C8E6C9;
                }}
            """)
            control_layout.addWidget(btn)
        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # 地图显示区域
        map_frame = QFrame()
        map_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
            }
        """)
        map_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        map_layout = QVBoxLayout(map_frame)
        self.map_tip = QLabel("地图加载中...\n（预留卫星/无人机数据接口）")
        self.map_tip.setAlignment(Qt.AlignCenter)
        self.map_tip.setFont(QFont(FONT_MAIN, 14))
        self.map_tip.setStyleSheet("color: #757575;")
        map_layout.addWidget(self.map_tip)
        map_frame.setMinimumHeight(400)
        main_layout.addWidget(map_frame, stretch=7)

        # 区域选择信息
        info_layout = QHBoxLayout()
        info_label = QLabel("当前选择区域：未选择")
        info_label.setFont(QFont(FONT_MAIN, 12))
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        main_layout.addLayout(info_layout)

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

        # 绑定刷新按钮事件
        control_layout.itemAt(3).widget().clicked.connect(self.simulate_loading)

    def simulate_loading(self):
        """模拟地图加载"""
        self.progress_bar.setVisible(True)
        self.map_tip.setText("正在加载卫星/无人机数据...")
        self.load_thread = LoadingThread()
        self.load_thread.progress_update.connect(self.progress_bar.setValue)
        self.load_thread.finished_signal.connect(self.load_finished)
        self.load_thread.start()

    def load_finished(self):
        """加载完成"""
        self.progress_bar.setVisible(False)
        self.map_tip.setText("地图加载完成\n（可选择区域，后续对接API）")