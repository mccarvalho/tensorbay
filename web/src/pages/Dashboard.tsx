// Executive dashboard — TensorBay big-stat layout + on-brand charts.
// Single call to GET /v1/dashboards/executive returns fleet + capacity +
// commercial + finance rollups; we render headline KPIs plus visualizations.
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts';
import { api } from '../api';
import {
  KpiCard,
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
} from '../components/ui';
import { ChartCard, ThemedTooltip, CHART } from '../components/charts';

interface FleetSummary {
  installed_gpus: number;
  operational_gpus: number;
  available_gpus: number;
  reserved_gpus: number;
  allocated_gpus: number;
  maintenance_gpus: number;
  offline_gpus: number;
  failed_gpus: number;
  failure_rate_pct: number;
}
interface CapacityRow {
  gpu_model: string; physical: number; operational: number;
  reserved: number; allocated: number; available: number; incoming: number;
}
interface CommercialSummary {
  contracted_gpus: number; reserved_gpus: number; active_contracts: number;
  pipeline_gpu_demand: number; weighted_pipeline_gpu_demand: number; open_opportunities: number;
}
interface FinanceSummary {
  mrr: string; arr: string; contracted_arr: string; revenue_backlog: string; weighted_pipeline_mrr: string;
}
interface ExecutiveDashboard {
  fleet: FleetSummary; capacity: CapacityRow[]; commercial: CommercialSummary; finance: FinanceSummary;
}

const fmtInt = (n: number) => n.toLocaleString('en-US');
const fmtMoney = (v: string | number) => {
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};
const fmtMoneyShort = (n: number) => {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['dashboard', 'executive'],
    queryFn: () => api.get<ExecutiveDashboard>('/v1/dashboards/executive'),
  });

  // Derived chart datasets (hooks must run before any early return).
  const fleetPie = useMemo(() => {
    const f = data?.fleet;
    if (!f) return [];
    return [
      { name: 'Available', value: f.available_gpus, color: CHART.cyan },
      { name: 'Reserved', value: f.reserved_gpus, color: CHART.grape },
      { name: 'Allocated', value: f.allocated_gpus, color: CHART.flamingo },
      { name: 'Maintenance', value: f.maintenance_gpus, color: CHART.maintenance },
      { name: 'Offline', value: f.offline_gpus, color: CHART.offline },
    ].filter((s) => s.value > 0);
  }, [data]);

  const financeBar = useMemo(() => {
    const f = data?.finance;
    if (!f) return [];
    return [
      { name: 'MRR', value: Number(f.mrr) },
      { name: 'ARR', value: Number(f.arr) },
      { name: 'Contracted ARR', value: Number(f.contracted_arr) },
      { name: 'Backlog', value: Number(f.revenue_backlog) },
      { name: 'Wtd Pipeline MRR', value: Number(f.weighted_pipeline_mrr) },
    ];
  }, [data]);

  const pipelineBar = useMemo(() => {
    const c = data?.commercial;
    if (!c) return [];
    return [
      { name: 'Pipeline', value: c.pipeline_gpu_demand },
      { name: 'Weighted', value: Math.round(c.weighted_pipeline_gpu_demand) },
      { name: 'Reserved', value: c.reserved_gpus },
      { name: 'Contracted', value: c.contracted_gpus },
    ];
  }, [data]);

  if (isLoading) return <Spinner label="Loading executive overview…" />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <EmptyState title="No data" hint="The executive dashboard returned no payload." />;

  const { fleet, capacity, commercial, finance } = data;
  const hasCapacity = capacity.length > 0;

  return (
    <div className="flex flex-col gap-10">
      <SectionHeader
        eyebrow="OVERVIEW · FY2026"
        title="Executive Control Plane"
        description="Real-time rollup of fleet health, capacity, commercial pipeline, and revenue across the TensorBay GPU estate."
      />

      {/* Finance — headline revenue numbers */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">FINANCE · REVENUE</span>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="MRR" value={fmtMoney(finance.mrr)} accent="cyan" sub="Monthly recurring revenue" />
          <KpiCard label="ARR" value={fmtMoney(finance.arr)} accent="cyan" sub="Annual recurring revenue" />
          <KpiCard label="Contracted ARR" value={fmtMoney(finance.contracted_arr)} accent="grape" sub="Signed contract value" />
          <KpiCard label="Revenue Backlog" value={fmtMoney(finance.revenue_backlog)} accent="grape" sub="Remaining to recognize" />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartCard title="Revenue Composition" hint="USD">
            <BarChart data={financeBar} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid vertical={false} stroke={CHART.grid} />
              <XAxis dataKey="name" tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={{ stroke: CHART.grid }} interval={0} />
              <YAxis tickFormatter={(v) => fmtMoneyShort(Number(v))} tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={false} width={48} />
              <ThemedTooltip valueFormatter={(v) => fmtMoney(v)} />
              <Bar dataKey="value" name="Amount" radius={[6, 6, 0, 0]} fill={CHART.cyan} />
            </BarChart>
          </ChartCard>
          <ChartCard title="Fleet Status Mix" hint={`${fmtInt(fleet.installed_gpus)} installed`}>
            <PieChart>
              <Pie data={fleetPie} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2} stroke="none">
                {fleetPie.map((s) => <Cell key={s.name} fill={s.color} />)}
              </Pie>
              <ThemedTooltip valueFormatter={(v, n) => `${n}: ${fmtInt(v)} GPUs`} />
              <Legend wrapperStyle={{ fontSize: 11, color: CHART.axis }} />
            </PieChart>
          </ChartCard>
        </div>
      </section>

      {/* Fleet — GPU health */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">FLEET · GPU HEALTH</span>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
          <KpiCard label="Installed GPUs" value={fmtInt(fleet.installed_gpus)} accent="white" />
          <KpiCard label="Operational" value={fmtInt(fleet.operational_gpus)} accent="cyan" />
          <KpiCard label="Available" value={fmtInt(fleet.available_gpus)} accent="cyan" />
          <KpiCard label="Reserved" value={fmtInt(fleet.reserved_gpus)} accent="grape" />
          <KpiCard label="Allocated" value={fmtInt(fleet.allocated_gpus)} accent="grape" />
          <KpiCard label="Maintenance" value={fmtInt(fleet.maintenance_gpus)} accent="white" />
          <KpiCard label="Offline" value={fmtInt(fleet.offline_gpus)} accent="white" />
          <KpiCard label="Failure Rate" value={`${fleet.failure_rate_pct.toFixed(1)}%`} accent="flamingo" sub={`${fmtInt(fleet.failed_gpus)} failed units`} />
        </div>
      </section>

      {/* Capacity — per-model stacked bar */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">CAPACITY · BY MODEL</span>
        {hasCapacity ? (
          <ChartCard title="Capacity by GPU Model" hint="Available · Reserved · Allocated (+ incoming)" height={340}>
            <BarChart data={capacity} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid vertical={false} stroke={CHART.grid} />
              <XAxis dataKey="gpu_model" tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={{ stroke: CHART.grid }} interval={0} />
              <YAxis tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={false} width={44} />
              <ThemedTooltip valueFormatter={(v, n) => `${n}: ${fmtInt(v)}`} />
              <Legend wrapperStyle={{ fontSize: 11, color: CHART.axis }} />
              <Bar dataKey="available" stackId="live" name="Available" fill={CHART.cyan} radius={[0, 0, 0, 0]} />
              <Bar dataKey="reserved" stackId="live" name="Reserved" fill={CHART.grape} />
              <Bar dataKey="allocated" stackId="live" name="Allocated" fill={CHART.flamingo} radius={[6, 6, 0, 0]} />
              <Bar dataKey="incoming" name="Incoming" fill={CHART.grapeSoft} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ChartCard>
        ) : (
          <EmptyState title="No capacity records" hint="Register GPU assets in Inventory to populate the capacity view." />
        )}
      </section>

      {/* Commercial — pipeline */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">COMMERCIAL · PIPELINE</span>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <KpiCard label="Active Contracts" value={fmtInt(commercial.active_contracts)} accent="cyan" />
          <KpiCard label="Contracted GPUs" value={fmtInt(commercial.contracted_gpus)} accent="grape" />
          <KpiCard label="Reserved GPUs" value={fmtInt(commercial.reserved_gpus)} accent="grape" />
          <KpiCard label="Open Opportunities" value={fmtInt(commercial.open_opportunities)} accent="flamingo" />
          <KpiCard label="Pipeline Demand" value={fmtInt(commercial.pipeline_gpu_demand)} accent="white" sub="GPUs" />
          <KpiCard label="Weighted Demand" value={fmtInt(Math.round(commercial.weighted_pipeline_gpu_demand))} accent="white" sub="GPUs (weighted)" />
        </div>
        <ChartCard title="GPU Demand vs Commitments" hint="GPUs">
          <BarChart data={pipelineBar} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid horizontal={false} stroke={CHART.grid} />
            <XAxis type="number" tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={{ stroke: CHART.grid }} />
            <YAxis type="category" dataKey="name" tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={false} width={88} />
            <ThemedTooltip valueFormatter={(v) => `${fmtInt(v)} GPUs`} />
            <Bar dataKey="value" name="GPUs" radius={[0, 6, 6, 0]} fill={CHART.grape} />
          </BarChart>
        </ChartCard>
      </section>

      <p className="text-xs text-grape-soft/70">
        Weighted pipeline figures are probability-weighted by opportunity stage. All values are live rollups across the GPU estate.
      </p>
    </div>
  );
}
