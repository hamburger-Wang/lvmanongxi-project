"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LockKeyhole, Sprout } from "lucide-react";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("123456");
  const [message, setMessage] = useState("请输入账号进入农业智能分析工作台");
  const [busy, setBusy] = useState(false);

  const handleLogin = async () => {
    setBusy(true);
    setMessage("正在验证登录信息...");
    try {
      const data = await login(username, password);
      localStorage.setItem("agri-user", JSON.stringify({ name: data.name, role: data.role, token: data.token }));
      router.push("/");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-brand">
          <div className="brand-mark">
            <Sprout size={28} />
          </div>
          <div>
            <p>农业智能分析系统</p>
            <h1>作物长势三维可视化平台</h1>
          </div>
        </div>
        <div className="login-copy">
          <strong>本地联调入口</strong>
          <span>当前账号接口用于本地功能联调，正式上线前需要替换为数据库用户、密码哈希和服务端会话认证。</span>
        </div>
        <div className="login-form standalone">
          <label>
            账号
            <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="请输入账号" />
          </label>
          <label>
            密码
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入密码"
              type="password"
            />
          </label>
          <button onClick={handleLogin} disabled={busy}>
            <LockKeyhole size={18} />
            进入系统
          </button>
        </div>
        <p className="login-message">{message}</p>
      </section>
    </main>
  );
}
