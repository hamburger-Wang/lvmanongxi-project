"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity, BarChart3, Bot, CheckCircle2, CloudUpload, Database, FileArchive,
  Layers3, Leaf, LogOut, MapPinned, RefreshCw, Send, Server, ShieldCheck,
  Sparkles, Sprout, TrendingUp, TriangleAlert,
} from "lucide-react";
import FieldScene from "@/components/FieldScene";
import {
  analyzeDataset, askAdvice, fetchBackendHealth, fetchCropSupervisionSample,
  fetchDemoAnalysis, type AnalysisResult, type BackendHealth, type CropCell,
} from "@/lib/api";

type User = { name: string; role: string; token: string };
type ChatMessage = { role: "user" | "assistant"; content: string; provider?: string };
type RightView = "analysis" | "assistant";
type ColorMode = "growth" | "crop";

const percent = (value?: number) => `${Math.round((value ?? 0) * 100)}%`;
const analysisModeLabels: Record<AnalysisResult["source"]["analysisMode"], string> = {
  demo: "演示数据",
  heuristic: "规则分析",
  "dataset-label": "数据集标注",
  "model-inference": "模型推理",
};

export default function DashboardPage() {
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedCell, setSelectedCell] = useState<CropCell | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("等待上传单样本遥感数据。");
  const [sampleIndex, setSampleIndex] = useState(0);
  const [colorMode, setColorMode] = useState<ColorMode>("growth");
  const [rightView, setRightView] = useState<RightView>("analysis");
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [question, setQuestion] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "分析完成后，我会把当前分类、长势和风险区域作为问答上下文。", provider: "system" },
  ]);

  const checkBackend = useCallback(async () => {
    try {
      setHealth(await fetchBackendHealth());
      setHealthError(false);
    } catch {
      setHealth(null);
      setHealthError(true);
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem("agri-user");
    if (!stored) {
      router.replace("/login");
      return;
    }
    try {
      setUser(JSON.parse(stored));
      setAuthChecked(true);
      void checkBackend();
    } catch {
      localStorage.removeItem("agri-user");
      router.replace("/login");
    }
  }, [checkBackend, router]);

  const handleLogout = () => {
    localStorage.removeItem("agri-user");
    router.replace("/login");
  };

  const acceptResult = (data: AnalysisResult, successMessage: string) => {
    setResult(data);
    setSelectedCell(null);
    setColorMode("growth");
    setRightView("analysis");
    setMessage(successMessage);
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setMessage(`正在读取 ${file.name} 的第 ${sampleIndex} 个样本...`);
    try {
      acceptResult(await analyzeDataset(file, sampleIndex), "分析完成，界面已使用本次后端结果刷新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "遥感数据分析失败");
    } finally {
      setBusy(false);
    }
  };

  const loadDemo = async () => {
    setBusy(true);
    setMessage("正在加载后端生成的开发示例...");
    try {
      acceptResult(await fetchDemoAnalysis(), "开发示例已加载，数据并非实测结果。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "示例数据加载失败");
    } finally {
      setBusy(false);
    }
  };

  const loadCropSupervisionSample = async () => {
    setBusy(true);
    setMessage(`正在读取服务器本地 CropSupervision 的第 ${sampleIndex} 个样本...`);
    try {
      acceptResult(await fetchCropSupervisionSample(sampleIndex), "已读取 CropSupervision 样本；分类来自 truth 标签，不是模型预测。");
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
      setChatMessages((items) => [...items, {
        role: "assistant",
        content: error instanceof Error ? error.message : "问答接口调用失败",
        provider: "error",
      }]);
    } finally {
      setChatBusy(false);
    }
  };

  const coreMetrics = useMemo(() => {
    if (!result) return [];
    return [
      { label: "归一化平均长势", value: percent(result.summary.avgGrowth), icon: <Leaf size={18} /> },
      { label: "健康区域", value: percent(result.summary.healthyRatio), icon: <ShieldCheck size={18} /> },
      { label: "风险区域", value: percent(result.summary.riskRatio), icon: <TriangleAlert size={18} /> },
      { label: "规则估算产量", value: `${result.summary.estimatedYieldKg.toFixed(1)} kg`, icon: <TrendingUp size={18} /> },
    ];
  }, [result]);

  if (!authChecked) return <main className="loading-shell">正在进入系统...</main>;

  return (
    <main className="dashboard-shell">
      <header className="topbar compact">
        <div className="brand">
          <div className="brand-mark"><Sprout size={24} /></div>
          <div><p>农业智能分析系统</p><strong>作物长势三维可视化平台</strong></div>
        </div>
        <div className="topbar-status">
          <button className={`connection-chip ${healthError ? "offline" : ""}`} onClick={checkBackend} title="重新检测后端">
            <span className="connection-dot" />
            {healthError ? "后端离线" : health ? "后端已连接" : "检测后端"}
            <RefreshCw size={13} />
          </button>
          <div className="operator">
            <span>{user?.role}</span><strong>{user?.name}</strong>
            <button className="icon-action" onClick={handleLogout} title="退出登录" aria-label="退出登录"><LogOut size={17} /></button>
          </div>
        </div>
      </header>

      <section className="workspace">
        <aside className="left-rail">
          <Panel title="遥感数据接入" icon={<CloudUpload size={18} />} eyebrow="DATA INPUT">
            <label className="upload-box">
              <input
                type="file"
                accept=".hdf5,.h5,.tif,.tiff,.img"
                onChange={(event) => {
                  void handleFile(event.target.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
              <FileArchive size={28} />
              <strong>{busy ? "后端正在处理" : "选择单样本数据文件"}</strong>
              <span>支持 HDF5、GeoTIFF、IMG；建议先使用已切分的小样本。</span>
            </label>
            <label className="sample-index-field">
              <span>文件内样本序号</span>
              <input type="number" min={0} value={sampleIndex} onChange={(event) => setSampleIndex(Math.max(0, Number(event.target.value) || 0))} />
            </label>
            <div className="button-stack">
              <button className="secondary-action strong" onClick={loadCropSupervisionSample} disabled={busy}><Database size={16} />读取服务器样本</button>
              <button className="secondary-action" onClick={loadDemo} disabled={busy}><Sparkles size={16} />加载开发示例</button>
            </div>
          </Panel>

          <Panel title="运行状态" icon={<Server size={18} />} eyebrow="SERVICE STATUS">
            <div className="service-list">
              <ServiceRow label="Web API" ready={Boolean(health)} value={health ? "正常" : "未连接"} />
              <ServiceRow label="智能问答" ready={health?.adviceProvider === "aliyun-dashscope"} value={health?.adviceProvider === "aliyun-dashscope" ? "阿里云" : "本地兜底"} />
              <ServiceRow label="模型推理" ready={Boolean(health?.modelInference)} value="尚未接入" />
            </div>
          </Panel>

          <Panel title="数据档案" icon={<Database size={18} />} eyebrow="DATA PROFILE">
            <div className="stat-list">
              <InfoRow label="文件" value={result?.source.filename ?? "未接入"} />
              <InfoRow label="格式" value={result?.source.format ?? "-"} />
              <InfoRow label="原始尺寸" value={result ? `${result.source.width} x ${result.source.height}` : "-"} />
              <InfoRow label="场景网格" value={result ? `${result.source.gridSize} x ${result.source.gridSize}` : "-"} />
              <InfoRow label="样本位置" value={result ? `${result.source.sampleIndex + 1} / ${result.source.sampleCount}` : "-"} />
              <InfoRow label="标签来源" value={result?.source.labelSource ?? "-"} />
            </div>
          </Panel>
        </aside>

        <section className="main-stage">
          <div className="stage-header">
            <div>
              <div className="title-row">
                <h1>作物长势三维表达</h1>
                {result && <span className={`mode-badge mode-${result.source.analysisMode}`}>{analysisModeLabels[result.source.analysisMode]}</span>}
              </div>
              <p>基于分类网格的语义场景，可切换查看长势风险与作物类别。</p>
            </div>
            <span className={busy ? "status busy" : "status"}>{message}</span>
          </div>

          <div className="scene-toolbar">
            <div className="segmented-control" aria-label="三维场景着色方式">
              <button className={colorMode === "growth" ? "active" : ""} onClick={() => setColorMode("growth")}><Activity size={15} />长势风险</button>
              <button className={colorMode === "crop" ? "active" : ""} onClick={() => setColorMode("crop")}><Layers3 size={15} />作物分类</button>
            </div>
            <div className="scene-legend">
              {colorMode === "growth" ? <>
                <Legend color="#2f7e43" label="健康" /><Legend color="#8aa64a" label="关注" /><Legend color="#bb553f" label="风险" />
              </> : result ? result.cropStats.slice(0, 4).map((crop) => (
                <Legend key={crop.key} color={result.scene.cropProfiles[crop.key]?.baseColor ?? "#727d72"} label={crop.name} />
              )) : <span className="legend-empty">等待分类结果</span>}
            </div>
          </div>

          <div className="scene-panel">
            {result ? <FieldScene result={result} selectedCell={selectedCell} colorMode={colorMode} onSelectCell={setSelectedCell} /> : (
              <div className="empty-scene"><CloudUpload size={40} /><strong>等待遥感数据分析结果</strong><span>上传文件后，后端返回分类网格与指标，浏览器只负责展示。</span></div>
            )}
            {result && <div className="scene-hint">拖拽旋转 · 滚轮缩放 · 点击地块查看指标</div>}
          </div>

          <div className="metric-grid">
            {coreMetrics.length ? coreMetrics.map((metric) => (
              <div className="metric-card" key={metric.label}><span>{metric.icon}</span><div><p>{metric.label}</p><strong>{metric.value}</strong></div></div>
            )) : <div className="metric-empty">核心指标将在后端分析完成后显示。</div>}
          </div>

          {result && <section className="methodology-strip">
            <div className="methodology-heading"><CheckCircle2 size={18} /><div><strong>本次结果的计算依据</strong><span>页面展示的不是写死数据</span></div></div>
            <MethodItem label="分类" value={result.methodology.classification} />
            <MethodItem label="长势" value={result.methodology.growth} />
            <MethodItem label="产量" value={result.methodology.estimatedYield} />
          </section>}
        </section>

        <aside className="right-rail">
          <div className="side-tabs">
            <button className={rightView === "analysis" ? "active" : ""} onClick={() => setRightView("analysis")}><BarChart3 size={16} />分析结果</button>
            <button className={rightView === "assistant" ? "active" : ""} onClick={() => setRightView("assistant")}><Bot size={16} />智能问答</button>
          </div>

          {rightView === "analysis" ? <>
            <Panel title="作物分类" icon={<BarChart3 size={18} />} eyebrow="CLASSIFICATION">
              {result ? <div className="crop-bars">{result.cropStats.map((crop) => (
                <div className="crop-bar" key={crop.key}><div><strong>{crop.name}</strong><span>{percent(crop.ratio)}</span></div><progress value={crop.ratio} max={1} /><small>网格 {crop.area} · 平均长势 {percent(crop.avgGrowth)}</small></div>
              ))}</div> : <p className="muted">暂无分类结果。</p>}
            </Panel>

            <Panel title="当前地块" icon={<MapPinned size={18} />} eyebrow="SELECTED CELL">
              {selectedCell ? <div className="selected-card">
                <div className="selected-title"><strong>{selectedCell.cropName}</strong><span>({selectedCell.x}, {selectedCell.z})</span></div>
                <InfoRow label="归一化长势" value={percent(selectedCell.growth)} />
                <InfoRow label="水分代理指标" value={percent(selectedCell.moisture)} />
                <InfoRow label="异常指数" value={percent(selectedCell.anomaly)} />
              </div> : <p className="muted">点击三维场景中的地块查看局部指标。</p>}
            </Panel>

            <Panel title="高风险区域" icon={<Activity size={18} />} eyebrow="RISK CELLS">
              {result ? <div className="risk-list">{result.abnormalCells.slice(0, 6).map((cell) => (
                <button key={`${cell.x}-${cell.z}`} className={selectedCell?.x === cell.x && selectedCell?.z === cell.z ? "active" : ""} onClick={() => setSelectedCell(cell)}>
                  <span>{cell.cropName}<small>({cell.x}, {cell.z})</small></span><strong>{percent(cell.anomaly)}</strong>
                </button>
              ))}</div> : <p className="muted">暂无风险区域。</p>}
            </Panel>

            {result && <Panel title="规则建议" icon={<Leaf size={18} />} eyebrow="SYSTEM ADVICE"><ul className="advice-list">{result.advice.map((item) => <li key={item}>{item}</li>)}</ul></Panel>}
          </> : (
            <Panel title="智能种植问答" icon={<Bot size={18} />} eyebrow="AGRI ASSISTANT">
              <div className="assistant-context"><span>上下文</span><strong>{result ? result.source.filename : "尚无分析结果"}</strong><small>{health?.adviceProvider === "aliyun-dashscope" ? "阿里云 DashScope" : "本地兜底回答"}</small></div>
              <div className="chat-window">
                <div className="chat-messages">
                  {chatMessages.map((item, index) => <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}><p>{item.content}</p>{item.provider && <span>{item.provider}</span>}</div>)}
                  {chatBusy && <div className="chat-message assistant">正在生成回答...</div>}
                </div>
                <div className="chat-input"><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="例如：当前低长势区域应该如何复核？" /><button onClick={submitQuestion} disabled={chatBusy || !question.trim()} title="发送问题" aria-label="发送问题"><Send size={16} /></button></div>
              </div>
            </Panel>
          )}
        </aside>
      </section>
    </main>
  );
}

function Panel({ title, icon, eyebrow, children }: { title: string; icon: React.ReactNode; eyebrow?: string; children: React.ReactNode }) {
  return <section className="panel"><div className="panel-title"><span>{icon}</span><div>{eyebrow && <small>{eyebrow}</small>}<h2>{title}</h2></div></div>{children}</section>;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return <div className="info-row"><span>{label}</span><strong title={value}>{value}</strong></div>;
}

function ServiceRow({ label, value, ready }: { label: string; value: string; ready: boolean }) {
  return <div className="service-row"><span className={ready ? "service-dot ready" : "service-dot"} /><strong>{label}</strong><small>{value}</small></div>;
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="legend-item"><i style={{ backgroundColor: color }} />{label}</span>;
}

function MethodItem({ label, value }: { label: string; value: string }) {
  return <div className="method-item"><span>{label}</span><strong>{value}</strong></div>;
}
