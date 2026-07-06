import React, { useEffect, useState } from 'react';
import { 
  Check, 
  X, 
  Play, 
  Clock, 
  AlertTriangle, 
  CheckCircle, 
  Info,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { 
  getApprovalsByMode,
  approveApproval, 
  rejectApproval, 
  executeApproval 
} from '../../services/approvalService';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge 
} from '../../components/Common/DesignSystem';

const ApprovalQueue = () => {
  const [approvalsList, setApprovalsList] = useState([]);
  const [activeTab, setActiveTab] = useState('pending'); // pending, approved, rejected, executed, all
  const [loading, setLoading] = useState(true);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [mfaCode, setMfaCode] = useState('');
  const [approvalComment, setApprovalComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const { addToast } = useToast();

  const fetchApprovals = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const data = await getApprovalsByMode('gateway');
      setApprovalsList(data);
    } catch (error) {
      console.error('Error fetching approvals:', error);
      addToast('Failed to load approvals.', 'error');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals(true);
    const interval = setInterval(() => fetchApprovals(false), 15000);
    return () => clearInterval(interval);
  }, []);

  // Countdown timer for pending approvals
  useEffect(() => {
    const timer = setInterval(() => {
      setApprovalsList((prevList) => 
        prevList.map((app) => {
          if (app.status === 'pending' && app.remaining_seconds > 0) {
            return { ...app, remaining_seconds: app.remaining_seconds - 1 };
          }
          return app;
        })
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleApproveClick = (app) => {
    setSelectedApproval(app);
    setMfaCode('');
    setApprovalComment('');
  };

  const handleApproveConfirm = async () => {
    if (!selectedApproval) return;
    if (!mfaCode.trim()) {
      addToast('Enter the MFA code before approving this request.', 'error');
      return;
    }
    setActionLoading(true);
    try {
      await approveApproval(selectedApproval.approval_id, mfaCode || null, approvalComment);
      addToast(`Approval ${selectedApproval.approval_id.substr(0, 8)} approved.`, 'success');
      setSelectedApproval(null);
      fetchApprovals();
      window.dispatchEvent(new CustomEvent('audit-updated'));
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail || 'MFA validation failed.';
      addToast(detail, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (id) => {
    if (!window.confirm('Are you sure you want to reject this request?')) return;
    const comment = window.prompt('Add a rejection comment for the audit trail:', '') || '';
    try {
      await rejectApproval(id, comment);
      addToast(`Request rejected successfully.`, 'success');
      fetchApprovals();
      window.dispatchEvent(new CustomEvent('audit-updated'));
    } catch (err) {
      addToast('Failed to reject request.', 'error');
    }
  };

  const handleExecute = async (id) => {
    const comment = window.prompt('Add an execution comment for the audit trail:', '') || '';
    try {
      const result = await executeApproval(id, comment);
      addToast(`Action executed successfully! Output: ${result.response?.substr(0, 40)}...`, 'success');
      fetchApprovals();
      window.dispatchEvent(new CustomEvent('audit-updated'));
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail || 'Execution failed.';
      addToast(detail, 'error');
    }
  };

  const filteredApprovals = approvalsList.filter(app => {
    if (activeTab === 'all') return true;
    return app.status === activeTab;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'pending':
        return <StatusBadge status="Awaiting Approval" />;
      case 'approved':
        return <StatusBadge status="Approved" />;
      case 'rejected':
        return <StatusBadge status="Rejected" />;
      case 'expired':
        return <StatusBadge status="Expired" />;
      case 'executed':
        return <StatusBadge status="Completed" />;
      default:
        return <StatusBadge status={status} />;
    }
  };

  const formatSeconds = (seconds) => {
    const safeSeconds = seconds || 0;
    const mins = Math.floor(safeSeconds / 60);
    const secs = safeSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (value) => {
    if (!value) return 'N/A';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
  };

  const formatReason = (reason) => {
    const labels = {
      high_risk: 'High risk',
      policy_violation: 'Policy violation',
      sensitive_data: 'Sensitive data',
      unknown_provider_risk: 'Unknown provider risk',
    };
    return labels[reason] || String(reason || 'High risk').replace(/_/g, ' ');
  };

  const getTimelineSteps = (status) => {
    const steps = [
      { key: 'READ_ONLY', label: 'Read Only' },
      { key: 'PLAN', label: 'Plan Assessment' },
      { key: 'PENDING_APPROVAL', label: 'Pending Approval' },
      { key: 'APPROVED', label: 'Approved' },
      { key: 'EXECUTING', label: 'Executing' },
      { key: 'COMPLETED', label: status === 'rejected' ? 'Rejected' : (status === 'expired' ? 'Expired' : 'Completed') }
    ];

    let activeIdx = 2; // PENDING_APPROVAL
    if (status === 'approved') activeIdx = 3;
    if (status === 'executed') activeIdx = 5; 
    if (status === 'rejected' || status === 'expired') activeIdx = 5;

    return { steps, activeIdx };
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
          HITL Approval Center
        </h1>
        <p className="text-gray-400 text-sm">Review, authorize, and track human-in-the-loop state transitions and execution logs.</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border border-white/5 bg-slate-950/30 rounded-xl p-4">
        <div>
          <p className="text-xs font-bold text-white uppercase tracking-wider">Approval Source</p>
          <p className="text-[11px] text-gray-500">Gateway approvals are backed by persistent request-linked records.</p>
        </div>
        <span className="px-3 py-1.5 rounded-lg bg-violet-600/15 border border-violet-500/25 text-[11px] font-bold text-violet-200">
          Gateway Approvals
        </span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/5 space-x-6 text-sm">
        {['pending', 'approved', 'rejected', 'executed', 'all'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 font-semibold capitalize border-b-2 transition ${
              activeTab === tab 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {tab === 'executed' ? 'Completed' : tab}
          </button>
        ))}
      </div>

      {/* Main List */}
      {loading ? (
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-[250px] bg-white/5 rounded-lg animate-pulse"></div>
          ))}
        </div>
      ) : filteredApprovals.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 border border-dashed border-white/10 rounded-xl bg-slate-900/10">
          <Info className="w-8 h-8 text-gray-500 mb-3" />
          <h3 className="text-sm font-bold text-gray-300">No approvals found</h3>
          <p className="text-xs text-gray-500 mt-1">There are no override tickets matching the current filter.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {filteredApprovals.map((app) => {
            const { steps, activeIdx } = getTimelineSteps(app.status);
            return (
              <GlassCard key={app.approval_id} className="space-y-6" hover={false}>
                {/* Header info */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-white/5 pb-4">
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-mono block">Ticket ID: {app.approval_id}</span>
                    {app.request_id && (
                      <span className="text-[10px] text-violet-300 font-mono block">Request ID: {app.request_id}</span>
                    )}
                    <h3 className="text-sm font-mono font-bold text-white whitespace-pre-wrap">{app.requested_action}</h3>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <span className={`px-2.5 py-0.5 rounded text-xs font-semibold ${
                      app.risk_level === 'HIGH' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}>
                      {app.risk_level} RISK
                    </span>
                    {app.decision && (
                      <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-violet-500/10 text-violet-300 border border-violet-500/20">
                        {app.decision}
                      </span>
                    )}
                    {getStatusBadge(app.status)}
                    <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {formatReason(app.reason)}
                    </span>
                    {app.status === 'pending' && (
                      <span className="flex items-center gap-1.5 text-amber-400 text-xs font-mono bg-amber-500/10 px-2 py-0.5 border border-amber-500/20 rounded">
                        <Clock className="w-3.5 h-3.5" />
                        {formatSeconds(app.remaining_seconds)}
                      </span>
                    )}
                  </div>
                </div>

                {/* State Transition Timeline */}
                <div className="py-2 overflow-x-auto">
                  <div className="flex items-center justify-between min-w-[600px] px-4">
                    {steps.map((step, idx) => (
                      <React.Fragment key={step.key}>
                        {/* Step Circle */}
                        <div className="flex flex-col items-center justify-center text-center relative shrink-0">
                          <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold font-mono text-xs border-2 transition-all ${
                            idx <= activeIdx 
                              ? (app.status === 'rejected' && idx === activeIdx ? 'bg-rose-600/20 border-rose-500 text-rose-400' : 'bg-violet-600/20 border-violet-500 text-white shadow shadow-violet-500/10') 
                              : 'bg-slate-900 border-white/10 text-gray-500'
                          }`}>
                            {idx + 1}
                          </span>
                          <span className={`text-[10px] font-semibold mt-1.5 ${
                            idx <= activeIdx ? 'text-white' : 'text-gray-500'
                          }`}>
                            {step.label}
                          </span>
                        </div>
                        {/* Edge line */}
                        {idx < steps.length - 1 && (
                          <div className={`flex-1 h-0.5 mx-2 min-w-[40px] ${
                            idx < activeIdx ? 'bg-violet-500/50' : 'bg-white/5'
                          }`}></div>
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>

                {/* Bottom Actions and logs */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/40 p-4 border border-white/5 rounded-xl">
                  <div className="text-xs text-gray-400 font-mono space-y-1">
                    <div>Created: <span className="text-white">{formatDate(app.created_at)}</span></div>
                    {app.approved_at && <div>Approved: <span className="text-white">{formatDate(app.approved_at)}</span></div>}
                    {app.executed_at && <div>Executed: <span className="text-white">{formatDate(app.executed_at)}</span></div>}
                    {app.approved_by && <div>Approved By: <span className="text-white">{app.approved_by}</span></div>}
                    {app.rejected_by && <div>Rejected By: <span className="text-white">{app.rejected_by}</span></div>}
                    {app.executed_by && <div>Executed By: <span className="text-white">{app.executed_by}</span></div>}
                    <div>MFA: <span className={app.mfa_verified ? 'text-emerald-400 font-bold' : 'text-gray-500'}>{app.mfa_verified ? 'Verified' : 'Not verified'}</span></div>
                  </div>

                  <div className="flex gap-3 ml-auto shrink-0">
                    {app.status === 'pending' && (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleReject(app.approval_id)}
                        >
                          Reject
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleApproveClick(app)}
                        >
                          Approve (MFA)
                        </Button>
                      </>
                    )}
                    {app.status === 'approved' && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleExecute(app.approval_id)}
                      >
                        <Play className="w-4 h-4 animate-pulse" />
                        Execute Action
                      </Button>
                    )}
                  </div>
                </div>

                {Array.isArray(app.history) && app.history.length > 0 && (
                  <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 space-y-2">
                    <div className="text-xs font-bold text-gray-300 uppercase tracking-wider">Approval Audit Trail</div>
                    <div className="space-y-2">
                      {app.history.slice(-4).map((event, idx) => (
                        <div key={`${event.action}-${idx}`} className="flex flex-col md:flex-row md:items-center md:justify-between gap-1 text-xs text-gray-400 border-t border-white/5 pt-2 first:border-t-0 first:pt-0">
                          <span>
                            <span className="text-white font-semibold">{event.action}</span>
                            {event.actor && <span> by {event.actor}</span>}
                            {event.comment && <span className="text-gray-300"> - {event.comment}</span>}
                          </span>
                          <span className="font-mono text-gray-500">{formatDate(event.created_at)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </GlassCard>
            );
          })}
        </div>
      )}

      {/* MFA Modal Dialog */}
      {selectedApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <GlassCard className="relative max-w-md w-full p-6 space-y-6" hover={false}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
                Authorize Action
              </h3>
              <button 
                onClick={() => setSelectedApproval(null)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold block">Requested Action</span>
                <span className="text-xs font-mono break-all text-gray-200 mt-0.5 block bg-slate-900/50 p-2.5 border border-white/5 rounded">
                  {selectedApproval.requested_action}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold block">Risk Level</span>
                  <span className="text-xs text-rose-400 font-semibold">{selectedApproval.risk_level}</span>
                </div>
                <div>
                  <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold block">Time Remaining</span>
                  <span className="text-xs font-mono text-amber-400">{formatSeconds(selectedApproval.remaining_seconds)}</span>
                </div>
              </div>
            </div>

            {/* MFA Payload input */}
            <div className="space-y-2">
              <label className="text-xs text-gray-400 uppercase tracking-wider font-semibold block">MFA Verification Code</label>
              <input
                type="text"
                placeholder="Enter 6-digit MFA code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 uppercase tracking-wider font-semibold block">Approval Comment</label>
              <textarea
                rows={3}
                placeholder="Why are you approving this request?"
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors resize-none"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedApproval(null)}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleApproveConfirm}
                disabled={actionLoading}
              >
                {actionLoading ? 'Verifying...' : 'Confirm Approval'}
              </Button>
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
};

export default ApprovalQueue;
