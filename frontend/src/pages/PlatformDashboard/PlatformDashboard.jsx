import React, { useEffect, useState } from 'react';
import { Activity, Building2, CheckCircle, Database, RefreshCw, ShieldAlert, Users } from 'lucide-react';
import apiClient from '../../services/api';
import { 
  Button, 
  GlassCard, 
  StatusBadge, 
  DataTable 
} from '../../components/Common/DesignSystem';

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

  const columns = [
    {
      key: 'name',
      header: 'Tenant',
      sortable: true,
      render: (tenant) => (
        <div>
          <div className="font-semibold text-white">{tenant.name}</div>
          <div className="text-[10px] text-gray-500 font-mono">Tenant #{tenant.id}</div>
        </div>
      )
    },
    {
      key: 'email',
      header: 'Admin Email',
      render: (tenant) => <span className="text-gray-300 text-xs">{tenant.email || 'N/A'}</span>
    },
    {
      key: 'domain',
      header: 'Domain',
      render: (tenant) => <span className="text-gray-400 font-mono text-xs">{tenant.domain || 'N/A'}</span>
    },
    {
      key: 'users_count',
      header: 'Users',
      render: (tenant) => <span className="font-mono text-gray-200">{tenant.users_count}</span>
    },
    {
      key: 'api_keys_count',
      header: 'API Keys',
      render: (tenant) => <span className="font-mono text-gray-200">{tenant.api_keys_count}</span>
    },
    {
      key: 'provider_credentials_count',
      header: 'Providers',
      render: (tenant) => <span className="font-mono text-gray-200">{tenant.provider_credentials_count}</span>
    },
    {
      key: 'gateway_requests_count',
      header: 'Requests',
      render: (tenant) => <span className="font-mono text-gray-200">{tenant.gateway_requests_count}</span>
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (tenant) => {
        const isVerified = tenant.email_verified && tenant.domain_verified;
        const text = isVerified ? tenant.status : 'Pending';
        return <StatusBadge status={text} />;
      }
    }
  ];

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.24em] text-violet-300 font-bold font-display">Platform Owner URL</p>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent font-display mt-1">
            AuthClaw Platform Administration
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Owner-only view across tenants, users, gateway traffic, and global platform health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-2 rounded-lg border border-white/5 bg-slate-950/60 text-xs font-mono text-violet-300">
            /platform/dashboard
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={loadPlatformData}
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-rose-500/25 bg-rose-950/20 text-sm text-rose-200 animate-fadeIn">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Tenants</span>
            <Building2 className="w-4 h-4 text-violet-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.total_tenants}</p>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Active Tenants</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.active_tenants}</p>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Users</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.total_users}</p>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Platform Admins</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.platform_admins}</p>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Gateway Requests</span>
            <Activity className="w-4 h-4 text-fuchsia-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.total_gateway_requests}</p>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex flex-col justify-between h-24">
          <div className="flex items-center justify-between text-gray-500">
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Blocked</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2 font-mono">{summary?.blocked_gateway_requests}</p>
        </GlassCard>
      </div>

      <GlassCard hover={false} className="p-0 overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-white/5 bg-slate-950/20">
          <div>
            <h2 className="text-base font-bold text-white font-display">Tenant Directory</h2>
            <p className="text-xs text-gray-400 mt-1">All customer organizations registered in AuthClaw.</p>
          </div>
          <Database className="w-5 h-5 text-violet-400 animate-pulse" />
        </div>

        <DataTable
          columns={columns}
          data={tenants}
        />
      </GlassCard>
    </div>
  );
};

export default PlatformDashboard;
