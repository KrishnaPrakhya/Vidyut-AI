"use client";

interface TimelineScrubberProps {
  currentTick: number;
  totalTicks?: number;
  isPlaying: boolean;
  speed: number;
  clockTime: string;
  onSeek: (tick: number) => void;
  onTogglePlay: () => void;
  onSpeedChange: (speed: number) => void;
}

export default function TimelineScrubber({
  currentTick,
  totalTicks = 96,
  isPlaying,
  speed,
  clockTime,
  onSeek,
  onTogglePlay,
  onSpeedChange,
}: TimelineScrubberProps) {
  const speeds = [1, 2, 4, 8];

  return (
    <div className="timeline-scrubber">
      <button
        type="button"
        onClick={onTogglePlay}
        className="secondary"
        style={{ minWidth: 90 }}
      >
        {isPlaying ? "⏸ Pause" : "▶ Play"}
      </button>

      <div style={{ font: "700 16px monospace", minWidth: 80 }}>
        {clockTime || "00:00"}
      </div>

      <input
        type="range"
        min={0}
        max={totalTicks - 1}
        value={currentTick}
        onChange={(e) => onSeek(Number(e.target.value))}
        className="timeline-slider"
      />

      <div style={{ font: "700 11px monospace", color: "var(--muted)" }}>
        TICK {currentTick + 1}/{totalTicks}
      </div>

      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <span style={{ font: "700 9px monospace", color: "var(--muted)", marginRight: 4 }}>SPEED:</span>
        {speeds.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSpeedChange(s)}
            style={{
              minHeight: 28,
              padding: "0 8px",
              fontSize: 11,
              background: speed === s ? "var(--ink)" : "white",
              color: speed === s ? "var(--green)" : "var(--ink)",
              border: "1px solid var(--line)",
            }}
          >
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
}
