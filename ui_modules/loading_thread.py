# ==================================================
# loading_thread.py - 通用加载线程
# 作用：模拟加载进度，用于UI中的进度条更新
# 功能模块：
# 1. 模拟进度从0到100的更新
# 2. 发送进度更新信号
# 3. 发送加载完成信号
# ==================================================
from PySide6.QtCore import QThread, Signal

class LoadingThread(QThread):
    progress_update = Signal(int)  # 进度更新信号，用于更新UI中的进度条
    finished_signal = Signal()     # 加载完成信号，用于通知UI加载完成

    def run(self):
        """线程运行：进度从0到100，每次休眠30ms
        
        说明：模拟加载过程，从0%到100%，每30毫秒更新一次进度
        """
        for i in range(101):  # 从0到100
            self.progress_update.emit(i)  # 发送进度更新信号
            self.msleep(30)  # 休眠30毫秒
        self.finished_signal.emit()  # 发送加载完成信号