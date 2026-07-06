import { useNavigate } from "react-router-dom";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="utility-page">
      <header className="app-header">
        <button className="prediction-back" onClick={() => navigate("/")}>←</button>
        <div className="app-logo-text">
          <h1>页面走丢了</h1>
          <p>这个链接暂时没有对应内容</p>
        </div>
        <span className="app-badge">404</span>
      </header>

      <main className="utility-panel">
        <div className="utility-icon">⚽</div>
        <h2>这条进攻路线越位了</h2>
        <p>链接可能已经失效，或者路径写错了。可以回到首页继续看战报，也可以直接查看冠军预测。</p>
        <div className="utility-actions">
          <button className="chat-send-btn" onClick={() => navigate("/")}>
            返回首页
          </button>
          <button className="chat-send-btn secondary" onClick={() => navigate("/predictions")}>
            查看预测
          </button>
        </div>
      </main>
    </div>
  );
}
