import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Clock, Database, GitBranch, Router, ShieldCheck } from 'lucide-react';
import { getGatewayRequestById } from '../../services/gatewayService';
import { useToast } from '../../components/Common/Toast';

const formatDate = (value) => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
};

const GatewayRequestDetail = () => {
  const { requestId } = useParams();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    const fetchRequest = async () => {
      try {
        const data = await getGatewayRequestById(requestId);
        setRequest(data);
      } catch (error) {
        console.error('Failed to load gateway request detail:', error);
        addToast('Failed to load gateway request detail.', 'error');
      } finally {
        setLoading(false);
      }
    };

    fetchRequest();
  }, [requestId]);

  if (loading) {
    return <div className="glass-card p-6 text-sm text-gray-400">Loading gateway request detail...</div>;
  }

  if (!request) {
    return (
      <div className="space-y-4">
        <Link to="/requests" className="inline-flex items-center gap-2 text-sm text-violet-400 hover:text-violet-300">
          <ArrowLeft className="w-4 h-4" /> Back to Gateway Requests
        </Link>
        <div className="glass-card p-6 text-sm text-gray-400">Gateway request not found.</div>
      </div>
    );
  }

  const trace = request.trace || [];
  const routerEvents = trace.filter((event) => event.agent_name?.toLowerCase().includes('router') || event.agent?.toLowerCase().includes('router'));
  const approvalEvents = trace.filter((event) => String(event.details || '').toLowerCase().includes('approval') || event.event_type?.toLowerCase().includes('approval'));
  const auditEvents = trace.filter((event) => event.agent_name?.toLowerCase().includes('audit') || event.agent?.toLowerCase().includes('audit') || event.agent_name?.toLowerCase().includes('registrar'));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link to="/requests" className="inline-flex items-center gap-2 text-xs text-violet-400 hover:text-violet-300 mb-3">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Gateway Requests
          </Link>
          <h1 className="text-2xl font-bold text-white">Request Detail</h1>
          <p className="text-xs text-gray-400 font-mono mt-1">{request.request_id}</p>
        </div>
        <span className="px-3 py-1 rounded-lg bg-slate-900 border border-white/10 text-xs font-bold text-gray-200">
          {request.decision || request.status || 'UNKNOWN'}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase font-bold tracking-wider">
            <Database className="w-4 h-4 text-violet-400" /> Tenant
          </div>
          <p className="text-lg font-bold text-white mt-2">{request.tenant_id || 'N/A'}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase font-bold tracking-wider">
            <Router className="w-4 h-4 text-violet-400" /> Provider
          </div>
          <p className="text-lg font-bold text-white mt-2 capitalize">{request.provider || 'N/A'}</p>
          <p className="text-xs text-gray-500 font-mono mt-1">{request.model || 'N/A'}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase font-bold tracking-wider">
            <GitBranch className="w-4 h-4 text-violet-400" /> Route
          </div>
          <p className="text-lg font-bold text-white mt-2">{request.route_id || 'Default'}</p>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase font-bold tracking-wider">
            <Clock className="w-4 h-4 text-violet-400" /> Duration
          </div>
          <p className="text-lg font-bold text-white mt-2">{request.duration_ms ?? request.latency ?? 0} ms</p>
          <p className="text-xs text-gray-500 mt-1">{formatDate(request.created_at || request.timestamp)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass-card p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-white mb-3">Provider Routing</h3>
          {routerEvents.length === 0 ? (
            <p className="text-xs text-gray-500">No provider router events recorded.</p>
          ) : (
            <div className="space-y-2">
              {routerEvents.map((event, index) => (
                <div key={index} className="bg-slate-900/60 border border-white/5 rounded-lg p-3 text-xs">
                  <p className="font-bold text-violet-300">{event.event_type || event.event}</p>
                  <p className="text-gray-400 mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="glass-card p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-white mb-3">Approval Decisions</h3>
          {approvalEvents.length === 0 ? (
            <p className="text-xs text-gray-500">No approval events recorded for this request.</p>
          ) : (
            <div className="space-y-2">
              {approvalEvents.map((event, index) => (
                <div key={index} className="bg-slate-900/60 border border-white/5 rounded-lg p-3 text-xs">
                  <p className="font-bold text-amber-300">{event.event_type || event.event}</p>
                  <p className="text-gray-400 mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="glass-card p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-white mb-3">Audit References</h3>
          {auditEvents.length === 0 ? (
            <p className="text-xs text-gray-500">No audit or registrar events recorded.</p>
          ) : (
            <div className="space-y-2">
              {auditEvents.map((event, index) => (
                <div key={index} className="bg-slate-900/60 border border-white/5 rounded-lg p-3 text-xs">
                  <p className="font-bold text-emerald-300">{event.agent_name || event.agent}</p>
                  <p className="text-gray-400 mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="glass-card p-5">
        <h3 className="text-xs font-bold uppercase tracking-wider text-white mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          Agent Sequence
        </h3>
        <div className="space-y-3">
          {trace.length === 0 ? (
            <p className="text-xs text-gray-500">No trace events recorded for this request.</p>
          ) : (
            trace.map((event, index) => (
              <div key={index} className="grid grid-cols-[64px_160px_1fr] gap-4 items-start bg-slate-900/50 border border-white/5 rounded-lg p-3 text-xs">
                <div className="font-mono text-violet-300">#{event.sequence ?? index + 1}</div>
                <div>
                  <p className="font-bold text-white">{event.agent_name || event.agent || 'Agent'}</p>
                  <p className="text-[10px] text-gray-500">{formatDate(event.timestamp)}</p>
                </div>
                <div>
                  <p className="font-bold text-gray-300">{event.event_type || event.event}</p>
                  <p className="text-gray-500 mt-1 whitespace-pre-wrap break-words">{event.details}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default GatewayRequestDetail;
