# ui_login.py 顶部正确的导入（替换原有导入）
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
    login_success = Signal()
    skip_login = Signal()

    def __init__(self):
        super().__init__()
        self.settings = QSettings(str(SETTINGS_PATH), QSettings.IniFormat)
        self.init_ui()
        self.load_saved_login_info()

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(80, 60, 80, 60)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("农业智能分析系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont(FONT_MAIN, 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")
        main_layout.addWidget(title_label)

        # 表单布局
        form_layout = QGridLayout()
        form_layout.setSpacing(15)

        # 用户名
        username_label = QLabel("用户名：")
        username_label.setFont(QFont(FONT_MAIN, 12))
        self.username_edit = QLineEdit()
        self.username_edit.setFixedHeight(40)
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
        form_layout.addWidget(username_label, 0, 0, Qt.AlignRight)
        form_layout.addWidget(self.username_edit, 0, 1)

        # 密码
        password_label = QLabel("密  码：")
        password_label.setFont(QFont(FONT_MAIN, 12))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setFixedHeight(40)
        self.password_edit.setStyleSheet(self.username_edit.styleSheet())
        form_layout.addWidget(password_label, 1, 0, Qt.AlignRight)
        form_layout.addWidget(self.password_edit, 1, 1)

        # 记住密码/自动登录
        checkbox_layout = QHBoxLayout()
        self.remember_me = QCheckBox("记住密码")
        self.auto_login = QCheckBox("自动登录")
        self.remember_me.setFont(QFont(FONT_MAIN, 10))
        self.auto_login.setFont(QFont(FONT_MAIN, 10))
        checkbox_layout.addWidget(self.remember_me)
        checkbox_layout.addWidget(self.auto_login)
        checkbox_layout.setAlignment(Qt.AlignLeft)
        form_layout.addLayout(checkbox_layout, 2, 1, Qt.AlignLeft)

        # 密码找回
        forgot_pwd = QLabel('<a href="#">忘记密码？</a>')
        forgot_pwd.setFont(QFont(FONT_MAIN, 10))
        forgot_pwd.setOpenExternalLinks(False)
        forgot_pwd.linkActivated.connect(self.on_forgot_pwd)
        form_layout.addWidget(forgot_pwd, 2, 1, alignment=Qt.AlignRight)

        main_layout.addLayout(form_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        # 登录按钮
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(45)
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
        self.login_btn.clicked.connect(self.on_login)
        btn_layout.addWidget(self.login_btn)

        # 注册按钮
        self.register_btn = QPushButton("注册")
        self.register_btn.setFixedHeight(45)
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
        self.register_btn.clicked.connect(self.on_register)
        btn_layout.addWidget(self.register_btn)

        # 跳过登录按钮
        self.skip_btn = QPushButton("跳过登录")
        self.skip_btn.setFixedHeight(45)
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
        self.skip_btn.clicked.connect(self.skip_login.emit)
        btn_layout.addWidget(self.skip_btn)

        main_layout.addLayout(btn_layout)

        # 整体样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #F8F8F8;
                font-family: {FONT_MAIN};
            }}
        """)

    def load_saved_login_info(self):
        """加载保存的登录信息"""
        if self.settings.value("Login/remember_me", False):
            self.remember_me.setChecked(True)
            self.username_edit.setText(self.settings.value("Login/username", ""))
            self.password_edit.setText(self.settings.value("Login/password", ""))
        if self.settings.value("Login/auto_login", False):
            self.auto_login.setChecked(True)

    def save_login_info(self):
        """保存登录信息到配置文件"""
        self.settings.setValue("Login/remember_me", self.remember_me.isChecked())
        self.settings.setValue("Login/auto_login", self.auto_login.isChecked())
        if self.remember_me.isChecked():
            self.settings.setValue("Login/username", self.username_edit.text())
            self.settings.setValue("Login/password", self.password_edit.text())
        else:
            self.settings.setValue("Login/username", "")
            self.settings.setValue("Login/password", "")

    def on_login(self):
        """模拟登录逻辑"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "提示", "用户名和密码不能为空！")
            return
        self.login_btn.setDisabled(True)
        QTimer.singleShot(1000, self.login_success_handler)

    def login_success_handler(self):
        """登录成功处理"""
        self.save_login_info()
        self.login_btn.setDisabled(False)
        self.login_success.emit()

    def on_register(self):
        """注册功能（待开发）"""
        QMessageBox.information(self, "提示", "注册功能正在开发中，敬请期待！")

    def on_forgot_pwd(self):
        """密码找回（待开发）"""
        QMessageBox.information(self, "提示", "密码找回功能正在开发中，敬请期待！")