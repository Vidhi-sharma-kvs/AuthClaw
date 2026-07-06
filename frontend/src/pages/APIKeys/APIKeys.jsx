import React, { useEffect, useState } from 'react';
import { Check, Copy, Key, Plus, RefreshCw, Trash2, RotateCcw } from 'lucide-react';
import apiClient from '../../services/api';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge, 
  DataTable 
} from '../../components/Common/DesignSystem';

const APIKeys = () => {
  const { addToast } = useToast();
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState('');
  const [createdKey, setCreatedKey] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copiedEndpoint, setCopiedEndpoint] = useState(false);
  const configuredGatewayBase = import.meta.env.VITE_GATEWAY_PUBLIC_URL || import.meta.env.VITE_API_BASE_URL || '';
  const gatewayBaseUrl = configuredGatewayBase.startsWith('/')
    ? `${window.location.origin}${configuredGatewayBase}`
    : (configuredGatewayBase || window.location.origin);
  const gatewayEndpoint = `${gatewayBaseUrl.replace(/\/$/, '')}/gateway/chat`;

  const loadKeys = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/keys/list');
      setKeys(response.data || []);
    } catch (error) {
      addToast('Failed to load API keys.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const createKey = async (event) => {
    event.preventDefault();
    const keyName = name.trim() || 'Production gateway key';
    try {
      const response = await apiClient.post('/keys/generate', { name: keyName });
      setCreatedKey(response.data.api_key);
      setName('');
      addToast('API key created. Copy it now; it will not be shown again.', 'success');
      await loadKeys();
    } catch (error) {
      addToast('Failed to create API key.', 'error');
    }
  };

  const revokeKey = async (id) => {
    try {
      await apiClient.delete(`/keys/${id}`);
      addToast('API key revoked.', 'success');
      await loadKeys();
    } catch (error) {
      addToast('Failed to revoke API key.', 'error');
    }
  };

  const rotateKey = async (key) => {
    if (!confirm(`Rotate API key "${key.name}"? The current key will be revoked immediately.`)) return;
    try {
      const response = await apiClient.post(`/keys/${key.id}/rotate`, {});
      setCreatedKey(response.data.api_key);
      addToast('API key rotated. Copy the new key now; it will not be shown again.', 'success');
      await loadKeys();
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to rotate API key.', 'error');
    }
  };

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textarea);

    if (!copied) {
      throw new Error('Clipboard copy failed.');
    }
  };

  const copyGatewayEndpoint = async () => {
    try {
      await copyText(gatewayEndpoint);
      setCopiedEndpoint(true);
      addToast('Gateway endpoint copied.', 'success');
      setTimeout(() => setCopiedEndpoint(false), 2000);
    } catch (error) {
      addToast('Copy failed. Select and copy the URL manually.', 'error');
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (key) => <span className="font-semibold text-white">{key.name}</span>
    },
    {
      key: 'key_prefix',
      header: 'Prefix',
      render: (key) => <span className="font-mono text-gray-400">{key.key_prefix || 'N/A'}</span>
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (key) => <StatusBadge status={key.status} />
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (key) => <span className="text-gray-400">{key.created_at || 'N/A'}</span>
    },
    {
      key: 'last_used_at',
      header: 'Last Used',
      render: (key) => <span className="text-gray-400">{key.last_used_at || 'Never'}</span>
    },
    {
      key: 'expires_at',
      header: 'Expires',
      render: (key) => <span className="text-gray-400">{key.expires_at || 'No expiration'}</span>
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (key) => (
        <div className="flex justify-end gap-3" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => rotateKey(key)}
            disabled={key.status !== 'active'}
            className="inline-flex items-center gap-1.5 text-violet-400 hover:text-violet-300 disabled:opacity-40 disabled:pointer-events-none transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Rotate
          </button>
          <button
            onClick={() => revokeKey(key.id)}
            disabled={key.status !== 'active'}
            className="inline-flex items-center gap-1.5 text-rose-400 hover:text-rose-300 disabled:opacity-40 disabled:pointer-events-none transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" /> Revoke
          </button>
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
          API Keys
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Create, rotate, and revoke AuthClaw gateway keys for tenant-scoped integrations.
        </p>
      </div>

      <GlassCard hover={false} className="border-emerald-500/10 bg-emerald-500/5">
        <div className="flex items-center gap-3 text-sm text-emerald-300">
          <Key className="w-4 h-4" />
          <span>Your API key is securely stored and encrypted. Full key values are only shown once.</span>
        </div>
      </GlassCard>

      <GlassCard hover={false} className="border-violet-500/10 bg-violet-500/5 space-y-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">Customer Gateway URL</p>
          <p className="text-sm text-gray-300 mt-1">
            Use this endpoint from your company app. Every request passes through AuthClaw governance before reaching the configured LLM provider.
          </p>
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <code className="flex-1 rounded-lg bg-slate-950 border border-white/5 p-3 text-sm text-white break-all font-mono">
            POST {gatewayEndpoint}
          </code>
          <Button
            variant="secondary"
            onClick={copyGatewayEndpoint}
            className="shrink-0"
          >
            {copiedEndpoint ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
            {copiedEndpoint ? 'Copied' : 'Copy URL'}
          </Button>
        </div>
        <p className="text-xs text-gray-500">
          Send the generated AuthClaw API key as a Bearer token from your backend service. Do not expose it in browser code.
        </p>
      </GlassCard>

      {createdKey && (
        <GlassCard hover={false} className="border-amber-500/20 bg-amber-500/5">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-300 mb-2">New API Key</p>
          <code className="block rounded bg-slate-950 border border-white/5 p-3 text-sm text-white break-all font-mono">
            {createdKey}
          </code>
          <p className="text-xs text-gray-400 mt-2">This is the only time the full key is displayed.</p>
        </GlassCard>
      )}

      <form onSubmit={createKey} className="flex flex-col gap-3 sm:flex-row items-stretch">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Production gateway key"
          aria-label="API key name"
          className="flex-1 bg-slate-950 border border-white/5 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-purple-500/40 focus:ring-1 focus:ring-purple-500/40 transition duration-200"
        />
        <Button type="submit">
          <Plus className="w-4 h-4" /> Create Key
        </Button>
      </form>

      <GlassCard hover={false} className="p-0 overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">Tenant API Keys</h2>
          <button onClick={loadKeys} className="text-gray-400 hover:text-white" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <DataTable
          columns={columns}
          data={keys}
          loading={loading}
        />
      </GlassCard>
    </div>
  );
};

export default APIKeys;
