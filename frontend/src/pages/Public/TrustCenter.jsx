import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ExternalLink, FileCheck2, ShieldCheck } from 'lucide-react';
import apiClient from '../../services/api';
import './PublicPage.css';

const TrustCenter = () => {
  const [trustState, setTrustState] = useState(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .get('/trust/public')
      .then((response) => {
        if (mounted) setTrustState(response.data);
      })
      .catch(() => {
        if (mounted) setTrustState(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const trustItems = useMemo(() => {
    const scores = trustState?.payload?.framework_scores;
    return [
      { label: 'Gateway status', value: 'Operational' },
      { label: 'SOC2 score', value: scores ? `${scores.soc2}%` : 'Published' },
      { label: 'GDPR score', value: scores ? `${scores.gdpr}%` : 'Published' },
      { label: 'Export signature', value: trustState?.verification?.valid ? 'Verified' : 'Pending' }
    ];
  }, [trustState]);

  return (
    <main className="public-container trust-center">
      <section className="trust-hero">
        <div className="wrap nav-in trust-nav">
          <Link to="/" className="brand">
            <span className="mark"></span>
            AuthClaw
            <span className="ai">.ai</span>
          </Link>
          <Link to="/login" className="btn btn-ghost">Console</Link>
        </div>

        <div className="wrap trust-hero-inner">
          <div className="eyebrow">
            <ShieldCheck size={16} />
            Trust Center
          </div>
          <h1>AuthClaw Security Status</h1>
          <p>
            Public security posture, governance controls, and export integrity for
            organizations evaluating AuthClaw as an AI gateway.
          </p>
          <div className="trust-status-grid">
            {trustItems.map((item) => (
              <div className="trust-status-card" key={item.label}>
                <CheckCircle2 size={20} />
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="trust-section">
        <div>
          <FileCheck2 size={28} />
          <h2>Signed Evidence Exports</h2>
          <p>
            Audit and evidence packages include an asymmetric signature manifest,
            hash-chain root, signing key ID, framework scope, and payload digest for
            independent verification.
          </p>
          {trustState?.manifest && (
            <div className="trust-manifest">
              <span>Signing key</span>
              <strong>{trustState.manifest.signing_key_id}</strong>
              <span>Hash-chain root</span>
              <strong>{trustState.manifest.hash_chain_root?.slice(0, 18)}...</strong>
            </div>
          )}
        </div>
        <a className="trust-link" href="/documentation">
          View security documentation
          <ExternalLink size={16} />
        </a>
      </section>
    </main>
  );
};

export default TrustCenter;
