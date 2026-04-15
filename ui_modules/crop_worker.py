# ==================================================
# crop_worker.py - 作物模型运行线程
# 作用：异步调用crop_model.py执行模型训练或预测，避免UI卡顿
# 功能模块：
# 1. 异步执行模型脚本
# 2. 实时读取和处理脚本输出
# 3. 解析模型执行结果
# 4. 发送日志、进度和结果信号
# 5. 支持任务停止功能
# ==================================================
import subprocess
import ast
from PySide6.QtCore import QThread, Signal

class CropWorker(QThread):
    # 定义信号：日志、结果、错误、进度
    log_signal = Signal(str)  # 日志信号，用于更新UI中的日志显示
    result_signal = Signal(dict)  # 结果信号，用于传递模型执行结果
    error_signal = Signal(str)  # 错误信号，用于传递执行过程中的错误信息
    progress_signal = Signal(int)  # 进度信号，用于更新UI中的进度条

    def __init__(self, crop_env_python_path, crop_script_path, mode, model_choice, data_path, 
                 out_loss, epochs, model_path, img_path):
        """初始化CropWorker线程
        
        参数:
            crop_env_python_path: str - Python解释器路径
            crop_script_path: str - 作物模型脚本路径
            mode: str - 运行模式（train/predict）
            model_choice: str - 模型选择（第一模型/第二模型/第三模型）
            data_path: str - 数据文件路径
            out_loss: str - 损失函数类型
            epochs: int - 训练轮数
            model_path: str - 模型保存/加载路径
            img_path: str - 结果图保存路径
        """
        super().__init__()
        # 初始化参数
        self.crop_env_python_path = crop_env_python_path  # Python解释器路径
        self.crop_script_path = crop_script_path  # 作物模型脚本路径
        self.mode = mode  # 运行模式（train/predict）
        self.model_choice = model_choice  # 模型选择
        self.data_path = data_path  # 数据文件路径
        self.out_loss = out_loss  # 损失函数类型
        self.epochs = epochs  # 训练轮数
        self.model_path = model_path  # 模型保存/加载路径
        self.img_path = img_path  # 结果图保存路径
        self.is_running = True  # 线程运行状态

    def stop(self):
        """停止线程
        
        说明：设置is_running为False，终止线程执行
        """
        self.is_running = False

    def run(self):
        """线程核心：调用模型脚本、实时读取输出、解析结果
        
        说明：执行模型脚本，实时读取输出日志，解析执行结果，发送相应信号
        """
        try:
            # 构造调用命令
            cmd = [
                self.crop_env_python_path,
                self.crop_script_path,
                "--mode", self.mode,
                "--model_choice", self.model_choice,
                "--data_path", self.data_path,
                "--out_loss", self.out_loss,
                "--epochs", str(self.epochs),
                "--model_path", self.model_path,
                "--img_path", self.img_path
            ]

            self.log_signal.emit(f"执行命令：{' '.join(cmd)}")  # 发送命令执行日志
            
            # 启动子进程（合并stdout/stderr，实时读取）
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并标准输出和标准错误
                text=True,  # 以文本模式读取
                bufsize=1,  # 行缓冲
                universal_newlines=True,  # 使用通用换行符
                encoding="utf-8",  # 编码
                errors="ignore"  # 忽略编码错误
            )

            # 实时读取输出+进度更新
            result_data = ""  # 存储结果数据
            current_progress = 0  # 当前进度
            while self.is_running and process.poll() is None:  # 线程运行且进程未结束
                line = process.stdout.readline()  # 读取一行输出
                if line:
                    line_stripped = line.strip()  # 去除首尾空白
                    self.log_signal.emit(line_stripped)  # 发送日志信号
                    # 捕获结果标记（===RESULT===...===END===）
                    if "===RESULT===" in line_stripped and "===END===" in line_stripped:
                        result_data = line_stripped.split("===RESULT===")[1].split("===END===")[0].strip()
                # 进度递增（限制99，完成后拉满100）
                current_progress = min(current_progress + 1, 99)
                self.progress_signal.emit(current_progress)  # 发送进度信号

            # 结果处理
            if process.poll() == 0 and self.is_running:  # 进程正常结束且线程未被停止
                self.progress_signal.emit(100)  # 发送100%进度
                result = {}  # 结果字典
                if result_data:  # 如果有结果数据
                    try:
                        result = ast.literal_eval(result_data)  # 安全解析字典
                    except Exception as e:
                        self.log_signal.emit(f"结果解析失败：{str(e)} | 原始数据：{result_data}")
                        result = {"status": "成功", "msg": f"解析失败：{str(e)}", "raw": result_data}
                else:  # 如果没有结果数据
                    result = {"status": "成功", "kappa": 0.0, "model_path": self.model_path, "img_path": self.img_path}
                self.result_signal.emit(result)  # 发送结果信号
            elif not self.is_running:  # 线程被停止
                process.terminate()  # 终止进程
                self.log_signal.emit("任务已手动停止")
                self.error_signal.emit("任务已停止")
            else:  # 进程异常结束
                exit_code = process.poll()
                self.error_signal.emit(f"脚本运行失败，退出码：{exit_code}")

        except Exception as e:  # 捕获异常
            self.error_signal.emit(f"运行异常：{str(e)}")
