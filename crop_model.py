# ==============================================
# 基于论文的卫星影像作物制图完整实现（Windows桌面版）
# 新增：支持命令行参数调用，新增predict模式
# ==============================================
import sys
import argparse
import tables
import numpy as np
import tensorflow as tf
from tensorflow.keras.utils import to_categorical
import random
import cv2
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Input, Conv3D, BatchNormalization, Activation, UpSampling3D, Concatenate, Lambda, Reshape
from tensorflow.keras.optimizers import SGD
from tensorflow.keras import backend as K
from tensorflow.keras import callbacks
import matplotlib.pyplot as plt
from sklearn.metrics import cohen_kappa_score
import h5py
import tifffile  # 新增：支持TIFF/IMG数据读取

# ----------------------
# 1. 自定义损失函数（论文同款）
# ----------------------
def IOU_Loss(y_true, y_pred):
    y_true = K.flatten(y_true)
    y_pred = K.flatten(y_pred)
    intersection = K.sum(y_true * y_pred)
    union = K.sum(y_true) + K.sum(y_pred) - intersection
    return 1 - (intersection + K.epsilon()) / (union + K.epsilon())

def F1_Loss(y_true, y_pred):
    y_true = K.flatten(y_true)
    y_pred = K.flatten(y_pred)
    tp = K.sum(y_true * y_pred)
    fp = K.sum((1 - y_true) * y_pred)
    fn = K.sum(y_true * (1 - y_pred))
    precision = tp / (tp + fp + K.epsilon())
    recall = tp / (tp + fn + K.epsilon())
    return 1 - 2 * ((precision * recall) / (precision + recall + K.epsilon()))

# 占位（论文里的SupCon Loss，先不用）
def SupCon_Loss(y_true, y_pred):
    return tf.reduce_mean(y_pred)

# ----------------------
# 新增：数据读取工具（支持HDF5/TIFF/IMG）
# ----------------------
def load_data(file_path):
    """通用数据读取函数，适配HDF5/TIFF/IMG格式"""
    file_ext = file_path.split('.')[-1].lower()
    
    if file_ext in ['hdf5', 'h5']:
        # 读取HDF5格式（兼容原有数据）
        hdf5_file = tables.open_file(file_path, mode='r')
        data = hdf5_file.root.data[:]
        truth = hdf5_file.root.truth[:] if hasattr(hdf5_file.root, 'truth') else None
        hdf5_file.close()
        return data, truth
    elif file_ext in ['tiff', 'tif', 'img']:
        # 读取TIFF/IMG影像（新增）
        with tifffile.TiffFile(file_path) as tif:
            data = tif.asarray()
            # 适配模型输入形状 (N, 128, 128, 23, 6)
            if len(data.shape) == 4:  # (H, W, T, C)
                data = np.expand_dims(data, axis=0)
            elif len(data.shape) == 3:  # (H, W, C)
                data = np.expand_dims(data, axis=0)
                data = np.expand_dims(data, axis=3)
        return data, None
    else:
        raise ValueError(f"不支持的文件格式：{file_ext}")

# ----------------------
# 2. 数据生成器（论文同款，无修改）
# ----------------------
def data_generator(images, labels, MidS, batch_size=1):
    mm = 0
    zz = np.arange(len(labels))
    random.shuffle(zz)
    while True:
        mm += batch_size
        if mm > len(labels):
            mini_batch_indices = zz[mm - batch_size:len(labels)]
            r = mm - len(labels)
            mm = 0
            zz = np.arange(len(labels))
            random.shuffle(zz)
            mm += r
            mini_batch_indices = np.concatenate([mini_batch_indices, zz[:r]])
        else:
            mini_batch_indices = zz[mm - batch_size:mm]
        
        imgs = []
        lbls = []
        for t in mini_batch_indices:
            imgs.append(images[t])
            lbls.append(to_categorical(labels[t], 3))  # 3类作物
        
        a = np.array(imgs)
        b = np.array(lbls)
        
        if MidS == 'off':
            yield a, b
        elif MidS == 'SupCon':
            mid1_lbls = []
            mid2_lbls = []
            mid3_lbls = []
            mid4_lbls = []
            for j in b:
                cc = cv2.resize(j, (0, 0), fx=0.5, fy=0.5)
                cc = np.where(cc >= 0.5, 1, 0)
                mid1_lbls.append(cc)
                d = cv2.resize(j, (0, 0), fx=0.25, fy=0.25)
                d = np.where(d >= 0.5, 1, 0)
                mid2_lbls.append(d)
                e = cv2.resize(j, (0, 0), fx=0.125, fy=0.125)
                e = np.where(e >= 0.5, 1, 0)
                mid3_lbls.append(e)
                f = cv2.resize(j, (0, 0), fx=0.0625, fy=0.0625)
                f = np.where(f >= 0.5, 1, 0)
                mid4_lbls.append(f)
            yield (a, [b, np.reshape(np.argmax(b, axis=-1), (batch_size, 128, 128)),
                       np.array(mid1_lbls), np.array(mid2_lbls),
                       np.array(mid3_lbls), np.array(mid4_lbls)])
        elif MidS == 'Cross-entropy':
            mid1_lbls = []
            mid2_lbls = []
            mid3_lbls = []
            mid4_lbls = []
            for j in b:
                cc = cv2.resize(j, (0, 0), fx=0.5, fy=0.5)
                cc = np.where(cc >= 0.5, 1, 0)
                mid1_lbls.append(cc)
                d = cv2.resize(j, (0, 0), fx=0.25, fy=0.25)
                d = np.where(d >= 0.5, 1, 0)
                mid2_lbls.append(d)
                e = cv2.resize(j, (0, 0), fx=0.125, fy=0.125)
                e = np.where(e >= 0.5, 1, 0)
                mid3_lbls.append(e)
                f = cv2.resize(j, (0, 0), fx=0.0625, fy=0.0625)
                f = np.where(f >= 0.5, 1, 0)
                mid4_lbls.append(f)
            yield (a, [b, b, np.array(mid1_lbls), np.array(mid2_lbls),
                       np.array(mid3_lbls), np.array(mid4_lbls)])

# ----------------------
# 3. FCN-3D模型（论文同款，无修改）
# ----------------------
def FCN_3D(MidS, OutS, lr_rate):
    K.set_image_data_format("channels_last")
    
    inputlayer = Input(shape=(128, 128, 23, 6))
    
    # 编码器
    conv0 = Conv3D(32, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(inputlayer)
    conv0 = BatchNormalization()(conv0)
    conv0 = Activation('relu')(conv0)
    
    conv1 = Conv3D(64, kernel_size=(3, 3, 5), strides=(2, 2, 1), padding='same')(conv0)
    conv1 = BatchNormalization()(conv1)
    conv1 = Activation('relu')(conv1)
    
    conv2 = Conv3D(128, kernel_size=(3, 3, 5), strides=(2, 2, 1), padding='same')(conv1)
    conv2 = BatchNormalization()(conv2)
    conv2 = Activation('relu')(conv2)
    
    conv3 = Conv3D(256, kernel_size=(3, 3, 5), strides=(2, 2, 1), padding='same')(conv2)
    conv3 = BatchNormalization()(conv3)
    conv3 = Activation('relu')(conv3)
    
    conv4 = Conv3D(512, kernel_size=(3, 3, 5), strides=(2, 2, 1), padding='same')(conv3)
    conv4 = BatchNormalization()(conv4)
    conv4 = Activation('relu')(conv4)
    
    # 解码器
    conv4U = UpSampling3D(size=(2, 2, 1))(conv4)
    conv4Uconv3 = Concatenate()([conv4U, conv3])
    
    conv5 = Conv3D(256, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv4Uconv3)
    conv5 = BatchNormalization()(conv5)
    conv5 = Activation('relu')(conv5)
    
    conv5U = UpSampling3D(size=(2, 2, 1))(conv5)
    conv5Uconv2 = Concatenate()([conv5U, conv2])
    
    conv6 = Conv3D(128, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv5Uconv2)
    conv6 = BatchNormalization()(conv6)
    conv6 = Activation('relu')(conv6)
    
    conv6U = UpSampling3D(size=(2, 2, 1))(conv6)
    conv6Uconv1 = Concatenate()([conv6U, conv1])
    
    conv7 = Conv3D(64, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv6Uconv1)
    conv7 = BatchNormalization()(conv7)
    conv7 = Activation('relu')(conv7)
    
    conv7U = UpSampling3D(size=(2, 2, 1))(conv7)
    conv7Uconv0 = Concatenate()([conv7U, conv0])
    
    conv8 = Conv3D(32, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv7Uconv0)
    conv8 = BatchNormalization()(conv8)
    conv8 = Activation('relu')(conv8)
    
    conv9 = Conv3D(32, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv8)
    conv9 = BatchNormalization()(conv9)
    conv9 = Activation('relu')(conv9)
    
    conv10 = Conv3D(16, kernel_size=(3, 3, 5), strides=(1, 1, 1), padding='same')(conv9)
    conv10 = BatchNormalization()(conv10)
    conv10 = Activation('relu')(conv10)
    
    conv11 = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv10)
    squeezed = Lambda(lambda x: K.squeeze(x, 3))(conv11)
    mainoutput = Activation('softmax', name='mainoutput')(squeezed)
    
    # 选择输出损失函数
    if OutS == 'IOU':
        output_loss = IOU_Loss
    elif OutS == 'F1':
        output_loss = F1_Loss
    else:
        output_loss = 'categorical_crossentropy'
    
    # 构建模型
    if MidS == 'off':
        model = Model(inputlayer, mainoutput)
        model.compile(optimizer=SGD(lr=lr_rate, momentum=0.9), loss=output_loss, metrics=['accuracy'])
    elif MidS == 'SupCon':
        mid4_out = Reshape((-1, 23*512), name='mid4_out')(conv4)
        mid3_out = Reshape((-1, 23*256), name='mid3_out')(conv5)
        mid2_out = Reshape((-1, 23*128), name='mid2_out')(conv6)
        mid1_out = Reshape((-1, 23*64), name='mid1_out')(conv7)
        mid0_out = Reshape((-1, 23*32), name='mid0_out')(conv8)
        model = Model(inputlayer, [mainoutput, mid0_out, mid1_out, mid2_out, mid3_out, mid4_out])
        model.compile(optimizer=SGD(lr=lr_rate, momentum=0.9), 
                      loss=[output_loss, SupCon_Loss, SupCon_Loss, SupCon_Loss, SupCon_Loss, SupCon_Loss], 
                      metrics=['accuracy'])
    elif MidS == 'Cross-entropy':
        mid4_out = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv4)
        mid4_out = Lambda(lambda x: K.squeeze(x, 3))(mid4_out)
        mid4_out = Activation('softmax', name="mid4_out")(mid4_out)
        
        mid3_out = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv5)
        mid3_out = Lambda(lambda x: K.squeeze(x, 3))(mid3_out)
        mid3_out = Activation('softmax', name="mid3_out")(mid3_out)
        
        mid2_out = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv6)
        mid2_out = Lambda(lambda x: K.squeeze(x, 3))(mid2_out)
        mid2_out = Activation('softmax', name="mid2_out")(mid2_out)
        
        mid1_out = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv7)
        mid1_out = Lambda(lambda x: K.squeeze(x, 3))(mid1_out)
        mid1_out = Activation('softmax', name="mid1_out")(mid1_out)
        
        mid0_out = Conv3D(3, kernel_size=(1, 1, 23), strides=(1, 1, 1))(conv8)
        mid0_out = Lambda(lambda x: K.squeeze(x, 3))(mid0_out)
        mid0_out = Activation('softmax', name="mid0_out")(mid0_out)
        
        model = Model(inputlayer, [mainoutput, mid0_out, mid1_out, mid2_out, mid3_out, mid4_out])
        model.compile(optimizer=SGD(lr=lr_rate, momentum=0.9), 
                      loss=[output_loss, 'categorical_crossentropy', 'categorical_crossentropy', 
                            'categorical_crossentropy', 'categorical_crossentropy', 'categorical_crossentropy'], 
                      metrics=['accuracy'])
    
    return model

# ----------------------
# 4. 训练逻辑（原有逻辑封装）
# ----------------------
def train_model(data_path, out_loss, epochs, model_path, img_path):
    """训练模型函数"""
    # 加载数据
    try:
        images, labels = load_data(data_path)
        print(f"✅ 训练数据加载成功，形状：{images.shape}")
    except Exception as e:
        print(f"❌ 数据加载失败：{e}")
        return {"status": "失败", "msg": str(e)}
    
    # 划分数据集（论文同款：前300个样本，训练210，验证90，测试5）
    total_samples = min(300, len(images))
    i = np.arange(total_samples)
    j = np.arange(0, 90)
    k = np.delete(i, j)
    t = np.arange(min(300, len(images)), min(305, len(images)))
    
    train_images = images[k, :, :, :, :]
    train_labels = labels[k, :, :] if labels is not None else None
    val_images = images[j, :, :, :, :]
    val_labels = labels[j, :, :] if labels is not None else None
    test_images = images[t, :, :, :, :] if len(t) > 0 else images[:5, :, :, :, :]
    test_labels = labels[t, :, :] if (labels is not None and len(t) > 0) else labels[:5, :, :]
    
    print(f"📊 数据划分完成：训练{len(train_images)} | 验证{len(val_images)} | 测试{len(test_images)}")
    
    # 初始化生成器和模型
    train_data = data_generator(train_images, train_labels, MidS='off')
    val_data = data_generator(val_images, val_labels, MidS='off')
    model = FCN_3D(MidS='off', OutS=out_loss, lr_rate=0.001)
    
    print("✅ 模型构建成功！")
    
    # 训练模型
    check_point = callbacks.ModelCheckpoint(model_path, monitor='val_accuracy', save_best_only=True, mode='max')
    
    print(f"🚀 开始训练模型（{epochs}个epoch）...")
    history = model.fit(
        train_data,
        steps_per_epoch=int(np.ceil(len(train_labels) / 1)),
        epochs=epochs,
        validation_data=val_data,
        validation_steps=int(np.ceil(len(val_labels) / 1)),
        callbacks=[check_point]
    )
    
    # 预测+评估
    print("📈 加载最优模型，开始预测...")
    best_model = load_model(model_path, custom_objects={'IOU_Loss': IOU_Loss, 'F1_Loss': F1_Loss, 'SupCon_Loss': SupCon_Loss})
    predictions = best_model.predict(test_images)
    predicted_classes = np.argmax(predictions, axis=-1)
    
    # 可视化第一个样本的结果
    predicted_image = predicted_classes[0]
    true_image = test_labels[0] if test_labels is not None else predicted_image
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    im1 = axes[0].imshow(true_image, cmap='jet')
    axes[0].set_title('True Labels (真实标签)')
    fig.colorbar(im1, ax=axes[0])
    
    im2 = axes[1].imshow(predicted_image, cmap='jet')
    axes[1].set_title('Predicted Labels (预测结果)')
    fig.colorbar(im2, ax=axes[1])
    
    plt.savefig(img_path, dpi=150)
    plt.close()
    
    # 计算Kappa系数
    kappa_score = cohen_kappa_score(true_image.flatten(), predicted_image.flatten()) if test_labels is not None else 0.0
    
    print(f"\n🎉 训练完成！")
    print(f"📊 Kappa系数：{kappa_score:.3f}")
    print(f"💾 最优模型已保存：{model_path}")
    print(f"🖼️ 结果图已保存：{img_path}")
    
    # 返回结果（供Qt解析）
    result = {
        "status": "成功",
        "kappa": kappa_score,
        "model_path": model_path,
        "img_path": img_path,
        "epochs": epochs,
        "loss": out_loss
    }
    print(f"===RESULT==={result}===END===")
    return result

# ----------------------
# 新增：预测逻辑（核心补全）
# ----------------------
def predict_model(data_path, model_path, img_path):
    """加载已有模型，直接预测新数据"""
    try:
        # 加载待预测数据
        images, _ = load_data(data_path)
        print(f"✅ 预测数据加载成功，形状：{images.shape}")
        
        # 加载训练好的模型
        best_model = load_model(model_path, custom_objects={'IOU_Loss': IOU_Loss, 'F1_Loss': F1_Loss, 'SupCon_Loss': SupCon_Loss})
        print(f"✅ 模型加载成功：{model_path}")
        
        # 执行预测
        predictions = best_model.predict(images)
        predicted_classes = np.argmax(predictions, axis=-1)
        
        # 可视化第一个样本的预测结果
        predicted_image = predicted_classes[0]
        
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        im = ax.imshow(predicted_image, cmap='jet')
        ax.set_title('Predicted Labels (预测结果)')
        fig.colorbar(im, ax=ax)
        plt.savefig(img_path, dpi=150)
        plt.close()
        
        # 统计分类结果（3类作物）
        class_counts = np.bincount(predicted_image.flatten())
        class_ratio = class_counts / np.sum(class_counts) if np.sum(class_counts) > 0 else [0,0,0]
        
        print(f"\n🎉 预测完成！")
        print(f"📊 分类结果：作物1({class_ratio[0]:.2%}) | 作物2({class_ratio[1]:.2%}) | 作物3({class_ratio[2]:.2%})")
        print(f"💾 预测结果图已保存：{img_path}")
        
        # 返回结果（供Qt解析）
        result = {
            "status": "成功",
            "kappa": 0.0,  # 无真实标签时kappa为0
            "model_path": model_path,
            "img_path": img_path,
            "class_ratio": {
                "作物1": float(class_ratio[0]),
                "作物2": float(class_ratio[1]),
                "作物3": float(class_ratio[2])
            }
        }
        print(f"===RESULT==={result}===END===")
        return result
    
    except Exception as e:
        print(f"❌ 预测失败：{e}")
        return {"status": "失败", "msg": str(e)}

# ----------------------
# 主函数（新增：命令行参数解析）
# ----------------------
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='作物分类模型（训练/预测）')
    parser.add_argument('--mode', type=str, required=True, choices=['train', 'predict'], help='运行模式：train/predict')
    parser.add_argument('--data_path', type=str, required=True, help='数据文件路径（HDF5/TIFF/IMG）')
    parser.add_argument('--out_loss', type=str, default='Cross-entropy', choices=['Cross-entropy', 'IOU', 'F1'], help='损失函数')
    parser.add_argument('--epochs', type=int, default=5, help='训练轮数（仅train模式有效）')
    parser.add_argument('--model_path', type=str, default='./B.hdf5', help='模型保存/加载路径')
    parser.add_argument('--img_path', type=str, default='./result.png', help='结果图保存路径')
    
    args = parser.parse_args()
    
    # 根据模式执行对应逻辑
    if args.mode == 'train':
        train_model(args.data_path, args.out_loss, args.epochs, args.model_path, args.img_path)
    elif args.mode == 'predict':
        predict_model(args.data_path, args.model_path, args.img_path)

if __name__ == "__main__":
    main()