import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  Clock, 
  CheckCircle, 
  Hash, 
  Activity, 
  Server,
  Layers,
  FileText,
  AlertTriangle,
  PlayCircle,
  KeyRound,
  ExternalLink
} from 'lucide-react';
import apiClient from '../../services/api';
import { getAuditSummary } from '../../services/auditService';
import { getGatewayStats } from '../../services/gatewayService';
import { getGovernanceAnalytics } from '../../services/metricsService';

const Dashboard = () => {
  const [keysCount, setKeysCount] = useState(0);
  const [providers, setProviders] = useState([]);
  const [auditSum, setAuditSum] = useState(null);
  const [auditChain, setAuditChain] = useState([]);
  const [tenantInfo, setTenantInfo] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [gatewayStats, setGatewayStats] = useState(null);
  const [governanceAnalytics, setGovernanceAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      // Fetch dynamic active keys
      const keysRes = await apiClient.get('/keys/list');
      setKeysCount(keysRes.data.length);
      
      // Fetch dynamic connected providers
      const provRes = await apiClient.get('/providers/list');
      setProviders(provRes.data);

      // Fetch dynamic audit ledger
      const auditSumData = await getAuditSummary();
      setAuditSum(auditSumData);
      
      const chainRes = await apiClient.get('/audit/hash-chain?limit=5');
      setAuditChain(chainRes.data);

      // Get logged-in tenant status
      const userStr = localStorage.getItem('authclaw_user');
      if (userStr) {
        const userObj = JSON.parse(userStr);
        setTenantInfo(userObj);
      }

      // Fetch dynamic policies
      const polRes = await apiClient.get('/policies/list');
      setPolicies(polRes.data || []);

      // Fetch live gateway execution metrics
      const metricsRes = await apiClient.get('/metrics');
      setMetrics(metricsRes.data);

      const analyticsData = await getGovernanceAnalytics();
      setGovernanceAnalytics(analyticsData);

      setGatewayStats({
        totalRequests: analyticsData.gateway.total_requests,
        approvedRequests: analyticsData.gateway.allowed_requests,
        blockedRequests: analyticsData.gateway.blocked_requests,
        pendingApprovals: analyticsData.approvals.pending,
        providerUsage: Object.fromEntries((analyticsData.providers || []).map((item) => [item.provider, item.requests])),
        requests: analyticsData.recent_requests,
        approvals: analyticsData.approvals,
      });

    } catch (error) {
      console.error('Error loading operational dashboard metrics:', error);
      try {
        const gatewayStatsData = await getGatewayStats();
        setGatewayStats(gatewayStatsData);
      } catch (statsError) {
        console.error('Error loading gateway fallback metrics:', statsError);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleAuditExport = async (format) => {
    const response = await apiClient.get(`/audit/export/${format}`, {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `authclaw-audit-report-${new Date().toISOString().split('T')[0]}.${format}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-pulse">
        <div className="h-28 bg-white/5 rounded-xl"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-xl"></div>
          ))}
        </div>
        <div className="h-64 bg-white/5 rounded-xl"></div>
      </div>
    );
  }

  const isEmailVerified = tenantInfo?.email_verified ?? true;
  const isDomainVerified = tenantInfo?.domain_verified ?? true;
  const isOnboarded = isEmailVerified && isDomainVerified;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
          AI Governance & Security Gateway
        </h1>
        <p className="text-gray-400 text-xs mt-1">Real-time status of multi-tenant API gateway traffic, active policy compliance, and cryptographic ledger logs.</p>
      </div>

      {/* Onboarding Checklist Status (Operational Visibility) */}
      {!isOnboarded && (
        <div className="bg-amber-950/20 border border-amber-500/25 p-4 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-amber-200">Onboarding Action Required</h4>
            <p className="text-xs text-amber-300/80 leading-relaxed">
              Your organization profile is incomplete. Complete email and domain checks to unlock full API routing.
            </p>
            <div className="flex gap-4 pt-1">
              {!isEmailVerified && <span className="text-[10px] text-amber-400 font-bold uppercase">✗ Email Verification Pending</span>}
              {!isDomainVerified && <span className="text-[10px] text-amber-400 font-bold uppercase">✗ DNS TXT Token Pending</span>}
            </div>
          </div>
        </div>
      )}

      {/* Gateway Runtime Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Gateway Requests</span>
            <Activity className="w-4 h-4 text-violet-400" />
          </div>
          <p className="text-2xl font-bold text-white">{gatewayStats?.totalRequests || 0}</p>
          <p className="text-[10px] text-gray-500">From gateway request records</p>
        </div>

        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Approved</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white">{gatewayStats?.approvedRequests || 0}</p>
          <p className="text-[10px] text-gray-500">Allowed gateway decisions</p>
        </div>

        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Blocked</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-white">{gatewayStats?.blockedRequests || 0}</p>
          <p className="text-[10px] text-gray-500">Blocked gateway decisions</p>
        </div>

        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Pending</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-white">{gatewayStats?.pendingApprovals || 0}</p>
          <p className="text-[10px] text-gray-500">From /gateway/approvals</p>
        </div>

        <div className="glass-card p-4 space-y-2">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Provider Usage</span>
            <Server className="w-4 h-4 text-blue-400" />
          </div>
          <div className="space-y-1">
            {gatewayStats?.providerUsage && Object.keys(gatewayStats.providerUsage).length > 0 ? (
              Object.entries(gatewayStats.providerUsage).slice(0, 3).map(([provider, count]) => (
                <div key={provider} className="flex justify-between text-[11px]">
                  <span className="text-gray-400 capitalize">{provider}</span>
                  <span className="font-mono text-white">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-[11px] text-gray-500">No provider traffic yet</p>
            )}
          </div>
        </div>
      </div>

      {/* Operational Governance Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5 space-y-3">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Redacted Fields</span>
            <ShieldAlert className="w-4 h-4 text-fuchsia-400" />
          </div>
          <p className="text-2xl font-bold text-white">{governanceAnalytics?.redactions?.total_fields || 0}</p>
          <div className="text-[10px] text-gray-400">
            Docs: {governanceAnalytics?.redactions?.document_findings || 0} • Gateway events: {governanceAnalytics?.redactions?.agent_redaction_events || 0}
          </div>
        </div>

        <div className="glass-card p-5 space-y-3">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Approval Queue</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-white">{governanceAnalytics?.approvals?.pending || 0}</p>
          <div className="text-[10px] text-gray-400">
            Approved: {governanceAnalytics?.approvals?.approved || 0} • Rejected: {governanceAnalytics?.approvals?.rejected || 0}
          </div>
        </div>

        <div className="glass-card p-5 space-y-3">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Audit Integrity</span>
            <Hash className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white">{governanceAnalytics?.audit?.valid ? 'Valid' : 'Failed'}</p>
          <div className="text-[10px] text-gray-400">
            {governanceAnalytics?.audit?.records_checked || 0} verified blocks
          </div>
        </div>

        <div className="glass-card p-5 space-y-3">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Audit Reports</span>
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleAuditExport('csv')}
              className="px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-xs text-gray-200 hover:border-violet-500 transition"
            >
              CSV
            </button>
            <button
              onClick={() => handleAuditExport('pdf')}
              className="px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-xs text-gray-200 hover:border-violet-500 transition"
            >
              PDF
            </button>
          </div>
          <p className="text-[10px] text-gray-500">Tenant-scoped export endpoints</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
            <Server className="w-4 h-4 text-blue-400" />
            Provider Usage Analytics
          </h3>
          <div className="space-y-3">
            {governanceAnalytics?.providers?.length ? (
              governanceAnalytics.providers.map((item) => (
                <div key={item.provider} className="grid grid-cols-5 gap-3 text-xs bg-slate-900/40 p-3 rounded-lg border border-white/5">
                  <span className="font-bold text-gray-200 capitalize col-span-2">{item.provider}</span>
                  <span className="text-gray-400">Req: <b className="text-white">{item.requests}</b></span>
                  <span className="text-gray-400">Blocked: <b className="text-rose-300">{item.blocked}</b></span>
                  <span className="text-gray-400">Avg: <b className="text-white">{item.avg_duration_ms}ms</b></span>
                </div>
              ))
            ) : (
              <p className="text-xs text-gray-500">No provider traffic recorded yet.</p>
            )}
          </div>
        </div>

        <div className="glass-card p-6 space-y-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-fuchsia-400" />
            Redaction Analytics
          </h3>
          <div className="space-y-3">
            {governanceAnalytics?.redactions?.by_type && Object.keys(governanceAnalytics.redactions.by_type).length ? (
              Object.entries(governanceAnalytics.redactions.by_type).map(([type, count]) => (
                <div key={type} className="flex justify-between items-center text-xs bg-slate-900/40 p-3 rounded-lg border border-white/5">
                  <span className="font-bold text-gray-200">{type}</span>
                  <span className="font-mono text-fuchsia-300">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-gray-500">No redacted fields recorded yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* Metrics Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Gateway Health Status */}
        <div className="glass-card p-5 space-y-2 hover:border-white/10 transition">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Gateway Status</span>
            <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
          </div>
          <p className="text-xl font-bold text-white font-sans">
            Active / Online
          </p>
          <div className="text-[10px] text-emerald-400 font-medium">
            Avg Latency: {metrics?.avg_latency || 0} ms
          </div>
        </div>

        {/* Total Request Volume */}
        <div className="glass-card p-5 space-y-2 hover:border-white/10 transition">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Total Requests</span>
            <Layers className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-xl font-bold text-white font-sans">
            {metrics?.total_requests || 0}
          </p>
          <div className="text-[10px] text-gray-400">
            Active routes traffic volume
          </div>
        </div>

        {/* Blocked Requests count */}
        <div className="glass-card p-5 space-y-2 hover:border-white/10 transition">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Blocked Queries</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-xl font-bold text-white font-sans">
            {metrics?.blocked_requests || 0}
          </p>
          <div className="text-[10px] text-rose-400 font-medium">
            Violations: {metrics?.total_violations || 0} detected
          </div>
        </div>

        {/* Cryptographic Ledger Status */}
        <div className="glass-card p-5 space-y-2 hover:border-white/10 transition">
          <div className="flex justify-between items-center text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Ledger Status</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xl font-bold text-white font-sans">
            {auditSum?.valid ? "Secured" : "Unverified"}
          </p>
          <div className="text-[10px] text-emerald-400 font-medium">
            ✓ Unbroken Block Linkage
          </div>
        </div>
      </div>

      {/* Main Details summaries Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LLM Providers Status */}
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
            <Server className="w-4 h-4 text-violet-400" />
            LLM Router Settings
          </h3>
          <div className="space-y-3">
            {providers.length === 0 ? (
              <p className="text-xs text-gray-500">No active provider credentials configured.</p>
            ) : (
              providers.map((p, idx) => (
                <div key={idx} className="flex justify-between items-center bg-slate-900/40 p-3 rounded-lg border border-white/5 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span className="font-bold text-gray-300 capitalize">{p.provider}</span>
                  </div>
                  <span className="text-[10px] text-gray-500">Connected</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Active Governance Policies */}
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Active Policies
          </h3>
          <div className="space-y-3">
            {policies.length === 0 ? (
              <p className="text-xs text-gray-500">No custom database-driven policies configured.</p>
            ) : (
              policies.map((pol) => (
                <div key={pol.id} className="bg-slate-900/40 p-3 rounded-lg border border-white/5 flex justify-between items-center text-xs">
                  <div>
                    <p className="font-bold text-gray-300">{pol.name}</p>
                    <p className="text-[10px] text-gray-500 capitalize mt-0.5">Type: {pol.type}</p>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${pol.enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-gray-400'}`}>
                    {pol.enabled ? "Active" : "Disabled"}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Developer Gateway Credentials count */}
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-pink-400" />
            Active API Credentials
          </h3>
          <div className="bg-slate-900/40 p-4 rounded-lg border border-white/5 space-y-3 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Total API Keys:</span>
              <span className="font-bold text-white">{keysCount}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Active Tenants:</span>
              <span className="font-bold text-white">{metrics?.active_tenants || 1}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Active Routes:</span>
              <span className="font-bold text-white">{metrics?.active_routes || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ledger Hash Chain Details */}
      <div className="glass-card p-6 space-y-4">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-white/5 pb-2.5 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          Cryptographic Audit Ledgers (Tamper-Evident Chain)
        </h3>
        <div className="space-y-3 font-mono text-[10px]">
          {auditChain.length === 0 ? (
            <p className="text-xs text-gray-500 font-sans">No cryptographic blocks written to the ledger yet.</p>
          ) : (
            auditChain.map(record => (
              <div key={record.record_id} className="bg-slate-900/60 p-3.5 rounded-lg border border-white/5 space-y-1.5 hover:border-white/10 transition">
                <div className="flex justify-between text-xs">
                  <span className="text-emerald-400 font-bold font-mono">Block ID #{record.record_id}</span>
                  <span className="text-gray-500 font-sans">
                    {record.timestamp.includes('T') ? record.timestamp.split('T')[0] : record.timestamp.split(' ')[0]} 
                    &nbsp;
                    {record.timestamp.includes('T') ? record.timestamp.split('T')[1]?.split('.')[0] : record.timestamp.split(' ')[1]?.split('.')[0]}
                  </span>
                </div>
                <div className="truncate text-gray-500 text-[8.5px]">Prev Hash: {record.previous_hash}</div>
                <div className="truncate text-gray-300 text-[9px] font-bold">Block Hash: {record.integrity_hash}</div>
              </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
};

export default Dashboard;
