export type CropCell = {
  x: number;
  z: number;
  cropId: number;
  crop: string;
  cropName: string;
  growth: number;
  moisture: number;
  anomaly: number;
  height: number;
};

export type CropStat = {
  id: number;
  key: string;
  name: string;
  area: number;
  ratio: number;
  avgGrowth: number;
  estimatedYieldKg: number;
};

export type AnalysisResult = {
  source: {
    filename: string;
    width: number;
    height: number;
    gridSize: number;
    format?: string;
    analysisMode: "demo" | "heuristic" | "dataset-label" | "model-inference";
    labelSource: string;
    sampleIndex: number;
    sampleCount: number;
  };
  summary: {
    avgGrowth: number;
    healthyRatio: number;
    warningRatio: number;
    riskRatio: number;
    estimatedYieldKg: number;
    mainCrop: string;
  };
  cropStats: CropStat[];
  abnormalCells: CropCell[];
  scene: {
    cells: CropCell[];
    cropProfiles: Record<string, { name: string; baseColor: string; healthyColor: string; riskColor: string }>;
  };
  methodology: {
    classification: string;
    growth: string;
    estimatedYield: string;
    modelInference: boolean;
    notice: string;
  };
  advice: string[];
};

export type BackendHealth = {
  status: string;
  service: string;
  modelInference: boolean;
  adviceProvider: "aliyun-dashscope" | "local-fallback";
};

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function login(username: string, password: string) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function fetchDemoAnalysis(): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE}/api/analysis/demo`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function fetchCropSupervisionSample(sampleIndex = 0): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE}/api/analysis/crop-supervision/sample?sample_index=${sampleIndex}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function analyzeImage(file: File): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/analysis/image`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function analyzeDataset(file: File, sampleIndex = 0): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/analysis/dataset?sample_index=${sampleIndex}`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

export async function askAdvice(question: string, analysis: AnalysisResult | null): Promise<{ answer: string; provider: string }> {
  const response = await fetch(`${API_BASE}/api/advice/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, analysis }),
  });
  if (!response.ok) {
    throw new Error(await getErrorText(response));
  }
  return response.json();
}

async function getErrorText(response: Response) {
  try {
    const data = await response.json();
    return data.detail ?? "请求失败";
  } catch {
    return response.statusText || "请求失败";
  }
}
