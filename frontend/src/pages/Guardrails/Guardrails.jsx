import React, { useEffect, useState } from 'react';
import apiClient from '../../services/api';
import { 
  ShieldCheck, 
  Sliders, 
  Trash2, 
  Plus, 
  Sparkles,
  ToggleLeft,
  ToggleRight,
  ArrowRight,
  Lock
} from 'lucide-react';
import Modal from '../../components/Common/Modal';
import { useToast } from '../../components/Common/Toast';
import { 
  Button, 
  GlassCard, 
  StatusBadge 
} from '../../components/Common/DesignSystem';

const Guardrails = () => {
  const [activeTab, setActiveTab] = useState('policies');
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  // Policy Builder form
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [policyForm, setPolicyForm] = useState({
    name: '',
    type: 'PII',
    rules: '{"categories": ["pii"], "action": "redact", "blocked_keywords": []}',
    enabled: true,
    status: 'draft',
    severity_level: 'MEDIUM'
  });
  const [simulationText, setSimulationText] = useState('Customer email is john.doe@acme.com and API key is sk-live-example1234567890.');
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulationRunning, setSimulationRunning] = useState(false);

  // Redaction playground state
  const [playgroundInput, setPlaygroundInput] = useState("Hi, my email is john.doe@acme.com and my Aadhar number is 1234-5678-9012.");
  const [playgroundOutput, setPlaygroundOutput] = useState("");
  const [redactedCount, setRedactedCount] = useState(0);
  const [playgroundConfidence, setPlaygroundConfidence] = useState(100);
  const [playgroundTriggered, setPlaygroundTriggered] = useState("N/A");
  const [playgroundEvaluating, setPlaygroundEvaluating] = useState(false);

  const fetchPolicies = async () => {
    try {
      const res = await apiClient.get('/policies/list');
      setPolicies(res.data);
    } catch (error) {
      console.error('Error fetching policies:', error);
      addToast('Failed to load guardrail policies.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handlePolicySubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingPolicy) {
        await apiClient.put(`/policies/${editingPolicy.id}`, policyForm);
        addToast('Policy updated.', 'success');
      } else {
        await apiClient.post('/policies', policyForm);
        addToast('Policy created.', 'success');
      }
      setPolicyModalOpen(false);
      setEditingPolicy(null);
      fetchPolicies();
    } catch (error) {
      addToast('Failed to save policy.', 'error');
    }
  };

  const handleEditPolicy = (policy) => {
    setEditingPolicy(policy);
    setPolicyForm({
      name: policy.name,
      type: policy.type,
      rules: typeof policy.rules === 'string' ? policy.rules : JSON.stringify(policy.rules),
      enabled: policy.enabled,
      status: policy.status || 'published',
      severity_level: policy.severity_level || 'MEDIUM'
    });
    setPolicyModalOpen(true);
  };

  const handleDeletePolicy = async (id) => {
    if (!confirm('Are you sure you want to delete this policy?')) return;
    try {
      await apiClient.delete(`/policies/${id}`);
      addToast('Policy removed.', 'success');
      fetchPolicies();
    } catch (error) {
      addToast('Error deleting policy.', 'error');
    }
  };

  const handleTogglePolicy = async (policy) => {
    try {
      const updated = { ...policy, enabled: !policy.enabled };
      const { id, ...payload } = updated;
      if (typeof payload.rules !== 'string') {
        payload.rules = JSON.stringify(payload.rules);
      }
      await apiClient.put(`/policies/${policy.id}`, payload);
      addToast(`Policy '${policy.name}' ${updated.enabled ? 'activated' : 'deactivated'}.`, 'success');
      fetchPolicies();
    } catch (error) {
      addToast('Error toggling policy.', 'error');
    }
  };

  const runPolicySimulation = async () => {
    setSimulationRunning(true);
    setSimulationResult(null);
    try {
      const response = await apiClient.post('/policies/simulate', {
        ...policyForm,
        sample_text: simulationText
      });
      setSimulationResult(response.data);
      addToast('Policy simulation complete.', 'success');
    } catch (error) {
      addToast('Policy simulation failed.', 'error');
    } finally {
      setSimulationRunning(false);
    }
  };

  const runRedactorPlayground = async () => {
    setPlaygroundEvaluating(true);
    try {
      const response = await apiClient.post('/policies/redact', {
        text: playgroundInput
      });
      const data = response.data;
      setPlaygroundOutput(data.redacted_text);
      setRedactedCount(data.count);
      setPlaygroundConfidence(data.confidence);
      setPlaygroundTriggered(data.triggered);
      addToast("Playground inspection complete.", "success");
    } catch (error) {
      console.error("Redactor playground error:", error);
      addToast("Failed to execute inspection on backend.", "error");
    } finally {
      setPlaygroundEvaluating(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-48 bg-[#F5F7FA] rounded-lg"></div>
        <div className="h-[200px] bg-[#F5F7FA] rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-[#0E1726]">
          Guardrails & Redaction Center
        </h1>
        <p className="text-[#475069] text-sm">
          Build compliance rules and inspect real-time response redactions.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E6E9F0] space-x-2">
        <button
          onClick={() => setActiveTab('policies')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'policies'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Sliders className="w-4 h-4" />
          Policies & Guardrails
        </button>
        <button
          onClick={() => setActiveTab('redaction')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'redaction'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Lock className="w-4 h-4" />
          Redaction Playground
        </button>
      </div>

      {/* Policies View */}
      {activeTab === 'policies' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setEditingPolicy(null);
                setPolicyForm({
                  name: '',
                  type: 'PII',
                  rules: '{"categories": ["pii"], "action": "redact", "blocked_keywords": []}',
                  enabled: true,
                  status: 'draft',
                  severity_level: 'MEDIUM'
                });
                setSimulationResult(null);
                setPolicyModalOpen(true);
              }}
            >
              <Plus className="w-4 h-4" />
              Create Guardrail Policy
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {policies.length === 0 ? (
              <div className="lg:col-span-3 flex flex-col items-center justify-center p-12 border border-dashed border-[#E6E9F0] rounded-xl bg-[#F5F7FA]/70">
                <p className="text-sm font-semibold text-[#0E1726]">No policies configured yet.</p>
                <p className="text-xs text-[#6B7488] mt-1">Create tenant guardrails for PII, secrets, prompt injection, and compliance rules.</p>
              </div>
            ) : policies.map((p) => (
              <GlassCard key={p.id} className="flex flex-col justify-between h-[210px] space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs uppercase tracking-wider text-fuchsia-400 font-mono font-bold">{p.type} Framework</span>
                    <h3 className="text-base font-bold text-[#0E1726] mt-0.5">{p.name}</h3>
                    <p className="text-[10px] uppercase tracking-wider text-[#6B7488] mt-1 font-mono">
                      v{p.version || 1} - {p.status || 'published'} - {p.severity_level || 'MEDIUM'}
                    </p>
                  </div>
                  <button onClick={() => handleTogglePolicy(p)} className="focus:outline-none transition-transform hover:scale-105">
                    {p.enabled ? (
                      <ToggleRight className="w-6 h-6 text-emerald-500" />
                    ) : (
                      <ToggleLeft className="w-6 h-6 text-[#6B7488]" />
                    )}
                  </button>
                </div>

                <div className="bg-[#F5F7FA] p-2.5 rounded border border-[#E6E9F0] text-[11px] font-mono text-[#475069] overflow-y-auto max-h-[70px]">
                  {typeof p.rules === 'string' ? p.rules : JSON.stringify(p.rules)}
                </div>

                <div className="flex justify-between items-center text-xs text-[#475069] border-t border-[#E6E9F0] pt-3">
                  <span className={`flex items-center gap-1 font-semibold ${p.enabled ? 'text-emerald-400 font-bold' : 'text-[#6B7488]'}`}>
                    <ShieldCheck className="w-3.5 h-3.5" /> {p.enabled ? 'Active Guardrail' : 'Suspended'}
                  </span>
                  <div className="flex gap-3">
                    <button onClick={() => handleEditPolicy(p)} className="text-[#475069] hover:text-[#0E1726] transition-colors" title="Edit">
                      <Sliders className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => handleDeletePolicy(p.id)} className="text-rose-400 hover:text-rose-500 transition-colors" title="Delete">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        </div>
      )}

      {/* Redaction Playground */}
      {activeTab === 'redaction' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Playground inputs */}
          <div className="lg:col-span-2 space-y-4">
            <GlassCard hover={false} className="p-6 space-y-4">
              <h3 className="text-base font-bold text-[#0E1726] flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#6D28D9]" />
                PII Redaction Playground Sandbox
              </h3>
              <div className="space-y-1">
                <label className="text-xs text-[#475069] font-semibold block">Input Text Completion</label>
                <textarea
                  value={playgroundInput}
                  onChange={(e) => setPlaygroundInput(e.target.value)}
                  className="w-full bg-white border border-[#E6E9F0] rounded-lg p-3 text-sm text-[#0E1726] focus:outline-none focus:border-[#6D28D9] h-[120px] transition-colors resize-none"
                ></textarea>
              </div>

              <div className="flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={runRedactorPlayground}
                  disabled={playgroundEvaluating}
                >
                  {playgroundEvaluating ? 'Evaluating...' : 'Inspect & Redact'}
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </GlassCard>

            {playgroundOutput && (
              <GlassCard hover={false} className="p-6 space-y-3 border-[#6D28D9]/20 bg-[#F1ECFE]/70">
                <span className="text-xs font-bold uppercase tracking-wider text-[#6D28D9]">Inspected Output</span>
                <p className="text-sm font-mono text-[#0E1726] p-3 bg-[#F5F7FA] rounded-lg border border-[#E6E9F0] whitespace-pre-wrap">
                  {playgroundOutput}
                </p>
              </GlassCard>
            )}
          </div>

          {/* Playground Metrics */}
          <GlassCard hover={false} className="p-6 h-fit space-y-6">
            <h4 className="text-sm font-bold text-[#0E1726] border-b border-[#E6E9F0] pb-3">Playground Inspection telemetry</h4>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center bg-[#F5F7FA] p-3 rounded-lg border border-[#E6E9F0]">
                <span className="text-xs text-[#475069] font-semibold">Redacted Fields</span>
                <span className="text-lg font-mono font-bold text-fuchsia-400">{redactedCount}</span>
              </div>
              <div className="flex justify-between items-center bg-[#F5F7FA] p-3 rounded-lg border border-[#E6E9F0]">
                <span className="text-xs text-[#475069] font-semibold">Detection Confidence</span>
                <span className="text-lg font-mono font-bold text-emerald-400">{playgroundConfidence}%</span>
              </div>
              <div className="bg-[#F5F7FA] p-3 rounded-lg border border-[#E6E9F0] space-y-1">
                <span className="text-[10px] text-[#6B7488] font-bold uppercase block">Triggered Guardrails</span>
                <span className="text-xs font-mono font-bold text-[#0E1726] block truncate">{playgroundTriggered}</span>
              </div>
            </div>

            <div className="p-3 bg-[#F5F7FA]/70 border border-[#E6E9F0] rounded-lg text-[11px] text-[#475069] leading-relaxed font-sans">
              Supported detection categories include SSN, email, credit card, Aadhaar card, PAN card, and phone records.
            </div>
          </GlassCard>
        </div>
      )}

      {/* Policy Modal */}
      <Modal isOpen={policyModalOpen} onClose={() => setPolicyModalOpen(false)} title={editingPolicy ? 'Edit Guardrail Policy' : 'Create Guardrail Policy'}>
        <form onSubmit={handlePolicySubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Policy Name</label>
            <input
              type="text"
              required
              placeholder="e.g. SOC2 Financial Guardrail"
              value={policyForm.name}
              onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Framework Type</label>
              <select
                value={policyForm.type}
                onChange={(e) => setPolicyForm({ ...policyForm, type: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
              >
                <option value="PII">PII</option>
                <option value="Secrets">Secrets</option>
                <option value="Prompt Injection">Prompt Injection</option>
                <option value="Financial Data">Financial Data</option>
                <option value="Medical Data">Medical Data</option>
                <option value="Legal Data">Legal Data</option>
                <option value="Customer Topic">Customer Topic</option>
                <option value="SOC2">SOC2</option>
                <option value="GDPR">GDPR</option>
                <option value="HIPAA">HIPAA</option>
                <option value="Custom">Custom</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Active</label>
              <select
                value={policyForm.enabled ? 'true' : 'false'}
                onChange={(e) => setPolicyForm({ ...policyForm, enabled: e.target.value === 'true' })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
              >
                <option value="true">Active</option>
                <option value="false">Suspended</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Lifecycle Status</label>
              <select
                value={policyForm.status}
                onChange={(e) => setPolicyForm({ ...policyForm, status: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Severity</label>
              <select
                value={policyForm.severity_level}
                onChange={(e) => setPolicyForm({ ...policyForm, severity_level: e.target.value })}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
              >
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Rule Config (JSON Rules String)</label>
            <textarea
              required
              placeholder='{"blocked_keywords": ["passcode"], "pii_redaction": true}'
              value={policyForm.rules}
              onChange={(e) => setPolicyForm({ ...policyForm, rules: e.target.value })}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] h-[100px] font-mono text-xs transition-colors resize-none"
            ></textarea>
          </div>

          <div className="space-y-2 p-3 bg-[#F5F7FA]/80 border border-[#E6E9F0] rounded-lg">
            <label className="block text-xs font-semibold text-[#475069]">Simulation Text</label>
            <textarea
              value={simulationText}
              onChange={(e) => setSimulationText(e.target.value)}
              className="w-full bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] h-[80px] text-xs transition-colors resize-none"
            />
            <div className="flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={runPolicySimulation}
                disabled={simulationRunning}
              >
                {simulationRunning ? 'Simulating...' : 'Simulate Before Publishing'}
              </Button>
              {simulationResult && (
                <span className="text-xs font-bold text-[#0E1726]">
                  {simulationResult.decision} - {simulationResult.risk_level}
                </span>
              )}
            </div>
            {simulationResult && (
              <div className="text-[11px] font-mono bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-2 text-[#475069] max-h-[90px] overflow-y-auto">
                {JSON.stringify({
                  categories: simulationResult.triggered_categories,
                  findings: simulationResult.findings?.length || 0
                })}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-[#E6E9F0]">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setPolicyModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
            >
              {editingPolicy ? 'Save Policy' : 'Create Policy'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Guardrails;
