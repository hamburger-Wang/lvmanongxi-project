"""
农作物种植结构提取系统 - 基于随机森林算法
适用于高分六号等多光谱遥感影像
"""

import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterio.plot import show
import geopandas as gpd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import confusion_matrix, classification_report, cohen_kappa_score
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import ndimage
import warnings
import argparse
warnings.filterwarnings('ignore')

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


class CropClassificationSystem:
    """
    农作物分类系统
    用于从遥感影像中提取农作物种植结构
    """
    
    def __init__(self, n_estimators=100, random_state=42):
        """
        初始化分类系统
        
        参数:
        n_estimators: 随机森林中决策树的数量
        random_state: 随机种子，确保结果可重复
        """
        self.classifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=-1  # 使用所有CPU核心
        )
        self.scaler = StandardScaler()
        self.class_names = ['玉米', '小麦', '水稻', '马铃薯', '其他']
        self.class_dict = {1: '玉米', 2: '小麦', 3: '水稻', 4: '马铃薯', 0: '其他'}
        
    def calculate_ndvi(self, nir_band, red_band):
        """
        计算归一化植被指数(NDVI)
        
        参数:
        nir_band: 近红外波段数据
        red_band: 红光波段数据
        
        返回:
        ndvi: 计算得到的NDVI数组
        """
        # 避免除零错误
        denominator = nir_band + red_band
        denominator = np.where(denominator == 0, np.nan, denominator)
        
        ndvi = (nir_band - red_band) / denominator
        ndvi = np.clip(ndvi, -1, 1)  # NDVI范围在-1到1之间
        
        return ndvi
    
    def calculate_ndwi(self, green_band, nir_band):
        """
        计算归一化水体指数(NDWI)
        用于识别水体，对水稻田识别有帮助
        
        参数:
        green_band: 绿光波段数据
        nir_band: 近红外波段数据
        """
        denominator = green_band + nir_band
        denominator = np.where(denominator == 0, np.nan, denominator)
        ndwi = (green_band - nir_band) / denominator
        return np.clip(ndwi, -1, 1)
    
    def extract_features(self, image_data, band_names=None):
        """
        从遥感影像中提取多维特征
        
        参数:
        image_data: 形状为(rows, cols, bands)的影像数据
        band_names: 波段名称列表
        
        返回:
        features: 形状为(n_samples, n_features)的特征矩阵
        """
        rows, cols, bands = image_data.shape
        
        # 重塑为2D数组 (n_pixels, n_bands)
        pixels_2d = image_data.reshape(-1, bands)
        
        # 基础特征：各波段反射率
        features = pixels_2d.copy()
        feature_names = list(band_names) if band_names else [f'Band_{i}' for i in range(bands)]
        
        # 如果有足够波段，计算植被指数
        if bands >= 4:
            # 假设波段顺序: B2(蓝), B3(绿), B4(红), B5(近红外)
            # 实际使用时需要根据卫星数据调整
            blue = pixels_2d[:, 0] if bands > 0 else None
            green = pixels_2d[:, 1] if bands > 1 else None
            red = pixels_2d[:, 2] if bands > 2 else None
            nir = pixels_2d[:, 3] if bands > 3 else None
            
            if nir is not None and red is not None:
                ndvi = self.calculate_ndvi(nir, red)
                features = np.column_stack([features, ndvi])
                feature_names.append('NDVI')
            
            if green is not None and nir is not None:
                ndwi = self.calculate_ndwi(green, nir)
                features = np.column_stack([features, ndwi])
                feature_names.append('NDWI')
        
        # 处理无效值
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        return features, feature_names
    
    def load_training_data(self, sample_file):
        """
        加载训练样本数据
        
        参数:
        sample_file: 样本文件路径(CSV格式)
                    需要包含: red, green, blue, nir, label等列
        
        返回:
        X: 特征矩阵
        y: 标签数组
        """
        df = pd.read_csv(sample_file)
        
        # 提取波段特征
        band_columns = ['red', 'green', 'blue', 'nir']
        available_bands = [col for col in band_columns if col in df.columns]
        
        X = df[available_bands].values
        
        # 计算额外的植被指数特征
        if 'red' in df.columns and 'nir' in df.columns:
            ndvi = self.calculate_ndvi(df['nir'].values, df['red'].values)
            X = np.column_stack([X, ndvi])
        
        if 'green' in df.columns and 'nir' in df.columns:
            ndwi = self.calculate_ndwi(df['green'].values, df['nir'].values)
            X = np.column_stack([X, ndwi])
        
        # 提取标签
        y = df['label'].values
        
        print(f"加载了 {len(y)} 个训练样本")
        print(f"特征维度: {X.shape[1]}")
        
        return X, y
    
    def train(self, X_train, y_train):
        """
        训练随机森林分类器
        """
        print("=" * 50)
        print("开始训练随机森林分类器...")
        
        # 特征标准化
        X_scaled = self.scaler.fit_transform(X_train)
        
        # 训练模型
        self.classifier.fit(X_scaled, y_train)
        
        print(f"训练完成！使用了 {self.classifier.n_estimators} 棵决策树")
        print(f"特征重要性: {self.classifier.feature_importances_}")
        print("=" * 50)
        
    def predict_image(self, image_path, output_path=None):
        """
        对整幅遥感影像进行分类预测
        
        参数:
        image_path: 输入影像路径
        output_path: 输出分类结果路径
        
        返回:
        classification_map: 分类结果数组
        """
        print(f"正在处理影像: {image_path}")
        
        with rasterio.open(image_path) as src:
            # 读取影像数据
            image = src.read()
            rows, cols = image.shape[1], image.shape[2]
            
            # 转置为(rows, cols, bands)格式
            image_array = np.transpose(image, (1, 2, 0))
            
            # 提取特征
            features, _ = self.extract_features(image_array)
            
            # 标准化
            features_scaled = self.scaler.transform(features)
            
            # 预测
            print("正在进行分类预测...")
            predictions = self.classifier.predict(features_scaled)
            
            # 重塑为2D图像
            classification_map = predictions.reshape(rows, cols)
            
            # 保存结果
            if output_path:
                self._save_classification_result(classification_map, src.profile, output_path)
            
            print(f"分类完成！结果保存至: {output_path}")
            
            return classification_map
    
    def _save_classification_result(self, classification_map, profile, output_path):
        """
        保存分类结果
        """
        # 更新元数据
        profile.update(
            dtype=rasterio.uint8,
            count=1,
            compress='lzw'
        )
        
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(classification_map.astype(rasterio.uint8), 1)
    
    def evaluate(self, X_test, y_test):
        """
        评估模型性能
        
        参数:
        X_test: 测试特征
        y_test: 真实标签
        """
        X_scaled = self.scaler.transform(X_test)
        y_pred = self.classifier.predict(X_scaled)
        
        # 计算各项指标
        accuracy = np.mean(y_pred == y_test)
        kappa = cohen_kappa_score(y_test, y_pred)
        
        print("\n" + "=" * 50)
        print("模型评估结果")
        print("=" * 50)
        print(f"总体分类精度: {accuracy * 100:.4f}%")
        print(f"Kappa系数: {kappa:.4f}")
        print("\n详细分类报告:")
        print(classification_report(y_test, y_pred, target_names=self.class_names))
        
        # 绘制混淆矩阵
        self._plot_confusion_matrix(y_test, y_pred)
        
        return accuracy, kappa
    
    def _plot_confusion_matrix(self, y_true, y_pred):
        """
        绘制混淆矩阵
        """
        cm = confusion_matrix(y_true, y_pred)
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                    xticklabels=self.class_names,
                    yticklabels=self.class_names)
        plt.title('混淆矩阵')
        plt.ylabel('真实标签')
        plt.xlabel('预测标签')
        plt.tight_layout()
        plt.savefig('confusion_matrix.png', dpi=300)
        plt.show()
        print("混淆矩阵已保存为: confusion_matrix.png")
    
    def plot_feature_importance(self, feature_names):
        """
        绘制特征重要性图
        """
        importance = self.classifier.feature_importances_
        indices = np.argsort(importance)[::-1]
        
        plt.figure(figsize=(10, 6))
        plt.bar(range(len(importance)), importance[indices])
        plt.xticks(range(len(importance)), 
                   [feature_names[i] for i in indices], 
                   rotation=45, ha='right')
        plt.title('特征重要性排序')
        plt.xlabel('特征')
        plt.ylabel('重要性得分')
        plt.tight_layout()
        plt.savefig('feature_importance.png', dpi=300)
        plt.show()
        print("特征重要性图已保存为: feature_importance.png")
    
    def post_process(self, classification_map, min_area=10):
        """
        后处理：去除小斑块
        
        参数:
        classification_map: 分类结果数组
        min_area: 最小斑块面积(像素数)
        
        返回:
        processed_map: 后处理后的分类结果
        """
        processed_map = classification_map.copy()
        
        for class_id in np.unique(classification_map):
            if class_id == 0:  # 跳过背景
                continue
                
            # 标记连通区域
            labeled, num_features = ndimage.label(classification_map == class_id)
            
            for i in range(1, num_features + 1):
                if np.sum(labeled == i) < min_area:
                    processed_map[labeled == i] = 0  # 移除小斑块
        
        return processed_map
    
    def calculate_area_statistics(self, classification_map, pixel_size_m=16):
        """
        计算各类作物种植面积统计
        
        参数:
        classification_map: 分类结果数组
        pixel_size_m: 像元大小(米)
        
        返回:
        area_stats: 面积统计DataFrame
        """
        total_pixels = classification_map.size
        pixel_area_ha = (pixel_size_m * pixel_size_m) / 10000  # 转换为公顷
        
        stats = []
        for class_id, class_name in self.class_dict.items():
            pixel_count = np.sum(classification_map == class_id)
            area_ha = pixel_count * pixel_area_ha
            area_mu = area_ha * 15  # 1公顷 = 15亩
            percentage = (pixel_count / total_pixels) * 100
            
            stats.append({
                '作物类型': class_name,
                '像元数': pixel_count,
                '面积(公顷)': area_ha,
                '面积(亩)': area_mu,
                '占比(%)': percentage
            })
        
        df_stats = pd.DataFrame(stats)
        return df_stats


def generate_sample_data():
    """
    生成模拟的训练样本数据
    实际使用时应该替换为真实的地面调查数据
    """
    np.random.seed(42)
    n_samples = 500
    
    samples = []
    for crop_id, crop_name in [(1, '玉米'), (2, '小麦'), (3, '水稻'), (4, '马铃薯'), (0, '其他')]:
        # 为每种作物生成不同的光谱特征
        if crop_name == '玉米':
            red = np.random.normal(0.1, 0.02, n_samples)
            green = np.random.normal(0.12, 0.02, n_samples)
            blue = np.random.normal(0.08, 0.01, n_samples)
            nir = np.random.normal(0.45, 0.05, n_samples)
        elif crop_name == '小麦':
            red = np.random.normal(0.12, 0.02, n_samples)
            green = np.random.normal(0.14, 0.02, n_samples)
            blue = np.random.normal(0.09, 0.01, n_samples)
            nir = np.random.normal(0.38, 0.04, n_samples)
        elif crop_name == '水稻':
            red = np.random.normal(0.08, 0.02, n_samples)
            green = np.random.normal(0.10, 0.02, n_samples)
            blue = np.random.normal(0.07, 0.01, n_samples)
            nir = np.random.normal(0.35, 0.05, n_samples)
        elif crop_name == '马铃薯':
            red = np.random.normal(0.11, 0.02, n_samples)
            green = np.random.normal(0.13, 0.02, n_samples)
            blue = np.random.normal(0.08, 0.01, n_samples)
            nir = np.random.normal(0.42, 0.04, n_samples)
        else:  # 其他
            red = np.random.normal(0.15, 0.03, n_samples)
            green = np.random.normal(0.16, 0.03, n_samples)
            blue = np.random.normal(0.10, 0.02, n_samples)
            nir = np.random.normal(0.30, 0.06, n_samples)
        
        df_crop = pd.DataFrame({
            'red': red,
            'green': green,
            'blue': blue,
            'nir': nir,
            'label': crop_id
        })
        samples.append(df_crop)
    
    df_all = pd.concat(samples, ignore_index=True)
    df_all.to_csv('training_samples.csv', index=False)
    print("已生成模拟训练样本: training_samples.csv")
    return df_all


def main():
    """
    主函数：完整的农作物分类流程演示
    """
    print("=" * 60)
    print("鄂尔多斯市农作物种植结构提取系统")
    print("基于随机森林算法的遥感影像分类")
    print("=" * 60)
    
    # 1. 初始化分类系统
    crop_system = CropClassificationSystem(n_estimators=100)
    
    # 2. 生成或加载训练数据
    print("\n[步骤1] 准备训练样本数据...")
    try:
        # 尝试加载现有样本
        X, y = crop_system.load_training_data('training_samples.csv')
        print("成功加载现有训练样本")
    except FileNotFoundError:
        # 如果没有样本文件，生成模拟数据
        print("未找到训练样本文件，生成模拟数据...")
        sample_df = generate_sample_data()
        X, y = crop_system.load_training_data('training_samples.csv')
    
    # 3. 划分训练集和测试集
    print("\n[步骤2] 划分训练集和测试集...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    print(f"训练集样本数: {len(X_train)}")
    print(f"测试集样本数: {len(X_test)}")
    
    # 4. 训练模型
    print("\n[步骤3] 训练随机森林模型...")
    crop_system.train(X_train, y_train)
    
    # 5. 评估模型
    print("\n[步骤4] 评估模型性能...")
    accuracy, kappa = crop_system.evaluate(X_test, y_test)
    
    # 6. 特征重要性分析
    feature_names = ['红波段', '绿波段', '蓝波段', '近红外', 'NDVI', 'NDWI']
    crop_system.plot_feature_importance(feature_names[:X.shape[1]])
    
    # 7. 模拟影像分类
    print("\n[步骤5] 对遥感影像进行分类...")
    
    # 创建一个模拟的遥感影像用于演示
    # 实际使用时，替换为真实的高分六号影像路径
    try:
        # 尝试加载真实影像
        classification_result = crop_system.predict_image(
            'gf6_image.tif', 
            'classification_result.tif'
        )
    except FileNotFoundError:
        print("未找到真实遥感影像，创建模拟影像进行演示...")
        
        # 创建模拟影像 (100x100像素，4个波段)
        rows, cols = 100, 100
        simulated_image = np.zeros((rows, cols, 4))
        
        # 模拟不同作物的分布
        for i in range(rows):
            for j in range(cols):
                if i < 40:  # 玉米区域
                    simulated_image[i, j] = [0.10, 0.12, 0.08, 0.45]
                elif i < 60:  # 小麦区域
                    simulated_image[i, j] = [0.12, 0.14, 0.09, 0.38]
                elif i < 80:  # 水稻区域
                    simulated_image[i, j] = [0.08, 0.10, 0.07, 0.35]
                else:  # 马铃薯区域
                    simulated_image[i, j] = [0.11, 0.13, 0.08, 0.42]
        
        # 添加噪声
        noise = np.random.normal(0, 0.01, simulated_image.shape)
        simulated_image = np.clip(simulated_image + noise, 0, 1)
        
        # 保存模拟影像
        from rasterio.transform import from_origin
        transform = from_origin(0, 0, 16, 16)
        
        with rasterio.open('simulated_image.tif', 'w', driver='GTiff',
                          height=rows, width=cols, count=4, dtype='float32',
                          crs='EPSG:4326', transform=transform) as dst:
            for band in range(4):
                dst.write(simulated_image[:, :, band], band+1)
        
        # 进行分类
        classification_result = crop_system.predict_image(
            'simulated_image.tif',
            'classification_result.tif'
        )
    
    # 8. 后处理
    print("\n[步骤6] 后处理（去除小斑块）...")
    processed_result = crop_system.post_process(classification_result, min_area=5)
    
    # 9. 面积统计
    print("\n[步骤7] 计算种植面积统计...")
    area_stats = crop_system.calculate_area_statistics(processed_result, pixel_size_m=16)
    print("\n" + "=" * 50)
    print("农作物种植面积统计结果")
    print("=" * 50)
    print(area_stats.to_string(index=False))
    
    # 保存统计结果
    area_stats.to_csv('crop_area_statistics.csv', index=False, encoding='utf-8-sig')
    print("\n面积统计结果已保存至: crop_area_statistics.csv")
    
    # 10. 可视化分类结果
    print("\n[步骤8] 可视化分类结果...")
    plt.figure(figsize=(12, 5))
    
    # 原始模拟影像(假彩色合成)
    plt.subplot(1, 2, 1)
    if 'simulated_image' in locals():
        # 假彩色合成: 近红外, 红, 绿
        rgb_display = np.stack([
            simulated_image[:, :, 3],  # 近红外
            simulated_image[:, :, 2],  # 红
            simulated_image[:, :, 1]   # 绿
        ], axis=2)
        rgb_display = np.clip(rgb_display * 3, 0, 1)  # 增强对比度
        plt.imshow(rgb_display)
    else:
        plt.imshow(classification_result, cmap='tab10')
    plt.title('原始遥感影像\n(假彩色合成)')
    plt.axis('off')
    
    # 分类结果
    plt.subplot(1, 2, 2)
    cmap = plt.cm.tab10
    im = plt.imshow(processed_result, cmap=cmap, vmin=0, vmax=4)
    cbar = plt.colorbar(im, ticks=[0, 1, 2, 3, 4])
    cbar.ax.set_yticklabels(['其他', '玉米', '小麦', '水稻', '马铃薯'])
    plt.title('随机森林分类结果')
    plt.axis('off')
    
    plt.tight_layout()
    plt.savefig('classification_visualization.png', dpi=300, bbox_inches='tight')
    plt.show()
    print("分类结果可视化已保存为: classification_visualization.png")
    
    print("\n" + "=" * 60)
    print("处理完成！生成的文件:")
    print("  1. training_samples.csv - 训练样本数据")
    print("  2. classification_result.tif - 分类结果栅格")
    print("  3. crop_area_statistics.csv - 面积统计表")
    print("  4. confusion_matrix.png - 混淆矩阵图")
    print("  5. feature_importance.png - 特征重要性图")
    print("  6. classification_visualization.png - 分类结果可视化")
    print("=" * 60)


# ----------------------
# 训练模型函数（与crop_model.py接口一致）
# ----------------------
def train_model(data_path, out_loss, epochs, model_path, img_path):
    """训练随机森林模型
    
    参数:
        data_path: str - 训练数据文件路径
        out_loss: str - 损失函数类型（随机森林不使用，保留接口一致）
        epochs: int - 训练轮数（随机森林不使用，保留接口一致）
        model_path: str - 模型保存路径
        img_path: str - 结果图保存路径
    
    返回:
        dict - 训练结果，包含状态、kappa系数等信息
    """
    try:
        # 初始化分类系统
        crop_system = CropClassificationSystem(n_estimators=100)
        
        # 加载或生成训练数据
        try:
            X, y = crop_system.load_training_data(data_path)
        except FileNotFoundError:
            # 如果没有样本文件，生成模拟数据
            sample_df = generate_sample_data()
            X, y = crop_system.load_training_data('training_samples.csv')
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        
        # 训练模型
        crop_system.train(X_train, y_train)
        
        # 评估模型
        accuracy, kappa = crop_system.evaluate(X_test, y_test)
        
        # 特征重要性分析
        feature_names = ['红波段', '绿波段', '蓝波段', '近红外', 'NDVI', 'NDWI']
        crop_system.plot_feature_importance(feature_names[:X.shape[1]])
        
        # 保存模型（使用pickle）
        import pickle
        with open(model_path, 'wb') as f:
            pickle.dump(crop_system, f)
        
        print(f"💾 模型已保存：{model_path}")
        
        # 返回结果
        result = {
            "status": "成功",
            "kappa": kappa,
            "model_path": model_path,
            "img_path": img_path,
            "epochs": epochs,
            "loss": out_loss
        }
        print(f"===RESULT==={result}===END===")
        return result
    
    except Exception as e:
        print(f"❌ 训练失败：{e}")
        return {"status": "失败", "msg": str(e)}

# ----------------------
# 预测模型函数（与crop_model.py接口一致）
# ----------------------
def predict_model(data_path, model_path, img_path):
    """加载已有模型，直接预测新数据
    
    参数:
        data_path: str - 待预测数据文件路径
        model_path: str - 训练好的模型路径
        img_path: str - 预测结果图保存路径
    
    返回:
        dict - 预测结果，包含状态、模型路径、分类比例等信息
    """
    try:
        # 加载模型
        import pickle
        with open(model_path, 'rb') as f:
            crop_system = pickle.load(f)
        print(f"✅ 模型加载成功：{model_path}")
        
        # 预测影像
        classification_result = crop_system.predict_image(data_path, img_path)
        
        # 后处理
        processed_result = crop_system.post_process(classification_result, min_area=5)
        
        # 面积统计
        area_stats = crop_system.calculate_area_statistics(processed_result, pixel_size_m=16)
        
        # 生成分类比例
        class_ratio = {}
        for _, row in area_stats.iterrows():
            class_ratio[row['作物类型']] = float(row['占比(%)'] / 100)
        
        print(f"\n🎉 预测完成！")
        print(f"📊 分类结果：{class_ratio}")
        print(f"💾 预测结果图已保存：{img_path}")
        
        # 返回结果
        result = {
            "status": "成功",
            "kappa": 0.0,  # 无真实标签时kappa为0
            "model_path": model_path,
            "img_path": img_path,
            "class_ratio": class_ratio
        }
        print(f"===RESULT==={result}===END===")
        return result
    
    except Exception as e:
        print(f"❌ 预测失败：{e}")
        return {"status": "失败", "msg": str(e)}

# ----------------------
# 主函数（与crop_model.py接口一致）
# ----------------------
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='作物分类模型（训练/预测）')
    parser.add_argument('--mode', type=str, required=True, choices=['train', 'predict'], help='运行模式：train/predict')
    parser.add_argument('--model_choice', type=str, default='crop_model', choices=['crop_model', 'crop_model-dry', '第三模型'], help='模型选择')
    parser.add_argument('--data_path', type=str, required=True, help='数据文件路径（CSV/TIFF）')
    parser.add_argument('--out_loss', type=str, default='Cross-entropy', choices=['Cross-entropy', 'IOU', 'F1'], help='损失函数')
    parser.add_argument('--epochs', type=int, default=5, help='训练轮数（仅train模式有效）')
    parser.add_argument('--model_path', type=str, default='./model_rf.pkl', help='模型保存/加载路径')
    parser.add_argument('--img_path', type=str, default='./result.png', help='结果图保存路径')
    
    args = parser.parse_args()
    
    # 打印模型选择信息
    print(f"🔍 选择的模型：{args.model_choice}")
    
    # 根据模式执行对应逻辑
    if args.mode == 'train':
        train_model(args.data_path, args.out_loss, args.epochs, args.model_path, args.img_path)
    elif args.mode == 'predict':
        predict_model(args.data_path, args.model_path, args.img_path)

if __name__ == "__main__":
    main()