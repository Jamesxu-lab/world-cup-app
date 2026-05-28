import type { NarrativeCard } from "../api/client";

interface Props {
  card: NarrativeCard;
  isLast: boolean;
}

const CARD_TYPE_META: Record<string, { icon: string; label: string }> = {
  opening: { icon: "🎬", label: "开篇" },
  key_moment: { icon: "⚡", label: "关键时刻" },
  player_spotlight: { icon: "⭐", label: "球员聚焦" },
  tactical: { icon: "📋", label: "战术解读" },
  data_story: { icon: "📊", label: "数据故事" },
  closing: { icon: "🌅", label: "收尾" },
};

export default function NarrativeCardView({ card, isLast }: Props) {
  const meta = CARD_TYPE_META[card.card_type] || { icon: "📌", label: card.card_type };

  return (
    <div className={`article-section${isLast ? " last-section" : ""}`}>
      <span className={`section-badge type-${card.card_type}`}>
        <span className="badge-dot" />
        {meta.icon} {meta.label}
      </span>
      <h3 className="section-heading">{card.title}</h3>
      <div className="section-body">
        <p>{card.content}</p>
      </div>
    </div>
  );
}
