import { useNavigate } from "react-router-dom";

export default function ProfilePage() {
  const navigate = useNavigate();

  return (
    <div className="utility-page">
      <header className="app-header">
        <div className="app-logo-text">
          <h1>我的</h1>
          <p>个人中心准备中</p>
        </div>
        <span className="app-badge">Soon</span>
      </header>

      <main className="utility-panel">
        <div className="utility-icon">👤</div>
        <h2>个人中心还在热身</h2>
        <p>这里会放收藏、订阅和浏览记录。现在先给你一个明确落点，不再让底部导航空点。</p>
        <button className="chat-send-btn" onClick={() => navigate("/")}>
          返回首页
        </button>
      </main>

      <nav className="bottom-nav">
        <button className="bottom-nav-item" onClick={() => navigate("/")}>
          <span className="nav-icon">🏠</span>首页
        </button>
        <button className="bottom-nav-item" onClick={() => navigate("/predictions")}>
          <span className="nav-icon">🏆</span>预测
        </button>
        <button className="bottom-nav-item active">
          <span className="nav-icon">👤</span>我的
        </button>
      </nav>
    </div>
  );
}
