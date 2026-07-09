import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cloud,
  ExternalLink,
  GitBranch,
  KeyRound,
  Lock,
  PlugZap,
  RefreshCw,
  ShieldCheck,
  X,
} from 'lucide-react';
import { Button, StatusBadge } from '../../components/Common/DesignSystem';
import { useToast } from '../../components/Common/Toast';
import {
  createRemediationPlan,
  listRemediationConnectors,
  listRemediationFindings,
  requestRemediationApproval,
  runRemediationScan,
  saveRemediationConnector,
  testRemediationConnector,
} from '../../services/remediationService';

const connectorCatalog = [
  {
    id: 'aws',
    provider: 'aws',
    name: 'AWS',
    icon: Cloud,
    status: 'Connected',
    scope: 'STS read-only, KMS decrypt, CloudTrail',
    lastSync: 'Today 14:48',
    region: 'ap-south-1',
    tone: 'gold',
  },
  {
    id: 'gcp',
    provider: 'gcp',
    name: 'Google Cloud',
    icon: Cloud,
    status: 'Ready',
    scope: 'IAM viewer, Cloud Logging, Secret Manager',
    lastSync: 'Not synced',
    region: 'asia-south1',
    tone: 'violet',
  },
  {
    id: 'github',
    provider: 'github',
    name: 'GitHub',
    icon: GitBranch,
    status: 'Connected',
    scope: 'Repos read, security events, actions logs',
    lastSync: 'Today 13:22',
    region: 'org: authclaw-labs',
    tone: 'ink',
  },
];

const toneStyles = {
  gold: 'bg-[#FBF1DE] text-[#8A5A16] border-[#E9A93C]/30',
  violet: 'bg-[#F1ECFE] text-[#6D28D9] border-[#A78BFA]/40',
  blue: 'bg-sky-50 text-sky-700 border-sky-200',
  ink: 'bg-[#F5F7FA] text-[#0E1726] border-[#E6E9F0]',
};

const Connectors = () => {
  const { addToast } = useToast();
  const [connectors, setConnectors] = useState(connectorCatalog);
  const [findings, setFindings] = useState([]);
  const [activeConnector, setActiveConnector] = useState(null);
  const [form, setForm] = useState({
    credentialRef: '',
    roleArn: '',
    region: '',
    scope: '',
  });

  const connectedCount = useMemo(
    () => connectors.filter((connector) => connector.status === 'Connected').length,
    [connectors]
  );

  const refreshRuntime = async () => {
    try {
      const [savedConnectors, runtimeFindings] = await Promise.all([
        listRemediationConnectors(),
        listRemediationFindings(),
      ]);
      const byProvider = new Map(savedConnectors.map((connector) => [connector.provider, connector]));
      setConnectors(
        connectorCatalog.map((catalog) => {
          const saved = byProvider.get(catalog.provider);
          if (!saved) return catalog;
          return {
            ...catalog,
            dbId: saved.id,
            status: saved.status === 'connected' ? 'Connected' : 'Configured',
            scope: saved.scope || catalog.scope,
            region: saved.region || catalog.region,
            lastSync: saved.last_tested_at ? new Date(saved.last_tested_at).toLocaleString() : 'Configured',
            credentialRef: saved.credential_ref,
            roleArn: saved.role_identifier || '',
          };
        })
      );
      setFindings(runtimeFindings);
    } catch (error) {
      console.error(error);
      addToast('Failed to load remediation runtime state.', 'error');
    }
  };

  useEffect(() => {
    refreshRuntime();
  }, []);

  const openConnector = (connector) => {
    setActiveConnector(connector);
    setForm({
      credentialRef: connector.credentialRef || `${connector.provider}-credential-ref`,
      roleArn: connector.roleArn || (connector.provider === 'aws' ? 'arn:aws:iam::123456789012:role/AuthClawReadOnly' : ''),
      region: connector.region,
      scope: connector.scope,
    });
  };

  const saveConnector = async () => {
    if (!activeConnector) return;
    try {
      await saveRemediationConnector({
        provider: activeConnector.provider,
        name: activeConnector.name,
        credential_ref: form.credentialRef,
        role_identifier: form.roleArn,
        region: form.region,
        scope: form.scope,
      });
      addToast(`${activeConnector.name} connector saved.`, 'success');
      setActiveConnector(null);
      refreshRuntime();
    } catch (error) {
      console.error(error);
      addToast('Connector save failed.', 'error');
    }
  };

  const testConnector = async (connector) => {
    if (!connector.dbId) {
      addToast('Save the connector before testing it.', 'error');
      return;
    }
    try {
      await testRemediationConnector(connector.dbId);
      addToast('Connector handshake completed.', 'success');
      refreshRuntime();
    } catch (error) {
      console.error(error);
      addToast('Connector handshake failed.', 'error');
    }
  };

  const scanConnector = async (connector) => {
    if (!connector.dbId) {
      addToast('Save the connector before scanning.', 'error');
      return;
    }
    try {
      const result = await runRemediationScan(connector.dbId);
      addToast(`Read-only scan created ${result.findings.length} findings.`, 'success');
      refreshRuntime();
    } catch (error) {
      console.error(error);
      addToast('Read-only scan failed.', 'error');
    }
  };

  const requestApprovalForFinding = async (findingId) => {
    try {
      const plan = await createRemediationPlan(findingId);
      const approval = await requestRemediationApproval(plan.id);
      addToast(`Approval requested: ${approval.approval_id.slice(0, 8)}`, 'success');
      refreshRuntime();
    } catch (error) {
      console.error(error);
      addToast('Failed to request remediation approval.', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <section className="auth-console-shell p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-[#A78BFA]/40 bg-[#F1ECFE] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6D28D9] font-mono">
              <PlugZap className="h-3.5 w-3.5" />
              Cloud Connectors
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#0E1726] font-display">
              Enterprise Connector Hub
            </h1>
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusBadge status={`${connectedCount} Connected`} />
              <StatusBadge status={`${connectors.length - connectedCount} Ready`} />
              <StatusBadge status="Scoped Runtime" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div className="rounded-lg border border-[#E6E9F0] bg-white/85 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Runtime TTL</p>
              <p className="mt-1 font-mono text-lg font-bold text-[#0E1726]">30m</p>
            </div>
            <div className="rounded-lg border border-[#E6E9F0] bg-white/85 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Mode</p>
              <p className="mt-1 font-mono text-lg font-bold text-[#0E1726]">Scoped</p>
            </div>
            <div className="rounded-lg border border-[#E6E9F0] bg-white/85 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Secrets</p>
              <p className="mt-1 font-mono text-lg font-bold text-[#0E1726]">Vaulted</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {connectors.map((connector) => {
          const Icon = connector.icon;
          const connected = connector.status === 'Connected';
          return (
            <article
              key={connector.id}
              className="rounded-lg border border-[#E6E9F0] bg-white/90 p-5 shadow-[0_20px_60px_-46px_rgba(11,31,63,0.45)] transition hover:border-[#A78BFA]/60"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-lg border ${toneStyles[connector.tone]}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-[#0E1726] font-display">{connector.name}</h2>
                    <p className="mt-0.5 text-xs font-mono text-[#6B7488]">{connector.region}</p>
                  </div>
                </div>
                {connected ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                )}
              </div>

              <div className="mt-5 space-y-3">
                <div className="rounded-lg border border-[#E6E9F0] bg-[#F5F7FA]/70 px-3 py-2">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Scope</p>
                  <p className="mt-1 text-sm font-semibold text-[#475069]">{connector.scope}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-[#E6E9F0] bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Status</p>
                    <p className="mt-1 text-sm font-bold text-[#0E1726]">{connector.status}</p>
                  </div>
                  <div className="rounded-lg border border-[#E6E9F0] bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#6B7488]">Last Sync</p>
                    <p className="mt-1 text-sm font-bold text-[#0E1726]">{connector.lastSync}</p>
                  </div>
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#E6E9F0] pt-4">
                <button
                  type="button"
                  onClick={() => testConnector(connector)}
                  className="auth-btn-soft inline-flex items-center gap-2 px-3 py-2 text-xs font-bold"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Test
                </button>
                <button
                  type="button"
                  onClick={() => scanConnector(connector)}
                  className="auth-btn-soft inline-flex items-center gap-2 px-3 py-2 text-xs font-bold"
                >
                  <Activity className="h-3.5 w-3.5" />
                  Scan
                </button>
                <button
                  type="button"
                  onClick={() => openConnector(connector)}
                  className="auth-btn-primary inline-flex items-center gap-2 px-3 py-2 text-xs"
                >
                  <KeyRound className="h-3.5 w-3.5" />
                  Configure
                </button>
              </div>
            </article>
          );
        })}
      </section>

      <section className="rounded-lg border border-[#E6E9F0] bg-white/85 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#A78BFA]/40 bg-[#F1ECFE] text-[#6D28D9]">
              <Lock className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#0E1726] font-display">Scoped Worker Runtime</h2>
              <p className="text-sm text-[#475069]">AWS, GCP, Azure, and SCM actions use temporary scoped credentials.</p>
            </div>
          </div>
          <a
            href="/trust"
            className="auth-btn-soft inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-bold"
          >
            Trust Center
            <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </section>

      <section className="rounded-lg border border-[#E6E9F0] bg-white/85 p-5">
        <div className="flex flex-col gap-2 border-b border-[#E6E9F0] pb-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-base font-bold text-[#0E1726] font-display">Remediation Findings</h2>
            <p className="text-sm text-[#475069]">Read-only worker scans create findings. Plan creation is non-destructive; execution waits for HITL approval.</p>
          </div>
          <StatusBadge status={`${findings.length} Findings`} />
        </div>
        <div className="mt-4 grid gap-3">
          {findings.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[#E6E9F0] bg-[#F5F7FA]/70 p-5 text-sm text-[#6B7488]">
              No findings yet. Run a read-only scan from a configured connector.
            </div>
          ) : (
            findings.slice(0, 8).map((finding) => (
              <div key={finding.id} className="rounded-lg border border-[#E6E9F0] bg-white p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={finding.provider?.toUpperCase() || 'Provider'} />
                      <StatusBadge status={finding.severity || 'MEDIUM'} />
                      <StatusBadge status={finding.status || 'open'} />
                    </div>
                    <h3 className="mt-2 text-sm font-bold text-[#0E1726]">{finding.finding}</h3>
                    <p className="mt-1 text-xs text-[#475069]">{finding.recommendation}</p>
                    <p className="mt-1 font-mono text-[11px] text-[#6B7488]">{finding.resource_id}</p>
                  </div>
                  <Button size="sm" onClick={() => requestApprovalForFinding(finding.id)}>
                    <ShieldCheck className="h-4 w-4" />
                    Plan + Request Approval
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {activeConnector && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-[#0E1726]/35 backdrop-blur-sm"
            onClick={() => setActiveConnector(null)}
            aria-label="Close connector modal"
          />
          <div className="relative z-10 w-full max-w-2xl rounded-lg border border-[#E6E9F0] bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#E6E9F0] px-6 py-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#6D28D9] font-mono">Connector</p>
                <h2 className="text-xl font-bold text-[#0E1726] font-display">{activeConnector.name}</h2>
              </div>
              <button
                type="button"
                onClick={() => setActiveConnector(null)}
                className="rounded-lg p-2 text-[#6B7488] hover:bg-[#F5F7FA] hover:text-[#0E1726]"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid gap-4 px-6 py-5">
              <label className="grid gap-1.5">
                <span className="text-xs font-bold text-[#475069]">Credential Reference</span>
                <input
                  value={form.credentialRef}
                  onChange={(event) => setForm((prev) => ({ ...prev, credentialRef: event.target.value }))}
                  className="glass-input h-11"
                />
              </label>
              <label className="grid gap-1.5">
                <span className="text-xs font-bold text-[#475069]">Role / App Identifier</span>
                <input
                  value={form.roleArn}
                  onChange={(event) => setForm((prev) => ({ ...prev, roleArn: event.target.value }))}
                  placeholder="Role ARN, App ID, or installation ID"
                  className="glass-input h-11"
                />
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="grid gap-1.5">
                  <span className="text-xs font-bold text-[#475069]">Region / Workspace</span>
                  <input
                    value={form.region}
                    onChange={(event) => setForm((prev) => ({ ...prev, region: event.target.value }))}
                    className="glass-input h-11"
                  />
                </label>
                <label className="grid gap-1.5">
                  <span className="text-xs font-bold text-[#475069]">Permission Scope</span>
                  <input
                    value={form.scope}
                    onChange={(event) => setForm((prev) => ({ ...prev, scope: event.target.value }))}
                    className="glass-input h-11"
                  />
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-[#E6E9F0] px-6 py-4">
              <Button variant="ghost" onClick={() => setActiveConnector(null)}>
                Cancel
              </Button>
              <Button onClick={saveConnector}>
                <PlugZap className="h-4 w-4" />
                Save Connector
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Connectors;
