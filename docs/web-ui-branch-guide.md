# Web UI 支线同步与运行说明

本文档用于团队成员同步本支线的 Web 可视化界面，并在本地运行前端、后端和单样本 HDF5 上传测试。

## 1. 支线内容

本支线在不删除原 Qt 桌面端代码的基础上新增了 Web 端能力：

- `web/`：Next.js 前端，包含登录页、遥感数据接入、作物分类结果、三维地块可视化、风险区域和智能种植问答界面。
- `backend/`：FastAPI 后端，提供登录、遥感数据上传分析、CropSupervision 样本读取和种植问答接口。
- `scripts/extract_crop_supervision_sample.py`：从完整 CropSupervision HDF5 中切出单样本测试文件。
- `requirements-web.txt`：Web 后端运行依赖。
- `.gitignore`：忽略 `datasets/`、`backend/uploads/`、`web/node_modules/`、`web/.next/` 等本地数据和缓存。

注意：`datasets/` 不会提交到 GitHub。团队成员需要自行下载数据集或使用别人单独传给你的测试样本。

## 2. 团队成员同步方法

### 已经克隆过仓库

```powershell
cd "D:\school activity\bisai\alvmanongxi"
git fetch origin
git switch codex/web-ui-dataset-entry
git pull origin codex/web-ui-dataset-entry
```

如果本地还没有这个分支：

```powershell
git fetch origin
git switch -c codex/web-ui-dataset-entry origin/codex/web-ui-dataset-entry
```

### 第一次克隆仓库

```powershell
cd "D:\school activity\bisai"
git clone -b codex/web-ui-dataset-entry https://github.com/hamburger-Wang/lvmanongxi-project.git alvmanongxi
cd alvmanongxi
```

## 3. 后端运行方法

建议使用虚拟环境，避免污染系统 Python。

```powershell
cd "D:\school activity\bisai\alvmanongxi"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-web.txt
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

后端启动成功后，可访问：

```text
http://127.0.0.1:8000/api/health
```

可选环境变量：

```powershell
$env:DASHSCOPE_API_KEY="你的阿里云百炼 API Key"
$env:ALLOWED_ORIGINS="http://127.0.0.1:3000,https://你的前端域名"
$env:MAX_UPLOAD_MB="512"
```

`ALLOWED_ORIGINS` 用于允许部署后的前端跨域访问后端；多个地址用英文逗号分隔。

## 4. 前端运行方法

另开一个 PowerShell 窗口：

```powershell
cd "D:\school activity\bisai\alvmanongxi\web"
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

前端地址：

```text
http://127.0.0.1:3000
```

本地演示账号：

```text
账号：demo
密码：123456
```

## 5. 单样本 HDF5 测试方法

Web 正式入口是 HDF5 / GeoTIFF / IMG 遥感数据，不是普通 jpg/png 图片。

如果你已经有完整数据集，例如：

```text
D:\school activity\bisai\alvmanongxi\datasets\CropSupervision\SiteC_train.hdf5
```

可以切出一个单样本文件：

```powershell
python scripts\extract_crop_supervision_sample.py `
  --source "D:\school activity\bisai\alvmanongxi\datasets\CropSupervision\SiteC_train.hdf5" `
  --sample-index 1 `
  --output "D:\school activity\bisai\alvmanongxi\datasets\CropSupervision\SiteC_sample1_test.hdf5"
```

上传时：

1. 打开 `http://127.0.0.1:3000`
2. 登录 `demo / 123456`
3. 左侧进入“遥感数据接入”
4. `HDF5 样本序号` 填 `0`
5. 点击“上传 HDF5 / GeoTIFF / IMG 数据”
6. 选择刚切出的 `SiteC_sample1_test.hdf5`

为什么样本序号填 `0`：单样本文件本身只包含一个样本，所以它内部的索引就是 0。

## 6. 当前功能真实性说明

当前 Web 页面不是静态假数据。上传 HDF5 后会走真实链路：

```text
HDF5 文件上传
→ FastAPI 后端读取 data / truth
→ 生成分类网格、长势评分、风险区域和三维场景数据
→ 前端 Three.js 渲染三维地块
```

目前已经真实接入：

- 登录页与主界面跳转
- HDF5 / GeoTIFF / IMG 上传入口
- CropSupervision HDF5 `data` / `truth` 读取
- TIFF 及 TIFF 兼容 IMG 的多波段读取与可视化规则分析
- 分类统计、长势指标、风险区域生成
- Three.js 三维地块渲染
- 阿里云 DashScope 问答接口预留，配置 `DASHSCOPE_API_KEY` 后可走正式接口

界面现在会显示后端在线状态、问答提供方和本次分析依据。HDF5 测试样本的分类结果来自 `/truth` 标签；长势、水分与产量是研究阶段的归一化或规则估算，并非训练模型输出。

当前仍属于后续接入项：

- Web 端完整训练任务管理
- Web 端调用 TensorFlow 模型权重做真正预测
- 大文件上传到对象存储或服务器数据目录
- 多用户账号系统和权限控制

当前登录接口只检查账号和密码是否为空，生成的是本地演示 token；它不能作为正式登录系统使用。

其中“训练模型”和“真正模型预测”依赖 TensorFlow 环境和训练好的模型权重。当前仓库没有提交 `B.hdf5`，本地如需跑原始模型，需要额外准备 Python 3.10/3.11 环境和 TensorFlow 依赖。

## 7. 常见问题

### 上传完整 `SiteC_train.hdf5` 可以吗？

可以，但不推荐本地网页测试直接上传 3GB 文件。更推荐先用脚本切出单样本 HDF5。

### 为什么数据集没有一起同步？

数据集体积太大，已经被 `.gitignore` 忽略。正式项目应把数据放在对象存储、服务器数据目录或数据集下载说明中，不直接放进 Git。

### 前端能部署到 Vercel 吗？

前端可以。训练和推理后端不建议放 Vercel，建议放阿里云 ECS / GPU 服务器 / 单独 FastAPI 服务。
