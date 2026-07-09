import React, { useEffect, useState } from 'react';
import { CreditCard, Gauge, RefreshCw, Save, ShieldCheck } from 'lucide-react';
import apiClient from '../../services/api';
import { Button, DataTable, GlassCard, MetricCard, StatusBadge, inputStyles, labelStyles } from '../../components/Common/DesignSystem';
import { useToast } from '../../components/Common/Toast';
import { useAuth } from '../../context/AuthContext';

const TenantPlan = () => {
  const [plan, setPlan] = useState(null);
  const [selectedPlan, setSelectedPlan] = useState('enterprise');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { addToast } = useToast();
  const { user } = useAuth();

  const loadPlan = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/tenant/plan');
      setPlan(response.data);
      setSelectedPlan(response.data.current_plan || 'enterprise');
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to load tenant plan.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlan();
  }, []);

  const savePlan = async () => {
    setSaving(true);
    try {
      const response = await apiClient.post('/tenant/plan/override', { plan: selectedPlan, override_reason: reason });
      setPlan(response.data);
      addToast('Tenant plan override saved.', 'success');
    } catch (error) {
      addToast(error.response?.data?.detail || 'Plan override failed.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const canOverride = ['Super Admin', 'Security Admin'].includes(user?.role);
  const usage = plan?.usage || {};
  const limits = plan?.limits || {};

  const historyColumns = [
    { key: 'timestamp', header: 'Timestamp' },
    { key: 'event', header: 'Event' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#0E1726] font-display">Tenant Plan</h1>
          <p className="text-sm text-[#475069]">Plan tier, quota, distributed rate-limit usage, and administrator override history.</p>
        </div>
        <Button variant="secondary" onClick={loadPlan} disabled={loading}><RefreshCw className="w-4 h-4" /> Refresh</Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard title="Current Plan" value={plan?.current_plan || 'N/A'} icon={CreditCard} />
        <MetricCard title="Requests" value={usage.requests ?? 0} icon={Gauge} />
        <MetricCard title="Remaining Quota" value={usage.remaining_quota ?? 'Unlimited'} icon={ShieldCheck} />
        <MetricCard title="Rate Limit" value={`${usage.rate_limit ?? limits.requests_per_minute ?? 0}/min`} icon={Gauge} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard hover={false}>
          <h2 className="text-sm font-bold text-[#0E1726] font-display mb-4">Limits</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-[#475069]">Monthly requests</dt><dd className="font-semibold text-[#0E1726]">{limits.monthly_requests ?? 'Unlimited'}</dd></div>
            <div className="flex justify-between"><dt className="text-[#475069]">Requests/minute</dt><dd className="font-semibold text-[#0E1726]">{limits.requests_per_minute ?? 'N/A'}</dd></div>
            <div className="flex justify-between"><dt className="text-[#475069]">Background workers</dt><dd className="font-semibold text-[#0E1726]">{limits.background_workers ?? 'N/A'}</dd></div>
            <div className="flex justify-between"><dt className="text-[#475069]">Blocked requests</dt><dd className="font-semibold text-[#0E1726]">{usage.blocked_requests ?? 0}</dd></div>
          </dl>
        </GlassCard>

        <GlassCard className="lg:col-span-2" hover={false}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-[#0E1726] font-display">Admin Override</h2>
            <StatusBadge status={plan?.admin_override?.updated_at ? 'active' : 'not configured'} />
          </div>
          <div className="grid gap-4 md:grid-cols-[220px_1fr_auto]">
            <div>
              <label className={labelStyles}>Plan</label>
              <select className={inputStyles} value={selectedPlan} onChange={(event) => setSelectedPlan(event.target.value)} disabled={!canOverride}>
                {(plan?.supported_plans || ['free', 'starter', 'professional', 'enterprise', 'unlimited']).map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelStyles}>Reason</label>
              <input className={inputStyles} value={reason} onChange={(event) => setReason(event.target.value)} disabled={!canOverride} placeholder="Operational reason for override" />
            </div>
            <div className="flex items-end">
              <Button onClick={savePlan} loading={saving} disabled={!canOverride}><Save className="w-4 h-4" /> Save</Button>
            </div>
          </div>
          {!canOverride && <p className="mt-3 text-xs text-[#6B7488]">Your role can view plan data but cannot change overrides.</p>}
        </GlassCard>
      </div>

      <GlassCard hover={false}>
        <h2 className="text-sm font-bold text-[#0E1726] font-display mb-4">Upgrade History</h2>
        <DataTable columns={historyColumns} data={plan?.upgrade_history || []} loading={loading} />
      </GlassCard>
    </div>
  );
};

export default TenantPlan;
