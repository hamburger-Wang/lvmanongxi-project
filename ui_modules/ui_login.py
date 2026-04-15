# ==================================================
# ui_login.py - 登录窗口实现
# 作用：实现用户登录界面，支持登录、注册和跳过登录功能
# 功能模块：
# 1. 登录界面UI构建
# 2. 登录逻辑处理
# 3. 注册功能（预留）
# 4. 密码找回（预留）
# 5. 登录信息保存和加载
# 6. 跳过登录功能
# ==================================================
import sqlite3
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QVBoxLayout, QGridLayout, QHBoxLayout  # 布局类归属于QtWidgets
)
from PySide6.QtGui import QFont, QAction
from PySide6.QtCore import Qt, QSettings, QTimer, Signal  # QtCore只保留这些核心类
from config import DB_PATH, SETTINGS_PATH, FONT_MAIN, COLOR_MAIN, COLOR_ORANGE

class LoginWindow(QWidget):
    # 定义登录成功/跳过登录信号，供主窗口接收
    login_success = Signal()  # 登录成功信号
    skip_login = Signal()  # 跳过登录信号

    def __init__(self):
        super().__init__()
        self.settings = QSettings(str(SETTINGS_PATH), QSettings.IniFormat)  # 加载配置文件
        self.init_ui()  # 初始化界面
        self.load_saved_login_info()  # 加载保存的登录信息

    def init_ui(self):
        """初始化登录界面
        
        说明：构建登录窗口的UI布局，包括标题、表单和按钮
        """
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(80, 60, 80, 60)  # 设置布局边距
        main_layout.setSpacing(20)  # 设置布局间距

        # 标题
        title_label = QLabel("农业智能分析系统")
        title_label.setAlignment(Qt.AlignCenter)  # 标题居中
        title_font = QFont(FONT_MAIN, 24, QFont.Bold)  # 标题字体
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 表单布局
        form_layout = QGridLayout()
        form_layout.setSpacing(15)  # 表单控件间距

        # 用户名
        username_label = QLabel("用户名：")
        username_label.setFont(QFont(FONT_MAIN, 12))
        self.username_edit = QLineEdit()
        self.username_edit.setFixedHeight(40)  # 输入框高度
        # 设置输入框样式
        self.username_edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 0 10px;
                font-size: 12px;
                font-family: {FONT_MAIN};
            }}
            QLineEdit:focus {{
                border-color: {COLOR_MAIN};
                outline: none;
            }}
        """)
        form_layout.addWidget(username_label, 0, 0, Qt.AlignRight)  # 用户名标签
        form_layout.addWidget(self.username_edit, 0, 1)  # 用户名输入框

        # 密码
        password_label = QLabel("密  码：")
        password_label.setFont(QFont(FONT_MAIN, 12))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)  # 密码输入模式
        self.password_edit.setFixedHeight(40)  # 输入框高度
        self.password_edit.setStyleSheet(self.username_edit.styleSheet())  # 使用与用户名输入框相同的样式
        form_layout.addWidget(password_label, 1, 0, Qt.AlignRight)  # 密码标签
        form_layout.addWidget(self.password_edit, 1, 1)  # 密码输入框

        # 记住密码/自动登录
        checkbox_layout = QHBoxLayout()
        self.remember_me = QCheckBox("记住密码")  # 记住密码复选框
        self.auto_login = QCheckBox("自动登录")  # 自动登录复选框
        self.remember_me.setFont(QFont(FONT_MAIN, 10))
        self.auto_login.setFont(QFont(FONT_MAIN, 10))
        checkbox_layout.addWidget(self.remember_me)
        checkbox_layout.addWidget(self.auto_login)
        checkbox_layout.setAlignment(Qt.AlignLeft)  # 复选框左对齐
        form_layout.addLayout(checkbox_layout, 2, 1, Qt.AlignLeft)  # 添加到表单布局

        # 密码找回
        forgot_pwd = QLabel('<a href="#">忘记密码？</a>')  # 密码找回链接
        forgot_pwd.setFont(QFont(FONT_MAIN, 10))
        forgot_pwd.setOpenExternalLinks(False)  # 不打开外部链接
        forgot_pwd.linkActivated.connect(self.on_forgot_pwd)  # 绑定密码找回事件
        form_layout.addWidget(forgot_pwd, 2, 1, alignment=Qt.AlignRight)  # 密码找回链接右对齐

        main_layout.addLayout(form_layout)  # 将表单布局添加到主布局

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)  # 按钮间距

        # 登录按钮
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(45)  # 按钮高度
        # 设置登录按钮样式
        self.login_btn.setStyleSheet(f"""
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
        self.login_btn.clicked.connect(self.on_login)  # 绑定登录事件
        btn_layout.addWidget(self.login_btn)

        # 注册按钮
        self.register_btn = QPushButton("注册")
        self.register_btn.setFixedHeight(45)  # 按钮高度
        # 设置注册按钮样式
        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {COLOR_MAIN};
                border: 1px solid {COLOR_MAIN};
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #E8F5E9;
            }}
        """)
        self.register_btn.clicked.connect(self.on_register)  # 绑定注册事件
        btn_layout.addWidget(self.register_btn)

        # 跳过登录按钮
        self.skip_btn = QPushButton("跳过登录")
        self.skip_btn.setFixedHeight(45)  # 按钮高度
        # 设置跳过登录按钮样式
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ORANGE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-family: {FONT_MAIN};
            }}
            QPushButton:hover {{
                background-color: #F57C00;
            }}
        """)
        self.skip_btn.clicked.connect(self.skip_login.emit)  # 绑定跳过登录事件
        btn_layout.addWidget(self.skip_btn)

        main_layout.addLayout(btn_layout)  # 将按钮布局添加到主布局

        # 整体样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #F8F8F8;
                font-family: {FONT_MAIN};
            }}
        """)  # 设置整体背景色和字体

    def load_saved_login_info(self):
        """加载保存的登录信息
        
        说明：从配置文件中加载保存的登录信息，包括用户名、密码、记住密码和自动登录状态
        """
        if self.settings.value("Login/remember_me", False):  # 检查是否记住密码
            self.remember_me.setChecked(True)  # 勾选记住密码复选框
            self.username_edit.setText(self.settings.value("Login/username", ""))  # 设置用户名
            self.password_edit.setText(self.settings.value("Login/password", ""))  # 设置密码
        if self.settings.value("Login/auto_login", False):  # 检查是否自动登录
            self.auto_login.setChecked(True)  # 勾选自动登录复选框

    def save_login_info(self):
        """保存登录信息到配置文件
        
        说明：将登录信息保存到配置文件，包括记住密码、自动登录、用户名和密码
        """
        self.settings.setValue("Login/remember_me", self.remember_me.isChecked())  # 保存记住密码状态
        self.settings.setValue("Login/auto_login", self.auto_login.isChecked())  # 保存自动登录状态
        if self.remember_me.isChecked():  # 如果记住密码
            self.settings.setValue("Login/username", self.username_edit.text())  # 保存用户名
            self.settings.setValue("Login/password", self.password_edit.text())  # 保存密码
        else:  # 如果不记住密码
            self.settings.setValue("Login/username", "")  # 清空用户名
            self.settings.setValue("Login/password", "")  # 清空密码

    def on_login(self):
        """模拟登录逻辑
        
        说明：处理登录按钮点击事件，验证用户名和密码，启动登录过程
        """
        username = self.username_edit.text().strip()  # 获取用户名
        password = self.password_edit.text().strip()  # 获取密码
        if not username or not password:  # 验证用户名和密码是否为空
            QMessageBox.warning(self, "提示", "用户名和密码不能为空！")  # 显示警告消息
            return
        self.login_btn.setDisabled(True)  # 禁用登录按钮
        QTimer.singleShot(1000, self.login_success_handler)  # 1秒后执行登录成功处理

    def login_success_handler(self):
        """登录成功处理
        
        说明：处理登录成功后的逻辑，保存登录信息并发送登录成功信号
        """
        self.save_login_info()  # 保存登录信息
        self.login_btn.setDisabled(False)  # 启用登录按钮
        self.login_success.emit()  # 发送登录成功信号

    def on_register(self):
        """注册功能（待开发）
        
        说明：处理注册按钮点击事件，显示注册功能正在开发中的提示
        """
        QMessageBox.information(self, "提示", "注册功能正在开发中，敬请期待！")  # 显示提示消息

    def on_forgot_pwd(self):
        """密码找回（待开发）
        
        说明：处理密码找回链接点击事件，显示密码找回功能正在开发中的提示
        """
        QMessageBox.information(self, "提示", "密码找回功能正在开发中，敬请期待！")  # 显示提示消息