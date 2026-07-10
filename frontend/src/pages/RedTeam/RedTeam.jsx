import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, Play, RefreshCw, ShieldAlert, Target } from 'lucide-react';
import apiClient from '../../services/api';
import { Button, DataTable, EmptyState, GlassCard, MetricCard, StatusBadge } from '../../components/Common/DesignSystem';
import { useToast } from '../../components/Common/Toast';

const RedTeam = () => {
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const { addToast } = useToast();
  const mountedRef = useRef(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    const [reportRes, historyRes] = await Promise.allSettled([
      apiClient.get('/redteam/report'),
      apiClient.get('/redteam/history?limit=100'),
    ]);

    if (!mountedRef.current) return;

    if (reportRes.status === 'fulfilled') {
      setReport(reportRes.value.data);
    } else {
      setReport((current) => current || { total_probes: 0, successful_attacks: 0, regressions: [], by_severity: {}, failed_prompts: [] });
      addToast(reportRes.reason?.response?.data?.detail || 'Failed to load red-team summary.', 'error');
    }

    if (historyRes.status === 'fulfilled') {
      setHistory(historyRes.value.data || []);
    } else {
      setHistory([]);
      addToast(historyRes.reason?.response?.data?.detail || 'Failed to load red-team history.', 'error');
    }

    setLoading(false);
  }, [addToast]);

  useEffect(() => {
    mountedRef.current = true;
    loadData();
    return () => {
      mountedRef.current = false;
    };
  }, [loadData]);

  const runRedTeam = async () => {
    setRunning(true);
    try {
      await apiClient.post('/redteam/run');
      addToast('Red-team probes completed and persisted.', 'success');
      await loadData();
    } catch (error) {
      addToast(error.response?.data?.detail || 'Red-team run failed.', 'error');
    } finally {
      setRunning(false);
    }
  };

  const severityRows = useMemo(() => Object.entries(report?.by_severity || {}), [report]);

  const columns = [
    { key: 'probe', header: 'Probe', render: (row) => <span className="font-mono text-xs text-[#0E1726]">{row.probe}</span> },
    { key: 'category', header: 'Category' },
    { key: 'severity', header: 'Severity', render: (row) => <StatusBadge status={row.severity} /> },
    { key: 'result', header: 'Result', render: (row) => <StatusBadge status={row.result === 'PASS' ? 'success' : 'failed'} /> },
    { key: 'regression_status', header: 'Regression', render: (row) => <StatusBadge status={row.regression_status} /> },
    { key: 'confidence', header: 'Confidence', render: (row) => `${Math.round((row.confidence || 0) * 100)}%` },
    { key: 'timestamp', header: 'Timestamp', render: (row) => row.timestamp || 'N/A' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#0E1726] font-display">Red Team Register</h1>
          <p className="text-sm text-[#475069]">Persistent adversarial probe history, severity trends, and regression status.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={loadData} disabled={loading}><RefreshCw className="w-4 h-4" /> Refresh</Button>
          <Button onClick={runRedTeam} loading={running}><Play className="w-4 h-4" /> Run Probes</Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard title="Total Probes" value={report?.total_probes ?? 0} icon={Target} />
        <MetricCard title="Successful Attacks" value={report?.successful_attacks ?? 0} changeType={report?.successful_attacks ? 'negative' : 'positive'} icon={ShieldAlert} />
        <MetricCard title="Regressions" value={report?.regressions?.length ?? 0} changeType={report?.regressions?.length ? 'negative' : 'positive'} icon={AlertTriangle} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-1" hover={false}>
          <h2 className="text-sm font-bold text-[#0E1726] font-display mb-4">Severity Trend</h2>
          {severityRows.length ? (
            <div className="space-y-3">
              {severityRows.map(([severity, count]) => (
                <div key={severity}>
                  <div className="flex justify-between text-xs font-semibold text-[#475069] mb-1">
                    <span>{severity}</span>
                    <span>{count}</span>
                  </div>
                  <div className="h-2 rounded bg-[#E6E9F0] overflow-hidden">
                    <div className="h-full bg-[#6D28D9]" style={{ width: `${Math.min(100, count * 20)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No severity data" description="Run probes to populate severity history." icon={Activity} />
          )}
        </GlassCard>

        <GlassCard className="lg:col-span-2" hover={false}>
          <h2 className="text-sm font-bold text-[#0E1726] font-display mb-4">Failed Prompts And Successful Attacks</h2>
          {report?.failed_prompts?.length ? (
            <div className="space-y-3">
              {report.failed_prompts.map((item) => (
                <div key={item.id || item.probe} className="rounded-lg border border-rose-200 bg-rose-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs text-[#0E1726]">{item.probe}</span>
                    <StatusBadge status={item.severity} />
                  </div>
                  <p className="mt-2 text-xs text-[#475069]">{item.evidence || 'No evidence payload recorded.'}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No successful attacks" description="Stored probes have not produced a failing red-team result." icon={ShieldAlert} />
          )}
        </GlassCard>
      </div>

      <DataTable
        columns={columns}
        data={history}
        loading={loading}
        emptyMessage="No probe history has been recorded yet."
      />
    </div>
  );
};

export default RedTeam;
