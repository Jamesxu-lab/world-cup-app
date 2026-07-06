import { useState, useRef, useEffect } from "react";
import { chatWithAIStream, type ChatMessage } from "../api/client";

interface Props {
  matchId: string;
}

export default function ChatPanel({ matchId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || sending) return;

    setInput("");
    const userMsg: ChatMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    setStreamingText("");

    let assistantText = "";
    await chatWithAIStream(
      matchId,
      question,
      messages,
      // onToken: 逐 token 追加
      (token) => {
        assistantText += token;
        setStreamingText((prev) => prev + token);
      },
      // onDone: 流结束，将完整文本加入消息列表
      () => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistantText || "这场比赛暂时没有更多可回答的信息。" },
        ]);
        setStreamingText("");
        setSending(false);
      },
      // onError
      () => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "抱歉，回答出了点问题，请重试。" },
        ]);
        setStreamingText("");
        setSending(false);
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = ["本场最佳球员是谁？", "比赛的转折点是什么？", "双方战术有什么不同？"];

  return (
    <div className="chat-panel">
      {/* 头部 */}
      <div className="chat-panel-header">
        <h3>💬 追问这场比赛</h3>
        <p>AI 球搭子为你解答比赛的任何细节</p>
      </div>

      {/* 消息列表 */}
      <div className="chat-messages">
        {messages.length === 0 && !sending && (
          <div className="chat-empty">
            <div className="icon">💬</div>
            <p>关于这场比赛，你想了解什么？</p>
            <div className="chat-suggestions">
              {suggestions.map((q) => (
                <button
                  key={q}
                  className="chat-suggestion-btn"
                  onClick={() => {
                    setInput(q);
                    inputRef.current?.focus();
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "chat-msg-user" : "chat-msg-assistant"}>
            <div className="bubble">{msg.content}</div>
          </div>
        ))}

        {/* 流式输出中 */}
        {sending && streamingText && (
          <div className="chat-msg-assistant">
            <div className="bubble">{streamingText}</div>
          </div>
        )}

        {/* 等待首 token */}
        {sending && !streamingText && (
          <div className="chat-msg-assistant">
            <div className="bubble">
              <div className="chat-typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 输入栏 */}
      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="追问比赛细节..."
          maxLength={500}
          disabled={sending}
          className="chat-input"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || sending}
          className="chat-send-btn"
        >
          发送
        </button>
      </div>
    </div>
  );
}
