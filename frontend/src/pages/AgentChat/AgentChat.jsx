import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  User, 
  Bot, 
  AlertTriangle, 
  Plus, 
  Loader, 
  Trash2, 
  Clock, 
  ShieldAlert,
  Activity,
  X,
  ShieldCheck,
  CheckCircle,
  FileText,
  HelpCircle,
  ArrowRight
} from 'lucide-react';
import { 
  sendChatMessage, 
  createChatSession, 
  getChatSessions, 
  getSessionMessages, 
  deleteChatSession, 
  deleteAllChatSessions 
} from '../../services/chatService';

const AgentChat = () => {
  const [sessionId, setSessionId] = useState('');
  const [sessionsList, setSessionsList] = useState([]);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your AuthClaw security-wrapped assistant. Type anything to test security compliance, risk assessments, or redactions.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Trace drawer state
  const [activeTrace, setActiveTrace] = useState(null);

  const messagesEndRef = useRef(null);

  const extractGatewayMeta = (data) => ({
    request_id: data.request_id,
    tenant_id: data.tenant_id,
    provider: data.provider,
    model: data.model,
    route_id: data.route_id,
    decision: data.decision,
    duration: data.duration_ms ?? data.duration,
    risk_level: data.risk_level,
  });

  const hasGatewayMeta = (meta) => meta && Object.values(meta).some((value) => value !== undefined && value !== null && value !== '');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const fetchSessions = async () => {
    try {
      const list = await getChatSessions();
      if (list && list.length > 0) {
        const ids = list.map(s => s.session_id);
        setSessionsList(ids);
        setSessionId(ids[0]);
      } else {
        const newId = `session-${Math.random().toString(36).substr(2, 9)}`;
        await createChatSession(newId, "Initial Chat");
        setSessionsList([newId]);
        setSessionId(newId);
      }
    } catch (e) {
      console.error("Failed to fetch sessions:", e);
    }
  };

  const loadMessages = async (id) => {
    if (!id) return;
    setLoading(true);
    try {
      const msgs = await getSessionMessages(id);
      if (msgs && msgs.length > 0) {
        setMessages(msgs);
      } else {
        setMessages([
          { role: 'assistant', content: 'Hello! I am your AuthClaw security-wrapped assistant. Type anything to test security compliance, risk assessments, or redactions.' }
        ]);
      }
    } catch (e) {
      console.error("Failed to load messages:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    if (sessionId) {
      loadMessages(sessionId);
      setActiveTrace(null); // Clear active trace when changing session
    }
  }, [sessionId]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    // Optimistically add user message to UI
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const data = await sendChatMessage(sessionId, userMessage);
      const gatewayMeta = extractGatewayMeta(data);

      // ── CASE A: Policy Violation Block ────────────────────────────────────
      if (data.status === 'blocked' && data.reason === 'policy_violation') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'blocked',
            category: data.category,
            reason: data.reason,
            gatewayMeta,
            trace: data.trace
          }
        ]);
        // Auto-show trace on block
        if (data.trace && data.trace.length > 0) {
          setActiveTrace(data.trace);
        }
        return; 
      }

      // ── CASE B: Approval Required (HIGH risk) ────────────────────────────
      if (data.status === 'approval_required' || data.approval_status === 'PENDING_APPROVAL') {
        setMessages((prev) => {
          if (data.approval_id && prev.some(m => m.approvalId === data.approval_id)) {
            return prev;
          }
          return [
            ...prev,
            {
              role: 'approval',
              content: '⚠️ High-risk action detected. This request requires manual approval before it can proceed.',
              approvalId: data.approval_id,
              riskLevel: data.risk_level || 'HIGH',
              gatewayMeta,
              trace: data.trace
            }
          ];
        });
        // Auto-show trace on approval flow trigger
        if (data.trace && data.trace.length > 0) {
          setActiveTrace(data.trace);
        }
        return; 
      }

      // ── CASE C: Normal Assistant Response ────────────────────────────────
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response || 'No response returned from the proxy.',
          gatewayMeta,
          trace: data.trace
        }
      ]);

    } catch (err) {
      console.error('[AgentChat] Request error:', err);

      // Handle policy violation returned as HTTP error
      if (err.response && err.response.status === 403 && err.response.data?.error?.type === 'policy_violation') {
        const errorData = err.response.data;
        setMessages((prev) => [
          ...prev,
          {
            role: 'blocked',
            category: errorData.error.category || 'prompt_injection',
            reason: 'policy_violation',
            trace: errorData.trace || []
          }
        ]);
        if (errorData.trace && errorData.trace.length > 0) {
          setActiveTrace(errorData.trace);
        }
        return;
      }

      // Handle provider not configured
      if (err.response && err.response.status === 500 && err.response.data?.error === 'provider_not_configured') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'error',
            content: '⚠️ Model provider is not configured. Please check your API credentials.'
          }
        ]);
        return;
      }

      // Handle provider unavailable (rate limit, timeout, etc.)
      if (err.response && err.response.status === 503) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'error',
            content: '⚠️ Model provider is currently unavailable. Please try again in a moment.'
          }
        ]);
        return;
      }

      // Generic network / server error
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: '❌ Failed to communicate with AuthClaw Gateway. Please check the server.' }
      ]);

    } finally {
      setLoading(false);
    }
  };

  const handleNewSession = async () => {
    const newId = `session-${Math.random().toString(36).substr(2, 9)}`;
    try {
      await createChatSession(newId, "New Session");
      setSessionsList((prev) => [newId, ...prev]);
      setSessionId(newId);
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  };

  const handleDeleteSession = async (e, idToDelete) => {
    e.stopPropagation();
    try {
      await deleteChatSession(idToDelete);
      if (idToDelete === sessionId) {
        const remaining = sessionsList.filter(id => id !== idToDelete);
        if (remaining.length > 0) {
          setSessionsList(remaining);
          setSessionId(remaining[0]);
        } else {
          await fetchSessions();
        }
      } else {
        setSessionsList(prev => prev.filter(id => id !== idToDelete));
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const handleDeleteAllSessions = async () => {
    if (!window.confirm("Are you sure you want to delete all chat sessions?")) return;
    try {
      await deleteAllChatSessions();
      await fetchSessions();
    } catch (err) {
      console.error("Failed to delete all sessions:", err);
    }
  };

  // Prettify details helper
  const renderDetails = (details) => {
    if (!details) return '';
    try {
      const parsed = typeof details === 'string' ? JSON.parse(details) : details;
      return JSON.stringify(parsed, null, 2);
    } catch (e) {
      return String(details);
    }
  };

  const renderGatewayMeta = (meta) => {
    if (!hasGatewayMeta(meta)) return null;
    const rows = [
      ['Request', meta.request_id],
      ['Tenant', meta.tenant_id],
      ['Provider', meta.provider],
      ['Model', meta.model],
      ['Route', meta.route_id],
      ['Decision', meta.decision],
      ['Duration', meta.duration !== undefined && meta.duration !== null ? `${meta.duration} ms` : null],
      ['Risk', meta.risk_level],
    ].filter(([, value]) => value !== undefined && value !== null && value !== '');

    return (
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-white/5 pt-3">
        {rows.map(([label, value]) => (
          <div key={label} className="bg-slate-950/45 border border-white/5 rounded-lg px-2.5 py-2">
            <p className="text-[9px] text-gray-500 uppercase font-bold tracking-wider">{label}</p>
            <p className="text-[11px] text-gray-200 font-mono truncate mt-0.5">{value}</p>
          </div>
        ))}
      </div>
    );
  };

  // ── Message Renderers ──────────────────────────────────────────────────────

  const renderMessage = (msg, index) => {
    const hasTrace = msg.trace && msg.trace.length > 0;

    // Approval Required Card
    if (msg.role === 'approval') {
      return (
        <div key={index} className="flex justify-center">
          <div className="glass-card max-w-lg w-full p-4 bg-amber-950/30 border border-amber-500/20 text-amber-200 text-sm">
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                  <Clock className="w-4 h-4 text-amber-400" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-amber-300 text-sm">Approval Required</p>
                <p className="text-amber-200/80 text-xs mt-1 leading-relaxed">{msg.content}</p>
                {msg.riskLevel && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-[10px] text-amber-400/70 uppercase tracking-wider">Risk Level:</span>
                    <span className="text-xs font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">{msg.riskLevel}</span>
                  </div>
                )}
                {msg.approvalId && (
                  <div className="mt-3 flex items-center gap-2 bg-slate-950/40 p-2 border border-white/5 rounded text-xs font-mono text-gray-400">
                    <span className="text-gray-500">ID:</span>
                    <span className="truncate">{msg.approvalId}</span>
                  </div>
                )}
                {renderGatewayMeta(msg.gatewayMeta)}
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-amber-500/15">
                  <p className="text-xs text-amber-300/60 italic flex-1">
                    Visit the Approval Center to review this request.
                  </p>
                  {hasTrace && (
                    <button
                      onClick={() => setActiveTrace(msg.trace)}
                      className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 font-semibold transition"
                    >
                      <Activity className="w-3.5 h-3.5" /> View Trace
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    // Legacy system role
    if (msg.role === 'system') {
      const isApproval = msg.approvalId || (msg.content && msg.content.includes('manual approval'));
      return (
        <div key={index} className="flex justify-center">
          <div className={`glass-card max-w-lg p-4 text-sm flex gap-3.5 ${isApproval ? 'bg-amber-950/30 border-amber-500/20 text-amber-200' : 'bg-slate-900/50 border-white/10 text-gray-300'}`}>
            <AlertTriangle className={`w-5 h-5 shrink-0 ${isApproval ? 'text-amber-400' : 'text-gray-400'}`} />
            <div className="flex-1 min-w-0">
              <p className="font-semibold">{msg.content}</p>
              {msg.riskLevel && (
                <p className="text-xs mt-1 opacity-80">Risk Level: <span className="font-bold">{msg.riskLevel}</span></p>
              )}
              {msg.approvalId && (
                <div className="mt-3 flex items-center gap-2 bg-slate-950/40 p-2 border border-white/5 rounded text-xs font-mono">
                  <span>Approval ID: {msg.approvalId}</span>
                </div>
              )}
              {hasTrace && (
                <button
                  onClick={() => setActiveTrace(msg.trace)}
                  className="mt-3 flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 font-semibold transition"
                >
                  <Activity className="w-3.5 h-3.5" /> View Trace Logs
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    // Policy Block Card
    if (msg.role === 'blocked') {
      const formatCategory = (cat) => {
        if (!cat) return 'Policy Violation';
        return cat.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      };
      return (
        <div key={index} className="flex justify-center">
          <div className="glass-card max-w-lg w-full p-4 bg-red-950/30 border border-red-500/20 text-red-200 text-sm">
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="w-8 h-8 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-red-400 text-sm">Request Blocked</p>
                <p className="text-xs text-red-300/80 mt-1">Reason: <span className="font-bold text-red-200">Policy Violation</span></p>
                <p className="text-xs text-red-300/80 mt-0.5">Category: <span className="font-bold text-red-200">{formatCategory(msg.category)}</span></p>
                <p className="text-xs text-red-300/60 mt-3 border-t border-red-500/10 pt-2 leading-relaxed">
                  This request violated AuthClaw security policies and was prevented from reaching the model provider.
                </p>
                {renderGatewayMeta(msg.gatewayMeta)}
                {hasTrace && (
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={() => setActiveTrace(msg.trace)}
                      className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 font-semibold transition"
                    >
                      <Activity className="w-3.5 h-3.5" /> View Policy Block Trace
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }

    // Error Card
    if (msg.role === 'error') {
      return (
        <div key={index} className="flex justify-center">
          <div className="glass-card max-w-lg p-4 bg-slate-900/60 border border-white/10 text-gray-300 text-sm flex gap-3">
            <AlertTriangle className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
            <p>{msg.content}</p>
          </div>
        </div>
      );
    }

    // User / Assistant messages
    const isUser = msg.role === 'user';
    return (
      <div key={index} className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
        {!isUser && (
          <div className="w-8 h-8 rounded-lg bg-violet-600/10 border border-violet-500/20 flex items-center justify-center text-violet-400 shrink-0 shadow-lg">
            <Bot className="w-4 h-4" />
          </div>
        )}
        <div className={`p-4 rounded-xl max-w-xl text-sm leading-relaxed shadow-lg flex flex-col ${
          isUser
            ? 'bg-gradient-to-tr from-violet-600 to-fuchsia-600 text-white rounded-tr-none'
            : 'glass-card text-gray-300 rounded-tl-none'
        }`}>
          <p className="whitespace-pre-wrap">{msg.content}</p>
          {!isUser && renderGatewayMeta(msg.gatewayMeta)}
          {!isUser && hasTrace && (
            <div className="mt-2.5 pt-2.5 border-t border-white/5 flex justify-end">
              <button
                onClick={() => setActiveTrace(msg.trace)}
                className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 font-semibold transition"
              >
                <Activity className="w-3.5 h-3.5" /> View Security Trace
              </button>
            </div>
          )}
        </div>
        {isUser && (
          <div className="w-8 h-8 rounded-lg bg-fuchsia-600/10 border border-fuchsia-500/20 flex items-center justify-center text-fuchsia-400 shrink-0 shadow-lg">
            <User className="w-4 h-4" />
          </div>
        )}
      </div>
    );
  };

  // Parse trace logs by agent
  const securityEvents = activeTrace?.filter(e => {
    const agent = e.agent?.toLowerCase() || '';
    return agent.includes('security') || agent.includes('risk') || agent.includes('authclaw checks');
  }) || [];
  const policyEvents = activeTrace?.filter(e => {
    const agent = e.agent?.toLowerCase() || '';
    return agent.includes('policy') || agent.includes('decision');
  }) || [];
  const registrarEvents = activeTrace?.filter(e => {
    const agent = e.agent?.toLowerCase() || '';
    return agent.includes('audit') || agent.includes('registrar');
  }) || [];
  const routerEvents = activeTrace?.filter(e => e.agent?.toLowerCase().includes('router')) || [];
  const guardEvents = activeTrace?.filter(e => e.agent?.toLowerCase().includes('guard')) || [];

  return (
    <div className="flex h-[calc(100vh-8rem)] rounded-xl border border-white/5 bg-slate-950/45 overflow-hidden relative">
      {/* Sidebar for Sessions */}
      <div className="w-64 border-r border-white/5 bg-slate-950/20 flex flex-col">
        <div className="p-4 border-b border-white/5 space-y-2">
          <button
            onClick={handleNewSession}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-lg text-sm font-semibold hover:opacity-90 transition shadow-lg shadow-violet-500/10"
          >
            <Plus className="w-4 h-4" />
            New Gateway Session
          </button>
          <button
            onClick={handleDeleteAllSessions}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-950/45 border border-red-500/20 text-red-200 rounded-lg text-xs font-semibold hover:bg-red-900/30 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear Gateway History
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <span className="text-xs text-gray-500 font-bold uppercase tracking-wider block mb-2">Gateway Sessions</span>
          {sessionsList.map((id) => (
            <div
              key={id}
              className={`group flex items-center justify-between px-3 py-1.5 rounded-lg border transition ${
                id === sessionId
                  ? 'bg-violet-600/10 border-violet-500/20 text-white font-medium'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white border-transparent'
              }`}
            >
              <button
                onClick={() => setSessionId(id)}
                className="flex-1 text-left text-xs font-mono truncate mr-2"
              >
                {id}
              </button>
              <button
                onClick={(e) => handleDeleteSession(e, id)}
                className="opacity-0 group-hover:opacity-100 hover:text-red-400 p-1 rounded transition"
                title="Delete Session"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col bg-slate-950/10 min-w-0">
        {/* Chat Header */}
        <div className="h-14 border-b border-white/5 bg-slate-950/45 px-6 flex items-center justify-between">
          <span className="text-sm font-medium text-white flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Gateway Chat Console
          </span>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1.5 rounded-lg bg-violet-600/15 border border-violet-500/25 text-[11px] font-bold text-violet-200">
              Gateway Pipeline
            </span>
            <span className="text-xs font-mono text-gray-500">ID: {sessionId}</span>
          </div>
        </div>

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, index) => renderMessage(msg, index))}

          {loading && (
            <div className="flex gap-4 justify-start">
              <div className="w-8 h-8 rounded-lg bg-violet-600/10 border border-violet-500/20 flex items-center justify-center text-violet-400 shrink-0 animate-spin">
                <Loader className="w-4 h-4" />
              </div>
              <div className="p-4 glass-card text-gray-400 rounded-xl rounded-tl-none flex items-center gap-2 text-xs">
                <span>Running Security Agent, Policy Agent, and Audit Agent checks...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form onSubmit={handleSend} className="p-4 border-t border-white/5 bg-slate-950/45">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Send a prompt through the AuthClaw Gateway..."
              disabled={loading}
              className="flex-1 glass-input py-3"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-5 py-3 bg-gradient-to-tr from-violet-600 to-fuchsia-600 hover:opacity-90 rounded-lg text-white font-semibold transition disabled:opacity-50 flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>

      {/* Multi-Agent Trace Drawer */}
      {activeTrace && (
        <div className="w-96 border-l border-white/5 bg-slate-950/95 flex flex-col h-full z-20 absolute right-0 top-0 shadow-2xl animate-slideLeft">
          {/* Header */}
          <div className="h-14 px-5 border-b border-white/5 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-bold text-white">Security execution Trace</span>
            </div>
            <button 
              onClick={() => setActiveTrace(null)} 
              className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Timeline Contents */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6 scrollbar-thin">
            
            {/* Sequence flow illustration */}
            <div className="flex items-center justify-between p-2.5 bg-slate-900/60 rounded-lg border border-white/5 text-[8.5px] text-gray-400 font-semibold tracking-wider uppercase mb-2">
              <span>Security</span>
              <ArrowRight className="w-2.5 h-2.5 text-violet-500" />
              <span>Policy</span>
              <ArrowRight className="w-2.5 h-2.5 text-violet-500" />
              <span>Audit</span>
            </div>

            {/* Timeline */}
            <div className="relative pl-6 border-l border-dashed border-white/10 space-y-6">
              
              {/* Agent 1: Security */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  securityEvents.length > 0 
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400' 
                    : 'bg-slate-900 border-white/15 text-gray-500'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">1. Security Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      securityEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-900 text-gray-500'
                    }`}>
                      {securityEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Validates input, detects prompt injection, secrets, PII, and assigns request risk.
                  </p>

                  <div className="space-y-1.5">
                    {securityEvents.map((e, idx) => (
                      <div key={idx} className="bg-slate-900/80 p-2.5 rounded border border-white/5 text-xs font-mono">
                        <div className="text-[10px] text-violet-400 font-bold mb-1">{e.event}</div>
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {securityEvents.length === 0 && (
                      <div className="text-xs text-gray-600 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 2: Policy */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  policyEvents.length > 0 
                    ? (activeTrace.some(e => e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('blocked') || e.event?.toLowerCase().includes('leak')) ? 'bg-red-500/10 border-red-500 text-red-400' : 'bg-emerald-500/10 border-emerald-500 text-emerald-400')
                    : 'bg-slate-900 border-white/15 text-gray-500'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">2. Policy Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      policyEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-900 text-gray-500'
                    }`}>
                      {policyEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Evaluates prompt safety, scans for PII/PHI leak vectors, redacts inputs statefully, and checks custom tenant policies.
                  </p>

                  <div className="space-y-1.5">
                    {policyEvents.map((e, idx) => (
                      <div key={idx} className={`p-2.5 rounded border text-xs font-mono ${
                        e.event?.toLowerCase().includes('block') || e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('leak')
                          ? 'bg-red-950/20 border-red-500/20'
                          : 'bg-slate-900/80 border-white/5'
                      }`}>
                        <div className={`text-[10px] font-bold mb-1 ${
                          e.event?.toLowerCase().includes('block') || e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('leak')
                            ? 'text-red-400'
                            : 'text-violet-400'
                        }`}>{e.event}</div>
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {policyEvents.length === 0 && (
                      <div className="text-xs text-gray-600 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 3: Audit */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  registrarEvents.length > 0 
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400' 
                    : 'bg-slate-900 border-white/15 text-gray-500'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">3. Audit Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      registrarEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-900 text-gray-500'
                    }`}>
                      {registrarEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Records immutable request, response, decision, and compliance evidence for this tenant.
                  </p>

                  <div className="space-y-1.5">
                    {registrarEvents.map((e, idx) => (
                      <div key={idx} className="bg-slate-900/80 p-2.5 rounded border border-white/5 text-xs font-mono">
                        <div className="text-[10px] text-violet-400 font-bold mb-1">{e.event}</div>
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {registrarEvents.length === 0 && (
                      <div className="text-xs text-gray-600 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 4: LLM Router */}
              <div className="relative hidden">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  routerEvents.length > 0 
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400' 
                    : 'bg-slate-900 border-white/15 text-gray-500'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">4. LLM Router</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      routerEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-900 text-gray-500'
                    }`}>
                      {routerEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Dynamically routes compliant queries to selected models (OpenAI, Gemini, Claude) with retry failover logic.
                  </p>

                  <div className="space-y-1.5">
                    {routerEvents.map((e, idx) => (
                      <div key={idx} className="bg-slate-900/80 p-2.5 rounded border border-white/5 text-xs font-mono">
                        <div className="text-[10px] text-violet-400 font-bold mb-1">{e.event}</div>
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {routerEvents.length === 0 && (
                      <div className="text-xs text-gray-600 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 5: Response Guard */}
              <div className="relative hidden">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  guardEvents.length > 0 
                    ? (activeTrace.some(e => e.event?.toLowerCase().includes('redact')) ? 'bg-amber-500/10 border-amber-500 text-amber-400' : 'bg-emerald-500/10 border-emerald-500 text-emerald-400')
                    : 'bg-slate-900 border-white/15 text-gray-500'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">5. Response Guard</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      guardEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-900 text-gray-500'
                    }`}>
                      {guardEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Filters model outputs for security leaks, redacts accidental PII disclosure, and audits response payload content.
                  </p>

                  <div className="space-y-1.5">
                    {guardEvents.map((e, idx) => (
                      <div key={idx} className={`p-2.5 rounded border text-xs font-mono ${
                        e.event?.toLowerCase().includes('redact')
                          ? 'bg-amber-950/20 border-amber-500/20'
                          : 'bg-slate-900/80 border-white/5'
                      }`}>
                        <div className={`text-[10px] font-bold mb-1 ${
                          e.event?.toLowerCase().includes('redact') ? 'text-amber-400' : 'text-violet-400'
                        }`}>{e.event}</div>
                        <pre className="text-[10px] text-gray-400 whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {guardEvents.length === 0 && (
                      <div className="text-xs text-gray-600 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentChat;
