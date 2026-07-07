import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Clock, Database, GitBranch, Router, ShieldCheck } from 'lucide-react';
import { getGatewayRequestById } from '../../services/gatewayService';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge 
} from '../../components/Common/DesignSystem';

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
    return <div className="glass-card p-6 text-sm text-[#475069]">Loading gateway request detail...</div>;
  }

  if (!request) {
    return (
      <div className="space-y-4">
        <Link to="/requests" className="inline-flex items-center gap-2 text-sm text-[#6D28D9] hover:text-[#6D28D9]">
          <ArrowLeft className="w-4 h-4" /> Back to Gateway Requests
        </Link>
        <div className="glass-card p-6 text-sm text-[#475069]">Gateway request not found.</div>
      </div>
    );
  }

  const trace = request.trace || [];
  const routerEvents = trace.filter((event) => event.agent_name?.toLowerCase().includes('router') || event.agent?.toLowerCase().includes('router'));
  const approvalEvents = trace.filter((event) => String(event.details || '').toLowerCase().includes('approval') || event.event_type?.toLowerCase().includes('approval'));
  const auditEvents = trace.filter((event) => event.agent_name?.toLowerCase().includes('audit') || event.agent?.toLowerCase().includes('audit') || event.agent_name?.toLowerCase().includes('registrar'));

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
        <div>
          <Link to="/requests" className="inline-flex items-center gap-2 text-xs text-[#6D28D9] hover:text-[#6D28D9] mb-3">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Gateway Requests
          </Link>
          <h1 className="text-2xl font-bold text-[#0E1726] font-display">
            Request Detail
          </h1>
          <p className="text-xs text-[#475069] font-mono mt-1">{request.request_id}</p>
        </div>
        <StatusBadge status={request.decision || request.status || 'UNKNOWN'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <GlassCard hover={false} className="p-4">
          <div className="flex items-center gap-2 text-[10px] text-[#6B7488] uppercase font-bold tracking-wider font-display">
            <Database className="w-4 h-4 text-[#6D28D9]" /> Tenant
          </div>
          <p className="text-lg font-bold text-[#0E1726] mt-2 font-mono">{request.tenant_id || 'N/A'}</p>
        </GlassCard>
        
        <GlassCard hover={false} className="p-4">
          <div className="flex items-center gap-2 text-[10px] text-[#6B7488] uppercase font-bold tracking-wider font-display">
            <Router className="w-4 h-4 text-[#6D28D9]" /> Provider
          </div>
          <p className="text-lg font-bold text-[#0E1726] mt-2 capitalize font-mono">{request.provider || 'N/A'}</p>
          <p className="text-xs text-[#6B7488] font-mono mt-1">{request.model || 'N/A'}</p>
        </GlassCard>
        
        <GlassCard hover={false} className="p-4">
          <div className="flex items-center gap-2 text-[10px] text-[#6B7488] uppercase font-bold tracking-wider font-display">
            <GitBranch className="w-4 h-4 text-[#6D28D9]" /> Route
          </div>
          <p className="text-lg font-bold text-[#0E1726] mt-2 font-mono">{request.route_id || 'Default'}</p>
        </GlassCard>
        
        <GlassCard hover={false} className="p-4">
          <div className="flex items-center gap-2 text-[10px] text-[#6B7488] uppercase font-bold tracking-wider font-display">
            <Clock className="w-4 h-4 text-[#6D28D9]" /> Duration
          </div>
          <p className="text-lg font-bold text-[#0E1726] mt-2 font-mono">{request.duration_ms ?? request.latency ?? 0} ms</p>
          <p className="text-xs text-[#6B7488] mt-1 font-mono">{formatDate(request.created_at || request.timestamp)}</p>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard hover={false} className="p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0E1726] mb-3 font-display">Provider Routing</h3>
          {routerEvents.length === 0 ? (
            <p className="text-xs text-[#6B7488]">No provider router events recorded.</p>
          ) : (
            <div className="space-y-2">
              {routerEvents.map((event, index) => (
                <div key={index} className="bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-3 text-xs font-mono">
                  <p className="font-bold text-[#6D28D9]">{event.event_type || event.event}</p>
                  <p className="text-[#475069] mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        <GlassCard hover={false} className="p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0E1726] mb-3 font-display">Approval Decisions</h3>
          {approvalEvents.length === 0 ? (
            <p className="text-xs text-[#6B7488]">No approval events recorded for this request.</p>
          ) : (
            <div className="space-y-2">
              {approvalEvents.map((event, index) => (
                <div key={index} className="bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-3 text-xs font-mono">
                  <p className="font-bold text-amber-300">{event.event_type || event.event}</p>
                  <p className="text-[#475069] mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        <GlassCard hover={false} className="p-5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0E1726] mb-3 font-display">Audit References</h3>
          {auditEvents.length === 0 ? (
            <p className="text-xs text-[#6B7488]">No audit or registrar events recorded.</p>
          ) : (
            <div className="space-y-2">
              {auditEvents.map((event, index) => (
                <div key={index} className="bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-3 text-xs font-mono">
                  <p className="font-bold text-emerald-300">{event.agent_name || event.agent}</p>
                  <p className="text-[#475069] mt-1">{event.details}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      <GlassCard hover={false} className="p-5">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#0E1726] mb-4 flex items-center gap-2 font-display">
          <ShieldCheck className="w-4 h-4 text-emerald-400 animate-pulse" />
          Agent Sequence
        </h3>
        <div className="space-y-3">
          {trace.length === 0 ? (
            <p className="text-xs text-[#6B7488]">No trace events recorded for this request.</p>
          ) : (
            trace.map((event, index) => (
              <div key={index} className="grid grid-cols-[64px_160px_1fr] gap-4 items-start bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-3 text-xs">
                <div className="font-mono text-[#6D28D9]">#{event.sequence ?? index + 1}</div>
                <div>
                  <p className="font-bold text-[#0E1726]">{event.agent_name || event.agent || 'Agent'}</p>
                  <p className="text-[10px] text-[#6B7488] font-mono">{formatDate(event.timestamp)}</p>
                </div>
                <div>
                  <p className="font-bold text-[#475069]">{event.event_type || event.event}</p>
                  <p className="text-[#6B7488] mt-1 whitespace-pre-wrap break-words">{event.details}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </GlassCard>
    </div>
  );
};

export default GatewayRequestDetail;
