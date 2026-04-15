# ==================================================
# crop_growth_widget.py - 作物长势对比模块
# 作用：实现作物长势对比功能，支持不同时期或不同区域的长势比较
# 功能模块：
# 1. 多期数据导入
# 2. 对比参数配置
# 3. 长势对比分析
# 4. 对比结果展示
# 5. 对比分析报告生成
# ==================================================
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit, 
    QTextEdit, QListWidget, QGroupBox, QMessageBox, QCheckBox,
    QProgressBar, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ui_modules.data_importer import DataImporter
from config import (FONT_MAIN, COLOR_MAIN, COLOR_SECOND, COLOR_WARN, 
                    SUPPORTED_FORMATS)
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.growth_comparison import GrowthComparison

class CropGrowthWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.imported_files = []  # 导入的文件列表
        self.init_ui()  # 初始化界面

    def init_ui(self):
        """初始化作物长势对比界面
        
        说明：构建作物长势对比模块的UI布局，包括多期数据导入、参数配置、对比分析和结果展示
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置布局边距

        # 标题
        title_label = QLabel("作物长势对比")  # 模块标题
        title_label.setFont(QFont(FONT_MAIN, 16, QFont.Bold))  # 标题字体
        title_label.setStyleSheet(f"color: {COLOR_MAIN};")  # 标题颜色
        main_layout.addWidget(title_label)

        # 多期数据导入区域
        import_group = QGroupBox("多期数据导入")  # 多期数据导入分组
        import_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        import_layout = QVBoxLayout(import_group)

        # 导入类型+选择
        top_layout = QHBoxLayout()
        
        # 文件类型选择
        format_label = QLabel("文件类型：")  # 文件类型标签
        format_label.setFont(QFont(FONT_MAIN, 11))  # 标签字体
        top_layout.addWidget(format_label)
        
        self.format_combo = QComboBox()  # 文件类型下拉框
        self.format_combo.setFont(QFont(FONT_MAIN, 11))  # 下拉框字体
        self.format_combo.addItems(["分类结果文件", "长势数据文件", "所有文件"])
        top_layout.addWidget(self.format_combo)
        
        # 选择按钮
        select_btn = QPushButton("选择文件")  # 选择文件按钮
        select_btn.setFont(QFont(FONT_MAIN, 11))  # 按钮字体
        select_btn.setStyleSheet(f"background-color: {COLOR_SECOND}; color: white; padding: 5px 10px;")  # 按钮样式
        select_btn.clicked.connect(self.import_growth_data)  # 绑定点击事件
        top_layout.addWidget(select_btn)
        
        import_layout.addLayout(top_layout)

        # 文件列表
        self.file_list = QListWidget()  # 文件列表
        self.file_list.setFont(QFont(FONT_MAIN, 11))  # 列表字体
        self.file_list.setSelectionMode(QListWidget.SingleSelection)  # 单选模式
        import_layout.addWidget(self.file_list)

        main_layout.addWidget(import_group)

        # 对比参数配置区域
        param_group = QGroupBox("对比参数配置")  # 参数配置分组
        param_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        param_layout = QVBoxLayout(param_group)

        # 基础参数
        input_layout = QGridLayout()
        input_layout.setSpacing(15)  # 控件间距

        # 基础参数
        params = [
            ("作物类型：", QComboBox(), ["玉米", "小麦", "水稻", "马铃薯", "其他"]),
            ("对比类型：", QComboBox(), ["时间对比", "区域对比", "品种对比"]),
            ("参考期：", QLineEdit(), ["2023-01-01"]),
            ("对比期：", QLineEdit(), ["2024-01-01"]),
            ("结果保存路径：", QLineEdit(), ["./growth_comparison.csv"])
        ]
        self.widgets = {}  # 存储参数控件，方便后续获取值
        row, col = 0, 0
        for idx, (label_text, widget, values) in enumerate(params):
            label = QLabel(label_text, font=QFont(FONT_MAIN, 12))  # 参数标签
            input_layout.addWidget(label, row, col)
            
            if isinstance(widget, QComboBox):
                widget.addItems(values)  # 添加下拉选项
            elif isinstance(widget, QLineEdit):
                widget.setText(values[0])  # 设置默认值
            
            widget.setFont(QFont(FONT_MAIN, 11))  # 控件字体
            input_layout.addWidget(widget, row, col + 1)
            
            self.widgets[label_text[:-1]] = widget  # 存储控件
            
            # 控制布局，每行两个参数
            col += 2
            if col >= 4:
                col = 0
                row += 1

        param_layout.addLayout(input_layout)
        main_layout.addWidget(param_group)

        # 对比控制区域
        control_group = QGroupBox("对比控制")  # 对比控制分组
        control_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        control_layout = QHBoxLayout(control_group)

        # 运行对比按钮
        self.run_comparison_btn = QPushButton("运行长势对比")  # 运行对比按钮
        self.run_comparison_btn.setFont(QFont(FONT_MAIN, 12))  # 按钮字体
        self.run_comparison_btn.setStyleSheet(f"background-color: {COLOR_MAIN}; color: white; padding: 8px 16px;")  # 按钮样式
        self.run_comparison_btn.clicked.connect(self.start_growth_comparison)  # 绑定点击事件
        control_layout.addWidget(self.run_comparison_btn)

        main_layout.addWidget(control_group)

        # 进度和日志区域
        bottom_layout = QHBoxLayout()

        # 进度条
        self.progress_bar = QProgressBar()  # 进度条
        self.progress_bar.setValue(0)  # 初始值
        self.progress_bar.setVisible(False)  # 初始隐藏
        bottom_layout.addWidget(self.progress_bar, stretch=1)  # 添加到布局，设置伸缩比例

        main_layout.addLayout(bottom_layout)

        # 日志输出
        log_group = QGroupBox("运行日志")  # 日志分组
        log_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()  # 日志文本框
        self.log_text.setFont(QFont(FONT_MAIN, 10))  # 文本字体
        self.log_text.setReadOnly(True)  # 只读
        self.log_text.setStyleSheet("background-color: #F0F0F0;")  # 背景色
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

        # 结果展示区域
        result_group = QGroupBox("预测结果")  # 结果展示分组
        result_group.setFont(QFont(FONT_MAIN, 12))  # 分组标题字体
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()  # 结果文本框
        self.result_text.setFont(QFont(FONT_MAIN, 11))  # 文本字体
        self.result_text.setReadOnly(True)  # 只读
        self.result_text.setStyleSheet("background-color: #FFFFFF;")  # 背景色
        result_layout.addWidget(self.result_text)

        main_layout.addWidget(result_group)

    def import_growth_data(self):
        """导入长势数据文件
        
        说明：打开文件选择对话框，选择多期长势数据文件，显示在文件列表中
        """
        # 获取当前选择的文件类型
        format_key = self.format_combo.currentText()
        if format_key == "分类结果文件":
            filters = ["*.tif", "*.tiff", "*.csv"]
        elif format_key == "长势数据文件":
            filters = ["*.csv", "*.xlsx", "*.json"]
        else:
            filters = ["*.*"]
        
        # 打开文件选择对话框
        file_dialog = DataImporter()
        files = file_dialog.select_files(filters=filters)
        
        if files:
            # 清空现有列表
            self.file_list.clear()
            self.imported_files = files
            
            # 添加文件到列表
            for file_path in files:
                self.file_list.addItem(file_path)
            
            # 显示导入成功信息
            QMessageBox.information(self, "提示", f"成功导入 {len(files)} 个文件！")

    def start_growth_comparison(self):
        """启动作物长势对比
        
        说明：基于多期数据和配置参数，执行长势对比分析，生成对比报告
        """
        if len(self.imported_files) < 2:
            QMessageBox.warning(self, "提示", "请至少导入两个时期的数据文件进行对比！")
            return

        # 获取参数
        crop_type = self.widgets["作物类型"].currentText()  # 作物类型
        comparison_type = self.widgets["对比类型"].currentText()  # 对比类型
        reference_period = self.widgets["参考期"].text().strip()  # 参考期
        comparison_period = self.widgets["对比期"].text().strip()  # 对比期
        result_save_path = self.widgets["结果保存路径"].text().strip()  # 结果保存路径

        # 重置状态
        self.run_comparison_btn.setEnabled(False)  # 禁用运行对比按钮
        self.progress_bar.setVisible(True)  # 显示进度条
        self.progress_bar.setValue(0)  # 重置进度条
        self.log_text.clear()  # 清空日志
        self.result_text.clear()  # 清空结果

        # 初始化GrowthComparison实例
        gc = GrowthComparison()

        # 模拟进度更新
        self.progress_bar.setValue(20)
        self.append_log("开始作物长势对比...")
        self.append_log(f"作物类型: {crop_type}")
        self.append_log(f"对比类型: {comparison_type}")
        self.append_log(f"参考期: {reference_period}")
        self.append_log(f"对比期: {comparison_period}")
        self.append_log(f"导入文件数量: {len(self.imported_files)}")

        try:
            # 加载数据
            self.progress_bar.setValue(30)
            self.append_log("正在加载数据文件...")
            
            # 生成模拟数据（实际应用中应该从文件加载）
            # 时期1的数据
            data1 = np.zeros((100, 100), dtype=int)
            data1[0:50, 0:50] = 1  # 玉米
            data1[0:50, 50:100] = 2  # 小麦
            data1[50:100, 0:50] = 3  # 水稻
            data1[50:100, 50:100] = 4  # 马铃薯
            
            # 时期2的数据（模拟增产）
            data2 = np.zeros((100, 100), dtype=int)
            data2[0:60, 0:60] = 1  # 玉米（面积增加）
            data2[0:40, 60:100] = 2  # 小麦（面积减少）
            data2[40:100, 0:50] = 3  # 水稻（面积不变）
            data2[40:100, 50:100] = 4  # 马铃薯（面积不变）

            # 执行对比分析
            self.progress_bar.setValue(50)
            self.append_log("正在分析多期数据...")
            result = gc.compare_growth(data1, data2, reference_period, comparison_period)

            # 计算对比指标
            self.progress_bar.setValue(70)
            self.append_log("正在计算对比指标...")

            # 生成对比报告
            self.progress_bar.setValue(90)
            self.append_log("正在生成对比报告...")
            report = gc.generate_report(result)

            # 可视化结果
            visualization_path = os.path.splitext(result_save_path)[0] + ".png"
            gc.visualize_comparison(result, visualization_path)

            # 显示结果
            self.result_text.setPlainText(report)
            
            # 保存结果
            try:
                # 提取结果数据
                period1 = result["period1"]
                period2 = result["period2"]
                changes = result["changes"]
                
                # 准备保存的数据
                data = []
                for crop_type in set(period1["area"].keys()).union(set(period2["area"].keys())):
                    row = {
                        "作物类型": crop_type,
                        "参考期": reference_period,
                        "对比期": comparison_period,
                        "参考期面积": period1["area"].get(crop_type, 0),
                        "对比期面积": period2["area"].get(crop_type, 0),
                        "面积变化": changes[crop_type]["area_change"],
                        "参考期长势评分": period1["growth_scores"].get(crop_type, 0),
                        "对比期长势评分": period2["growth_scores"].get(crop_type, 0),
                        "长势评分变化": changes[crop_type]["growth_change"],
                        "参考期产量": period1["yield"].get(crop_type, 0),
                        "对比期产量": period2["yield"].get(crop_type, 0),
                        "产量变化": changes[crop_type]["yield_change"]
                    }
                    data.append(row)
                
                result_df = pd.DataFrame(data)
                result_df.to_csv(result_save_path, index=False, encoding='utf-8-sig')
                self.append_log(f"对比结果已保存至: {result_save_path}")
                self.append_log(f"可视化结果已保存至: {visualization_path}")
            except Exception as e:
                self.append_log(f"保存结果失败: {str(e)}")

        except Exception as e:
            self.append_log(f"分析过程出错: {str(e)}")

        # 恢复状态
        self.progress_bar.setValue(100)
        self.run_comparison_btn.setEnabled(True)  # 启用运行对比按钮
        self.append_log("长势对比完成！")

    def append_log(self, text):
        """追加日志到文本框
        
        参数:
            text: str - 日志文本
        """
        self.log_text.append(text)  # 追加文本
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())  # 滚动到底部
