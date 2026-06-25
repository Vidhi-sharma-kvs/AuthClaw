import React, { useEffect, useState } from 'react';
import apiClient from '../../services/api';
import { 
  Users, 
  Layers, 
  Plus, 
  CheckCircle, 
  Shield, 
  UserCheck,
  Mail
} from 'lucide-react';
import Modal from '../../components/Common/Modal';
import { useToast } from '../../components/Common/Toast';

const Settings = () => {
  const [activeTab, setActiveTab] = useState('tenants');
  const [tenants, setTenants] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  // User Role Form State
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [userForm, setUserForm] = useState({
    username: '',
    role: 'Developer',
    permissions: 'read_write_gateway'
  });

  const rolePermissions = {
    'Super Admin': 'all_access',
    'Security Admin': 'security_admin',
    'Compliance Officer': 'compliance_review',
    'Developer': 'read_write_gateway',
    'Auditor': 'audit_read',
    'Viewer': 'read_only'
  };

  const fetchData = async () => {
    try {
      const tenantRes = await apiClient.get('/tenants');
      const userRes = await apiClient.get('/access-control/users');
      
      setTenants(tenantRes.data);
      setUsers(userRes.data);
    } catch (error) {
      console.error('Error fetching settings:', error);
      addToast('Error loading workspace configuration.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // RBAC User handlers
  const handleUserSubmit = async (e) => {
    e.preventDefault();
    try {
      await apiClient.post('/access-control/users', userForm);
      addToast('User role mappings configured.', 'success');
      setUserModalOpen(false);
      setUserForm({ username: '', role: 'Developer', permissions: 'read_write_gateway' });
      fetchData();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to configure user role.';
      addToast(detail, 'error');
    }
  };

  const handleRoleChange = (role) => {
    setUserForm({ ...userForm, role, permissions: rolePermissions[role] || 'read_only' });
  };

  const getRoleBadge = (role) => {
    const maps = {
      'Super Admin': 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
      'Security Admin': 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
      'Compliance Officer': 'bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20',
      'Developer': 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      'Auditor': 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      'Viewer': 'bg-gray-800 text-gray-400'
    };
    return maps[role] || 'bg-gray-800 text-gray-400';
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
          Settings & Access Control
        </h1>
        <p className="text-gray-400 text-sm">
          Orchestrate multi-tenant data boundaries and assign granular role-based permissions (RBAC).
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/5 pb-px">
        <button
          onClick={() => setActiveTab('tenants')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'tenants'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Layers className="w-4 h-4" />
          Tenant Isolation
        </button>
        <button
          onClick={() => setActiveTab('rbac')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'rbac'
              ? 'border-violet-500 text-white bg-white/5 rounded-t-lg'
              : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5 rounded-t-lg'
          }`}
        >
          <Users className="w-4 h-4" />
          RBAC Permissions
        </button>
      </div>

      {/* Tenants list */}
      {activeTab === 'tenants' && (
        <div className="space-y-4 animate-fadeIn">
          {/* Action trigger */}
          <div className="glass-card p-5 border border-emerald-500/10 bg-emerald-500/5">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-sm font-bold text-white">Tenant Workspace Is Created During Registration</h2>
                <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                  Tenant creation is handled by the verified onboarding flow. This page shows your active tenant isolation boundary and runtime usage.
                </p>
              </div>
            </div>
          </div>

          {/* Tenants list */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {tenants.map((t) => (
              <div key={t.id} className="glass-card p-6 flex flex-col justify-between h-[210px] space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-base font-bold text-white">{t.name}</h3>
                    <span className="text-[10px] text-gray-500 font-mono mt-1 block">Tenant ID: tenant-{t.id}</span>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                    t.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-800 text-gray-400'
                  }`}>
                    {t.status}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-gray-400">
                  <div className="flex justify-between">
                    <span>Isolation Status:</span>
                    <strong className="text-emerald-400">Verified</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Requests Checked:</span>
                    <strong className="text-white font-mono">{t.usage_count}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Tokens Processed:</span>
                    <strong className="text-white font-mono">{t.tokens_used}</strong>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-white/5 pt-3 text-[10px] text-gray-500">
                  <span>Managed by onboarding</span>
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* RBAC List */}
      {activeTab === 'rbac' && (
        <div className="space-y-4 animate-fadeIn">
          <div className="glass-card p-5 border border-violet-500/10 bg-violet-500/5">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-violet-300 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-sm font-bold text-white">Tenant Role Management</h2>
                <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                  Public registration always creates the first verified administrator as a Super Admin. Use this page after onboarding to assign tenant users roles such as Security Admin, Compliance Officer, Developer, Auditor, or Viewer.
                </p>
              </div>
            </div>
          </div>

          {/* Action Trigger */}
          <div className="flex justify-end">
            <button
              onClick={() => {
                setUserForm({ username: '', role: 'Developer', permissions: 'read_write_gateway' });
                setUserModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg text-sm font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              <Plus className="w-4 h-4" />
              Configure Role Mapping
            </button>
          </div>

          {/* Table */}
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 text-xs text-gray-400 uppercase tracking-wider bg-white/2">
                  <th className="py-4 px-6">System User ID</th>
                  <th className="py-4 px-6">Assigned Role</th>
                  <th className="py-4 px-6">Mapped Permissions</th>
                  <th className="py-4 px-6">Account Status</th>
                  <th className="py-4 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-sm font-mono">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-white/2 transition-colors">
                    <td className="py-4 px-6 font-semibold text-white font-sans flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-violet-400" />
                      {u.username}
                    </td>
                    <td className="py-4 px-6">
                      <span className={`px-2.5 py-0.5 rounded text-[10px] font-sans font-bold uppercase ${getRoleBadge(u.role)}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-xs text-gray-300">{u.permissions}</td>
                    <td className="py-4 px-6 font-sans text-xs text-emerald-400">ACTIVE</td>
                    <td className="py-4 px-6 text-right">
                      <button 
                        onClick={() => {
                          setUserForm({ username: u.username, role: u.role, permissions: u.permissions });
                          setUserModalOpen(true);
                        }} 
                        className="text-violet-400 hover:text-violet-300 text-xs font-sans font-semibold transition-colors"
                      >
                        Edit Role
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* User Role Modal */}
      <Modal isOpen={userModalOpen} onClose={() => setUserModalOpen(false)} title="Configure User Access Level">
        <form onSubmit={handleUserSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5">Tenant User Work Email</label>
            <input
              type="email"
              required
              placeholder="e.g. user@company.com"
              value={userForm.username}
              onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
              className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
            />
            <p className="text-[10px] text-gray-500 mt-1.5 flex items-center gap-1.5">
              <Mail className="w-3 h-3" />
              The user must already exist in this tenant. Invite/onboard them first, then assign the role here.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">System Role</label>
              <select
                value={userForm.role}
                onChange={(e) => handleRoleChange(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-white focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="Super Admin">Super Admin</option>
                <option value="Security Admin">Security Admin</option>
                <option value="Compliance Officer">Compliance Officer</option>
                <option value="Developer">Developer</option>
                <option value="Auditor">Auditor</option>
                <option value="Viewer">Viewer</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">Mapped Scope Permission</label>
              <input
                type="text"
                required
                readOnly
                placeholder="e.g. read_write_gateway"
                value={userForm.permissions}
                className="w-full bg-slate-950 border border-white/10 rounded-lg p-2.5 text-gray-300 focus:outline-none cursor-not-allowed"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
            <button
              type="button"
              onClick={() => setUserModalOpen(false)}
              className="px-4 py-2 border border-white/10 text-gray-400 rounded-lg font-semibold hover:text-white hover:bg-white/5 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-lg font-semibold hover:opacity-90 shadow-lg shadow-violet-500/10 transition-all"
            >
              Assign Role Map
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Settings;
