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
    type: 'Custom',
    rules: '{"blocked_keywords": [], "pii_redaction": true}',
    enabled: true
  });

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
      enabled: policy.enabled
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

  // Redactor playground process
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
          Guardrails & Redaction Center
        </h1>
        <p className="text-gray-400 text-sm">
          Build compliance rules and inspect real-time response redactions.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/5 pb-px">
        <button
          onClick={() => setActiveTab('policies')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'policies'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Sliders className="w-4 h-4" />
          Policies & Guardrails
        </button>
        <button
          onClick={() => setActiveTab('redaction')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'redaction'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Lock className="w-4 h-4" />
          Redaction Playground
        </button>
      </div>

      {/* Policies View */}
      {activeTab === 'policies' && (
        <div className="space-y-4 animate-fadeIn">
          <div className="flex justify-end">
            <button
              onClick={() => {
                setEditingPolicy(null);
                setPolicyForm({
                  name: '',
                  type: 'Custom',
                  rules: '{"blocked_keywords": [], "pii_redaction": true}',
                  enabled: true
                });
                setPolicyModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              <Plus className="w-4 h-4" />
              Create Guardrail Policy
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {policies.length === 0 ? (
              <div className="lg:col-span-3 glass-card p-10 text-center text-gray-400">
                <p className="text-sm font-semibold text-white">No policies configured yet.</p>
                <p className="text-xs mt-1">Create tenant guardrails for PII, secrets, prompt injection, and compliance rules.</p>
              </div>
            ) : policies.map((p) => (
              <div key={p.id} className="glass-card p-6 flex flex-col justify-between h-[210px] space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs uppercase tracking-wider text-fuchsia-400 font-mono font-bold">{p.type} Framework</span>
                    <h3 className="text-base font-bold text-white mt-0.5">{p.name}</h3>
                  </div>
                  <button onClick={() => handleTogglePolicy(p)} className="focus:outline-none">
                    {p.enabled ? (
                      <ToggleRight className="w-6 h-6 text-emerald-500" />
                    ) : (
                      <ToggleLeft className="w-6 h-6 text-gray-600" />
                    )}
                  </button>
                </div>

                <div className="bg-slate-900/50 p-2.5 rounded border border-white/5 text-[11px] font-mono text-gray-400 overflow-y-auto max-h-[70px]">
                  {typeof p.rules === 'string' ? p.rules : JSON.stringify(p.rules)}
                </div>

                <div className="flex justify-between items-center text-xs text-gray-400 border-t border-white/5 pt-3">
                  <span className={`flex items-center gap-1 font-semibold ${p.enabled ? 'text-emerald-400' : 'text-gray-500'}`}>
                    <ShieldCheck className="w-3.5 h-3.5" /> {p.enabled ? 'Active Guardrail' : 'Suspended'}
                  </span>
                  <div className="flex gap-3">
                    <button onClick={() => handleEditPolicy(p)} className="text-gray-400 hover:text-white transition-colors" title="Edit">
                      <Sliders className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => handleDeletePolicy(p.id)} className="text-rose-400 hover:text-rose-600 transition-colors" title="Delete">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Redaction Playground */}
      {activeTab === 'redaction' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Playground inputs */}
          <div className="lg:col-span-2 space-y-4">
            <div className="glass-card p-6 space-y-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-400" />
                PII Redaction Playground Sandbox
              </h3>
              <div className="space-y-1">
                <label className="text-xs text-gray-400 font-semibold block">Input Text Completion</label>
                <textarea
                  value={playgroundInput}
                  onChange={(e) => setPlaygroundInput(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-violet-500 h-[120px] transition-colors"
                ></textarea>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={runRedactorPlayground}
                  disabled={playgroundEvaluating}
                  className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-90 transition-all disabled:opacity-50"
                >
                  {playgroundEvaluating ? 'Evaluating...' : 'Inspect & Redact'}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {playgroundOutput && (
              <div className="glass-card p-6 space-y-3 bg-violet-600/5 border-violet-500/20">
                <span className="text-xs font-bold uppercase tracking-wider text-violet-400">Inspected Output</span>
                <p className="text-sm font-mono text-white p-3 bg-slate-900 rounded-lg border border-white/5 whitespace-pre-wrap">
                  {playgroundOutput}
                </p>
              </div>
            )}
          </div>

          {/* Playground Metrics */}
          <div className="glass-card p-6 h-fit space-y-6">
            <h4 className="text-sm font-bold text-white border-b border-white/5 pb-3">Playground Inspection telemetry</h4>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center bg-slate-900/50 p-3 rounded-lg border border-white/5">
                <span className="text-xs text-gray-400 font-semibold">Redacted Fields</span>
                <span className="text-lg font-mono font-bold text-fuchsia-400">{redactedCount}</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900/50 p-3 rounded-lg border border-white/5">
                <span className="text-xs text-gray-400 font-semibold">Detection Confidence</span>
                <span className="text-lg font-mono font-bold text-emerald-400">{playgroundConfidence}%</span>
              </div>
              <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5 space-y-1">
                <span className="text-[10px] text-gray-500 font-bold uppercase block">Triggered Guardrails</span>
                <span className="text-xs font-mono font-bold text-white block truncate">{playgroundTriggered}</span>
              </div>
            </div>

            <div className="p-3 bg-slate-900/30 border border-white/5 rounded-lg text-[11px] text-gray-400">
              ⚡ Supported detection categories include SSN, email, credit card, Aadhaar card, PAN card, and phone records.
            </div>
          </div>
        </div>
      )}

      {/* Policy Modal */}
      <Modal isOpen={policyModalOpen} onClose={() => setPolicyModalOpen(false)} title={editingPolicy ? 'Edit Guardrail Policy' : 'Create Guardrail Policy'}>
        <form onSubmit={handlePolicySubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Policy Name</label>
            <input
              type="text"
              required
              placeholder="e.g. SOC2 Financial Guardrail"
              value={policyForm.name}
              onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Framework Type</label>
              <select
                value={policyForm.type}
                onChange={(e) => setPolicyForm({ ...policyForm, type: e.target.value })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="SOC2">SOC2</option>
                <option value="GDPR">GDPR</option>
                <option value="HIPAA">HIPAA</option>
                <option value="Custom">Custom</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Active</label>
              <select
                value={policyForm.enabled ? 'true' : 'false'}
                onChange={(e) => setPolicyForm({ ...policyForm, enabled: e.target.value === 'true' })}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="true">Active</option>
                <option value="false">Suspended</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Rule Config (JSON Rules String)</label>
            <textarea
              required
              placeholder='{"blocked_keywords": ["passcode"], "pii_redaction": true}'
              value={policyForm.rules}
              onChange={(e) => setPolicyForm({ ...policyForm, rules: e.target.value })}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 h-[100px] font-mono text-xs transition-colors"
            ></textarea>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
            <button
              type="button"
              onClick={() => setPolicyModalOpen(false)}
              className="px-4 py-2 border border-white/10 text-gray-400 rounded-lg font-semibold hover:text-white hover:bg-white/5 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              {editingPolicy ? 'Save Policy' : 'Create Policy'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Guardrails;
