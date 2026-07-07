import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Clock, Database, RefreshCw, Router, ShieldAlert } from 'lucide-react';
import { getGatewayRequests } from '../../services/gatewayService';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge, 
  DataTable, 
  SearchBar 
} from '../../components/Common/DesignSystem';

const formatDate = (value) => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
};

const GatewayRequests = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterDecision, setFilterDecision] = useState('ALL');
  const [filterProvider, setFilterProvider] = useState('ALL');
  
  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

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

  // Filter & Search Logic
  const filteredRequests = requests.filter((req) => {
    const matchesSearch = 
      req.request_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      req.model?.toLowerCase().includes(searchTerm.toLowerCase());
      
    const decisionText = (req.decision || req.status || 'UNKNOWN').toUpperCase();
    const matchesDecision = 
      filterDecision === 'ALL' || 
      decisionText.includes(filterDecision);

    const providerText = (req.provider || '').toUpperCase();
    const matchesProvider = 
      filterProvider === 'ALL' || 
      providerText.includes(filterProvider);

    return matchesSearch && matchesDecision && matchesProvider;
  });

  // Pagination Logic
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = filteredRequests.slice(indexOfFirstItem, indexOfLastItem);
  const totalPages = Math.ceil(filteredRequests.length / itemsPerPage);

  const columns = [
    {
      key: 'request_id',
      header: 'Request ID',
      sortable: true,
      render: (req) => <span className="font-mono text-[#6D28D9] font-bold">{req.request_id}</span>
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (req) => <span className="text-[#475069] text-xs">{formatDate(req.created_at || req.timestamp)}</span>
    },
    {
      key: 'tenant_id',
      header: 'Tenant ID',
      render: (req) => <span className="font-mono text-[#475069]">{req.tenant_id || 'N/A'}</span>
    },
    {
      key: 'provider',
      header: 'Provider',
      sortable: true,
      render: (req) => (
        <span className="capitalize inline-flex items-center gap-1.5">
          <Router className="w-3.5 h-3.5 text-[#6D28D9]" />
          {req.provider || 'N/A'}
        </span>
      )
    },
    {
      key: 'model',
      header: 'Model',
      sortable: true,
      render: (req) => <span className="font-mono text-[#475069]">{req.model || 'N/A'}</span>
    },
    {
      key: 'decision',
      header: 'Decision',
      sortable: true,
      render: (req) => {
        const text = req.decision || req.status || 'UNKNOWN';
        return <StatusBadge status={text} />;
      }
    },
    {
      key: 'duration_ms',
      header: 'Duration',
      sortable: true,
      render: (req) => <span className="text-[#475069] font-mono">{req.duration_ms ?? req.latency ?? 0} ms</span>
    },
    {
      key: 'actions',
      header: 'Trace',
      render: (req) => (
        <Link
          to={`/requests/${req.request_id}`}
          className="inline-flex items-center gap-1 text-[#6D28D9] hover:text-[#6D28D9] font-semibold"
        >
          Details <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      )
    }
  ];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0E1726]">
            Gateway Requests
          </h1>
          <p className="text-xs text-[#475069] mt-1">
            Runtime request lifecycle records from the AuthClaw Gateway.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchRequests}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <GlassCard hover={false} className="p-4 flex items-center justify-between">
          <div>
            <p className="text-[#6B7488] text-[10px] font-bold uppercase tracking-wider">Total</p>
            <p className="text-2xl font-bold text-[#0E1726] mt-1">{totals.all}</p>
          </div>
          <div className="p-2 bg-[#F1ECFE] rounded-lg text-[#6D28D9] border border-[#6D28D9]/10">
            <Database className="w-4 h-4" />
          </div>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex items-center justify-between">
          <div>
            <p className="text-[#6B7488] text-[10px] font-bold uppercase tracking-wider">Allowed</p>
            <p className="text-2xl font-bold text-[#0E1726] mt-1">{totals.allowed}</p>
          </div>
          <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400 border border-emerald-500/10">
            <Activity className="w-4 h-4" />
          </div>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex items-center justify-between">
          <div>
            <p className="text-[#6B7488] text-[10px] font-bold uppercase tracking-wider">Blocked</p>
            <p className="text-2xl font-bold text-[#0E1726] mt-1">{totals.blocked}</p>
          </div>
          <div className="p-2 bg-rose-500/10 rounded-lg text-rose-400 border border-rose-500/10">
            <ShieldAlert className="w-4 h-4" />
          </div>
        </GlassCard>

        <GlassCard hover={false} className="p-4 flex items-center justify-between">
          <div>
            <p className="text-[#6B7488] text-[10px] font-bold uppercase tracking-wider">Pending</p>
            <p className="text-2xl font-bold text-[#0E1726] mt-1">{totals.pending}</p>
          </div>
          <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400 border border-amber-500/10">
            <Clock className="w-4 h-4" />
          </div>
        </GlassCard>
      </div>

      {/* Filter Options */}
      <GlassCard hover={false} className="flex flex-col md:flex-row gap-4 items-center justify-between p-4">
        <SearchBar 
          value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
          placeholder="Search Request ID or Model..."
          className="w-full md:w-80"
        />

        <div className="flex flex-wrap gap-4 items-center w-full md:w-auto">
          {/* Provider Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#6B7488] font-bold uppercase">Provider:</span>
            <select
              value={filterProvider}
              onChange={(e) => { setFilterProvider(e.target.value); setCurrentPage(1); }}
              className="bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg px-3 py-1.5 text-xs text-[#0E1726] focus:outline-none focus:border-[#6D28D9]"
            >
              <option value="ALL">All Providers</option>
              <option value="OPENAI">OpenAI</option>
              <option value="GEMINI">Gemini</option>
              <option value="ANTHROPIC">Anthropic</option>
              <option value="AZURE">Azure OpenAI</option>
            </select>
          </div>

          {/* Decision Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#6B7488] font-bold uppercase">Decision:</span>
            <select
              value={filterDecision}
              onChange={(e) => { setFilterDecision(e.target.value); setCurrentPage(1); }}
              className="bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg px-3 py-1.5 text-xs text-[#0E1726] focus:outline-none focus:border-[#6D28D9]"
            >
              <option value="ALL">All Decisions</option>
              <option value="ALLOW">ALLOW</option>
              <option value="BLOCK">BLOCK</option>
              <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
            </select>
          </div>
        </div>
      </GlassCard>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={currentItems}
        loading={loading}
      />

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-[#6B7488]">
            Showing <span className="text-[#0E1726] font-bold">{indexOfFirstItem + 1}</span> to{' '}
            <span className="text-[#0E1726] font-bold">{Math.min(indexOfLastItem, filteredRequests.length)}</span> of{' '}
            <span className="text-[#0E1726] font-bold">{filteredRequests.length}</span> requests
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GatewayRequests;
