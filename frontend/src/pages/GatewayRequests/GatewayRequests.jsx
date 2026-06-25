import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Clock, Database, RefreshCw, Router, ShieldAlert } from 'lucide-react';
import { getGatewayRequests } from '../../services/gatewayService';
import { useToast } from '../../components/Common/Toast';

const formatDate = (value) => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
};

const statusClass = (status, decision) => {
  if (status === 'blocked' || decision === 'BLOCK') return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  if (status === 'pending_approval' || decision === 'REQUIRE_APPROVAL') return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
};

const GatewayRequests = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  const fetchRequests = async () => {
    try {
      const data = await getGatewayRequests(200);
      setRequests(data || []);
    } catch (error) {
      console.error('Failed to load gateway requests:', error);
      addToast('Failed to load gateway request history.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
    const interval = setInterval(fetchRequests, 15000);
    return () => clearInterval(interval);
  }, []);

  const totals = {
    all: requests.length,
    allowed: requests.filter((req) => req.status === 'allowed' || req.decision === 'ALLOW').length,
    blocked: requests.filter((req) => req.status === 'blocked' || req.decision === 'BLOCK').length,
    pending: requests.filter((req) => req.status === 'pending_approval' || req.decision === 'REQUIRE_APPROVAL').length,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Gateway Requests</h1>
          <p className="text-xs text-gray-400 mt-1">
            Runtime request lifecycle records from the AuthClaw Gateway.
          </p>
        </div>
        <button
          onClick={fetchRequests}
          className="flex items-center gap-2 px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-xs font-semibold text-gray-200 hover:border-violet-500 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-gray-500 text-[10px] font-bold uppercase tracking-wider">
            Total
            <Database className="w-4 h-4 text-violet-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{totals.all}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-gray-500 text-[10px] font-bold uppercase tracking-wider">
            Allowed
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{totals.allowed}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-gray-500 text-[10px] font-bold uppercase tracking-wider">
            Blocked
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{totals.blocked}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-gray-500 text-[10px] font-bold uppercase tracking-wider">
            Pending
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{totals.pending}</p>
        </div>
      </div>

      <div className="glass-card overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-white/5 text-gray-400 uppercase tracking-wider bg-white/2">
              <th className="py-4 px-5 font-semibold">Request</th>
              <th className="py-4 px-5 font-semibold">Created</th>
              <th className="py-4 px-5 font-semibold">Tenant</th>
              <th className="py-4 px-5 font-semibold">Provider</th>
              <th className="py-4 px-5 font-semibold">Model</th>
              <th className="py-4 px-5 font-semibold">Decision</th>
              <th className="py-4 px-5 font-semibold">Duration</th>
              <th className="py-4 px-5 text-right font-semibold">Trace</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-gray-300">
            {loading ? (
              <tr>
                <td colSpan="8" className="py-10 text-center text-gray-500">Loading gateway requests...</td>
              </tr>
            ) : requests.length === 0 ? (
              <tr>
                <td colSpan="8" className="py-10 text-center text-gray-500">No gateway requests recorded yet.</td>
              </tr>
            ) : (
              requests.map((request) => (
                <tr key={request.request_id} className="hover:bg-white/2 transition-colors">
                  <td className="py-4 px-5 font-mono text-violet-300 max-w-[180px] truncate">{request.request_id}</td>
                  <td className="py-4 px-5 text-gray-400">{formatDate(request.created_at || request.timestamp)}</td>
                  <td className="py-4 px-5 font-mono text-gray-300">{request.tenant_id || 'N/A'}</td>
                  <td className="py-4 px-5 capitalize">
                    <span className="inline-flex items-center gap-1.5">
                      <Router className="w-3.5 h-3.5 text-violet-400" />
                      {request.provider || 'N/A'}
                    </span>
                  </td>
                  <td className="py-4 px-5 font-mono text-gray-400">{request.model || 'N/A'}</td>
                  <td className="py-4 px-5">
                    <span className={`px-2 py-1 rounded border text-[10px] font-bold ${statusClass(request.status, request.decision)}`}>
                      {request.decision || request.status || 'UNKNOWN'}
                    </span>
                  </td>
                  <td className="py-4 px-5 text-gray-400">{request.duration_ms ?? request.latency ?? 0} ms</td>
                  <td className="py-4 px-5 text-right">
                    <Link
                      to={`/requests/${request.request_id}`}
                      className="inline-flex items-center gap-1 text-violet-400 hover:text-violet-300 font-semibold"
                    >
                      Details <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default GatewayRequests;
