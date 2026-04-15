# ==================================================
# map_widget.py - 地图分析模块
# 作用：实现地图分析界面，支持卫星/无人机数据的可视化和区域选择
# 功能模块：
# 1. 地图控制按钮（放大、缩小、切换图层、刷新数据）
# 2. 地图显示区域
# 3. 区域选择信息显示
# 4. 加载进度显示
# 5. 模拟地图数据加载
# ==================================================
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QProgressBar,
    QVBoxLayout, QHBoxLayout, QSizePolicy  # 布局/尺寸策略归属于QtWidgets
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt  # QtCore只保留Qt枚举（如Qt.AlignCenter）
from ui_modules.loading_thread import LoadingThread
from config import FONT_MAIN, COLOR_MAIN

class MapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化地图分析界面
        
        说明：构建地图分析模块的UI布局，包括标题、控制按钮、地图显示区域、信息显示和进度条
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置布局边距

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("农业地图分析")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        title_layout.addWidget(title_label)
        title_layout.addStretch()  # 右侧伸缩空间
        main_layout.addLayout(title_layout)

        # 地图控件栏
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)  # 按钮间距
        btns = ["放大", "缩小", "切换图层", "刷新数据"]  # 控制按钮文本
        for btn_text in btns:
            btn = QPushButton(btn_text)
            btn.setFixedSize(80, 35)  # 按钮大小
            # 设置按钮样式
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
        control_layout.addStretch()  # 右侧伸缩空间
        main_layout.addLayout(control_layout)

        # 地图显示区域
        map_frame = QFrame()
        # 设置地图框样式
        map_frame.setStyleSheet("""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
            }}
        """)
        map_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 地图区域可伸缩
        map_layout = QVBoxLayout(map_frame)
        self.map_tip = QLabel("地图加载中...\n（预留卫星/无人机数据接口）")  # 地图提示信息
        self.map_tip.setAlignment(Qt.AlignCenter)  # 提示信息居中
        self.map_tip.setFont(QFont(FONT_MAIN, 14))  # 提示信息字体
        self.map_tip.setStyleSheet("color: #757575;")  # 提示信息颜色
        map_layout.addWidget(self.map_tip)
        map_frame.setMinimumHeight(400)  # 地图区域最小高度
        main_layout.addWidget(map_frame, stretch=7)  # 添加到主布局，设置伸缩比例

        # 区域选择信息
        info_layout = QHBoxLayout()
        info_label = QLabel("当前选择区域：未选择")  # 区域选择信息
        info_label.setFont(QFont(FONT_MAIN, 12))  # 信息字体
        info_layout.addWidget(info_label)
        info_layout.addStretch()  # 右侧伸缩空间
        main_layout.addLayout(info_layout)

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

        # 绑定刷新按钮事件
        control_layout.itemAt(3).widget().clicked.connect(self.simulate_loading)  # 绑定刷新数据按钮

    def simulate_loading(self):
        """模拟地图加载
        
        说明：模拟卫星/无人机数据加载过程，显示进度条和加载提示
        """
        self.progress_bar.setVisible(True)  # 显示进度条
        self.map_tip.setText("正在加载卫星/无人机数据...")  # 更新提示信息
        self.load_thread = LoadingThread()  # 创建加载线程
        self.load_thread.progress_update.connect(self.progress_bar.setValue)  # 绑定进度更新信号
        self.load_thread.finished_signal.connect(self.load_finished)  # 绑定加载完成信号
        self.load_thread.start()  # 启动线程

    def load_finished(self):
        """加载完成
        
        说明：处理地图加载完成后的逻辑，隐藏进度条并更新提示信息
        """
        self.progress_bar.setVisible(False)  # 隐藏进度条
        self.map_tip.setText("地图加载完成\n（可选择区域，后续对接API）")  # 更新提示信息