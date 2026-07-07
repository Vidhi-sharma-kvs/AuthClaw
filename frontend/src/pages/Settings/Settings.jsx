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
import { 
  Button, 
  GlassCard, 
  StatusBadge, 
  DataTable 
} from '../../components/Common/DesignSystem';

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

  // DataTable Columns for RBAC Permissions
  const userColumns = [
    {
      key: 'username',
      header: 'System User ID',
      sortable: true,
      render: (u) => (
        <span className="font-semibold text-[#0E1726] font-sans flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-[#6D28D9]" />
          {u.username}
        </span>
      )
    },
    {
      key: 'role',
      header: 'Assigned Role',
      sortable: true,
      render: (u) => <StatusBadge status={u.role} />
    },
    {
      key: 'permissions',
      header: 'Mapped Permissions',
      render: (u) => <span className="text-xs text-[#475069] font-mono">{u.permissions}</span>
    },
    {
      key: 'status',
      header: 'Account Status',
      render: () => <span className="text-emerald-400 text-xs font-semibold">ACTIVE</span>
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (u) => (
        <div className="text-right">
          <button 
            onClick={() => {
              setUserForm({ username: u.username, role: u.role, permissions: u.permissions });
              setUserModalOpen(true);
            }} 
            className="text-[#6D28D9] hover:text-[#6D28D9] text-xs font-sans font-semibold transition-colors"
          >
            Edit Role
          </button>
        </div>
      )
    }
  ];

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
          Settings & Access Control
        </h1>
        <p className="text-[#475069] text-sm">
          Orchestrate multi-tenant data boundaries and assign granular role-based permissions (RBAC).
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E6E9F0] space-x-2">
        <button
          onClick={() => setActiveTab('tenants')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'tenants'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Layers className="w-4 h-4" />
          Tenant Isolation
        </button>
        <button
          onClick={() => setActiveTab('rbac')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'rbac'
              ? 'border-[#6D28D9] text-[#0E1726] bg-[#F5F7FA] rounded-t-lg'
              : 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-[#F5F7FA] rounded-t-lg'
          }`}
        >
          <Users className="w-4 h-4" />
          RBAC Permissions
        </button>
      </div>

      {/* Tenant Isolation Content */}
      {activeTab === 'tenants' && (
        <div className="space-y-4">
          <GlassCard hover={false} className="border-emerald-500/10 bg-emerald-500/5">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-sm font-bold text-[#0E1726]">Tenant Workspace Is Created During Registration</h2>
                <p className="text-xs text-[#475069] mt-1 leading-relaxed">
                  Tenant creation is handled by the verified onboarding flow. This page shows your active tenant isolation boundary and runtime usage.
                </p>
              </div>
            </div>
          </GlassCard>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {tenants.map((t) => (
              <GlassCard key={t.id} className="flex flex-col justify-between h-[210px] space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-base font-bold text-[#0E1726]">{t.name}</h3>
                    <span className="text-[10px] text-[#6B7488] font-mono mt-1 block">Tenant ID: tenant-{t.id}</span>
                  </div>
                  <StatusBadge status={t.status} />
                </div>

                <div className="space-y-1.5 text-xs text-[#475069]">
                  <div className="flex justify-between">
                    <span>Isolation Status:</span>
                    <strong className="text-emerald-400">Verified</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Requests Checked:</span>
                    <strong className="text-[#0E1726] font-mono">{t.usage_count}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Tokens Processed:</span>
                    <strong className="text-[#0E1726] font-mono">{t.tokens_used}</strong>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[#E6E9F0] pt-3 text-[10px] text-[#6B7488]">
                  <span>Managed by onboarding</span>
                  <CheckCircle className="w-4 h-4 text-emerald-400 animate-pulse" />
                </div>
              </GlassCard>
            ))}
          </div>
        </div>
      )}

      {/* RBAC Content */}
      {activeTab === 'rbac' && (
        <div className="space-y-4">
          <GlassCard hover={false} className="border-[#6D28D9]/10 bg-[#F1ECFE]/70">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-[#6D28D9] shrink-0 mt-0.5" />
              <div>
                <h2 className="text-sm font-bold text-[#0E1726]">Tenant Role Management</h2>
                <p className="text-xs text-[#475069] mt-1 leading-relaxed">
                  Public registration always creates the first verified administrator as a Super Admin. Use this page after onboarding to assign tenant users roles such as Security Admin, Compliance Officer, Developer, Auditor, or Viewer.
                </p>
              </div>
            </div>
          </GlassCard>

          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setUserForm({ username: '', role: 'Developer', permissions: 'read_write_gateway' });
                setUserModalOpen(true);
              }}
            >
              <Plus className="w-4 h-4" />
              Configure Role Mapping
            </Button>
          </div>

          <DataTable
            columns={userColumns}
            data={users}
            loading={loading}
          />
        </div>
      )}

      {/* User Role Modal */}
      <Modal isOpen={userModalOpen} onClose={() => setUserModalOpen(false)} title="Configure User Access Level">
        <form onSubmit={handleUserSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-[#475069] mb-1.5">Tenant User Work Email</label>
            <input
              type="email"
              required
              placeholder="e.g. user@company.com"
              value={userForm.username}
              onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
              className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors"
            />
            <p className="text-[10px] text-[#6B7488] mt-1.5 flex items-center gap-1.5 font-sans">
              <Mail className="w-3 h-3 text-[#6D28D9]" />
              The user must already exist in this tenant. Invite/onboard them first, then assign the role here.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">System Role</label>
              <select
                value={userForm.role}
                onChange={(e) => handleRoleChange(e.target.value)}
                className="w-full bg-white border border-[#E6E9F0] rounded-lg p-2.5 text-[#0E1726] focus:outline-none focus:border-[#6D28D9] transition-colors font-bold text-xs"
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
              <label className="block text-xs font-semibold text-[#475069] mb-1.5">Mapped Scope Permission</label>
              <input
                type="text"
                required
                readOnly
                placeholder="e.g. read_write_gateway"
                value={userForm.permissions}
                className="w-full bg-[#F5F7FA] border border-[#E6E9F0] rounded-lg p-2.5 text-[#475069] focus:outline-none cursor-not-allowed font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-[#E6E9F0]">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setUserModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
            >
              Assign Role Map
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Settings;
