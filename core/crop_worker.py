# 作物模型运行线程 - 独立异步调用crop_model.py，无UI依赖
import subprocess
import ast
from PySide6.QtCore import QThread, Signal

class CropWorker(QThread):
    # 定义信号：日志、结果、错误、进度
    log_signal = Signal(str)
    result_signal = Signal(dict)
    error_signal = Signal(str)
    progress_signal = Signal(int)

    def __init__(self, crop_env_python_path, crop_script_path, mode, data_path, 
                 out_loss, epochs, model_path, img_path):
        super().__init__()
        # 初始化参数
        self.crop_env_python_path = crop_env_python_path
        self.crop_script_path = crop_script_path
        self.mode = mode
        self.data_path = data_path
        self.out_loss = out_loss
        self.epochs = epochs
        self.model_path = model_path
        self.img_path = img_path
        self.is_running = True

    def stop(self):
        """停止线程"""
        self.is_running = False

    def run(self):
        """线程核心：调用模型脚本、实时读取输出、解析结果"""
        try:
            # 构造调用命令
            cmd = [
                self.crop_env_python_path,
                self.crop_script_path,
                "--mode", self.mode,
                "--data_path", self.data_path,
                "--out_loss", self.out_loss,
                "--epochs", str(self.epochs),
                "--model_path", self.model_path,
                "--img_path", self.img_path
            ]

            self.log_signal.emit(f"执行命令：{' '.join(cmd)}")
            
            # 启动子进程（合并stdout/stderr，实时读取）
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore"
            )

            # 实时读取输出+进度更新
            result_data = ""
            current_progress = 0
            while self.is_running and process.poll() is None:
                line = process.stdout.readline()
                if line:
                    line_stripped = line.strip()
                    self.log_signal.emit(line_stripped)
                    # 捕获结果标记（===RESULT===...===END===）
                    if "===RESULT===" in line_stripped and "===END===" in line_stripped:
                        result_data = line_stripped.split("===RESULT===")[1].split("===END===")[0].strip()
                # 进度递增（限制99，完成后拉满100）
                current_progress = min(current_progress + 1, 99)
                self.progress_signal.emit(current_progress)

            # 结果处理
            if process.poll() == 0 and self.is_running:
                self.progress_signal.emit(100)
                result = {}
                if result_data:
                    try:
                        result = ast.literal_eval(result_data)  # 安全解析字典
                    except Exception as e:
                        self.log_signal.emit(f"结果解析失败：{str(e)} | 原始数据：{result_data}")
                        result = {"status": "成功", "msg": f"解析失败：{str(e)}", "raw": result_data}
                else:
                    result = {"status": "成功", "kappa": 0.0, "model_path": self.model_path, "img_path": self.img_path}
                self.result_signal.emit(result)
            elif not self.is_running:
                process.terminate()
                self.log_signal.emit("任务已手动停止")
                self.error_signal.emit("任务已停止")
            else:
                exit_code = process.poll()
                self.error_signal.emit(f"脚本运行失败，退出码：{exit_code}")

        except Exception as e:
            self.error_signal.emit(f"运行异常：{str(e)}")
