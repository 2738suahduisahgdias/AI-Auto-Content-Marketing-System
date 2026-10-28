import { Card } from "@/components/ui";

interface TrendChartProps {
  title: string;
  description: string;
  labels: string[];
  bars?: number[];
  line: number[];
  barLabel?: string;
  lineLabel: string;
  format?: "number" | "percent";
  compact?: boolean;
}

export function TrendChart({ title, description, labels, bars, line, barLabel, lineLabel, format = "number", compact = false }: TrendChartProps) {
  const width = 760;
  const height = compact ? 180 : 220;
  const top = 20;
  const bottom = height - 35;
  const left = 52;
  const right = width - 22;
  const values = [...(bars || []), ...line];
  const max = Math.max(...values, 1) * 1.12;
  const step = (right - left) / Math.max(labels.length, 1);
  const x = (index: number) => left + step * index + step / 2;
  const y = (value: number) => bottom - (value / max) * (bottom - top);
  const points = line.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  const formatValue = (value: number) => format === "percent" ? `${value.toFixed(1)}%` : new Intl.NumberFormat("zh-CN", { notation: value >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value);

  return <Card className={`trend-card${compact ? " compact" : ""}`}><div className="trend-card-head"><div><h3>{title}</h3><p>{description}</p></div><div className="trend-legend">{bars && <span><i className="bar" />{barLabel}</span>}<span><i className="line" />{lineLabel}</span></div></div><svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}，模拟趋势图`}>
    {[0, 1, 2, 3].map(index => { const ratio = index / 3; const gridY = bottom - ratio * (bottom - top); return <g key={index}><line x1={left} x2={right} y1={gridY} y2={gridY} className="trend-grid-line" /><text x={left - 8} y={gridY + 4} textAnchor="end" className="trend-axis-label">{formatValue(max * ratio / 1.12)}</text></g>; })}
    {bars?.map((value, index) => <rect key={index} x={x(index) - Math.min(15, step * .28)} y={y(value)} width={Math.min(30, step * .56)} height={Math.max(1, bottom - y(value))} rx={3} className="trend-bar"><title>{labels[index]}：{formatValue(value)}</title></rect>)}
    <polyline points={points} className="trend-line" />
    {line.map((value, index) => <circle key={index} cx={x(index)} cy={y(value)} r={index === line.length - 1 ? 4 : 2.5} className="trend-point"><title>{labels[index]}：{formatValue(value)}</title></circle>)}
    {labels.map((label, index) => (labels.length <= 8 || index % 2 === 0 || index === labels.length - 1) && <text key={label} x={x(index)} y={height - 12} textAnchor="middle" className="trend-axis-label">{label}</text>)}
  </svg></Card>;
}
