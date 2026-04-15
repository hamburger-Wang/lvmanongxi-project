# ==================================================
# growth_comparison.py - 作物长势对比核心模块
# 作用：基于分类区域图的面积对比，实现作物长势评估和产量预测
# 功能模块：
# 1. 分类区域图解析（支持不同格式的分类结果）
# 2. 面积计算和对比分析
# 3. 长势评估算法
# 4. 产量预测模型
# 5. 对比结果可视化
# ==================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import rasterio
from rasterio.plot import show
from typing import Dict, List, Tuple, Optional

class GrowthComparison:
    """作物长势对比类
    
    基于分类区域图的面积对比，实现作物长势评估和产量预测
    """
    
    def __init__(self):
        """初始化GrowthComparison类
        
        初始化必要的参数和配置
        """
        # 作物类型映射（根据分类结果的数值）
        self.crop_type_mapping = {
            1: "玉米",
            2: "小麦",
            3: "水稻",
            4: "马铃薯",
            5: "其他"
        }
        
        # 作物产量系数（单位：kg/亩）
        self.yield_coefficients = {
            "玉米": 500,
            "小麦": 400,
            "水稻": 600,
            "马铃薯": 3000,
            "其他": 300
        }
        
        # 长势等级划分
        self.growth_levels = {
            "优秀": (90, 100),
            "良好": (75, 90),
            "一般": (60, 75),
            "较差": (0, 60)
        }
    
    def load_classification_data(self, file_path: str) -> Tuple[np.ndarray, dict]:
        """加载分类结果数据
        
        参数:
            file_path: str - 分类结果文件路径
            
        返回:
            Tuple[np.ndarray, dict] - (分类数据数组, 元数据)
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in [".tif", ".tiff"]:
            # 读取TIFF格式的分类结果
            with rasterio.open(file_path) as src:
                data = src.read(1)  # 读取第一个波段
                meta = src.meta
            return data, meta
        elif file_ext == ".csv":
            # 读取CSV格式的分类结果
            df = pd.read_csv(file_path)
            # 假设CSV文件包含x, y, class三列
            if 'class' in df.columns:
                # 构建二维数组
                max_x = int(df['x'].max()) + 1
                max_y = int(df['y'].max()) + 1
                data = np.zeros((max_y, max_x), dtype=int)
                for _, row in df.iterrows():
                    data[int(row['y']), int(row['x'])] = int(row['class'])
                meta = {"crs": None, "transform": None}
                return data, meta
            else:
                raise ValueError("CSV文件必须包含'class'列")
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
    
    def calculate_area(self, classification_data: np.ndarray) -> Dict[str, float]:
        """计算各作物类型的面积
        
        参数:
            classification_data: np.ndarray - 分类结果数据
            
        返回:
            Dict[str, float] - 各作物类型的面积（像素数）
        """
        area_dict = {}
        total_pixels = classification_data.size
        
        for class_id, crop_type in self.crop_type_mapping.items():
            area = np.sum(classification_data == class_id)
            area_dict[crop_type] = area
        
        # 添加其他类别（如果有未映射的类别）
        unique_classes = np.unique(classification_data)
        for class_id in unique_classes:
            if class_id not in self.crop_type_mapping:
                area_dict["其他"] = area_dict.get("其他", 0) + np.sum(classification_data == class_id)
        
        return area_dict
    
    def calculate_growth_score(self, area_dict: Dict[str, float]) -> Dict[str, float]:
        """计算各作物类型的长势评分
        
        参数:
            area_dict: Dict[str, float] - 各作物类型的面积
            
        返回:
            Dict[str, float] - 各作物类型的长势评分
        """
        growth_scores = {}
        total_area = sum(area_dict.values())
        
        for crop_type, area in area_dict.items():
            if total_area > 0:
                # 基于面积占比计算长势评分
                # 面积占比越高，长势评分越高
                area_ratio = area / total_area
                # 基础评分 + 面积占比加分
                base_score = 70  # 基础分
                ratio_score = area_ratio * 30  # 面积占比最多加30分
                growth_score = base_score + ratio_score
                # 确保评分在0-100之间
                growth_score = max(0, min(100, growth_score))
                growth_scores[crop_type] = growth_score
            else:
                growth_scores[crop_type] = 0
        
        return growth_scores
    
    def predict_yield(self, area_dict: Dict[str, float], pixel_size: float = 1.0) -> Dict[str, float]:
        """预测各作物类型的产量
        
        参数:
            area_dict: Dict[str, float] - 各作物类型的面积（像素数）
            pixel_size: float - 每个像素的实际面积（平方米）
            
        返回:
            Dict[str, float] - 各作物类型的预测产量（kg）
        """
        yield_dict = {}
        # 1亩 = 666.67平方米
        m2_to_mu = 1 / 666.67
        
        for crop_type, area in area_dict.items():
            if crop_type in self.yield_coefficients:
                # 计算实际面积（亩）
                actual_area = area * pixel_size * m2_to_mu
                # 计算产量
                predicted_yield = actual_area * self.yield_coefficients[crop_type]
                yield_dict[crop_type] = predicted_yield
            else:
                yield_dict[crop_type] = 0
        
        return yield_dict
    
    def compare_growth(self, data1: np.ndarray, data2: np.ndarray, 
                      label1: str = "时期1", label2: str = "时期2") -> Dict:
        """对比两个时期的作物长势
        
        参数:
            data1: np.ndarray - 第一个时期的分类数据
            data2: np.ndarray - 第二个时期的分类数据
            label1: str - 第一个时期的标签
            label2: str - 第二个时期的标签
            
        返回:
            Dict - 对比结果
        """
        # 计算两个时期的面积
        area1 = self.calculate_area(data1)
        area2 = self.calculate_area(data2)
        
        # 计算两个时期的长势评分
        growth1 = self.calculate_growth_score(area1)
        growth2 = self.calculate_growth_score(area2)
        
        # 预测两个时期的产量
        yield1 = self.predict_yield(area1)
        yield2 = self.predict_yield(area2)
        
        # 计算变化
        changes = {}
        for crop_type in set(area1.keys()).union(set(area2.keys())):
            area_change = area2.get(crop_type, 0) - area1.get(crop_type, 0)
            growth_change = growth2.get(crop_type, 0) - growth1.get(crop_type, 0)
            yield_change = yield2.get(crop_type, 0) - yield1.get(crop_type, 0)
            
            changes[crop_type] = {
                "area_change": area_change,
                "growth_change": growth_change,
                "yield_change": yield_change
            }
        
        # 综合评估
        total_yield1 = sum(yield1.values())
        total_yield2 = sum(yield2.values())
        total_yield_change = total_yield2 - total_yield1
        
        # 确定整体趋势
        if total_yield_change > 0:
            overall_trend = "增产"
        elif total_yield_change < 0:
            overall_trend = "减产"
        else:
            overall_trend = "稳产"
        
        return {
            "period1": {
                "label": label1,
                "area": area1,
                "growth_scores": growth1,
                "yield": yield1,
                "total_yield": total_yield1
            },
            "period2": {
                "label": label2,
                "area": area2,
                "growth_scores": growth2,
                "yield": yield2,
                "total_yield": total_yield2
            },
            "changes": changes,
            "overall_trend": overall_trend,
            "total_yield_change": total_yield_change
        }
    
    def visualize_comparison(self, comparison_result: Dict, save_path: Optional[str] = None):
        """可视化对比结果
        
        参数:
            comparison_result: Dict - 对比结果
            save_path: Optional[str] - 保存路径
        """
        # 创建一个包含多个子图的画布
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('作物长势对比分析', fontsize=16)
        
        # 获取数据
        period1 = comparison_result["period1"]
        period2 = comparison_result["period2"]
        changes = comparison_result["changes"]
        
        # 1. 面积对比图
        crop_types = list(set(period1["area"].keys()).union(set(period2["area"].keys())))
        area1 = [period1["area"].get(ct, 0) for ct in crop_types]
        area2 = [period2["area"].get(ct, 0) for ct in crop_types]
        
        x = np.arange(len(crop_types))
        width = 0.35
        
        axes[0, 0].bar(x - width/2, area1, width, label=period1["label"])
        axes[0, 0].bar(x + width/2, area2, width, label=period2["label"])
        axes[0, 0].set_xlabel('作物类型')
        axes[0, 0].set_ylabel('面积 (像素)')
        axes[0, 0].set_title('作物面积对比')
        axes[0, 0].set_xticks(x)
        axes[0, 0].set_xticklabels(crop_types, rotation=45)
        axes[0, 0].legend()
        
        # 2. 长势评分对比图
        growth1 = [period1["growth_scores"].get(ct, 0) for ct in crop_types]
        growth2 = [period2["growth_scores"].get(ct, 0) for ct in crop_types]
        
        axes[0, 1].bar(x - width/2, growth1, width, label=period1["label"])
        axes[0, 1].bar(x + width/2, growth2, width, label=period2["label"])
        axes[0, 1].set_xlabel('作物类型')
        axes[0, 1].set_ylabel('长势评分')
        axes[0, 1].set_title('作物长势评分对比')
        axes[0, 1].set_xticks(x)
        axes[0, 1].set_xticklabels(crop_types, rotation=45)
        axes[0, 1].legend()
        
        # 3. 产量对比图
        yield1 = [period1["yield"].get(ct, 0) for ct in crop_types]
        yield2 = [period2["yield"].get(ct, 0) for ct in crop_types]
        
        axes[1, 0].bar(x - width/2, yield1, width, label=period1["label"])
        axes[1, 0].bar(x + width/2, yield2, width, label=period2["label"])
        axes[1, 0].set_xlabel('作物类型')
        axes[1, 0].set_ylabel('产量 (kg)')
        axes[1, 0].set_title('作物产量对比')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(crop_types, rotation=45)
        axes[1, 0].legend()
        
        # 4. 变化趋势图
        yield_changes = [changes[ct]["yield_change"] for ct in crop_types]
        
        colors = ['green' if change > 0 else 'red' if change < 0 else 'gray' for change in yield_changes]
        axes[1, 1].bar(crop_types, yield_changes, color=colors)
        axes[1, 1].axhline(y=0, color='black', linestyle='--')
        axes[1, 1].set_xlabel('作物类型')
        axes[1, 1].set_ylabel('产量变化 (kg)')
        axes[1, 1].set_title('作物产量变化趋势')
        axes[1, 1].set_xticklabels(crop_types, rotation=45)
        
        # 调整布局
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # 保存或显示
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"对比结果已保存至: {save_path}")
        else:
            plt.show()
    
    def generate_report(self, comparison_result: Dict, save_path: Optional[str] = None) -> str:
        """生成对比分析报告
        
        参数:
            comparison_result: Dict - 对比结果
            save_path: Optional[str] - 保存路径
            
        返回:
            str - 分析报告
        """
        period1 = comparison_result["period1"]
        period2 = comparison_result["period2"]
        changes = comparison_result["changes"]
        overall_trend = comparison_result["overall_trend"]
        total_yield_change = comparison_result["total_yield_change"]
        
        # 生成报告
        report = f"# 作物长势对比分析报告\n\n"
        report += f"## 基本信息\n"
        report += f"- 参考期: {period1['label']}\n"
        report += f"- 对比期: {period2['label']}\n"
        report += f"- 整体趋势: {overall_trend}\n"
        report += f"- 总产量变化: {total_yield_change:.2f} kg\n\n"
        
        report += f"## {period1['label']} 情况\n"
        report += f"- 总产量: {period1['total_yield']:.2f} kg\n"
        for crop_type, yield_value in period1['yield'].items():
            area = period1['area'].get(crop_type, 0)
            growth = period1['growth_scores'].get(crop_type, 0)
            report += f"  - {crop_type}: 面积={area}像素, 长势评分={growth:.2f}, 产量={yield_value:.2f} kg\n"
        
        report += f"\n## {period2['label']} 情况\n"
        report += f"- 总产量: {period2['total_yield']:.2f} kg\n"
        for crop_type, yield_value in period2['yield'].items():
            area = period2['area'].get(crop_type, 0)
            growth = period2['growth_scores'].get(crop_type, 0)
            report += f"  - {crop_type}: 面积={area}像素, 长势评分={growth:.2f}, 产量={yield_value:.2f} kg\n"
        
        report += f"\n## 变化分析\n"
        for crop_type, change_data in changes.items():
            area_change = change_data['area_change']
            growth_change = change_data['growth_change']
            yield_change = change_data['yield_change']
            
            report += f"- {crop_type}:\n"
            report += f"  - 面积变化: {area_change} 像素\n"
            report += f"  - 长势评分变化: {growth_change:.2f}\n"
            report += f"  - 产量变化: {yield_change:.2f} kg\n"
        
        # 生成建议
        report += f"\n## 建议\n"
        if overall_trend == "增产":
            report += "1. 整体产量呈上升趋势，建议保持当前的种植管理措施\n"
        elif overall_trend == "减产":
            report += "1. 整体产量呈下降趋势，建议分析原因并调整种植策略\n"
        else:
            report += "1. 整体产量保持稳定，建议持续监测并优化管理\n"
        
        # 分析具体作物的变化
        for crop_type, change_data in changes.items():
            yield_change = change_data['yield_change']
            if yield_change > 0:
                report += f"2. {crop_type}产量增加，建议扩大种植面积\n"
            elif yield_change < 0:
                report += f"2. {crop_type}产量减少，建议分析原因并改进种植方法\n"
        
        report += "3. 定期收集数据，建立长期监测体系\n"
        report += "4. 根据对比结果，优化种植结构和管理方案\n"
        
        # 保存报告
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"分析报告已保存至: {save_path}")
        
        return report

def main():
    """主函数，用于测试GrowthComparison类的功能"""
    # 创建GrowthComparison实例
    gc = GrowthComparison()
    
    # 生成模拟数据
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
    result = gc.compare_growth(data1, data2, "2023年", "2024年")
    
    # 打印结果
    print("对比分析结果:")
    print(f"整体趋势: {result['overall_trend']}")
    print(f"总产量变化: {result['total_yield_change']:.2f} kg")
    
    # 生成报告
    report = gc.generate_report(result, "growth_comparison_report.md")
    print("\n分析报告已生成")
    
    # 可视化结果
    gc.visualize_comparison(result, "growth_comparison.png")

if __name__ == "__main__":
    main()
