import {
  ResponsiveContainer, PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LineChart, Line, Area, ComposedChart,
} from 'recharts';
import { fmtMoney } from '@shared/utils';
import { PAL, BAR_FILL, GRID, ORDER_COLOR, REVENUE_COLOR } from './palette';

const MONO = { fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#8e8b80' };

function Empty() {
  return <div className="flex items-center justify-center h-full text-ink-3 font-mono text-[11px]">No data</div>;
}

// Doughnut (cutout 58%, legend right) — items: [{label, count}]
export function DoughnutChart({ items }) {
  if (!items?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={items} dataKey="count" nameKey="label" innerRadius="58%" outerRadius="86%" stroke="#fff" strokeWidth={2}>
          {items.map((_, i) => <Cell key={i} fill={PAL[i % PAL.length]} />)}
        </Pie>
        <Tooltip contentStyle={{ fontSize: 11 }} />
        <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" iconSize={8}
          wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono' }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// Vertical bars — labels: string[], data: number[]
export function BarsChart({ labels, data }) {
  if (!labels?.length) return <Empty />;
  const rows = labels.map((l, i) => ({ label: l, value: data[i] }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} margin={{ top: 6, right: 6, left: -14, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tick={MONO} />
        <YAxis tickLine={false} axisLine={false} tick={MONO} allowDecimals={false} width={32} />
        <Tooltip cursor={{ fill: 'rgba(0,0,0,0.04)' }} contentStyle={{ fontSize: 11 }} />
        <Bar dataKey="value" fill={BAR_FILL} radius={[3, 3, 0, 0]} maxBarSize={30} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Horizontal bars
export function HBarsChart({ labels, data }) {
  if (!labels?.length) return <Empty />;
  const rows = labels.map((l, i) => ({ label: l, value: data[i] }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke={GRID} />
        <XAxis type="number" tickLine={false} axisLine={false} tick={MONO} allowDecimals={false} />
        <YAxis type="category" dataKey="label" tickLine={false} axisLine={false} tick={MONO} width={90} />
        <Tooltip cursor={{ fill: 'rgba(0,0,0,0.04)' }} contentStyle={{ fontSize: 11 }} />
        <Bar dataKey="value" fill={BAR_FILL} radius={[0, 3, 3, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Dual-axis Orders (left) + Revenue (right) area/line — rows: [{date, count, revenue}]
export function SalesOrdersChart({ rows }) {
  if (!rows?.length) return <Empty />;
  const data = rows.map((r) => {
    const d = new Date(String(r.date).replace(' ', 'T'));
    const label = isNaN(d) ? r.date : `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { label, orders: r.count || 0, revenue: r.revenue || 0 };
  });
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="gOrders" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ORDER_COLOR} stopOpacity={0.22} />
            <stop offset="100%" stopColor={ORDER_COLOR} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gRevenue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={REVENUE_COLOR} stopOpacity={0.18} />
            <stop offset="100%" stopColor={REVENUE_COLOR} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tick={MONO} interval="preserveStartEnd" />
        <YAxis yAxisID="y" tickLine={false} axisLine={false} tick={{ ...MONO, fill: ORDER_COLOR }} allowDecimals={false} width={32} />
        <YAxis yAxisID="y1" orientation="right" tickLine={false} axisLine={false}
          tick={{ ...MONO, fill: REVENUE_COLOR }} width={44} tickFormatter={(v) => '$' + fmtMoney(v)} />
        <Tooltip contentStyle={{ fontSize: 11 }}
          formatter={(v, n) => (n === 'revenue' ? [`$${fmtMoney(v)}`, 'Revenue'] : [v, 'Orders'])} />
        <Area yAxisID="y" type="monotone" dataKey="orders" stroke={ORDER_COLOR} strokeWidth={2} fill="url(#gOrders)" dot={false} />
        <Line yAxisID="y1" type="monotone" dataKey="revenue" stroke={REVENUE_COLOR} strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
