import React, { useEffect, useState } from 'react';
import { Check, Copy, Key, Plus, RefreshCw, Trash2, RotateCcw } from 'lucide-react';
import apiClient from '../../services/api';
import { useToast } from '../../components/Common/Toast';

const APIKeys = () => {
  const { addToast } = useToast();
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState('');
  const [createdKey, setCreatedKey] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copiedEndpoint, setCopiedEndpoint] = useState(false);
  const gatewayEndpoint = `${window.location.origin}/api/gateway/chat`;

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">API Keys</h1>
        <p className="text-sm text-gray-400 mt-1">
          Create, rotate, and revoke AuthClaw gateway keys for tenant-scoped integrations.
        </p>
      </div>

      <div className="glass-card p-5 border border-white/5">
        <div className="flex items-center gap-3 text-sm text-emerald-300">
          <Key className="w-4 h-4" />
          <span>Your API key is securely stored and encrypted. Full key values are only shown once.</span>
        </div>
      </div>

      <div className="glass-card p-5 border border-violet-500/20 bg-violet-500/5 space-y-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">Customer Gateway URL</p>
          <p className="text-sm text-gray-300 mt-1">
            Use this endpoint from your company app. Every request passes through AuthClaw governance before reaching the configured LLM provider.
          </p>
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <code className="flex-1 rounded-lg bg-slate-950 border border-white/10 p-3 text-sm text-white break-all">
            POST {gatewayEndpoint}
          </code>
          <button
            type="button"
            onClick={copyGatewayEndpoint}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 border border-white/10 px-4 py-3 text-sm font-semibold text-white hover:border-violet-500"
          >
            {copiedEndpoint ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
            {copiedEndpoint ? 'Copied' : 'Copy URL'}
          </button>
        </div>
        <p className="text-xs text-gray-500">
          Send the generated AuthClaw API key as a Bearer token from your backend service. Do not expose it in browser code.
        </p>
      </div>

      {createdKey && (
        <div className="glass-card p-5 border border-amber-500/20 bg-amber-500/5">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-300 mb-2">New API Key</p>
          <code className="block rounded bg-slate-950 border border-white/10 p-3 text-sm text-white break-all">
            {createdKey}
          </code>
          <p className="text-xs text-gray-400 mt-2">This is the only time the full key is displayed.</p>
        </div>
      )}

      <form onSubmit={createKey} className="glass-card p-5 border border-white/5 flex flex-col gap-3 sm:flex-row">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Production gateway key"
          aria-label="API key name"
          className="flex-1 bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
        />
        <button
          type="submit"
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500"
        >
          <Plus className="w-4 h-4" /> Create Key
        </button>
      </form>

      <div className="glass-card border border-white/5 overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">Tenant API Keys</h2>
          <button onClick={loadKeys} className="text-gray-400 hover:text-white" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-gray-500">
              <tr className="border-b border-white/5">
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Prefix</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Created</th>
                <th className="px-5 py-3">Last Used</th>
                <th className="px-5 py-3">Expires</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {keys.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-5 py-10 text-center text-gray-500">
                    No API keys created yet.
                  </td>
                </tr>
              ) : (
                keys.map((key) => (
                  <tr key={key.id}>
                    <td className="px-5 py-4 text-white">{key.name}</td>
                    <td className="px-5 py-4 font-mono text-gray-400">{key.key_prefix || 'N/A'}</td>
                    <td className="px-5 py-4">
                      <span className={`rounded-full px-2 py-1 text-xs ${
                        key.status === 'active' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'
                      }`}>
                        {key.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-gray-400">{key.created_at || 'N/A'}</td>
                    <td className="px-5 py-4 text-gray-400">{key.last_used_at || 'Never'}</td>
                    <td className="px-5 py-4 text-gray-400">{key.expires_at || 'No expiration'}</td>
                    <td className="px-5 py-4 text-right space-x-3">
                      <button
                        onClick={() => rotateKey(key)}
                        disabled={key.status !== 'active'}
                        className="inline-flex items-center gap-2 text-violet-300 hover:text-violet-200 disabled:opacity-40"
                      >
                        <RotateCcw className="w-4 h-4" /> Rotate
                      </button>
                      <button
                        onClick={() => revokeKey(key.id)}
                        disabled={key.status !== 'active'}
                        className="inline-flex items-center gap-2 text-rose-300 hover:text-rose-200 disabled:opacity-40"
                      >
                        <Trash2 className="w-4 h-4" /> Revoke
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default APIKeys;
