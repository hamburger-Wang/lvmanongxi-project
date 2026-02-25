# 程序入口 - 仅负责启动应用，无业务逻辑
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui_main import MainWindow
from config import FONT_MAIN

if __name__ == "__main__":
    # 创建应用实例
    app = QApplication(sys.argv)
    
    # 全局配置
    app.setApplicationName("农业智能分析系统")
    app.setApplicationVersion("1.0.0")
    
    # 设置全局字体（统一UI风格）
    font = QFont(FONT_MAIN)
    app.setFont(font)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用事件循环
    sys.exit(app.exec())