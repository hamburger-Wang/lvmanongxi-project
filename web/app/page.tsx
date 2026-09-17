"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bot,
  CloudUpload,
  Database,
  FileImage,
  Leaf,
  LogOut,
  MapPinned,
  Radar,
  Send,
  ShieldCheck,
  Sprout,
  TrendingUp,
} from "lucide-react";
import FieldScene from "@/components/FieldScene";
import {
  analyzeDataset,
  askAdvice,
  fetchCropSupervisionSample,
  fetchDemoAnalysis,
  type AnalysisResult,
  type CropCell,
} from "@/lib/api";

type User = {
  name: string;
  role: string;
  token: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  provider?: string;
};

const percent = (value?: number) => `${Math.round((value ?? 0) * 100)}%`;

export default function DashboardPage() {
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedCell, setSelectedCell] = useState<CropCell | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("等待上传 HDF5 / GeoTIFF / IMG 遥感数据后生成分析结果。");
  const [sampleIndex, setSampleIndex] = useState(0);
  const [question, setQuestion] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "上传遥感数据并生成分析结果后，可以在这里询问种植管理、异常区域处理、产量风险等问题。",
      provider: "system",
    },
  ]);

  useEffect(() => {
    const stored = localStorage.getItem("agri-user");
    if (!stored) {
      router.replace("/login");
      return;
    }
    try {
      setUser(JSON.parse(stored));
      setAuthChecked(true);
    } catch {
      localStorage.removeItem("agri-user");
      router.replace("/login");
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("agri-user");
    router.replace("/login");
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setMessage(`正在分析 ${file.name} 的第 ${sampleIndex} 个样本，请等待后端返回分类与长势结果。`);
    try {
      const data = await analyzeDataset(file, sampleIndex);
      setResult(data);
      setSelectedCell(null);
      setMessage("分析完成，页面内容已全部根据后端结果刷新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "遥感数据分析失败");
    } finally {
      setBusy(false);
    }
  };

  const loadDemo = async () => {
    setBusy(true);
    setMessage("正在加载后端示例数据，仅用于本地开发验证。");
    try {
      const data = await fetchDemoAnalysis();
      setResult(data);
      setSelectedCell(null);
      setMessage("示例数据已加载。正式使用时请以上传影像返回的分析结果为准。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "示例数据加载失败");
    } finally {
      setBusy(false);
    }
  };

  const loadCropSupervisionSample = async () => {
    setBusy(true);
    setMessage("正在读取本地 CropSupervision / SiteC_train.hdf5 的第 0 个样本。");
    try {
      const data = await fetchCropSupervisionSample(0);
      setResult(data);
      setSelectedCell(null);
      setMessage("已载入真实 HDF5 样本，页面内容来自 CropSupervision 数据。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CropSupervision 样本加载失败");
    } finally {
      setBusy(false);
    }
  };

  const submitQuestion = async () => {
    const text = question.trim();
    if (!text) return;
    setQuestion("");
    setChatBusy(true);
    setChatMessages((items) => [...items, { role: "user", content: text }]);
    try {
      const data = await askAdvice(text, result);
      setChatMessages((items) => [...items, { role: "assistant", content: data.answer, provider: data.provider }]);
    } catch (error) {
      setChatMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: error instanceof Error ? error.message : "问答接口调用失败",
          provider: "error",
        },
      ]);
    } finally {
      setChatBusy(false);
    }
  };

  const coreMetrics = useMemo(() => {
    if (!result) return [];
    return [
      { label: "平均长势", value: percent(result.summary.avgGrowth), icon: <Leaf size={18} /> },
      { label: "健康区域", value: percent(result.summary.healthyRatio), icon: <ShieldCheck size={18} /> },
      { label: "风险区域", value: percent(result.summary.riskRatio), icon: <Radar size={18} /> },
      { label: "预测产量", value: `${result.summary.estimatedYieldKg.toFixed(1)} kg`, icon: <TrendingUp size={18} /> },
    ];
  }, [result]);

  const moduleItems = [
    { title: "数据接入", text: result ? "已接入遥感数据" : "等待上传 HDF5 / GeoTIFF / IMG" },
    { title: "作物分类", text: result ? `${result.cropStats.length} 类作物结果` : "等待后端分类结果" },
    { title: "长势评估", text: result ? `平均长势 ${percent(result.summary.avgGrowth)}` : "等待长势评分" },
    { title: "三维可视化", text: result ? `${result.scene.cells.length} 个场景单元` : "等待场景数据" },
    { title: "种植问答", text: "通过后端问答接口生成建议" },
  ];

  if (!authChecked) {
    return <main className="loading-shell">正在进入系统...</main>;
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar compact">
        <div className="brand">
          <div className="brand-mark">
            <Sprout size={24} />
          </div>
          <div>
            <p>农业智能分析系统</p>
            <strong>作物长势三维可视化平台</strong>
          </div>
        </div>
        <div className="operator">
          <span>{user?.role}</span>
          <strong>{user?.name}</strong>
          <button className="text-action" onClick={handleLogout}>
            <LogOut size={16} />
            退出
          </button>
        </div>
      </header>

      <section className="workspace">
        <aside className="left-rail">
          <Panel title="遥感数据接入" icon={<CloudUpload size={18} />}>
            <label className="upload-box">
              <input
                type="file"
                accept=".hdf5,.h5,.tif,.tiff,.img"
                onChange={(event) => handleFile(event.target.files?.[0])}
              />
              <CloudUpload size={28} />
              <strong>上传 HDF5 / GeoTIFF / IMG 数据</strong>
              <span>正式入口按遥感数据集结构读取，页面指标、分类结果、三维场景和问答上下文都来自后端返回。</span>
            </label>
            <label className="sample-index-field">
              <span>HDF5 样本序号</span>
              <input
                type="number"
                min={0}
                value={sampleIndex}
                onChange={(event) => setSampleIndex(Math.max(0, Number(event.target.value) || 0))}
              />
            </label>
            <button className="secondary-action" onClick={loadDemo} disabled={busy}>
              加载开发示例数据
            </button>
            <button className="secondary-action strong" onClick={loadCropSupervisionSample} disabled={busy}>
              载入 CropSupervision 样本
            </button>
          </Panel>

          <Panel title="地块概况" icon={<Database size={18} />}>
            <div className="stat-list">
              <InfoRow label="数据来源" value={result?.source.filename ?? "未接入"} />
              <InfoRow label="数据格式" value={result?.source.format ?? "等待识别"} />
              <InfoRow label="影像尺寸" value={result ? `${result.source.width} x ${result.source.height}` : "-"} />
              <InfoRow label="网格精度" value={result ? `${result.source.gridSize} x ${result.source.gridSize}` : "-"} />
              <InfoRow label="主作物" value={result?.summary.mainCrop ?? "-"} />
            </div>
          </Panel>

          <Panel title="功能状态" icon={<FileImage size={18} />}>
            <div className="module-list">
              {moduleItems.map((item) => (
                <div className="module-item" key={item.title}>
                  <strong>{item.title}</strong>
                  <span>{item.text}</span>
                </div>
              ))}
            </div>
          </Panel>
        </aside>

        <section className="main-stage">
          <div className="stage-header">
            <div>
              <p>Semantic 3D Field</p>
              <h1>作物长势三维表达</h1>
            </div>
            <span className={busy ? "status busy" : "status"}>{message}</span>
          </div>

          <div className="scene-panel">
            {result ? (
              <FieldScene result={result} selectedCell={selectedCell} onSelectCell={setSelectedCell} />
            ) : (
              <div className="empty-scene">
                <CloudUpload size={40} />
                <strong>等待遥感数据分析结果</strong>
                <span>上传 HDF5 / GeoTIFF / IMG 后，后端会返回分类网格、长势评分、风险区域和三维场景数据。</span>
              </div>
            )}
            {result && (
              <div className="scene-tools">
                <span>拖拽旋转</span>
                <span>滚轮缩放</span>
                <span>点击地块查看指标</span>
              </div>
            )}
          </div>

          <div className="metric-grid">
            {coreMetrics.length ? (
              coreMetrics.map((metric) => (
                <div className="metric-card" key={metric.label}>
                  <span>{metric.icon}</span>
                  <p>{metric.label}</p>
                  <strong>{metric.value}</strong>
                </div>
              ))
            ) : (
              <div className="metric-empty">核心指标将在后端分析完成后显示。</div>
            )}
          </div>
        </section>

        <aside className="right-rail">
          <Panel title="作物分类结果" icon={<BarChart3 size={18} />}>
            {result ? (
              <div className="crop-bars">
                {result.cropStats.map((crop) => (
                  <div className="crop-bar" key={crop.key}>
                    <div>
                      <strong>{crop.name}</strong>
                      <span>{percent(crop.ratio)}</span>
                    </div>
                    <progress value={crop.ratio} max={1} />
                    <small>平均长势 {percent(crop.avgGrowth)} · 预测 {crop.estimatedYieldKg.toFixed(1)} kg</small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">暂无分类结果。</p>
            )}
          </Panel>

          <Panel title="当前选中地块" icon={<MapPinned size={18} />}>
            {selectedCell ? (
              <div className="selected-card">
                <strong>{selectedCell.cropName}</strong>
                <InfoRow label="网格坐标" value={`(${selectedCell.x}, ${selectedCell.z})`} />
                <InfoRow label="长势评分" value={percent(selectedCell.growth)} />
                <InfoRow label="水分估计" value={percent(selectedCell.moisture)} />
                <InfoRow label="异常指数" value={percent(selectedCell.anomaly)} />
              </div>
            ) : (
              <p className="muted">点击三维场景中的地块后，这里会显示该区域的作物类型和长势指标。</p>
            )}
          </Panel>

          <Panel title="风险区域" icon={<Activity size={18} />}>
            {result ? (
              <div className="risk-list">
                {result.abnormalCells.slice(0, 5).map((cell) => (
                  <button key={`${cell.x}-${cell.z}`} onClick={() => setSelectedCell(cell)}>
                    <span>{cell.cropName}</span>
                    <strong>{percent(cell.anomaly)}</strong>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted">暂无风险区域。</p>
            )}
          </Panel>

          <Panel title="智能种植问答" icon={<Bot size={18} />}>
            <div className="chat-window">
              <div className="chat-messages">
                {chatMessages.map((item, index) => (
                  <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}>
                    <p>{item.content}</p>
                    {item.provider && <span>{item.provider}</span>}
                  </div>
                ))}
                {chatBusy && <div className="chat-message assistant">正在生成回答...</div>}
              </div>
              <div className="chat-input">
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="例如：当前低长势区域应该如何处理？"
                />
                <button onClick={submitQuestion} disabled={chatBusy || !question.trim()}>
                  <Send size={16} />
                </button>
              </div>
            </div>
          </Panel>
        </aside>
      </section>
    </main>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <span>{icon}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
