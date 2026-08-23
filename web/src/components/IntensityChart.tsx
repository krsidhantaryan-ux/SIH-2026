import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrackPoint } from "../types";

interface Props {
  track: TrackPoint[];
  selectedIndex: number;
}

export default function IntensityChart({ track, selectedIndex }: Props) {
  const selected = track[selectedIndex];
  const forecastByTime = new Map(
    selected.forecasts.map((forecast) => [forecast.valid_time, forecast.vmax_kt]),
  );
  const data = track.map((point, index) => ({
    time: point.valid_time,
    reference: point.vmax_kt,
    guidance:
      index === selectedIndex ? point.vmax_kt : forecastByTime.get(point.valid_time) ?? null,
  }));

  return (
    <div className="chart-wrap" aria-label="Intensity history chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 14, right: 14, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="#243044" strokeDasharray="3 7" vertical={false} />
          <XAxis
            dataKey="time"
            tickFormatter={formatAxis}
            minTickGap={48}
            tick={{ fill: "#78879d", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 160]}
            ticks={[0, 40, 80, 120, 160]}
            tick={{ fill: "#78879d", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            unit=""
          />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine
            x={selected.valid_time}
            stroke="#e2e8f0"
            strokeDasharray="3 4"
            strokeOpacity={0.5}
          />
          <Line
            type="monotone"
            dataKey="reference"
            name="Best-track reference"
            stroke="#38bdf8"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: "#e0f2fe", stroke: "#0284c7", strokeWidth: 2 }}
          />
          <Line
            type="monotone"
            dataKey="guidance"
            name="Past-only guidance"
            stroke="#fbbf24"
            strokeWidth={2.5}
            strokeDasharray="6 5"
            connectNulls
            dot={{ r: 3, fill: "#fbbf24", strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function formatAxis(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
  });
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span>{formatFull(label)}</span>
      {payload
        .filter((entry: any) => entry.value !== null)
        .map((entry: any) => (
          <strong key={entry.dataKey} style={{ color: entry.color }}>
            {entry.name}: {Number(entry.value).toFixed(0)} kt
          </strong>
        ))}
    </div>
  );
}

function formatFull(value: string): string {
  return `${new Date(value).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })} UTC`;
}
