# ==================================================
# ui_main.py - 主窗口实现
# 作用：创建应用主界面，管理登录窗口和功能模块的切换
# 功能模块：
# 1. 数据库初始化
# 2. 配置文件初始化
# 3. 主界面布局（侧边栏+内容区）
# 4. 菜单栏创建
# 5. 功能模块切换（地图分析、作物预测、种植建议）
# 6. 登录状态管理
# ==================================================
import sqlite3
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QPushButton, 
    QStackedWidget, QMenuBar, QMenu, QMessageBox,
    QHBoxLayout, QVBoxLayout  # 这两个布局类属于QtWidgets，不是QtCore
)
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Qt, QSettings  # 只保留QtCore里的类
from ui_modules.ui_login import LoginWindow
from ui_modules.map_widget import MapWidget
from ui_modules.crop_classification_widget import CropClassificationWidget
from ui_modules.crop_growth_widget import CropGrowthWidget
from ui_modules.advice_widget import FarmingAdviceWidget
from config import DB_PATH, SETTINGS_PATH, FONT_MAIN, COLOR_MAIN

# 初始化数据库
# 说明：创建用户表，用于存储登录用户信息
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 创建users表，包含用户ID、用户名、密码、邮箱、电话和创建时间
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
# 说明：设置应用的默认配置，包括登录相关的设置
def init_settings():
    settings = QSettings(str(SETTINGS_PATH), QSettings.IniFormat)
    # 如果配置文件不存在或没有相关配置项，则设置默认值
    if not settings.contains("Login/remember_me"):
        settings.setValue("Login/remember_me", False)  # 是否记住密码
        settings.setValue("Login/auto_login", False)  # 是否自动登录
        settings.setValue("Login/username", "")  # 用户名
        settings.setValue("Login/password", "")  # 密码

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化数据库和配置
        init_database()  # 初始化用户数据库
        init_settings()  # 初始化应用配置
        # 窗口基础设置
        self.setWindowTitle("农业智能分析系统 - 大创项目")  # 设置窗口标题
        self.setMinimumSize(800, 600)  # 设置最小窗口大小
        self.resize(1280, 720)  # 设置默认窗口大小
        # 创建中心部件（登录+主界面切换）
        # 说明：使用QStackedWidget实现登录窗口和主界面的切换
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        # 初始化登录窗口和主界面
        self.login_window = LoginWindow()  # 创建登录窗口
        self.main_interface = self.create_main_interface()  # 创建主界面
        # 添加到栈控件
        self.central_widget.addWidget(self.login_window)
        self.central_widget.addWidget(self.main_interface)
        # 绑定登录信号
        # 说明：登录成功或跳过登录时切换到主界面
        self.login_window.login_success.connect(self.switch_to_main)
        self.login_window.skip_login.connect(self.switch_to_main)
        # 创建菜单栏
        self.create_menu_bar()  # 创建应用菜单栏

    def create_main_interface(self):
        """创建主界面：侧边栏+功能模块内容区
        
        返回:
            QWidget - 主界面部件
        """
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局边距为0
        main_layout.setSpacing(0)  # 设置布局间距为0

        # 左侧侧边栏
        # 说明：创建固定宽度的侧边栏，包含功能模块切换按钮
        sidebar = QFrame()
        sidebar.setFixedWidth(200)  # 侧边栏宽度
        sidebar.setStyleSheet(f"background-color: {COLOR_MAIN};")  # 侧边栏背景色
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 0)  # 侧边栏布局边距
        sidebar_layout.setSpacing(0)  # 侧边栏布局间距

        # 侧边栏按钮
        # 说明：创建功能模块切换按钮，包括地图分析、作物分类、作物长势预测、种植建议
        self.sidebar_btns = []  # 存储侧边栏按钮的列表
        btn_texts = ["地图分析", "作物分类", "作物长势预测", "种植建议"]  # 按钮文本
        for text in btn_texts:
            btn = QPushButton(text)
            btn.setFixedHeight(50)  # 按钮高度
            # 设置按钮样式
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
            btn.setCheckable(True)  # 设置按钮可选中
            btn.clicked.connect(self.on_sidebar_click)  # 绑定点击事件
            sidebar_layout.addWidget(btn)
            self.sidebar_btns.append(btn)

        sidebar_layout.addStretch()  # 添加伸缩空间
        main_layout.addWidget(sidebar)  # 将侧边栏添加到主布局

        # 右侧内容区
        # 说明：使用QStackedWidget实现功能模块的切换
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #F8F8F8;")  # 内容区背景色
        
        # 添加功能模块
        # 说明：创建并添加四个功能模块
        self.map_widget = MapWidget()  # 地图分析模块
        self.crop_classification_widget = CropClassificationWidget()  # 作物分类模块
        self.crop_growth_widget = CropGrowthWidget()  # 作物长势预测模块
        self.advice_widget = FarmingAdviceWidget()  # 种植建议模块
        
        self.content_stack.addWidget(self.map_widget)
        self.content_stack.addWidget(self.crop_classification_widget)
        self.content_stack.addWidget(self.crop_growth_widget)
        self.content_stack.addWidget(self.advice_widget)
        
        main_layout.addWidget(self.content_stack, stretch=1)  # 将内容区添加到主布局，设置伸缩比例

        # 默认选中第一个按钮
        self.sidebar_btns[0].setChecked(True)  # 默认选中地图分析按钮

        return main_widget

    def create_menu_bar(self):
        """创建菜单栏
        
        说明：创建应用的菜单栏，包含文件、设置和帮助三个菜单
        """
        menubar = self.menuBar()
        # 设置菜单栏样式
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
        # 说明：包含数据导出和退出功能
        file_menu = menubar.addMenu("文件")
        export_action = QAction("数据导出", self)  # 数据导出动作
        export_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "数据导出功能开发中！"))
        exit_action = QAction("退出", self)  # 退出应用动作
        exit_action.triggered.connect(self.close)
        file_menu.addAction(export_action)
        file_menu.addAction(exit_action)

        # 设置菜单
        # 说明：包含清除缓存和修改密码功能
        settings_menu = menubar.addMenu("设置")
        clear_cache_action = QAction("清除缓存", self)  # 清除缓存动作
        clear_cache_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "缓存已清除！"))
        change_pwd_action = QAction("修改密码", self)  # 修改密码动作
        change_pwd_action.triggered.connect(lambda: QMessageBox.information(self, "提示", "修改密码功能开发中！"))
        settings_menu.addAction(clear_cache_action)
        settings_menu.addAction(change_pwd_action)

        # 帮助菜单
        # 说明：包含关于项目功能
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于项目", self)  # 关于项目动作
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def on_sidebar_click(self):
        """侧边栏按钮点击：切换对应功能模块
        
        说明：处理侧边栏按钮点击事件，切换到对应的功能模块
        """
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
        btn_index = self.sidebar_btns.index(current_btn)  # 获取当前按钮的索引
        self.content_stack.setCurrentIndex(btn_index)  # 根据索引切换到对应功能模块

    def switch_to_main(self):
        """登录/跳过登录后切换到主界面
        
        说明：当用户登录成功或跳过登录时，从登录窗口切换到主界面
        """
        self.central_widget.setCurrentWidget(self.main_interface)  # 切换到主界面

    def show_about(self):
        """显示关于项目弹窗
        
        说明：显示应用的关于信息，包括版本、框架和功能说明
        """
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