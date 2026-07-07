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
  Download,
  HelpCircle,
  ArrowRight
} from 'lucide-react';
import { 
  sendChatMessage, 
  redactGatewayDocument,
  createChatSession, 
  getChatSessions, 
  getSessionMessages, 
  deleteChatSession, 
  deleteAllChatSessions 
} from '../../services/chatService';

const PROVIDER_UNAVAILABLE_COPY = 'The configured model provider is currently unavailable. AuthClaw completed the security, policy, and audit checks, but the upstream model call could not be completed. Check the Providers page, API credentials, and outbound network access, then try again.';

const sanitizeProviderMessage = (content) => {
  const text = String(content || '');
  const providerErrorMarkers = [
    '[Offline Fallback]',
    'Provider unavailable:',
    'HTTPSConnectionPool',
    'generativelanguage.googleapis.com',
    'Max retries exceeded',
    'Failed to establish a new connection',
    'key=',
  ];

  return providerErrorMarkers.some((marker) => text.includes(marker))
    ? PROVIDER_UNAVAILABLE_COPY
    : text;
};

const AgentChat = () => {
  const [sessionId, setSessionId] = useState('');
  const [sessionsList, setSessionsList] = useState([]);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your AuthClaw security-wrapped assistant. Type anything to test security compliance, risk assessments, or redactions.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [documentContext, setDocumentContext] = useState(null);
  
  // Trace drawer state
  const [activeTrace, setActiveTrace] = useState(null);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

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
        setMessages(msgs.map((msg) => (
          msg.role === 'user'
            ? msg
            : { ...msg, content: sanitizeProviderMessage(msg.content) }
        )));
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
    const outboundMessage = documentContext
      ? `Use this sanitized uploaded document context to answer. Do not infer or restore redacted personal data.\n\nDocument: ${documentContext.filename}\n\nSanitized document text:\n${documentContext.redactedText}\n\nUser question: ${userMessage}`
      : userMessage;
    setInput('');

    // Optimistically add user message to UI
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const data = await sendChatMessage(sessionId, outboundMessage);
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
          content: sanitizeProviderMessage(data.response || 'No response returned from the proxy.'),
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
            content: PROVIDER_UNAVAILABLE_COPY
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

  const handleDocumentUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || loading) return;
    e.target.value = '';

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: `Attached document for gateway redaction: ${file.name}` }
    ]);
    setLoading(true);

    try {
      const data = await redactGatewayDocument(file);
      const gatewayMeta = extractGatewayMeta(data);
      if (data.redacted_text) {
        setDocumentContext({
          filename: data.filename,
          redactedText: data.redacted_text,
          requestId: data.request_id,
        });
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'document',
          content: `${data.filename} inspected by AuthClaw gateway document redaction.`,
          documentResult: data,
          gatewayMeta,
          trace: data.trace || []
        }
      ]);
      if (data.trace && data.trace.length > 0) {
        setActiveTrace(data.trace);
      }
    } catch (err) {
      console.error('[AgentChat] Document redaction error:', err);
      const status = err.response?.status;
      const backendDetail = err.response?.data?.detail;
      const detail = status === 404
        ? 'Document redaction endpoint was not found on the running backend. Restart or redeploy the backend so /gateway/documents/redact is registered.'
        : backendDetail || 'Document redaction failed. Please check the file type and backend logs.';
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: detail }
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
      const safeDetails = typeof details === 'string'
        ? sanitizeProviderMessage(details)
        : sanitizeProviderMessage(JSON.stringify(details, null, 2));
      const parsed = typeof safeDetails === 'string' ? JSON.parse(safeDetails) : safeDetails;
      return JSON.stringify(parsed, null, 2);
    } catch (e) {
      return sanitizeProviderMessage(String(details));
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
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-slate-200/50 pt-3">
        {rows.map(([label, value]) => (
          <div key={label} className="bg-slate-50/60 border border-slate-200 rounded-lg px-2.5 py-2">
            <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider font-display">{label}</p>
            <p className="text-[11px] text-slate-700 font-mono truncate mt-0.5">{value}</p>
          </div>
        ))}
      </div>
    );
  };

  const downloadBase64File = (base64, filename, mimeType) => {
    if (!base64) return;
    const byteCharacters = atob(base64);
    const byteNumbers = Array.from(byteCharacters, (char) => char.charCodeAt(0));
    const blob = new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadJsonFile = (payload, filename) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  // ── Message Renderers ──────────────────────────────────────────────────────

  const renderMessage = (msg, index) => {
    const hasTrace = msg.trace && msg.trace.length > 0;

    // Approval Required Card
    if (msg.role === 'approval') {
      return (
        <div key={index} className="flex justify-center">
          <div className="glass-card max-w-lg w-full p-4 bg-amber-50/50 border border-amber-500/30 text-amber-900 text-sm">
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                  <Clock className="w-4 h-4 text-amber-600" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-amber-800 text-sm font-display">Approval Required</p>
                <p className="text-amber-800/90 text-xs mt-1 leading-relaxed">{msg.content}</p>
                {msg.riskLevel && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-[10px] text-amber-700/70 uppercase tracking-wider font-display">Risk Level:</span>
                    <span className="text-xs font-bold text-amber-700 bg-amber-500/15 px-2 py-0.5 rounded">{msg.riskLevel}</span>
                  </div>
                )}
                {msg.approvalId && (
                  <div className="mt-3 flex items-center gap-2 bg-white/70 p-2 border border-amber-200 rounded text-xs font-mono text-amber-800">
                    <span className="text-amber-600/70">ID:</span>
                    <span className="truncate">{msg.approvalId}</span>
                  </div>
                )}
                {renderGatewayMeta(msg.gatewayMeta)}
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-amber-500/15">
                  <p className="text-xs text-amber-700/60 italic flex-1">
                    Visit the Approval Center to review this request.
                  </p>
                  {hasTrace && (
                    <button
                      onClick={() => setActiveTrace(msg.trace)}
                      className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-800 font-semibold transition"
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
          <div className={`glass-card max-w-lg p-4 text-sm flex gap-3.5 ${isApproval ? 'bg-amber-50/50 border border-amber-500/30 text-amber-900' : 'bg-slate-100/80 border border-slate-200 text-slate-700'}`}>
            <AlertTriangle className={`w-5 h-5 shrink-0 ${isApproval ? 'text-amber-600' : 'text-slate-500'}`} />
            <div className="flex-1 min-w-0">
              <p className="font-bold">{msg.content}</p>
              {msg.riskLevel && (
                <p className="text-xs mt-1 opacity-80">Risk Level: <span className="font-bold">{msg.riskLevel}</span></p>
              )}
              {msg.approvalId && (
                <div className="mt-3 flex items-center gap-2 bg-white/70 p-2 border border-slate-200 rounded text-xs font-mono">
                  <span>Approval ID: {msg.approvalId}</span>
                </div>
              )}
              {hasTrace && (
                <button
                  onClick={() => setActiveTrace(msg.trace)}
                  className="mt-3 flex items-center gap-1 text-xs text-[#6D28D9] hover:text-[#7C3AED] font-semibold transition"
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
          <div className="glass-card max-w-lg w-full p-4 bg-rose-50/50 border border-rose-500/30 text-rose-900 text-sm">
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                  <ShieldAlert className="w-4 h-4 text-rose-600" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-rose-700 text-sm font-display">Request Blocked</p>
                <p className="text-xs text-rose-800 mt-1">Reason: <span className="font-bold text-rose-900">Policy Violation</span></p>
                <p className="text-xs text-rose-800 mt-0.5">Category: <span className="font-bold text-rose-900">{formatCategory(msg.category)}</span></p>
                <p className="text-xs text-rose-700/60 mt-3 border-t border-rose-500/15 pt-2 leading-relaxed font-sans">
                  This request violated AuthClaw security policies and was prevented from reaching the model provider.
                </p>
                {renderGatewayMeta(msg.gatewayMeta)}
                {hasTrace && (
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={() => setActiveTrace(msg.trace)}
                      className="flex items-center gap-1 text-xs text-rose-600 hover:text-rose-700 font-semibold transition"
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
          <div className="glass-card max-w-lg p-4 bg-rose-50 border border-rose-200 text-rose-700 text-sm flex gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
            <p>{sanitizeProviderMessage(msg.content)}</p>
          </div>
        </div>
      );
    }

    if (msg.role === 'document') {
      const result = msg.documentResult || {};
      const redactedPreview = result.redacted_text || '';
      const findings = result.findings || result.triggered_policies || [];
      return (
        <div key={index} className="flex gap-4 justify-start">
          <div className="w-8 h-8 rounded-lg bg-[#6D28D9]/10 border border-[#6D28D9]/20 flex items-center justify-center text-[#6D28D9] shrink-0 shadow-sm">
            <FileText className="w-4 h-4" />
          </div>
          <div className="glass-card text-slate-700 rounded-xl rounded-tl-none p-4 max-w-2xl text-sm leading-relaxed shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="font-bold text-slate-900 truncate font-display">{result.filename || 'Document inspected'}</p>
                <p className="text-xs text-slate-500 mt-1">
                  Status: <span className="text-slate-800 font-semibold">{result.status || 'processed'}</span>
                  <span className="mx-2 text-slate-300">|</span>
                  Redacted fields: <span className="text-[#6D28D9] font-semibold">{result.redacted_count ?? 0}</span>
                  <span className="mx-2 text-slate-300">|</span>
                  OCR: <span className="text-slate-800 font-semibold">{result.ocr_status || 'not_required'}</span>
                </p>
              </div>
              <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase ${
                result.decision === 'REDACT'
                  ? 'bg-amber-500/10 text-amber-700 border border-amber-500/20'
                  : 'bg-emerald-500/10 text-emerald-700 border border-emerald-500/20'
              }`}>
                {result.decision || 'ALLOW'}
              </span>
            </div>

            {renderGatewayMeta(msg.gatewayMeta)}

            <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
                <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider font-display">Security Agent</p>
                <p className="text-[11px] text-emerald-600 font-bold mt-0.5 font-display">
                  Scanned {findings.length} field{findings.length === 1 ? '' : 's'}
                </p>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
                <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider font-display">Policy Agent</p>
                <p className="text-[11px] text-[#6D28D9] font-bold mt-0.5 font-display">{result.decision || 'ALLOW'}</p>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
                <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider font-display">Audit Agent</p>
                <p className="text-[11px] text-slate-700 font-mono truncate mt-0.5">{result.request_id || 'recorded'}</p>
              </div>
            </div>

            {findings.length > 0 && (
              <div className="mt-3 border border-slate-200 rounded-lg bg-slate-50/50 overflow-hidden">
                <div className="px-3 py-2 border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-[#6D28D9] font-display">
                  Findings Report
                </div>
                <div className="max-h-48 overflow-y-auto divide-y divide-slate-200">
                  {findings.slice(0, 12).map((finding, idx) => (
                    <div key={`${finding.token_id || finding.value_hash || idx}`} className="grid grid-cols-4 gap-2 px-3 py-2 text-[11px]">
                      <span className="text-slate-800 font-semibold">{finding.field_type || finding.matched_pattern}</span>
                      <span className="text-slate-500">{finding.location || `page ${finding.page || 1}`}</span>
                      <span className="text-slate-500">{Math.round((finding.confidence || 0.8) * 100)}%</span>
                      <span className="text-[#6D28D9] font-semibold">{finding.action_taken || finding.action || 'redact'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-3 border border-[#E6E9F0] rounded-lg bg-[#F5F7FA] overflow-hidden">
              <div className="px-3 py-2 border-b border-[#E6E9F0] text-[10px] font-bold uppercase tracking-wider text-[#6D28D9] font-display">
                Inspected Output
              </div>
              <pre className="p-3 text-xs text-[#0E1726] whitespace-pre-wrap break-words max-h-64 overflow-y-auto font-mono">
                {redactedPreview || 'No redacted text returned.'}
              </pre>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap justify-end gap-2">
              {result.redacted_pdf_base64 && (
                <button
                  onClick={() => downloadBase64File(result.redacted_pdf_base64, `${result.request_id || 'authclaw'}-redacted.pdf`, 'application/pdf')}
                  className="flex items-center gap-1.5 text-xs text-emerald-600 hover:text-emerald-700 font-semibold transition"
                >
                  <Download className="w-3.5 h-3.5" /> Redacted PDF
                </button>
              )}
              {result.findings_report && (
                <button
                  onClick={() => downloadJsonFile(result.findings_report, `${result.request_id || 'authclaw'}-findings.json`)}
                  className="flex items-center gap-1.5 text-xs text-sky-600 hover:text-sky-700 font-semibold transition"
                >
                  <Download className="w-3.5 h-3.5" /> JSON Report
                </button>
              )}
              {hasTrace && (
                <button
                  onClick={() => setActiveTrace(msg.trace)}
                  className="flex items-center gap-1 text-xs text-[#6D28D9] hover:text-[#7C3AED] font-semibold transition"
                >
                  <Activity className="w-3.5 h-3.5" /> View Document Trace
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    // User / Assistant messages
    const isUser = msg.role === 'user';
    return (
      <div key={index} className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
        {!isUser && (
          <div className="w-8 h-8 rounded-lg bg-[#6D28D9]/10 border border-[#6D28D9]/20 flex items-center justify-center text-[#6D28D9] shrink-0 shadow-sm">
            <Bot className="w-4 h-4" />
          </div>
        )}
        <div className={`p-4 rounded-xl max-w-xl text-sm leading-relaxed shadow-sm flex flex-col ${
          isUser
            ? 'bg-[#6D28D9] text-white rounded-tr-none'
            : 'glass-card text-slate-700 rounded-tl-none font-medium'
        }`}>
          <p className="whitespace-pre-wrap">{isUser ? msg.content : sanitizeProviderMessage(msg.content)}</p>
          {!isUser && renderGatewayMeta(msg.gatewayMeta)}
          {!isUser && hasTrace && (
            <div className="mt-2.5 pt-2.5 border-t border-slate-200/50 flex justify-end">
              <button
                onClick={() => setActiveTrace(msg.trace)}
                className="flex items-center gap-1 text-xs text-[#6D28D9] hover:text-[#7C3AED] font-semibold transition"
              >
                <Activity className="w-3.5 h-3.5" /> View Security Trace
              </button>
            </div>
          )}
        </div>
        {isUser && (
          <div className="w-8 h-8 rounded-lg bg-[#6D28D9]/10 border border-[#6D28D9]/20 flex items-center justify-center text-[#6D28D9] shrink-0 shadow-sm">
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
    <div className="flex h-[calc(100vh-8rem)] rounded-xl border border-[#E6E9F0] bg-white/70 overflow-hidden relative font-sans shadow-sm">
      {/* Sidebar for Sessions */}
      <div className="w-64 border-r border-[#E6E9F0] bg-slate-50/50 flex flex-col shrink-0">
        <div className="p-4 border-b border-[#E6E9F0] space-y-2">
          <button
            onClick={handleNewSession}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[#6D28D9] hover:bg-[#7C3AED] text-white rounded-lg text-xs font-semibold hover:opacity-90 transition shadow-md shadow-violet-600/10 font-display"
          >
            <Plus className="w-4 h-4" />
            New Session
          </button>
          <button
            onClick={handleDeleteAllSessions}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-600 rounded-lg text-[10px] font-semibold hover:bg-rose-100/50 transition font-display"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear History
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block mb-2 font-display">Gateway Sessions</span>
          {sessionsList.map((id) => (
            <div
              key={id}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg border transition ${
                id === sessionId
                  ? 'bg-[#6D28D9]/10 border-[#6D28D9]/20 text-[#6D28D9] font-bold shadow-sm'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800 border-transparent'
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
                className="opacity-0 group-hover:opacity-100 hover:text-rose-600 p-1 rounded transition"
                title="Delete Session"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col bg-slate-50/20 min-w-0">
        {/* Chat Header */}
        <div className="h-14 border-b border-[#E6E9F0] bg-white/70 px-6 flex items-center justify-between">
          <span className="text-sm font-bold text-[#0E1726] flex items-center gap-2 font-display">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Gateway Chat Console
          </span>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded bg-[#6D28D9]/10 border border-[#6D28D9]/20 text-[10px] font-bold text-[#6D28D9] uppercase tracking-wider font-mono">
              Gateway Pipeline
            </span>
            <span className="text-[11px] font-mono text-slate-400">ID: {sessionId}</span>
          </div>
        </div>

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, index) => renderMessage(msg, index))}

          {loading && (
            <div className="flex gap-4 justify-start">
              <div className="w-8 h-8 rounded-lg bg-[#6D28D9]/10 border border-[#6D28D9]/20 flex items-center justify-center text-[#6D28D9] shrink-0 animate-spin">
                <Loader className="w-4 h-4" />
              </div>
              <div className="p-4 glass-card text-slate-600 rounded-xl rounded-tl-none flex items-center gap-2 text-xs">
                <span>Running Security Agent, Policy Agent, and Audit Agent checks...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form onSubmit={handleSend} className="p-4 border-t border-[#E6E9F0] bg-white/70">
          <div className="flex gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.text,.md,.markdown,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={handleDocumentUpload}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              title="Upload document for gateway redaction"
              className="px-4 py-3 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg text-slate-600 font-semibold transition disabled:opacity-50 flex items-center justify-center"
            >
              <FileText className="w-4 h-4" />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={documentContext ? `Ask about sanitized ${documentContext.filename}...` : 'Send a prompt through the AuthClaw Gateway...'}
              disabled={loading}
              className="flex-1 glass-input py-3"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-5 py-3 bg-[#6D28D9] hover:bg-[#7C3AED] rounded-lg text-white font-semibold transition disabled:opacity-50 flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>

      {/* Multi-Agent Trace Drawer */}
      {activeTrace && (
        <div className="w-96 border-l border-[#E6E9F0] bg-white flex flex-col h-full z-20 absolute right-0 top-0 shadow-xl animate-slideLeft">
          {/* Header */}
          <div className="h-14 px-5 border-b border-[#E6E9F0] flex items-center justify-between shrink-0 bg-slate-50">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#6D28D9]" />
              <span className="text-xs font-bold text-[#0E1726] uppercase tracking-wider font-display">Security execution Trace</span>
            </div>
            <button 
              onClick={() => setActiveTrace(null)} 
              className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Timeline Contents */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6 scrollbar-thin">
            
            {/* Sequence flow illustration */}
            <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-[#E6E9F0] text-[8.5px] text-slate-500 font-semibold tracking-wider uppercase mb-2 font-mono">
              <span>Security</span>
              <ArrowRight className="w-2.5 h-2.5 text-[#6D28D9]" />
              <span>Policy</span>
              <ArrowRight className="w-2.5 h-2.5 text-[#6D28D9]" />
              <span>Audit</span>
            </div>

            {/* Timeline */}
            <div className="relative pl-6 border-l border-dashed border-slate-200 space-y-6">
              
              {/* Agent 1: Security */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  securityEvents.length > 0 
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-600' 
                    : 'bg-slate-100 border-slate-300 text-slate-400'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider font-display">1. Security Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      securityEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {securityEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-relaxed font-sans">
                    Validates input, detects prompt injection, secrets, PII, and assigns request risk.
                  </p>

                  <div className="space-y-1.5">
                    {securityEvents.map((e, idx) => (
                      <div key={idx} className="bg-[#F5F7FA] p-2.5 rounded border border-[#E6E9F0] text-xs font-mono text-[#0E1726]">
                        <div className="text-[10px] text-[#6D28D9] font-bold mb-1">{e.event}</div>
                        <pre className="text-[10px] text-[#475069] whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {securityEvents.length === 0 && (
                      <div className="text-xs text-slate-400 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 2: Policy */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  policyEvents.length > 0 
                    ? (activeTrace.some(e => e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('blocked') || e.event?.toLowerCase().includes('leak')) ? 'bg-red-500/10 border-red-500 text-red-600' : 'bg-emerald-500/10 border-emerald-500 text-emerald-600')
                    : 'bg-slate-100 border-slate-300 text-slate-400'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider font-display">2. Policy Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      policyEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {policyEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-relaxed font-sans">
                    Evaluates prompt safety, scans for PII/PHI leak vectors, redacts inputs statefully, and checks custom tenant policies.
                  </p>

                  <div className="space-y-1.5">
                    {policyEvents.map((e, idx) => (
                      <div key={idx} className={`p-2.5 rounded border text-xs font-mono text-[#0E1726] ${
                        e.event?.toLowerCase().includes('block') || e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('leak')
                          ? 'bg-rose-50 border-red-500/20'
                          : 'bg-[#F5F7FA]'
                      }`}>
                        <div className={`text-[10px] font-bold mb-1 ${
                          e.event?.toLowerCase().includes('block') || e.event?.toLowerCase().includes('violation') || e.event?.toLowerCase().includes('leak')
                            ? 'text-red-400'
                            : 'text-[#6D28D9]'
                        }`}>{e.event}</div>
                        <pre className="text-[10px] text-[#475069] whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {policyEvents.length === 0 && (
                      <div className="text-xs text-slate-400 italic">No events recorded.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Agent 3: Audit */}
              <div className="relative">
                <div className={`absolute -left-[31px] top-0 w-4 h-4 rounded-full flex items-center justify-center border ${
                  registrarEvents.length > 0 
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-600' 
                    : 'bg-slate-100 border-slate-300 text-slate-400'
                }`}>
                  <div className="w-1.5 h-1.5 rounded-full bg-current" />
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold text-[#0E1726] uppercase tracking-wider font-display">3. Audit Agent</h4>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      registrarEvents.length > 0 ? 'bg-emerald-500/10 text-emerald-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {registrarEvents.length > 0 ? 'Executed' : 'Skipped'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-relaxed font-sans">
                    Records immutable request, response, decision, and compliance evidence for this tenant.
                  </p>

                  <div className="space-y-1.5">
                    {registrarEvents.map((e, idx) => (
                      <div key={idx} className="bg-[#F5F7FA] p-2.5 rounded border border-[#E6E9F0] text-xs font-mono text-[#0E1726]">
                        <div className="text-[10px] text-[#6D28D9] font-bold mb-1">{e.event}</div>
                        <pre className="text-[10px] text-[#475069] whitespace-pre-wrap break-all leading-normal">
                          {renderDetails(e.details)}
                        </pre>
                      </div>
                    ))}
                    {registrarEvents.length === 0 && (
                      <div className="text-xs text-slate-400 italic">No events recorded.</div>
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
