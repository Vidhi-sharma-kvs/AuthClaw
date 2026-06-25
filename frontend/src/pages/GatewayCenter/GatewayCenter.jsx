import React, { useEffect, useState } from 'react';
import apiClient from '../../services/api';
import { 
  Server, 
  Cpu, 
  Key, 
  ToggleLeft, 
  ToggleRight, 
  RefreshCw, 
  Trash2, 
  Edit3, 
  CheckCircle, 
  AlertTriangle,
  ExternalLink,
  Plus,
  ShieldCheck,
  Calendar,
  Layers,
  Lock,
  Globe,
  Database
} from 'lucide-react';
import Modal from '../../components/Common/Modal';
import { useToast } from '../../components/Common/Toast';
const GatewayCenter = () => {
  const [activeTab, setActiveTab] = useState('secrets');
  const [providers, setProviders] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [connectedProviders, setConnectedProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  // Route Form State
  const [routeModalOpen, setRouteModalOpen] = useState(false);
  const [editingRoute, setEditingRoute] = useState(null);
  const [routeForm, setRouteForm] = useState({
    name: '',
    provider: 'OpenAI',
    endpoint: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    rate_limit: 100,
    redaction_enabled: true,
    enabled: true,
    tenant_assignment: 'Current Tenant'
  });

  // Connected Provider Form State
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [apiKeyInput, setApiKeyInput] = useState('');
  
  // Additional fields for Azure OpenAI
  const [azureEndpoint, setAzureEndpoint] = useState('');
  const [azureVersion, setAzureVersion] = useState('');

  const fetchData = async () => {
    let failed = false;
    try {
      const [routeRes, connectedRes] = await Promise.allSettled([
        apiClient.get('/routes'),
        apiClient.get('/providers/list')
      ]);

      if (routeRes.status === 'fulfilled') {
        setRoutes(routeRes.value.data);
      } else {
        failed = true;
        console.error('Error loading gateway routes:', routeRes.reason);
      }

      if (connectedRes.status === 'fulfilled') {
        setConnectedProviders(connectedRes.value.data);
      } else {
        failed = true;
        console.error('Error loading provider credentials:', connectedRes.reason);
      }

      setProviders([
        { id: 'openai', name: 'OpenAI', model: 'gpt-4o', endpoint: 'https://api.openai.com/v1' },
        { id: 'anthropic', name: 'Anthropic', model: 'claude-3-5-sonnet', endpoint: 'https://api.anthropic.com/v1' },
        { id: 'gemini', name: 'Gemini', model: 'gemini-2.5-flash-lite', endpoint: 'https://generativelanguage.googleapis.com' },
        { id: 'azure_openai', name: 'Azure OpenAI', model: 'gpt-4', endpoint: 'https://{resource}.openai.azure.com' }
      ]);
      if (failed) {
        addToast('Some gateway settings could not be loaded.', 'error');
      }
    } catch (error) {
      console.error('Unexpected Gateway data error:', error);
      addToast('Error fetching Gateway settings.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  // Routes handlers
  const handleRouteSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingRoute) {
        await apiClient.put(`/routes/${editingRoute.id}`, routeForm);
        addToast('Gateway route updated.', 'success');
      } else {
        await apiClient.post('/routes', routeForm);
        addToast('New gateway route created.', 'success');
      }
      setRouteModalOpen(false);
      setEditingRoute(null);
      fetchData();
    } catch (error) {
      addToast('Failed to save gateway route.', 'error');
    }
  };

  const handleEditRoute = (route) => {
    setEditingRoute(route);
    setRouteForm({
      name: route.name,
      provider: route.provider,
      endpoint: route.endpoint,
      model: route.model,
      rate_limit: route.rate_limit,
      redaction_enabled: route.redaction_enabled,
      enabled: route.enabled,
      tenant_assignment: route.tenant_assignment
    });
    setRouteModalOpen(true);
  };

  const handleDeleteRoute = async (id) => {
    if (!confirm('Are you sure you want to delete this route?')) return;
    try {
      await apiClient.delete(`/routes/${id}`);
      addToast('Route successfully removed.', 'success');
      fetchData();
    } catch (error) {
      addToast('Error deleting route.', 'error');
    }
  };

  const handleToggleRoute = async (route) => {
    try {
      const updated = { ...route, enabled: !route.enabled };
      const { id, ...payload } = updated;
      await apiClient.put(`/routes/${route.id}`, payload);
      addToast(`Route '${route.name}' ${updated.enabled ? 'enabled' : 'disabled'}.`, 'success');
      fetchData();
    } catch (error) {
      addToast('Error toggling route state.', 'error');
    }
  };

  // Provider credentials handlers
  const handleConnectProviderSubmit = async (e) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) {
      addToast('Please enter the API key.', 'error');
      return;
    }

    const payload = { api_key: apiKeyInput.trim() };
    if (selectedProvider === 'azure_openai') {
      payload.api_base = azureEndpoint.trim();
      payload.api_version = azureVersion.trim();
    }

    try {
      await apiClient.post('/providers/connect', {
        provider: selectedProvider,
        payload: payload
      });
      addToast(`${selectedProvider.toUpperCase()} credentials connected.`, 'success');
      setProviderModalOpen(false);
      setApiKeyInput('');
      setAzureEndpoint('');
      setAzureVersion('');
      fetchData();
    } catch (error) {
      console.error(error);
      addToast('Failed to connect provider secrets.', 'error');
    }
  };

  const handleDisconnectProvider = async (providerName) => {
    if (!confirm(`Are you sure you want to disconnect ${providerName.toUpperCase()} credentials?`)) return;
    try {
      await apiClient.delete(`/providers/${providerName.toLowerCase()}`);
      addToast(`${providerName.toUpperCase()} secrets disconnected.`, 'success');
      fetchData();
    } catch (error) {
      console.error(error);
      addToast('Failed to disconnect provider secrets.', 'error');
    }
  };

  const getProviderConnectionStatus = (providerKey) => {
    const conn = connectedProviders.find(p => p.provider === providerKey.toLowerCase());
    return conn ? { connected: true, updated_at: conn.updated_at } : { connected: false };
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-48 bg-white/5 rounded-lg"></div>
        <div className="h-[200px] bg-white/5 rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
          Provider Configuration
        </h1>
        <p className="text-gray-400 text-sm">
          Add tenant-owned provider credentials and route AuthClaw Gateway traffic to customer LLMs.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/5 pb-px">
        <button
          onClick={() => setActiveTab('routes')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'routes'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Server className="w-4 h-4" />
          Route Management
        </button>
        <button
          onClick={() => setActiveTab('secrets')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'secrets'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Key className="w-4 h-4" />
          Provider Credentials
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'routes' && (
        <div className="space-y-4 animate-fadeIn">
          {/* Create Button */}
          <div className="flex justify-end">
            <button
              onClick={() => {
                setEditingRoute(null);
                setRouteForm({
                  name: '',
                  provider: 'OpenAI',
                  endpoint: 'https://api.openai.com/v1',
                  model: 'gpt-4o',
                  rate_limit: 100,
                  redaction_enabled: true,
                  enabled: true,
                  tenant_assignment: 'Current Tenant'
                });
                setRouteModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              <Plus className="w-4 h-4" />
              Add Gateway Route
            </button>
          </div>

          {/* Routes Table */}
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 text-xs text-gray-400 uppercase tracking-wider bg-white/2">
                  <th className="py-5 px-8">Route Name</th>
                  <th className="py-5 px-8">Model Mapping</th>
                  <th className="py-5 px-8">Rate Limit (RPM)</th>
                  <th className="py-5 px-8">Tenant Assignment</th>
                  <th className="py-5 px-8">Redactor</th>
                  <th className="py-5 px-8">Status</th>
                  <th className="py-5 px-8 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-sm">
                {routes.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="py-10 px-8 text-center text-gray-500">
                      No gateway routes configured yet. Add a route after connecting provider credentials.
                    </td>
                  </tr>
                ) : routes.map((r) => (
                  <tr key={r.id} className="hover:bg-white/2 transition-colors">
                    <td className="py-5 px-8 font-semibold text-white">{r.name}</td>
                    <td className="py-5 px-8 font-mono text-xs">
                      <span className="px-2.5 py-1 bg-violet-600/10 border border-violet-500/20 text-violet-400 rounded-md mr-2">{r.provider}</span>
                      {r.model}
                    </td>
                    <td className="py-5 px-8 font-mono">{r.rate_limit}</td>
                    <td className="py-5 px-8 text-gray-300">{r.tenant_assignment}</td>
                    <td className="py-5 px-8">
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                        r.redaction_enabled ? 'bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20' : 'bg-gray-800 text-gray-400'
                      }`}>
                        {r.redaction_enabled ? 'Mask' : 'Off'}
                      </span>
                    </td>
                    <td className="py-5 px-8">
                      <button onClick={() => handleToggleRoute(r)} className="focus:outline-none">
                        {r.enabled ? (
                          <span className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                            <ToggleRight className="w-5 h-5 text-emerald-500" /> Enabled
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5 text-gray-500 text-xs font-semibold">
                            <ToggleLeft className="w-5 h-5 text-gray-600" /> Disabled
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="py-5 px-8 text-right space-x-4">
                      <button onClick={() => handleEditRoute(r)} className="text-gray-400 hover:text-white transition-colors" title="Edit Route">
                        <Edit3 className="w-4 h-4 inline" />
                      </button>
                      <button onClick={() => handleDeleteRoute(r.id)} className="text-rose-400 hover:text-rose-600 transition-colors" title="Delete Route">
                        <Trash2 className="w-4 h-4 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'secrets' && (
        <div className="space-y-6 animate-fadeIn">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">Connected Model Providers</h2>
              <p className="text-xs text-gray-500">Provide credentials for OpenAI, Anthropic, Gemini, or Azure OpenAI to route LLM requests.</p>
            </div>
            <button
              onClick={() => {
                setApiKeyInput('');
                setAzureEndpoint('');
                setAzureVersion('');
                setProviderModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-xs font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              <Plus className="w-4 h-4" />
              Connect Provider Credentials
            </button>
          </div>

          <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-200">
            Your provider credentials are encrypted and never exposed to other tenants. Raw keys are never returned after saving.
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { id: 'openai', name: 'OpenAI', desc: 'GPT-4o, GPT-4, GPT-3.5 models routing wrapper' },
              { id: 'gemini', name: 'Google Gemini', desc: 'Gemini 2.5 Flash / Pro native governance wrap' },
              { id: 'anthropic', name: 'Anthropic', desc: 'Claude 3.5 Sonnet / Opus secure control proxy' },
              { id: 'azure_openai', name: 'Azure OpenAI', desc: 'Enterprise managed endpoints protection' }
            ].map(p => {
              const status = getProviderConnectionStatus(p.id);
              return (
                <div key={p.id} className="glass-card p-6 flex flex-col justify-between h-[210px] space-y-4 hover:border-white/10 transition-all duration-300">
                  <div className="flex justify-between items-start">
                    <div className="p-3 bg-violet-600/10 rounded-lg text-violet-400">
                      <Cpu className="w-6 h-6" />
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                        status.connected 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                          : 'bg-slate-900 border border-white/5 text-gray-500'
                      }`}>
                        {status.connected ? 'Connected' : 'Not Configured'}
                      </span>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-white">{p.name}</h4>
                    <p className="text-xs text-gray-500 leading-relaxed mt-1">{p.desc}</p>
                  </div>

                  <div className="flex justify-between items-center text-xs border-t border-white/5 pt-3">
                    <span className="text-[10px] text-gray-500 font-mono">
                      {status.connected && status.updated_at ? `Linked: ${status.updated_at.split('T')[0]}` : 'Secrets encrypted at rest'}
                    </span>
                    
                    {status.connected ? (
                      <button 
                        onClick={() => handleDisconnectProvider(p.id)} 
                        className="text-rose-400 hover:text-rose-600 font-semibold flex items-center gap-1 transition-colors text-xs"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Disconnect
                      </button>
                    ) : (
                      <button 
                        onClick={() => {
                          setSelectedProvider(p.id);
                          setApiKeyInput('');
                          setAzureEndpoint('');
                          setAzureVersion('');
                          setProviderModalOpen(true);
                        }} 
                        className="text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-1 transition-colors text-xs"
                      >
                        <Lock className="w-3.5 h-3.5" /> Connect Key
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Route Modal */}
      <Modal isOpen={routeModalOpen} onClose={() => setRouteModalOpen(false)} title={editingRoute ? 'Edit Gateway Route' : 'Add Gateway Route'}>
        <form onSubmit={handleRouteSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Route Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Default Production Route"
              value={routeForm.name}
              onChange={(e) => setRouteForm({ ...routeForm, name: e.target.value })}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Provider</label>
              <select
                value={routeForm.provider}
                onChange={(e) => setRouteForm({ ...routeForm, provider: e.target.value })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="OpenAI">OpenAI</option>
                <option value="Anthropic">Anthropic</option>
                <option value="Azure OpenAI">Azure OpenAI</option>
                <option value="Gemini">Gemini</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Model</label>
              <input
                type="text"
                required
                placeholder="e.g. gpt-4o"
                value={routeForm.model}
                onChange={(e) => setRouteForm({ ...routeForm, model: e.target.value })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Endpoint URL</label>
            <input
              type="text"
              required
              placeholder="e.g. https://api.openai.com/v1"
              value={routeForm.endpoint}
              onChange={(e) => setRouteForm({ ...routeForm, endpoint: e.target.value })}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Rate Limit (RPM)</label>
              <input
                type="number"
                required
                value={routeForm.rate_limit}
                onChange={(e) => setRouteForm({ ...routeForm, rate_limit: parseInt(e.target.value) || 0 })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Tenant Assignment</label>
              <select
                value={routeForm.tenant_assignment}
                onChange={(e) => setRouteForm({ ...routeForm, tenant_assignment: e.target.value })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="Current Tenant">Current Tenant</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-6 pt-2">
            <label className="flex items-center gap-2 text-white font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={routeForm.redaction_enabled}
                onChange={(e) => setRouteForm({ ...routeForm, redaction_enabled: e.target.checked })}
                className="w-4 h-4 accent-violet-600 rounded border-white/10"
              />
              Redaction Enabled
            </label>
            <label className="flex items-center gap-2 text-white font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={routeForm.enabled}
                onChange={(e) => setRouteForm({ ...routeForm, enabled: e.target.checked })}
                className="w-4 h-4 accent-violet-600 rounded border-white/10"
              />
              Route Active
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
            <button
              type="button"
              onClick={() => setRouteModalOpen(false)}
              className="px-4 py-2 border border-white/10 text-gray-400 rounded-lg font-semibold hover:text-white hover:bg-white/5 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              {editingRoute ? 'Save Changes' : 'Create Route'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Connect Provider Secrets Modal */}
      <Modal isOpen={providerModalOpen} onClose={() => setProviderModalOpen(false)} title={`Connect ${selectedProvider.replace('_', ' ').toUpperCase()} Secrets`}>
        <form onSubmit={handleConnectProviderSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">Provider Node</label>
            <select
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value);
                setApiKeyInput('');
                setAzureEndpoint('');
                setAzureVersion('');
              }}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors uppercase font-bold text-xs tracking-wider"
            >
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
              <option value="anthropic">Anthropic</option>
              <option value="azure_openai">Azure OpenAI</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Provider API Key</label>
            <input
              type="password"
              required
              placeholder="e.g. sk-... or AIzaSy..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors font-mono"
            />
          </div>

          {selectedProvider === 'azure_openai' && (
            <div className="space-y-4 animate-scaleUp">
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1.5">Azure Endpoint Base URL</label>
                <input
                  type="text"
                  required
                  placeholder="https://my-resource.openai.azure.com"
                  value={azureEndpoint}
                  onChange={(e) => setAzureEndpoint(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-400 mb-1.5">Azure Resource Version</label>
                <input
                  type="text"
                  required
                  placeholder="2024-02-15-preview"
                  value={azureVersion}
                  onChange={(e) => setAzureVersion(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors font-mono"
                />
              </div>
            </div>
          )}

          <div className="p-3 bg-violet-950/20 border border-violet-500/10 rounded-lg flex items-start gap-2.5">
            <Lock className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
            <p className="text-[10px] text-gray-400 leading-normal">
              <strong>Symmetric Cryptographic Shield:</strong> Your credentials are symmetrically encrypted using AES-GCM-256 before storage in our PostgreSQL database. Decryption occurs entirely in-memory at execution time.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
            <button
              type="button"
              onClick={() => setProviderModalOpen(false)}
              className="px-4 py-2 border border-white/10 text-gray-400 rounded-lg font-semibold hover:text-white hover:bg-white/5 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              Verify & Connect Secrets
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default GatewayCenter;
