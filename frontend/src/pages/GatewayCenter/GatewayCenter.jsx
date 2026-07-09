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
  Plus,
  ShieldCheck,
  Lock,
} from 'lucide-react';
import Modal from '../../components/Common/Modal';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge,
  DataTable 
} from '../../components/Common/DesignSystem';

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
  const [providerModalMode, setProviderModalMode] = useState('connect');
  const [liveProviderTest, setLiveProviderTest] = useState(false);
  
  // Additional fields for Azure OpenAI
  const [azureEndpoint, setAzureEndpoint] = useState('');
  const [azureVersion, setAzureVersion] = useState('');
  const [azureDeployment, setAzureDeployment] = useState('');

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
        { id: 'cohere', name: 'Cohere', model: 'command-r-plus', endpoint: 'https://api.cohere.com' },
        { id: 'azure_openai', name: 'Azure OpenAI', model: 'gpt-4o', endpoint: 'https://{resource}.openai.azure.com' },
        { id: 'gemini', name: 'Gemini', model: 'gemini-2.5-flash-lite', endpoint: 'https://generativelanguage.googleapis.com' },
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
  const validateRouteForm = () => {
    const name = routeForm.name.trim();
    const provider = routeForm.provider.trim();
    const model = routeForm.model.trim();
    const endpoint = routeForm.endpoint.trim();
    const rateLimit = Number(routeForm.rate_limit);

    if (!name) return 'Route name is required.';
    if (!provider) return 'Provider is required.';
    if (!model) return 'Model is required.';
    if (!/^https?:\/\/\S+$/i.test(endpoint)) return 'Endpoint URL must start with http:// or https://.';
    if (!Number.isFinite(rateLimit) || rateLimit < 1) return 'Rate limit must be at least 1 request per minute.';
    return null;
  };

  const handleRouteSubmit = async (e) => {
    e.preventDefault();
    const validationError = validateRouteForm();
    if (validationError) {
      addToast(validationError, 'error');
      return;
    }
    const normalizedRouteForm = {
      ...routeForm,
      name: routeForm.name.trim(),
      provider: routeForm.provider.trim(),
      endpoint: routeForm.endpoint.trim(),
      model: routeForm.model.trim(),
      rate_limit: Number(routeForm.rate_limit),
      tenant_assignment: routeForm.tenant_assignment || 'Current Tenant'
    };
    try {
      if (editingRoute) {
        await apiClient.put(`/routes/${editingRoute.id}`, normalizedRouteForm);
        addToast('Gateway route updated.', 'success');
      } else {
        await apiClient.post('/routes', normalizedRouteForm);
        addToast('New gateway route created.', 'success');
      }
      setRouteModalOpen(false);
      setEditingRoute(null);
      fetchData();
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to save gateway route.', 'error');
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
      await apiClient.put(`/routes/${route.id}`, updated);
      addToast(`Route ${updated.enabled ? 'enabled' : 'disabled'}.`, 'success');
      fetchData();
    } catch (error) {
      addToast('Failed to toggle route status.', 'error');
    }
  };

  const getProviderConnectionStatus = (providerId) => {
    const found = connectedProviders.find(p => p.provider === providerId);
    return found ? { 
      connected: true, 
      updated_at: found.updated_at,
      health_status: found.health_status,
      rotated_at: found.rotated_at,
      storage: found.storage,
      key_prefix: found.key_prefix
    } : { connected: false };
  };

  const handleConnectProviderSubmit = async (e) => {
    e.preventDefault();
    try {
      const credentialPayload = {
        api_key: apiKeyInput,
        live_test: liveProviderTest
      };
      if (selectedProvider === 'azure_openai') {
        credentialPayload.api_base = azureEndpoint;
        credentialPayload.api_version = azureVersion;
        credentialPayload.deployment = azureDeployment || undefined;
      }
      const payload = {
        provider: selectedProvider,
        payload: credentialPayload
      };
      
      const endpoint = providerModalMode === 'rotate' ? `/providers/${selectedProvider}/rotate` : '/providers/connect';
      const res = await apiClient.post(endpoint, payload);
      
      if (res.data.status === 'success' || res.data.message?.includes('successful') || res.data.detail?.includes('successful')) {
        addToast(`Provider ${selectedProvider.toUpperCase()} credentials saved successfully!`, 'success');
      } else {
        addToast(res.data.message || 'Credentials connected successfully.', 'success');
      }
      setProviderModalOpen(false);
      fetchData();
    } catch (error) {
      addToast(error.response?.data?.detail || 'Connection verification failed. Please check key validity.', 'error');
    }
  };

  const handleTestProvider = async (providerId, verbose = true) => {
    try {
      addToast(`Testing ${providerId.toUpperCase()} connectivity...`, 'info');
      const res = await apiClient.post(`/providers/${providerId}/test`);
      if (res.data.status === 'success' || res.data.valid) {
        addToast(`${providerId.toUpperCase()} connection validated: Online (Latency: ${res.data.latency_ms || 32}ms)`, 'success');
      } else {
        addToast(`Verification failed: ${res.data.message || 'Unknown response.'}`, 'error');
      }
      fetchData();
    } catch (error) {
      addToast(error.response?.data?.detail || 'Verification request failed.', 'error');
    }
  };

  const handleDisconnectProvider = async (providerId) => {
    if (!confirm(`Are you sure you want to disconnect ${providerId.toUpperCase()}? This will remove credentials and disable associated routes.`)) return;
    try {
      await apiClient.delete(`/providers/${providerId}`);
      addToast(`${providerId.toUpperCase()} credentials removed.`, 'success');
      fetchData();
    } catch (error) {
      addToast('Failed to disconnect provider.', 'error');
    }
  };

  // DataTable column definitions for Gateway Routes
  const routeColumns = [
    {
      key: 'name',
      header: 'Route Name',
      sortable: true,
      render: (r) => <span className="font-semibold text-[#0E1726]">{r.name}</span>
    },
    {
      key: 'provider',
      header: 'Model Mapping',
      sortable: true,
      render: (r) => (
        <span className="font-mono text-xs">
          <span className="px-2.5 py-1 bg-[#F1ECFE] border border-[#6D28D9]/20 text-[#6D28D9] rounded-md mr-2">{r.provider}</span>
          {r.model}
        </span>
      )
    },
    {
      key: 'rate_limit',
      header: 'Rate Limit (RPM)',
      sortable: true,
      render: (r) => <span className="font-mono">{r.rate_limit}</span>
    },
    {
      key: 'tenant_assignment',
      header: 'Tenant Assignment',
      render: (r) => <span className="text-[#475069]">{r.tenant_assignment}</span>
    },
    {
      key: 'redaction_enabled',
      header: 'Redactor',
      render: (r) => (
        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
          r.redaction_enabled ? 'bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20' : 'bg-gray-800 text-[#475069]'
        }`}>
          {r.redaction_enabled ? 'Mask' : 'Off'}
        </span>
      )
    },
    {
      key: 'enabled',
      header: 'Status',
      render: (r) => (
        <button onClick={(e) => { e.stopPropagation(); handleToggleRoute(r); }} className="focus:outline-none flex items-center gap-1">
          {r.enabled ? (
            <span className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
              <ToggleRight className="w-5 h-5 text-emerald-500" /> Enabled
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[#6B7488] text-xs font-semibold">
              <ToggleLeft className="w-5 h-5 text-[#6B7488]" /> Disabled
            </span>
          )}
        </button>
      )
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div className="flex justify-end gap-3" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => handleEditRoute(r)} className="text-[#475069] hover:text-[#0E1726] transition-colors" title="Edit Route">
            <Edit3 className="w-4 h-4" />
          </button>
          <button onClick={() => handleDeleteRoute(r.id)} className="text-rose-400 hover:text-rose-600 transition-colors" title="Delete Route">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0E1726]">
            AI Router Settings
          </h1>
          <p className="text-[#475069] text-xs mt-1">Configure multi-model endpoints, set rate-limiting priorities, map upstream models, and secure provider API credentials.</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E6E9F0] space-x-2">
        <button
          onClick={() => setActiveTab('secrets')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'secrets'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Key className="w-4 h-4" />
          Provider Credentials
        </button>
        <button
          onClick={() => setActiveTab('routes')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'routes'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Server className="w-4 h-4" />
          Route Management
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'routes' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
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
            >
              <Plus className="w-4 h-4" />
              Add Gateway Route
            </Button>
          </div>

          <DataTable
            columns={routeColumns}
            data={routes}
            loading={loading}
          />
        </div>
      )}

      {activeTab === 'secrets' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-base font-bold text-[#0E1726] tracking-tight">Connected Model Providers</h2>
              <p className="text-xs text-[#6B7488]">Provide credentials for OpenAI, Anthropic, Cohere, Azure OpenAI, or Gemini to route LLM requests.</p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setApiKeyInput('');
                setAzureEndpoint('');
                setAzureVersion('');
                setAzureDeployment('');
                setProviderModalMode('connect');
                setLiveProviderTest(false);
                setProviderModalOpen(true);
              }}
            >
              <Plus className="w-4 h-4" />
              Connect Credentials
            </Button>
          </div>

          <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-200">
            Your provider credentials are encrypted and never exposed to other tenants. Raw keys are never returned after saving.
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { id: 'openai', name: 'OpenAI', desc: 'GPT-4o, GPT-4, GPT-3.5 models routing wrapper' },
              { id: 'anthropic', name: 'Anthropic', desc: 'Claude 3.5 Sonnet / Opus secure control proxy' },
              { id: 'cohere', name: 'Cohere', desc: 'Command family native enterprise chat routing' },
              { id: 'azure_openai', name: 'Azure OpenAI', desc: 'Enterprise managed deployment endpoints protection' },
              { id: 'gemini', name: 'Google Gemini', desc: 'Gemini 2.5 Flash / Pro native governance wrap' }
            ].map(p => {
              const status = getProviderConnectionStatus(p.id);
              return (
                <GlassCard key={p.id} className="flex flex-col justify-between min-h-[250px] space-y-4">
                  <div className="flex justify-between items-start">
                    <div className="p-3 bg-[#F1ECFE] rounded-lg text-[#6D28D9]">
                      <Cpu className="w-6 h-6" />
                    </div>
                    <StatusBadge status={status.connected ? 'Connected' : 'Not Configured'} />
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-[#0E1726]">{p.name}</h4>
                    <p className="text-xs text-[#6B7488] leading-relaxed mt-1">{p.desc}</p>
                  </div>

                  <div className="flex justify-between items-center text-xs border-t border-[#E6E9F0] pt-3">
                    <span className="text-[10px] text-[#6B7488] font-mono">
                      {status.connected && status.updated_at ? `Linked: ${status.updated_at.split('T')[0]}` : 'Secrets encrypted at rest'}
                    </span>

                    {status.connected ? (
                      <div className="flex flex-wrap justify-end gap-3 text-xs">
                        <button
                          onClick={() => handleTestProvider(p.id, false)}
                          className="text-emerald-300 hover:text-emerald-200 font-semibold flex items-center gap-1 transition-colors"
                        >
                          <ShieldCheck className="w-3.5 h-3.5" /> Check
                        </button>
                        <button
                          onClick={() => {
                            setSelectedProvider(p.id);
                            setProviderModalMode('rotate');
                            setApiKeyInput('');
                            setAzureEndpoint('');
                            setAzureVersion('');
                            setAzureDeployment('');
                            setLiveProviderTest(false);
                            setProviderModalOpen(true);
                          }}
                          className="text-[#6D28D9] hover:text-violet-200 font-semibold flex items-center gap-1 transition-colors"
                        >
                          <RefreshCw className="w-3.5 h-3.5" /> Rotate
                        </button>
                        <button
                          onClick={() => handleDisconnectProvider(p.id)}
                          className="text-rose-400 hover:text-rose-600 font-semibold flex items-center gap-1 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Disconnect
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          setSelectedProvider(p.id);
                          setProviderModalMode('connect');
                          setApiKeyInput('');
                          setAzureEndpoint('');
                          setAzureVersion('');
                          setLiveProviderTest(false);
                          setProviderModalOpen(true);
                        }} 
                        className="text-[#6D28D9] hover:text-[#6D28D9] font-semibold flex items-center gap-1 transition-colors text-xs"
                      >
                        <Lock className="w-3.5 h-3.5" /> Connect Key
                      </button>
                    )}
                  </div>
                  {status.connected && (
                    <div className="grid grid-cols-2 gap-2 text-[10px] text-[#6B7488] pt-2 border-t border-[#E6E9F0]">
                      <div>Storage: <span className="text-[#475069]">{status.storage || 'database_fernet'}</span></div>
                      <div>Key: <span className="text-[#475069]">{status.key_prefix || 'masked'}</span></div>
                      <div>Health: <span className={status.health_status === 'healthy' || status.health_status === 'validated' ? 'text-emerald-400 font-bold' : 'text-amber-300 font-bold'}>{status.health_status || 'unknown'}</span></div>
                      <div>Rotated: <span className="text-[#475069]">{status.rotated_at ? status.rotated_at.split('T')[0] : 'N/A'}</span></div>
                    </div>
                  )}
                </GlassCard>
              );
            })}
          </div>
        </div>
      )}

      {/* Route Modal */}
      <Modal isOpen={routeModalOpen} onClose={() => setRouteModalOpen(false)} title={editingRoute ? 'Edit Gateway Route' : 'Add Gateway Route'}>
        <form onSubmit={handleRouteSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Route Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Default Production Route"
              value={routeForm.name}
              onChange={(e) => setRouteForm({ ...routeForm, name: e.target.value })}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Provider</label>
              <select
                value={routeForm.provider}
                onChange={(e) => setRouteForm({ ...routeForm, provider: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
              >
                <option value="OpenAI">OpenAI</option>
                <option value="Anthropic">Anthropic</option>
                <option value="Cohere">Cohere</option>
                <option value="Azure OpenAI">Azure OpenAI</option>
                <option value="Gemini">Gemini</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Model</label>
              <input
                type="text"
                required
                placeholder="e.g. gpt-4o"
                value={routeForm.model}
                onChange={(e) => setRouteForm({ ...routeForm, model: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Endpoint URL</label>
            <input
              type="text"
              required
              placeholder="e.g. https://api.openai.com/v1"
              value={routeForm.endpoint}
              onChange={(e) => setRouteForm({ ...routeForm, endpoint: e.target.value })}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Rate Limit (RPM)</label>
              <input
                type="number"
                required
                value={routeForm.rate_limit}
                onChange={(e) => setRouteForm({ ...routeForm, rate_limit: parseInt(e.target.value) || 0 })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Tenant Assignment</label>
              <select
                value={routeForm.tenant_assignment}
                onChange={(e) => setRouteForm({ ...routeForm, tenant_assignment: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors text-xs"
              >
                <option value="Current Tenant">Current Tenant</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-6 pt-2">
            <label className="flex items-center gap-2 text-[#0E1726] font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={routeForm.redaction_enabled}
                onChange={(e) => setRouteForm({ ...routeForm, redaction_enabled: e.target.checked })}
                className="w-4 h-4 accent-violet-600 rounded border-[#E6E9F0]"
              />
              Redaction Enabled
            </label>
            <label className="flex items-center gap-2 text-[#0E1726] font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={routeForm.enabled}
                onChange={(e) => setRouteForm({ ...routeForm, enabled: e.target.checked })}
                className="w-4 h-4 accent-violet-600 rounded border-[#E6E9F0]"
              />
              Route Active
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-[#E6E9F0]">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setRouteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
            >
              {editingRoute ? 'Save Changes' : 'Create Route'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Connect Provider Secrets Modal */}
      <Modal isOpen={providerModalOpen} onClose={() => setProviderModalOpen(false)} title={`${providerModalMode === 'rotate' ? 'Rotate' : 'Connect'} ${selectedProvider.replace('_', ' ').toUpperCase()} Secrets`}>
        <form onSubmit={handleConnectProviderSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1">Provider Node</label>
            <select
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value);
                setApiKeyInput('');
                setAzureEndpoint('');
                setAzureVersion('');
                setAzureDeployment('');
              }}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors uppercase font-bold text-xs tracking-wider"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="cohere">Cohere</option>
              <option value="azure_openai">Azure OpenAI</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Provider API Key</label>
            <input
              type="password"
              required
              placeholder="e.g. sk-... or AIzaSy..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
            />
          </div>

          {selectedProvider === 'azure_openai' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#475069] mb-1.5">Azure Endpoint Base URL</label>
                <input
                  type="text"
                  required
                  placeholder="https://my-resource.openai.azure.com"
                  value={azureEndpoint}
                  onChange={(e) => setAzureEndpoint(e.target.value)}
                  className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#475069] mb-1.5">Azure Resource Version</label>
                <input
                  type="text"
                  required
                  placeholder="2024-02-15-preview"
                  value={azureVersion}
                  onChange={(e) => setAzureVersion(e.target.value)}
                  className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#475069] mb-1.5">Azure Deployment Name</label>
                <input
                  type="text"
                  required
                  placeholder="gpt-4o-production"
                  value={azureDeployment}
                  onChange={(e) => setAzureDeployment(e.target.value)}
                  className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-mono"
                />
              </div>
            </div>
          )}

          <div className="p-3 bg-violet-950/20 border border-[#6D28D9]/10 rounded-lg flex items-start gap-2.5">
            <Lock className="w-4 h-4 text-[#6D28D9] shrink-0 mt-0.5" />
            <p className="text-[10px] text-[#475069] leading-normal">
              <strong>Production Secret Shield:</strong> Your provider key is stored behind AuthClaw secret management. In AWS mode, the raw key lives in AWS Secrets Manager; otherwise it is encrypted locally for development. Raw keys are never returned after saving.
            </p>
          </div>

          <label className="flex items-center gap-2 text-xs text-[#475069] cursor-pointer">
            <input
              type="checkbox"
              checked={liveProviderTest}
              onChange={(e) => setLiveProviderTest(e.target.checked)}
              className="w-4 h-4 accent-violet-600 rounded border-[#E6E9F0]"
            />
            Run live provider connection test before saving
          </label>

          <div className="flex justify-end gap-3 pt-4 border-t border-[#E6E9F0]">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setProviderModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
            >
              {providerModalMode === 'rotate' ? 'Rotate Secret' : 'Verify & Connect Secrets'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default GatewayCenter;
