import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ExternalLink, FileCheck2, ShieldCheck } from 'lucide-react';
import './PublicPage.css';

const trustItems = [
  { label: 'Gateway status', value: 'Operational' },
  { label: 'Policy engine', value: 'Active' },
  { label: 'Audit chain', value: 'Hash verified' },
  { label: 'Data protection', value: 'Encrypted' }
];

const TrustCenter = () => {
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
            Audit CSV and PDF exports include SHA-256 signature headers so recipients
            can verify that evidence bundles have not been modified after download.
          </p>
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
