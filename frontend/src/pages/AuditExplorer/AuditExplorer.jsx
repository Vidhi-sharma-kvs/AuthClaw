import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  RefreshCw, 
  Activity, 
  Lock, 
  Link2,
  FileCheck2,
  Search,
  Download,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { 
  getHashChain, 
  verifyAuditChain, 
  getAuditSummary 
} from '../../services/auditService';
import apiClient from '../../services/api';
import { useToast } from '../../components/Common/Toast';

const AuditExplorer = () => {
  const [chainList, setChainList] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [expandedRowId, setExpandedRowId] = useState(null);

  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Pagination States
  const [currentPage, setCurrentPage] = useState(1);
  const recordsPerPage = 10;

  const { addToast } = useToast();

  const fetchData = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const logs = await getHashChain(100); // fetch more records for better filtering/pagination
      const sum = await getAuditSummary();
      setChainList(logs);
      setSummary(sum);
    } catch (error) {
      console.error('Error loading audit explorer data:', error);
      addToast('Failed to load cryptographic audit logs.', 'error');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(true);
    const handleAuditUpdate = () => {
      fetchData(false);
    };
    window.addEventListener('audit-updated', handleAuditUpdate);
    const interval = setInterval(() => fetchData(false), 15000);
    return () => {
      window.removeEventListener('audit-updated', handleAuditUpdate);
      clearInterval(interval);
    };
  }, []);

  const handleVerifyChain = async () => {
    setVerifying(true);
    try {
      const result = await verifyAuditChain();
      if (result.valid) {
        addToast(`Chain verified successfully! ${result.records_checked} blocks checked.`, 'success');
      } else {
        addToast(`INTEGRITY ALERT: Verification failed at block ${result.failed_record_id}. Reason: ${result.reason}`, 'error');
      }
      fetchData();
    } catch (error) {
      addToast('Failed to execute chain verification.', 'error');
    } finally {
      setVerifying(false);
    }
  };

  const handleExport = async (format) => {
    try {
      const response = await apiClient.get(`/audit/export/${format}`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit_ledger_${new Date().toISOString().split('T')[0]}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      addToast(`Audit ledger exported as ${format.toUpperCase()} successfully.`, 'success');
    } catch (error) {
      console.error(error);
      addToast(`Failed to export audit ledger as ${format.toUpperCase()}.`, 'error');
    }
  };

  // Search and Filter logic
  const filteredChain = chainList.filter(log => {
    const query = searchQuery.toLowerCase();
    const matchesSearch = 
      (log.user_query && log.user_query.toLowerCase().includes(query)) ||
      (log.approver && log.approver.toLowerCase().includes(query)) ||
      (log.approval_id && log.approval_id.toLowerCase().includes(query)) ||
      (log.record_id && log.record_id.toString().includes(query));

    const matchesRisk = riskFilter === 'ALL' || (log.risk_level && log.risk_level.toUpperCase() === riskFilter);
    
    const logStatus = (log.status || '').toUpperCase();
    const matchesStatus = statusFilter === 'ALL' || 
      (statusFilter === 'COMPLETED' && (logStatus === 'EXECUTED' || logStatus === 'COMPLETED')) ||
      (statusFilter === 'PENDING' && logStatus === 'PENDING') ||
      (statusFilter === 'REJECTED' && logStatus === 'REJECTED');

    return matchesSearch && matchesRisk && matchesStatus;
  });

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, riskFilter, statusFilter]);

  // Pagination calculation
  const totalPages = Math.ceil(filteredChain.length / recordsPerPage) || 1;
  const indexOfLastRecord = currentPage * recordsPerPage;
  const indexOfFirstRecord = indexOfLastRecord - recordsPerPage;
  const currentRecords = filteredChain.slice(indexOfFirstRecord, indexOfLastRecord);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            Cryptographic Audit Explorer
          </h1>
          <p className="text-gray-400 text-sm">Chain verification ledger protecting logs against deletion and modifications.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-tr from-violet-600 to-fuchsia-600 rounded-lg text-xs font-semibold hover:opacity-90 disabled:opacity-50 transition shadow-lg shadow-violet-500/15"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
            {verifying ? 'Verifying Integrity...' : 'Verify Hash Chain'}
          </button>
        </div>
      </div>

      {/* Verification Status Banner */}
      {summary && (
        <div className={`p-4 rounded-xl border flex items-center gap-4 ${
          summary.valid 
            ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-300' 
            : 'bg-rose-950/20 border-rose-500/20 text-rose-300'
        }`}>
          {summary.valid ? (
            <ShieldCheck className="w-8 h-8 text-emerald-400 shrink-0" />
          ) : (
            <ShieldAlert className="w-8 h-8 text-rose-400 shrink-0" />
          )}
          <div>
            <h4 className="font-semibold text-sm">
              {summary.valid ? 'System Audit Integrity Intact' : 'INTEGRITY VERIFICATION FAILED'}
            </h4>
            <p className="text-xs opacity-80 mt-0.5">
              {summary.valid 
                ? `Successfully verified all ${summary.records_checked} cryptographic records in the audit logs database. Genesis status is active.`
                : `Tampering or deletion detected! Latest check failed at record ID ${summary.last_verified_record}.`
              }
            </p>
          </div>
        </div>
      )}

      {/* Chain Metadata summary boxes */}
      {summary && summary.valid && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-card p-5 space-y-2">
            <span className="text-xs text-gray-500 font-bold uppercase tracking-wider block">Verified Chain Blocks</span>
            <span className="text-2xl font-bold text-white block">{summary.records_checked}</span>
          </div>
          <div className="glass-card p-5 space-y-2 md:col-span-2">
            <span className="text-xs text-gray-500 font-bold uppercase tracking-wider block">Latest Hash (SHA-256)</span>
            <span className="text-xs font-mono break-all text-gray-300 block bg-slate-900/40 p-2 border border-white/5 rounded mt-1">
              {summary.latest_hash || 'N/A'}
            </span>
          </div>
        </div>
      )}

      {/* Search, Filter, and Export Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-950/40 border border-white/5 p-4 rounded-xl">
        <div className="flex flex-wrap items-center gap-3 flex-1">
          {/* Search Input */}
          <div className="relative min-w-[200px] flex-1 max-w-sm">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by block ID, query, approver..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-white/10 rounded-lg py-2 pl-9 pr-4 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          {/* Risk Filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="bg-slate-900 border border-white/10 rounded-lg py-2 px-3 text-xs text-white focus:outline-none focus:border-violet-500"
          >
            <option value="ALL">All Risks</option>
            <option value="LOW">Low Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="HIGH">High Risk</option>
            <option value="CRITICAL">Critical Risk</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-white/10 rounded-lg py-2 px-3 text-xs text-white focus:outline-none focus:border-violet-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="PENDING">Pending</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        {/* Exports */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/5 transition-all"
          >
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
          <button
            onClick={() => handleExport('pdf')}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/5 transition-all"
          >
            <Download className="w-3.5 h-3.5" /> Export PDF
          </button>
        </div>
      </div>

      {/* Audit Log Table */}
      {loading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-14 bg-white/5 rounded-lg animate-pulse"></div>
          ))}
        </div>
      ) : currentRecords.length === 0 ? (
        <div className="glass-card p-12 text-center flex flex-col items-center justify-center">
          <Lock className="w-8 h-8 text-gray-500 mb-3" />
          <h4 className="text-gray-300 font-semibold">No matching cryptographic records</h4>
          <p className="text-gray-500 text-sm mt-1">Try adjusting your filters or search queries.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5 text-xs font-semibold text-gray-400 uppercase tracking-wider bg-slate-950/20">
                    <th className="p-4">BLOCK</th>
                    <th className="p-4">USER / TENANT</th>
                    <th className="p-4">REQUEST</th>
                    <th className="p-4">PROVIDER</th>
                    <th className="p-4">SECURITY</th>
                    <th className="p-4">POLICY</th>
                    <th className="p-4 text-center">OUTCOME</th>
                    <th className="p-4">TIMESTAMP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-xs text-gray-300">
                  {currentRecords.map((log) => (
                    <React.Fragment key={log.record_id}>
                      <tr 
                        onClick={() => setExpandedRowId(expandedRowId === log.record_id ? null : log.record_id)}
                        className="hover:bg-white/[0.02] cursor-pointer transition-colors"
                      >
                        <td className="p-4 font-semibold text-white font-mono" title={log.hash_reference}># {log.record_id}</td>
                        <td className="p-4 text-gray-300">
                          <span className="block text-white">{log.username || log.approver || 'System'}</span>
                          <span className="block text-[10px] text-gray-500 font-mono">Tenant {log.tenant_id || 'N/A'}</span>
                        </td>
                        <td className="p-4 text-gray-300 max-w-[200px] truncate" title={log.original_request}>
                          {log.original_request || 'N/A'}
                        </td>
                        <td className="p-4 text-gray-400">{log.provider || 'Gateway Route'}</td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            log.security_decision === 'BLOCK'
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/15'
                              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/15'
                          }`}>
                            {log.security_decision || 'ALLOW'}
                          </span>
                        </td>
                        <td className="p-4 text-gray-300 max-w-[140px] truncate" title={log.policy_decision}>
                          {log.policy_decision || 'N/A'}
                        </td>
                        <td className="p-4 text-center">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold border uppercase ${
                            log.status === 'executed' || log.status === 'COMPLETED'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/15'
                              : log.status === 'approved'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/15'
                              : log.status === 'rejected'
                              ? 'bg-rose-500/10 text-rose-400 border-rose-500/15'
                              : log.status === 'pending'
                              ? 'bg-amber-500/10 text-amber-400 border-amber-500/15 animate-pulse'
                              : 'bg-slate-500/10 text-slate-400 border-slate-500/15'
                          }`}>
                            {log.status === 'executed' ? 'COMPLETED' : (log.status || 'DIRECT')}
                          </span>
                        </td>
                        <td className="p-4 font-mono text-gray-400" title={log.timestamp}>
                          {log.timestamp ? log.timestamp.split('T')[0] + ' ' + (log.timestamp.split('T')[1]?.split('.')[0] || '') : 'N/A'}
                        </td>
                      </tr>
                      {expandedRowId === log.record_id && (
                        <tr className="bg-slate-950/45">
                          <td colSpan="8" className="p-6 text-gray-300 border-b border-white/5">
                            <div className="space-y-4 font-sans text-xs">
                              <div className="flex items-center justify-between border-b border-white/5 pb-2">
                                <h4 className="text-sm font-bold text-white tracking-tight flex items-center gap-1.5">
                                  <FileCheck2 className="w-4 h-4 text-violet-400" />
                                  Block #{log.record_id} Cryptographic & Approval Metadata
                                </h4>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${
                                  log.approval_status === 'executed'
                                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/15'
                                    : log.approval_status === 'approved'
                                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/15'
                                    : log.approval_status === 'rejected'
                                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/15'
                                    : log.approval_status === 'pending'
                                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/15 animate-pulse'
                                    : 'bg-slate-500/10 text-slate-400 border-slate-500/15'
                                }`}>
                                  {log.approval_status ? log.approval_status : 'DIRECT_EXECUTION'}
                                </span>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">Approval Ticket ID</span>
                                  <span className="font-mono text-white break-all block mt-1">
                                    {log.approval_id || 'N/A (Direct Request / Administrative Action)'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">Approver Identity</span>
                                  <span className="text-white font-semibold block mt-1">
                                    {log.approver || 'System'}
                                  </span>
                                </div>
                                <div className="md:col-span-2">
                                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">Original Request Payload</span>
                                  <p className="text-gray-200 bg-slate-900/60 p-3 rounded-lg border border-white/5 font-mono whitespace-pre-wrap mt-1.5 leading-relaxed">
                                    {log.user_query || 'N/A'}
                                  </p>
                                </div>
                                <div>
                                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">Previous Block Hash Link</span>
                                  <span className="font-mono text-gray-400 break-all block mt-1 cursor-pointer hover:text-white transition" title="Click to copy previous hash" onClick={(e) => {
                                    e.stopPropagation();
                                    if (log.previous_hash) {
                                      navigator.clipboard.writeText(log.previous_hash);
                                      addToast('Previous block hash copied.', 'success');
                                    }
                                  }}>
                                    {log.previous_hash || 'GENESIS_HASH'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">Block Integrity Hash</span>
                                  <span className="font-mono text-violet-400 break-all block mt-1 cursor-pointer hover:text-violet-300 transition" title="Click to copy integrity hash" onClick={(e) => {
                                    e.stopPropagation();
                                    if (log.integrity_hash) {
                                      navigator.clipboard.writeText(log.integrity_hash);
                                      addToast('Block integrity hash copied.', 'success');
                                    }
                                  }}>
                                    {log.integrity_hash || 'N/A'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination Controls */}
          <div className="flex items-center justify-between border-t border-white/5 pt-4 text-xs">
            <span className="text-gray-500">
              Showing <strong className="text-white">{indexOfFirstRecord + 1}</strong> to{' '}
              <strong className="text-white">{Math.min(indexOfLastRecord, filteredChain.length)}</strong> of{' '}
              <strong className="text-white">{filteredChain.length}</strong> records
            </span>

            <div className="flex items-center gap-2">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                className="p-2 bg-slate-900 border border-white/10 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-gray-400 px-2 font-mono">
                Page <strong className="text-white">{currentPage}</strong> of {totalPages}
              </span>
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                className="p-2 bg-slate-900 border border-white/10 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditExplorer;
