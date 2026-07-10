import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  KeyRound,
  ExternalLink,
  Info
} from 'lucide-react';
import apiClient from '../../services/api';
import { getAuditSummary } from '../../services/auditService';
import { getGatewayStats } from '../../services/gatewayService';
import { getGovernanceAnalytics } from '../../services/metricsService';
import { 
  MetricCard, 
  GlassCard, 
  StatusBadge, 
  Button 
} from '../../components/Common/DesignSystem';

const INITIAL_DASHBOARD_DATA = {
  keysCount: 0,
  providers: [],
  auditSum: null,
  auditChain: [],
  tenantInfo: null,
  policies: [],
  metrics: null,
  gatewayStats: null,
  governanceAnalytics: null,
};

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(INITIAL_DASHBOARD_DATA);
  const [loading, setLoading] = useState(true);
  const mountedRef = useRef(false);
  const inFlightRef = useRef(false);

  const {
    keysCount,
    providers,
    auditSum,
    auditChain,
    tenantInfo,
    policies,
    metrics,
    gatewayStats,
    governanceAnalytics,
  } = dashboardData;

  const fetchData = useCallback(async ({ initial = false } = {}) => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    if (initial) setLoading(true);

    const userStr = localStorage.getItem('authclaw_user');
    let nextTenantInfo = null;
    if (userStr) {
      try {
        nextTenantInfo = JSON.parse(userStr);
      } catch {
        nextTenantInfo = null;
      }
    }

    try {
      const results = await Promise.allSettled([
        apiClient.get('/keys/list'),
        apiClient.get('/providers/list'),
        getAuditSummary(),
        apiClient.get('/audit/hash-chain?limit=5'),
        apiClient.get('/policies/list'),
        apiClient.get('/metrics'),
        getGovernanceAnalytics(),
      ]);

      const [keysRes, provRes, auditRes, chainRes, policiesRes, metricsRes, analyticsRes] = results;
      let fallbackGatewayStats = null;

      if (analyticsRes.status !== 'fulfilled') {
        try {
          fallbackGatewayStats = await getGatewayStats();
        } catch (statsError) {
          console.error('Error loading gateway fallback metrics:', statsError);
        }
      }

      if (!mountedRef.current) return;

      setDashboardData((prev) => {
        const analyticsData = analyticsRes.status === 'fulfilled' ? analyticsRes.value : null;
        const nextGatewayStats = analyticsData
          ? {
              totalRequests: analyticsData.gateway.total_requests,
              approvedRequests: analyticsData.gateway.allowed_requests,
              blockedRequests: analyticsData.gateway.blocked_requests,
              pendingApprovals: analyticsData.approvals.pending,
              providerUsage: Object.fromEntries((analyticsData.providers || []).map((item) => [item.provider, item.requests])),
              requests: analyticsData.recent_requests,
              approvals: analyticsData.approvals,
            }
          : fallbackGatewayStats || prev.gatewayStats;

        return {
          keysCount: keysRes.status === 'fulfilled' ? keysRes.value.data.length : prev.keysCount,
          providers: provRes.status === 'fulfilled' ? provRes.value.data : prev.providers,
          auditSum: auditRes.status === 'fulfilled' ? auditRes.value : prev.auditSum,
          auditChain: chainRes.status === 'fulfilled' ? chainRes.value.data : prev.auditChain,
          tenantInfo: nextTenantInfo,
          policies: policiesRes.status === 'fulfilled' ? policiesRes.value.data || [] : prev.policies,
          metrics: metricsRes.status === 'fulfilled' ? metricsRes.value.data : prev.metrics,
          gatewayStats: nextGatewayStats,
          governanceAnalytics: analyticsData || prev.governanceAnalytics,
        };
      });
    } finally {
      if (mountedRef.current) setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData({ initial: true });
    const interval = setInterval(() => fetchData(), 30000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  const providerUsageEntries = useMemo(
    () => Object.entries(gatewayStats?.providerUsage || {}).slice(0, 3),
    [gatewayStats]
  );

  const redactionEntries = useMemo(
    () => Object.entries(governanceAnalytics?.redactions?.by_type || {}),
    [governanceAnalytics]
  );

  const handleAuditExport = async (format) => {
    try {
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
    } catch (e) {
      console.error('Failed to export audit report:', e);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-pulse">
        <div className="h-28 bg-[#F5F7FA] rounded-xl"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-[#F5F7FA] rounded-xl"></div>
          ))}
        </div>
        <div className="h-64 bg-[#F5F7FA] rounded-xl"></div>
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
        <h1 className="text-2xl font-bold text-[#0E1726]">
          Observability & Audit Analytics
        </h1>
        <p className="text-[#475069] text-xs mt-1">Real-time status of multi-tenant gateway traffic, provider usage, policy enforcement, approvals, redactions, and cryptographic ledger logs.</p>
      </div>

      {/* Onboarding Checklist Status */}
      {!isOnboarded && (
        <div className="bg-amber-500/5 border border-amber-500/20 p-4 rounded-xl flex items-start gap-4">
          <div className="p-2 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-amber-200">Onboarding Action Required</h4>
            <p className="text-xs text-amber-400/80 leading-relaxed">
              Your organization profile is incomplete. Complete email and domain checks to unlock full API routing.
            </p>
            <div className="flex gap-4 pt-1.5">
              {!isEmailVerified && (
                <span className="text-[10px] text-amber-500 font-bold uppercase bg-amber-500/10 px-2 py-0.5 border border-amber-500/20 rounded">
                  Pending: Email Verification Pending
                </span>
              )}
              {!isDomainVerified && (
                <span className="text-[10px] text-amber-500 font-bold uppercase bg-amber-500/10 px-2 py-0.5 border border-amber-500/20 rounded">
                  Pending: DNS TXT Token Pending
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Gateway Runtime Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Gateway Requests"
          value={gatewayStats?.totalRequests || 0}
          icon={Activity}
        />
        <MetricCard
          title="Approved"
          value={gatewayStats?.approvedRequests || 0}
          icon={CheckCircle}
        />
        <MetricCard
          title="Blocked"
          value={gatewayStats?.blockedRequests || 0}
          icon={ShieldAlert}
          changeType="negative"
        />
        <MetricCard
          title="Pending Approvals"
          value={gatewayStats?.pendingApprovals || 0}
          icon={Clock}
        />
        <GlassCard className="flex flex-col justify-between">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Provider Usage</span>
            <Server className="w-4 h-4 text-blue-400" />
          </div>
          <div className="space-y-1.5 mt-2">
            {providerUsageEntries.length > 0 ? (
              providerUsageEntries.map(([provider, count]) => (
                <div key={provider} className="flex justify-between text-[11px]">
                  <span className="text-[#475069] capitalize">{provider}</span>
                  <span className="font-mono text-[#0E1726] font-bold">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-[11px] text-[#6B7488]">No provider traffic yet</p>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Operational Governance Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <GlassCard className="space-y-3">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Redacted Fields</span>
            <ShieldAlert className="w-4 h-4 text-fuchsia-400" />
          </div>
          <p className="text-2xl font-bold text-[#0E1726]">{governanceAnalytics?.redactions?.total_fields || 0}</p>
          <div className="text-[10px] text-[#475069]">
            Docs: {governanceAnalytics?.redactions?.document_findings || 0} - Gateway: {governanceAnalytics?.redactions?.agent_redaction_events || 0}
          </div>
        </GlassCard>

        <GlassCard className="space-y-3">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Approval Queue</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-[#0E1726]">{governanceAnalytics?.approvals?.pending || 0}</p>
          <div className="text-[10px] text-[#475069]">
            Approved: {governanceAnalytics?.approvals?.approved || 0} - Rejected: {governanceAnalytics?.approvals?.rejected || 0}
          </div>
        </GlassCard>

        <GlassCard className="space-y-3">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Audit Integrity</span>
            <Hash className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-[#0E1726]">{governanceAnalytics?.audit?.valid ? 'Valid' : 'Failed'}</p>
            <StatusBadge status={governanceAnalytics?.audit?.valid ? 'Intact' : 'Failed'} />
          </div>
          <div className="text-[10px] text-[#475069]">
            {governanceAnalytics?.audit?.records_checked || 0} verified blocks
          </div>
        </GlassCard>

        <GlassCard className="space-y-3">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Audit Reports</span>
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAuditExport('csv')}
            >
              CSV
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAuditExport('pdf')}
            >
              PDF
            </Button>
          </div>
          <p className="text-[10px] text-[#6B7488]">Export verified logs</p>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Provider Usage */}
        <GlassCard className="space-y-4">
          <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
            <Server className="w-4 h-4 text-blue-400" />
            Provider Usage Analytics
          </h3>
          <div className="space-y-3">
            {governanceAnalytics?.providers?.length ? (
              governanceAnalytics.providers.map((item) => (
                <div key={item.provider} className="grid grid-cols-5 gap-3 text-xs bg-[#F5F7FA]/80 p-3 rounded-lg border border-[#E6E9F0] items-center">
                  <span className="font-bold text-[#0E1726] capitalize col-span-2">{item.provider}</span>
                  <span className="text-[#475069]">Req: <b className="text-[#0E1726]">{item.requests}</b></span>
                  <span className="text-[#475069]">Blocked: <b className="text-rose-400">{item.blocked}</b></span>
                  <span className="text-[#475069]">Avg: <b className="text-[#0E1726]">{item.avg_duration_ms}ms</b></span>
                </div>
              ))
            ) : (
              <p className="text-xs text-[#6B7488]">No provider traffic recorded yet.</p>
            )}
          </div>
        </GlassCard>

        {/* Redaction Analytics */}
        <GlassCard className="space-y-4">
          <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-fuchsia-400" />
            Redaction Analytics
          </h3>
          <div className="space-y-3">
            {redactionEntries.length ? (
              redactionEntries.map(([type, count]) => (
                <div key={type} className="flex justify-between items-center text-xs bg-[#F5F7FA]/80 p-3 rounded-lg border border-[#E6E9F0]">
                  <span className="font-bold text-[#0E1726]">{type}</span>
                  <span className="font-mono text-fuchsia-300 font-bold">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-[#6B7488]">No redacted fields recorded yet.</p>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Metrics Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Gateway Status</span>
            <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">Active / Online</p>
          <div className="text-[10px] text-emerald-400 font-semibold">
            Avg Latency: {metrics?.avg_latency || 0} ms
          </div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Total Requests</span>
            <Layers className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{metrics?.total_requests || 0}</p>
          <div className="text-[10px] text-[#6B7488]">Active routes traffic volume</div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Blocked Queries</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{metrics?.blocked_requests || 0}</p>
          <div className="text-[10px] text-rose-400 font-semibold">
            Violations: {metrics?.total_violations || 0} detected
          </div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Ledger Status</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{auditSum?.valid ? "Secured" : "Unverified"}</p>
          <div className="text-[10px] text-emerald-400 font-semibold">OK Chained Block Linkage</div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Queue Lag</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{metrics?.queue_lag_seconds || governanceAnalytics?.queue_lag?.max_lag_seconds || 0}s</p>
          <div className="text-[10px] text-[#6B7488]">
            DLQ: {metrics?.dead_letter_events || governanceAnalytics?.queue_lag?.dead_letter_count || 0}
          </div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Provider Errors</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{metrics?.provider_errors || governanceAnalytics?.provider_errors?.total || 0}</p>
          <div className="text-[10px] text-[#6B7488]">Last hour gateway/provider failures</div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Approval Latency</span>
            <Activity className="w-4 h-4 text-blue-500" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{metrics?.avg_approval_latency_seconds || governanceAnalytics?.approval_latency?.avg_seconds || 0}s</p>
          <div className="text-[10px] text-[#6B7488]">Average approval lifecycle</div>
        </GlassCard>

        <GlassCard className="space-y-2">
          <div className="flex justify-between items-center text-[#6B7488]">
            <span className="text-[10px] font-bold uppercase tracking-wider">Rate Limiter</span>
            <Server className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-xl font-bold text-[#0E1726]">{governanceAnalytics?.rate_limits?.backend || 'none'}</p>
          <div className="text-[10px] text-[#6B7488]">
            Blocked: {metrics?.rate_limit_blocked || governanceAnalytics?.rate_limits?.blocked || 0}
          </div>
        </GlassCard>
      </div>

      {/* Main Details summaries Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LLM Providers Status */}
        <GlassCard className="space-y-4">
          <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
            <Server className="w-4 h-4 text-[#6D28D9]" />
            LLM Router Settings
          </h3>
          <div className="space-y-3">
            {providers.length === 0 ? (
              <p className="text-xs text-[#6B7488]">No active provider credentials configured.</p>
            ) : (
              providers.map((p, idx) => (
                <div key={idx} className="flex justify-between items-center bg-[#F5F7FA]/80 p-3 rounded-lg border border-[#E6E9F0] text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className="font-bold text-[#475069] capitalize">{p.provider}</span>
                  </div>
                  <StatusBadge status="Online" />
                </div>
              ))
            )}
          </div>
        </GlassCard>

        {/* Active Governance Policies */}
        <GlassCard className="space-y-4">
          <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Active Policies
          </h3>
          <div className="space-y-3">
            {policies.length === 0 ? (
              <p className="text-xs text-[#6B7488]">No custom database-driven policies configured.</p>
            ) : (
              policies.map((pol) => (
                <div key={pol.id} className="bg-[#F5F7FA]/80 p-3 rounded-lg border border-[#E6E9F0] flex justify-between items-center text-xs">
                  <div>
                    <p className="font-bold text-[#475069]">{pol.name}</p>
                    <p className="text-[10px] text-[#6B7488] capitalize mt-0.5">Type: {pol.type}</p>
                  </div>
                  <StatusBadge status={pol.enabled ? "Active" : "Disabled"} />
                </div>
              ))
            )}
          </div>
        </GlassCard>

        {/* Developer Gateway Credentials */}
        <GlassCard className="space-y-4">
          <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-pink-400" />
            Active API Credentials
          </h3>
          <div className="bg-[#F5F7FA]/80 p-4 rounded-lg border border-[#E6E9F0] space-y-3 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-[#475069]">Total API Keys:</span>
              <span className="font-bold text-[#0E1726] font-mono">{keysCount}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#475069]">Active Tenants:</span>
              <span className="font-bold text-[#0E1726] font-mono">{metrics?.active_tenants || 1}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#475069]">Active Routes:</span>
              <span className="font-bold text-[#0E1726] font-mono">{metrics?.active_routes || 0}</span>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Ledger Hash Chain Details */}
      <GlassCard className="space-y-4">
        <h3 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider border-b border-[#E6E9F0] pb-2.5 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          Cryptographic Audit Ledgers (Tamper-Evident Chain)
        </h3>
        <div className="space-y-3 font-mono text-[10px]">
          {auditChain.length === 0 ? (
            <p className="text-xs text-[#6B7488] font-sans">No cryptographic blocks written to the ledger yet.</p>
          ) : (
            auditChain.map(record => (
              <div key={record.record_id} className="bg-[#F5F7FA] p-3.5 rounded-lg border border-[#E6E9F0] space-y-1.5 hover:border-[#E6E9F0] transition-colors duration-200">
                <div className="flex justify-between text-xs">
                  <span className="text-emerald-400 font-bold font-mono">Block ID #{record.record_id}</span>
                  <span className="text-[#6B7488] font-sans">
                    {record.timestamp.includes('T') ? record.timestamp.split('T')[0] : record.timestamp.split(' ')[0]} 
                    &nbsp;
                    {record.timestamp.includes('T') ? record.timestamp.split('T')[1]?.split('.')[0] : record.timestamp.split(' ')[1]?.split('.')[0]}
                  </span>
                </div>
                <div className="truncate text-[#6B7488] text-[8.5px]">Prev Hash: {record.previous_hash}</div>
                <div className="truncate text-[#475069] text-[9px] font-bold">Block Hash: {record.integrity_hash}</div>
              </div>
            ))
          )}
        </div>
      </GlassCard>
    </div>
  );
};

export default React.memo(Dashboard);
