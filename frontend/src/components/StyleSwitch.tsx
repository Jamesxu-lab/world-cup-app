import { useAppStore } from "../store/useAppStore";

const STYLES = [
  { key: "formal", emoji: "📰", label: "正经复盘" },
  { key: "funny", emoji: "😂", label: "段子手" },
  { key: "tactical", emoji: "📋", label: "战术党" },
] as const;

interface Props {
  onSwitch?: (style: string) => void;
}

export default function StyleSwitch({ onSwitch }: Props) {
  const currentStyle = useAppStore((s) => s.currentStyle);
  const setStyle = useAppStore((s) => s.setStyle);

  const handleSwitch = (key: string) => {
    setStyle(key as "formal" | "funny" | "tactical");
    onSwitch?.(key);
  };

  return (
    <div className="style-switcher">
      {STYLES.map((s) => (
        <button
          key={s.key}
          className={`style-tab ${s.key} ${currentStyle === s.key ? "active" : ""}`}
          onClick={() => handleSwitch(s.key)}
        >
          <span className="emoji">{s.emoji}</span>
          <span className="label">{s.label}</span>
        </button>
      ))}
    </div>
  );
}
