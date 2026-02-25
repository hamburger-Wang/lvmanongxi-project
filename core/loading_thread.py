# 通用加载线程 - 模拟进度条更新，所有UI模块可复用
from PySide6.QtCore import QThread, Signal

class LoadingThread(QThread):
    progress_update = Signal(int)  # 进度更新信号
    finished_signal = Signal()     # 加载完成信号

    def run(self):
        """线程运行：进度从0到100，每次休眠30ms"""
        for i in range(101):
            self.progress_update.emit(i)
            self.msleep(30)
        self.finished_signal.emit()