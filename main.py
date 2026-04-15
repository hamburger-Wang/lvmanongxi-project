# ==================================================
# main.py - 程序入口文件
# 作用：启动应用程序，配置全局设置，显示主窗口
# 特点：无业务逻辑，仅负责应用的初始化和启动
# ==================================================
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui_modules.ui_main import MainWindow
from config import FONT_MAIN

if __name__ == "__main__":
    # 创建应用实例
    # 说明：QApplication是Qt应用的核心，管理应用的事件循环
    app = QApplication(sys.argv)
    
    # 全局配置
    # 说明：设置应用的基本信息
    app.setApplicationName("农业智能分析系统")  # 应用名称
    app.setApplicationVersion("1.0.0")  # 应用版本
    
    # 设置全局字体（统一UI风格）
    # 说明：使用配置文件中定义的字体，确保整个应用的字体一致性
    font = QFont(FONT_MAIN)
    app.setFont(font)
    
    # 创建并显示主窗口
    # 说明：实例化主窗口类并显示
    window = MainWindow()
    window.show()
    
    # 运行应用事件循环
    # 说明：进入Qt的事件循环，处理用户交互和系统事件
    # 当窗口关闭时，exec()会返回退出码
    sys.exit(app.exec())