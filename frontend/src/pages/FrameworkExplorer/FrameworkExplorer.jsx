import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileCheck2, Filter, RefreshCw, ShieldCheck } from 'lucide-react';
import apiClient from '../../services/api';
import { Button, DataTable, GlassCard, MetricCard, StatusBadge, inputStyles, labelStyles } from '../../components/Common/DesignSystem';
import { useToast } from '../../components/Common/Toast';

const frameworks = ['SOC2', 'ISO27001', 'HIPAA', 'GDPR', 'PCI_DSS', 'NIST'];

const FrameworkExplorer = () => {
  const [framework, setFramework] = useState('');
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const mountedRef = useRef(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const suffix = framework ? `?framework=${encodeURIComponent(framework)}` : '';
      const response = await apiClient.get(`/compliance/framework-explorer${suffix}`);
      if (mountedRef.current) setPayload(response.data);
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to load framework explorer.', 'error');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [addToast, framework]);

  useEffect(() => {
    mountedRef.current = true;
    loadData();
    return () => {
      mountedRef.current = false;
    };
  }, [loadData]);

  const controls = payload?.controls || [];
  const averageScore = useMemo(() => {
    const scored = controls.filter((item) => typeof item.score === 'number');
    if (!scored.length) return 'N/A';
    return Math.round(scored.reduce((total, item) => total + item.score, 0) / scored.length);
  }, [controls]);

  const columns = [
    { key: 'framework', header: 'Framework' },
    { key: 'control_id', header: 'Control', render: (row) => <span className="font-mono text-xs text-[#0E1726]">{row.control_id}</span> },
    { key: 'title', header: 'Title' },
    { key: 'score', header: 'Score', render: (row) => row.score ?? 'N/A' },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'risk', header: 'Risk', render: (row) => <StatusBadge status={row.risk} /> },
    { key: 'evidence', header: 'Evidence', render: (row) => row.evidence?.length || 0 },
    { key: 'timestamp', header: 'Timestamp', render: (row) => row.timestamp || 'N/A' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#0E1726] font-display">Framework Explorer</h1>
          <p className="text-sm text-[#475069]">Control-level evidence, scores, risk, audit links, policies, and documents.</p>
        </div>
        <Button variant="secondary" onClick={loadData} disabled={loading}><RefreshCw className="w-4 h-4" /> Refresh</Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard title="Average Score" value={averageScore} icon={ShieldCheck} />
        <MetricCard title="Controls" value={controls.length} icon={FileCheck2} />
        <MetricCard title="Score Changes" value={payload?.score_changes?.length ?? 0} icon={Filter} />
      </div>

      <GlassCard hover={false}>
        <div className="max-w-xs">
          <label className={labelStyles}>Framework</label>
          <select className={inputStyles} value={framework} onChange={(event) => setFramework(event.target.value)}>
            <option value="">All frameworks</option>
            {frameworks.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
      </GlassCard>

      <DataTable
        columns={columns}
        data={controls}
        loading={loading}
        emptyMessage="No framework controls or evidence are available for this tenant yet."
      />

      <GlassCard hover={false}>
        <h2 className="text-sm font-bold text-[#0E1726] font-display mb-4">Evidence Detail</h2>
        <div className="space-y-3">
          {controls.flatMap((control) => (control.evidence || []).map((item) => ({ control, item }))).slice(0, 20).map(({ control, item }) => (
            <div key={`${control.control_id}-${item.evidence_hash}-${item.created_at}`} className="rounded-lg border border-[#E6E9F0] bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-[#0E1726]">{control.control_id}</span>
                <StatusBadge status={item.source_type} />
              </div>
              <p className="mt-2 text-sm text-[#475069]">{item.reason}</p>
              <p className="mt-2 text-xs font-mono text-[#6B7488]">{item.evidence_hash}</p>
            </div>
          ))}
          {!controls.some((control) => control.evidence?.length) && (
            <p className="text-sm text-[#6B7488]">No evidence links exist yet for the selected framework.</p>
          )}
        </div>
      </GlassCard>
    </div>
  );
};

export default FrameworkExplorer;
