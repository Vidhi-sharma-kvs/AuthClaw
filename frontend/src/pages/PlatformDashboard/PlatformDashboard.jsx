import React, { useEffect, useState } from 'react';
import { Activity, Building2, CheckCircle, Database, RefreshCw, ShieldAlert, Users } from 'lucide-react';
import apiClient from '../../services/api';

const StatTile = ({ label, value, icon: Icon, tone = 'text-violet-400' }) => (
  <div className="glass-card p-4 space-y-2">
    <div className="flex items-center justify-between text-gray-500">
      <span className="text-[10px] font-bold uppercase tracking-wider">{label}</span>
      <Icon className={`w-4 h-4 ${tone}`} />
    </div>
    <p className="text-2xl font-bold text-white">{value ?? 0}</p>
  </div>
);

const PlatformDashboard = () => {
  const [summary, setSummary] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadPlatformData = async () => {
    try {
      setError('');
      const [summaryRes, tenantsRes] = await Promise.all([
        apiClient.get('/platform/summary'),
        apiClient.get('/platform/tenants')
      ]);
      setSummary(summaryRes.data);
      setTenants(tenantsRes.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load platform administration data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlatformData();
    const interval = setInterval(loadPlatformData, 20000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-pulse">
        <div className="h-24 bg-white/5 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, index) => (
            <div key={index} className="h-24 bg-white/5 rounded-lg" />
          ))}
        </div>
        <div className="h-80 bg-white/5 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.24em] text-violet-300 font-bold">Platform Owner URL</p>
          <h1 className="text-2xl font-bold text-white">AuthClaw Platform Administration</h1>
          <p className="text-xs text-gray-400 mt-1">
            Owner-only view across tenants, users, gateway traffic, and global platform health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-2 rounded-lg border border-white/10 bg-slate-900 text-xs font-mono text-violet-200">
            /platform/dashboard
          </span>
          <button
            type="button"
            onClick={loadPlatformData}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-xs font-semibold text-white hover:border-violet-500 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-rose-500/25 bg-rose-950/20 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatTile label="Tenants" value={summary?.total_tenants} icon={Building2} />
        <StatTile label="Active Tenants" value={summary?.active_tenants} icon={CheckCircle} tone="text-emerald-400" />
        <StatTile label="Users" value={summary?.total_users} icon={Users} tone="text-blue-400" />
        <StatTile label="Platform Admins" value={summary?.platform_admins} icon={ShieldAlert} tone="text-amber-400" />
        <StatTile label="Gateway Requests" value={summary?.total_gateway_requests} icon={Activity} tone="text-fuchsia-400" />
        <StatTile label="Blocked" value={summary?.blocked_gateway_requests} icon={ShieldAlert} tone="text-rose-400" />
      </div>

      <section className="glass-card overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-white/5">
          <div>
            <h2 className="text-lg font-bold text-white">Tenant Directory</h2>
            <p className="text-xs text-gray-400 mt-1">All customer organizations registered in AuthClaw.</p>
          </div>
          <Database className="w-5 h-5 text-violet-400" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-900/70 text-[10px] uppercase tracking-wider text-gray-500">
              <tr>
                <th className="px-5 py-4">Tenant</th>
                <th className="px-5 py-4">Admin Email</th>
                <th className="px-5 py-4">Domain</th>
                <th className="px-5 py-4">Users</th>
                <th className="px-5 py-4">API Keys</th>
                <th className="px-5 py-4">Providers</th>
                <th className="px-5 py-4">Requests</th>
                <th className="px-5 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {tenants.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-gray-500">
                    No tenants registered yet.
                  </td>
                </tr>
              ) : tenants.map((tenant) => (
                <tr key={tenant.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-4">
                    <div className="font-semibold text-white">{tenant.name}</div>
                    <div className="text-[10px] text-gray-500">Tenant #{tenant.id}</div>
                  </td>
                  <td className="px-5 py-4 text-gray-300">{tenant.email || 'N/A'}</td>
                  <td className="px-5 py-4 text-gray-400">{tenant.domain || 'N/A'}</td>
                  <td className="px-5 py-4 font-mono text-gray-200">{tenant.users_count}</td>
                  <td className="px-5 py-4 font-mono text-gray-200">{tenant.api_keys_count}</td>
                  <td className="px-5 py-4 font-mono text-gray-200">{tenant.provider_credentials_count}</td>
                  <td className="px-5 py-4 font-mono text-gray-200">{tenant.gateway_requests_count}</td>
                  <td className="px-5 py-4">
                    <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${
                      tenant.email_verified && tenant.domain_verified
                        ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                    }`}>
                      {tenant.email_verified && tenant.domain_verified ? tenant.status : 'Pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default PlatformDashboard;
