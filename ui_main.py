# ui_main.py 顶部正确的导入（替换原来的导入）
import sqlite3
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QPushButton, 
    QStackedWidget, QMenuBar, QMenu, QMessageBox,
    QHBoxLayout, QVBoxLayout  # 这两个布局类属于QtWidgets，不是QtCore
)
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Qt, QSettings  # 只保留QtCore里的类
from ui_login import LoginWindow
from ui_modules.map_widget import MapWidget
from ui_modules.crop_widget import CropPredictionWidget
from ui_modules.advice_widget import FarmingAdviceWidget
from config import DB_PATH, SETTINGS_PATH, FONT_MAIN, COLOR_MAIN

# 初始化数据库
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# 初始化配置文件
def init_settings():
    settings = QSettings(str(SETTINGS_PATH), QSettings.IniFormat)
    if not settings.contains("Login/remember_me"):
        settings.setValue("Login/remember_me", False)
        settings.setValue("Login/auto_login", False)
        settings.setValue("Login/username", "")
        settings.setValue("Login/password", "")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化数据库和配置
        init_database()
        init_settings()
        # 窗口基础设置
        self.setWindowTitle("农业智能分析系统 - 大创项目")
        self.setMinimumSize(800, 600)
        self.resize(1280, 720)
        # 创建中心部件（登录+主界面切换）
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        # 初始化登录窗口和主界面
        self.login_window = LoginWindow()
        self.main_interface = self.create_main_interface()
        # 添加到栈控件
        self.central_widget.addWidget(self.login_window)
        self.central_widget.addWidget(self.main_interface)
        # 绑定登录信号
        self.login_window.login_success.connect(self.switch_to_main)
        self.login_window.skip_login.connect(self.switch_to_main)
        # 创建菜单栏
        self.create_menu_bar()

    def create_main_interface(self):
        """创建主界面：侧边栏+功能模块内容区"""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧侧边栏
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background-color: {COLOR_MAIN};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 0)
        sidebar_layout.setSpacing(0)

        # 侧边栏按钮
        self.sidebar_btns = []
        btn_texts = ["地图分析", "作物预测", "种植建议"]
        for text in btn_texts:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_MAIN};
                    color: white;
                    border: none;
                    text-align: left;
                    padding-left: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    font-family: {FONT_MAIN};
                }}
                QPushButton:hover {{ background-color: #1B5E20; }}
                QPushButton:checked {{
                    background-color: #FFFFFF;
                    color: {COLOR_MAIN};
                    border-right: 3px solid {COLOR_MAIN};
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(self.on_sidebar_click)
            sidebar_layout.addWidget(btn)
            self.sidebar_btns.append(btn)

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # 右侧内容区
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #F8F8F8;")
        
        # 添加功能模块
        self.map_widget = MapWidget()
        self.crop_widget = CropPredictionWidget()
        self.advice_widget = FarmingAdviceWidget()
        
        self.content_stack.addWidget(self.map_widget)
        self.content_stack.addWidget(self.crop_widget)
        self.content_stack.addWidget(self.advice_widget)
        
        main_layout.addWidget(self.content_stack, stretch=1)

        # 默认选中第一个按钮
        self.sidebar_btns[0].setChecked(True)

        return main_widget

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: #F8F8F8;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QMenuBar::item {{
                padding: 5px 10px;
            }}
            QMenuBar::item:selected {{
                background-color: #E8F5E9;
                color: {COLOR_MAIN};
            }}
            QMenu {{
                background-color: white;
                border: 1px solid #EEEEEE;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QMenu::item:selected {{
                background-color: #E8F5E9;
                color: {COLOR_MAIN};
            }}
        """)

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        export_action = QAction("数据导出", self)
        export_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "数据导出功能开发中！"))
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(export_action)
        file_menu.addAction(exit_action)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        clear_cache_action = QAction("清除缓存", self)
        clear_cache_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "缓存已清除！"))
        change_pwd_action = QAction("修改密码", self)
        change_pwd_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "修改密码功能开发中！"))
        settings_menu.addAction(clear_cache_action)
        settings_menu.addAction(change_pwd_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于项目", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def on_sidebar_click(self):
     """侧边栏按钮点击：切换对应功能模块"""
    # 获取当前点击的按钮（核心修复：用sender()精准定位）
     current_btn = self.sender()
     if not current_btn:
         return
    
    # 1. 取消所有按钮的选中状态
     for btn in self.sidebar_btns:
         btn.setChecked(False)
    
    # 2. 只选中当前点击的按钮
     current_btn.setChecked(True)
    
    # 3. 根据按钮索引切换对应页面（100%精准）
     btn_index = self.sidebar_btns.index(current_btn)
     self.content_stack.setCurrentIndex(btn_index)

    def switch_to_main(self):
        """登录/跳过登录后切换到主界面"""
        self.central_widget.setCurrentWidget(self.main_interface)

    def show_about(self):
        """显示关于项目弹窗"""
        QMessageBox.about(self, "关于项目", f"""
农业智能分析系统 - 大创项目
版本：1.0.0
开发框架：PySide6
字体配置：{FONT_MAIN}
主色配置：{COLOR_MAIN}
功能说明：
1. 地图分析：对接卫星/无人机数据，支持区域选择
2. 作物预测：作物分类与长势预测（集成多格式数据导入）
3. 种植建议：AI驱动的农业种植建议（预留大模型接口）
""")