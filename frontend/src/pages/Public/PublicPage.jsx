import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import './PublicPage.css';

const productCapabilities = [
  ['Multi-model gateway', 'Reverse-proxy OpenAI, Anthropic, Azure OpenAI, Cohere, and Bedrock with native payload compatibility.'],
  ['PII / PHI redaction', 'Presidio plus custom NER detect sensitive data and mask, salt-hash, or synthetically replace it per field.'],
  ['Streaming-safe filtering', 'Token-by-token inspection on streamed responses with no fragmentation and no broken JSON.'],
  ['Policy-as-code', 'YAML policies validated by Open Policy Agent block topics, patterns, and prompt-injection classes before egress.'],
  ['Agentic remediation', 'A LangGraph orchestrator scans your cloud, explains gaps, and drafts the exact fix for human approval.'],
  ['Tamper-proof audit', 'An append-only SHA-256 hash-chained log records every request, decision, and approval.'],
];

const securityControls = [
  ['Zero-trust by default', 'Every service authenticates every call. No implicit trust between components, networks, or tenants.'],
  ['Envelope encryption', 'Provider credentials and secrets are wrapped with AES-256-GCM through KMS or Vault.'],
  ['Strict tenant isolation', 'Tenant data is isolated through scoped auth, RBAC, and row-level database boundaries.'],
  ['Data minimization', 'Sensitive data is redacted before egress so the least necessary context reaches any model.'],
  ['Human-gated changes', 'Consequential actions require explicit, expiring, MFA-backed approval.'],
  ['Continuous red-teaming', 'Adversarial probes track prompt injection, data disclosure, and regression status.'],
];

const pricingPlans = [
  {
    name: 'Team',
    description: 'For a first regulated AI workload going to production.',
    price: '$1,990',
    suffix: '/mo',
    billed: 'billed annually',
    cta: 'Start free trial',
    featured: false,
    features: ['1 compliance framework', 'Up to 5M protected calls / month', 'Gateway, audit, and trust center'],
  },
  {
    name: 'Growth',
    description: 'For teams scaling AI across multiple products and frameworks.',
    price: '$4,500',
    suffix: '/mo',
    billed: 'billed annually',
    cta: 'Start free trial',
    featured: true,
    features: ['SOC 2, GDPR, and HIPAA', 'Up to 25M protected calls / month', 'Agentic remediation and HITL approvals'],
  },
  {
    name: 'Enterprise',
    description: 'For regulated scale with custom volume, residency, and SLAs.',
    price: 'Custom',
    suffix: '',
    billed: 'annual contract',
    cta: 'Contact sales',
    featured: false,
    features: ['Unlimited frameworks and volume', 'VPC or air-gapped deployment', 'SSO/SAML and dedicated support'],
  },
];

const pageTitles = {
  home: 'AuthClaw - The runtime layer for AI compliance',
  products: 'Products - AuthClaw',
  platform: 'Platform - AuthClaw',
  pricing: 'Pricing - AuthClaw',
  security: 'Security - AuthClaw',
  resources: 'Resources - AuthClaw',
  documentation: 'Documentation - AuthClaw',
  contact: 'Contact - AuthClaw',
  about: 'About - AuthClaw',
  company: 'Company - AuthClaw',
  demo: 'Book Demo - AuthClaw',
};

const navItems = [
  ['Product', '/products'],
  ['Pricing', '/pricing'],
  ['Company', '/company'],
  ['Security', '/security'],
];

const HeroVisual = ({ isMasked, latency }) => (
  <div className="gw" aria-label="Live redaction gateway demonstration">
    <div className="lat">{latency}</div>
    <div className="gw-bar">
      <i></i>
      <i></i>
      <i className="g"></i>
      <span className="gw-title">authclaw - in-line gateway</span>
    </div>
    <div className="gw-flow">
      <div className="node">
        <div className="nlabel"><span>Inbound prompt</span><span>app to authclaw</span></div>
        <div className="code">
          <span className="tok">summarize the chart for patient </span>
          <span className={`pii ${isMasked ? 'masked' : ''}`}>{isMasked ? '......' : 'Priya Nair'}</span>
          <span className="tok">, dob </span>
          <span className={`pii ${isMasked ? 'masked' : ''}`}>{isMasked ? '......' : '04/12/1986'}</span>
          <span className="tok">, mrn </span>
          <span className={`pii ${isMasked ? 'masked' : ''}`}>{isMasked ? '......' : '8830-221'}</span>
        </div>
      </div>
      <div className="arrow">v</div>
      <div className="node gwcore">
        <div className="nlabel"><span>AuthClaw</span><span>redact - enforce - log</span></div>
        <div className="gw-chips">
          <span className="chip v">Presidio + NER</span>
          <span className="chip v">policy: PHI-block</span>
          <span className="chip ok">audit chained</span>
        </div>
      </div>
      <div className="arrow">v</div>
      <div className="node">
        <div className="nlabel"><span>Forwarded to model</span><span>authclaw to provider</span></div>
        <div className="code">
          <span className="tok">summarize the chart for patient </span>
          <span className="pii masked">[NAME]</span>
          <span className="tok">, dob </span>
          <span className="pii masked">[DATE]</span>
          <span className="tok">, mrn </span>
          <span className="pii masked">[ID]</span>
        </div>
      </div>
    </div>
  </div>
);

const PageHead = ({ eyebrow, title, children }) => (
  <section className="pagehead public-inline-head">
    <div className="wrap">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      {children && <p className="sub">{children}</p>}
    </div>
  </section>
);

const FeatureOverview = () => (
  <section className="band">
    <div className="wrap">
      <div className="sec-head reveal">
        <span className="eyebrow">One gateway, three jobs</span>
        <h2>Everything AI touches, governed in one place.</h2>
        <p className="sub">AuthClaw protects data on the way out, fixes the gaps it finds, and records proof of both.</p>
      </div>
      <div className="pillars">
        <div className="pcard reveal">
          <div className="top-accent"></div>
          <div className="pnum">01 / Gateway</div>
          <div className="picon">G</div>
          <h3>The checkpoint</h3>
          <p>Prompts and responses pass through AuthClaw before they reach model providers.</p>
        </div>
        <div className="pcard reveal">
          <div className="top-accent"></div>
          <div className="pnum">02 / Agent</div>
          <div className="picon">A</div>
          <h3>The remediation agent</h3>
          <p>Find gaps, draft fixes, and hold consequential changes for human approval.</p>
        </div>
        <div className="pcard reveal">
          <div className="top-accent"></div>
          <div className="pnum">03 / Audit</div>
          <div className="picon">L</div>
          <h3>The audit recorder</h3>
          <p>Write every request, decision, and approval to a tamper-evident trail.</p>
        </div>
      </div>
    </div>
  </section>
);

const ShortProductIntro = () => (
  <section className="band-tight lifecycle-band">
    <div className="wrap grid2">
      <div className="reveal">
        <span className="eyebrow">Product overview</span>
        <h2 className="public-h2">A runtime layer that sits where risk happens.</h2>
        <p className="public-lead">Deploy AuthClaw as an in-line AI gateway, connect your providers, and enforce redaction, policy, approvals, and audit without rewriting your application.</p>
      </div>
      <div className="m-visual reveal">
        <div className="mv-head"><span><span className="dotpill"></span>request lifecycle</span><span>live path</span></div>
        <div className="rowline"><span>Intercept</span><span className="pill appr">gateway</span></div>
        <div className="rowline"><span>Redact and enforce</span><span className="pill appr">policy</span></div>
        <div className="rowline"><span>Forward clean payload</span><span className="pill appr">provider</span></div>
        <div className="rowline"><span>Record evidence</span><span className="pill appr">audit</span></div>
      </div>
    </div>
  </section>
);

const ProductModules = () => (
  <section className="band">
    <div className="wrap">
      <div className="sec-head center reveal">
        <span className="eyebrow">The platform</span>
        <h2>Four products. One in-line service.</h2>
      </div>
      <div className="fgrid">
        {productCapabilities.map(([title, body]) => (
          <div className="fcard reveal" key={title}>
            <div className="ico">*</div>
            <h4>{title}</h4>
            <p>{body}</p>
          </div>
        ))}
      </div>
      <div className="callout reveal">
        <span className="eyebrow">Reference stack</span>
        <table className="spec">
          <tbody>
            <tr><td>Gateway proxy</td><td>Go data plane for low-latency request handling</td></tr>
            <tr><td>Control-plane APIs</td><td>Python FastAPI</td></tr>
            <tr><td>Agent framework</td><td>LangGraph orchestration with scoped workers</td></tr>
            <tr><td>Sensitive-data detection</td><td>Microsoft Presidio plus custom NER</td></tr>
            <tr><td>Policy engine</td><td>Open Policy Agent plus YAML policy-as-code</td></tr>
            <tr><td>Storage</td><td>PostgreSQL for tenant state, ClickHouse/Kafka-ready audit pipeline</td></tr>
          </tbody>
        </table>
      </div>
      <ProductModule
        eyebrow="In-line gateway"
        title="A safe path to every model."
        body="Reverse-proxy the major providers without changing your API calls. AuthClaw redacts in real time and enforces policy even on streaming responses."
        rows={[
          ['prompt - support-bot', '2 fields masked', 'appr'],
          ['prompt - billing-agent', 'blocked - card number', 'block'],
          ['response - claims-llm', 'clean', 'appr'],
          ['prompt - intake-form', '1 field hashed', 'appr'],
        ]}
      />
      <ProductModule
        reverse
        eyebrow="Agentic remediation"
        title="The agent proposes. A human decides."
        body="The remediation agent finds gaps, drafts the exact change as a Terraform or CLI diff, and waits. Consequential actions only run after approval."
        rows={[
          ['Restrict S3 bucket policy', 'awaiting approval', 'wait'],
          ['Rotate exposed API key', 'approved - applied', 'appr'],
          ['Enable audit logging', 'approved - applied', 'appr'],
          ['Delete public snapshot', 'needs MFA', 'wait'],
        ]}
      />
      <ProductModule
        eyebrow="Continuous audit and trust center"
        title="Proof that cannot be quietly changed."
        body="Every action lands in an append-only log, each entry chained to the last with a SHA-256 hash. Export signed evidence or publish a live trust page."
        rows={[
          ['#4471 - redaction - gateway', 'hash', 'appr'],
          ['#4472 - approval - user', 'hash', 'appr'],
          ['#4473 - execute - agent', 'hash', 'appr'],
          ['#4474 - export - SOC 2', 'signed', 'appr'],
        ]}
      />
    </div>
  </section>
);

const ProductModule = ({ eyebrow, title, body, rows, reverse = false }) => (
  <div className={`module ${reverse ? 'rev' : ''} reveal`}>
    <div className="m-copy">
      <span className="eyebrow">{eyebrow}</span>
      <h3>{title}</h3>
      <p className="md">{body}</p>
      <ul className="mlist">
        <li><span className="tk">&gt;</span> Multi-model routing with existing provider payload compatibility</li>
        <li><span className="tk">&gt;</span> Human-in-the-loop governance for consequential actions</li>
        <li><span className="tk">&gt;</span> Cryptographic evidence generated as work happens</li>
      </ul>
    </div>
    <div className="m-visual">
      <div className="mv-head"><span><span className="dotpill"></span>{eyebrow.toLowerCase()}</span><span>active</span></div>
      {rows.map(([label, status, type]) => (
        <div className="rowline" key={`${label}-${status}`}>
          <span className={label.startsWith('#') ? 'code module-code' : ''}>{label}</span>
          <span className={`pill ${type}`}>{status}</span>
        </div>
      ))}
    </div>
  </div>
);

const PricingCards = () => (
  <section className="band">
    <div className="wrap">
      <div className="plans">
        {pricingPlans.map((plan) => (
          <div className={`plan ${plan.featured ? 'featured' : ''} reveal`} key={plan.name}>
            {plan.featured && <div className="ptag">Most popular</div>}
            <div className="pname">{plan.name}</div>
            <p className="pdesc">{plan.description}</p>
            <div className="price">
              <span className={plan.price === 'Custom' ? 'custom' : 'amt'}>{plan.price}</span>
              {plan.suffix && <span className="per">{plan.suffix}</span>}
            </div>
            <div className="billed">{plan.billed}</div>
            <Link className={`btn ${plan.featured ? 'btn-primary' : 'btn-ghost'} btn-block p-cta`} to="/company">{plan.cta}</Link>
            <div className="pfeat-label">{plan.featured ? 'Everything in Team, plus' : 'Includes'}</div>
            <ul className="feat">
              {plan.features.map((feature) => <li key={feature}><span className="ck">OK</span> {feature}</li>)}
            </ul>
          </div>
        ))}
      </div>
      <p className="pricenote">All plans include zero markup on model tokens. 14-day free trial, no card required.</p>
    </div>
  </section>
);

const SecurityContent = () => (
  <section className="band-tight">
    <div className="wrap">
      <div className="badges">
        {['SOC 2 Type II', 'HIPAA', 'GDPR', 'ISO 42001'].map((item) => (
          <div className="cbadge reveal" key={item}>
            <div className="ring"><span>{item.split(' ')[0]}</span></div>
            <h5>{item}</h5>
            <p>Continuously monitored</p>
          </div>
        ))}
      </div>
      <div className="fgrid security-grid">
        {securityControls.map(([title, body]) => (
          <div className="fcard reveal" key={title}>
            <div className="ico">#</div>
            <h4>{title}</h4>
            <p>{body}</p>
          </div>
        ))}
      </div>
      <table className="dtable reveal">
        <thead><tr><th>Data type</th><th>How AuthClaw handles it</th><th>At rest</th></tr></thead>
        <tbody>
          <tr><td>PII / PHI in prompts</td><td>Detected and masked, salt-hashed, or synthetically replaced before egress</td><td className="code">never stored raw</td></tr>
          <tr><td>Model prompts and responses</td><td>Inspected in memory; only redacted metadata is retained for audit</td><td className="code">redacted only</td></tr>
          <tr><td>Provider API keys</td><td>Envelope-encrypted with per-tenant keys</td><td className="code">AES-256-GCM</td></tr>
          <tr><td>Audit records</td><td>Append-only, hash-chained, export-verifiable records</td><td className="code">immutable</td></tr>
        </tbody>
      </table>
    </div>
  </section>
);

const PlatformContent = () => (
  <>
    <section className="contrast band-tight">
      <div className="wrap">
        <div className="reveal">
          <span className="eyebrow" style={{ color: 'var(--violet-300)' }}>Posture tools prove yesterday</span>
          <h2>Most compliance tools tell you what happened. <span className="kv">AuthClaw acts on every request</span>, right now.</h2>
          <p className="lead">AuthClaw is the enforcement point: it inspects each model call, strips what should never leave, and blocks what breaks your rules.</p>
        </div>
        <div className="stat-grid reveal">
          <div className="stat"><div className="n">&lt;50<span className="u">ms</span></div><div className="l">added latency per request</div></div>
          <div className="stat"><div className="n">99.99<span className="u">%</span></div><div className="l">uptime target, multi-region</div></div>
          <div className="stat"><div className="n">100<span className="u">%</span></div><div className="l">of prompts and responses inspected</div></div>
          <div className="stat"><div className="n">1<span className="u">-click</span></div><div className="l">verifiable audit export</div></div>
        </div>
      </div>
    </section>
    <section className="band-tight lifecycle-band">
      <div className="wrap">
        <div className="sec-head reveal">
          <span className="eyebrow">The request lifecycle</span>
          <h2>Four steps, on every call.</h2>
        </div>
        <div className="steps">
          <div className="step reveal"><div className="sn">1</div><h4>Intercept</h4><p>Requests reach the gateway with provider format preserved.</p></div>
          <div className="step reveal"><div className="sn">2</div><h4>Redact and enforce</h4><p>Detection and policy run before egress.</p></div>
          <div className="step reveal"><div className="sn">3</div><h4>Forward</h4><p>The clean payload goes to the selected provider.</p></div>
          <div className="step reveal"><div className="sn">4</div><h4>Record</h4><p>Every decision is written to audit evidence.</p></div>
        </div>
      </div>
    </section>
    <section className="rail band-tight">
      <div className="wrap grid2">
        <div className="reveal">
          <h4>Speaks every major model</h4>
          <div className="taglist">
            {['OpenAI', 'Anthropic', 'Azure OpenAI', 'Cohere', 'AWS Bedrock'].map((item) => <span className="tag" key={item}><span className="d">+</span>{item}</span>)}
          </div>
          <h4 className="rail-subhead">Connects your environment</h4>
          <div className="taglist">
            {['AWS', 'GCP', 'Azure', 'GitHub'].map((item) => <span className="tag" key={item}><span className="d">-</span>{item}</span>)}
          </div>
        </div>
        <div className="reveal">
          <h4>Maps every framework</h4>
          <div className="taglist">
            {['SOC 2', 'HIPAA', 'GDPR', 'ISO 27001', 'ISO 42001', 'NIST AI RMF', 'EU AI Act', 'PCI DSS'].map((item) => <span className="tag" key={item}>{item}</span>)}
          </div>
          <p className="rail-note">Upload any regulation or contract, and AuthClaw turns it into controls it can score and enforce.</p>
        </div>
      </div>
    </section>
  </>
);

const ResourcesContent = ({ documentation = false }) => (
  <section className="band">
    <div className="wrap">
      <div className="fgrid">
        {[
          ['Implementation guide', 'Deploy the gateway, connect providers, and validate your first protected route.'],
          ['Security architecture', 'Understand tenant isolation, encryption, audit exports, and approval boundaries.'],
          ['Framework mapping', 'Map SOC 2, HIPAA, GDPR, ISO 42001, and custom control sets.'],
          ['API references', 'Use AuthClaw endpoints, API keys, and gateway-compatible payload formats.'],
          ['Buyer trust kit', 'Share security posture, signed evidence, and runtime assurance.'],
          ['Operational runbooks', 'Monitor traffic, triage policy decisions, and review audit trails.'],
        ].map(([title, body]) => (
          <div className="fcard reveal" key={title}>
            <div className="ico">{documentation ? 'D' : 'R'}</div>
            <h4>{title}</h4>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const AboutContent = () => (
  <section className="band">
    <div className="wrap grid2">
      <div className="reveal">
        <span className="eyebrow">Company</span>
        <h2 className="public-h2">Built for teams shipping AI in regulated environments.</h2>
        <p className="public-lead">AuthClaw focuses on the runtime layer where AI compliance decisions actually happen: the prompt, the response, the approval, and the audit record.</p>
      </div>
      <div className="m-visual reveal">
        <div className="mv-head"><span><span className="dotpill"></span>operating principles</span><span>active</span></div>
        <div className="rowline"><span>Least privilege</span><span className="pill appr">default</span></div>
        <div className="rowline"><span>Human approval</span><span className="pill appr">required</span></div>
        <div className="rowline"><span>Auditability</span><span className="pill appr">built in</span></div>
        <div className="rowline"><span>Provider neutrality</span><span className="pill appr">native</span></div>
      </div>
    </div>
  </section>
);

const ContactContent = ({ demo = false }) => (
  <section className="band">
    <div className="wrap grid2">
      <div className="reveal">
        <span className="eyebrow">{demo ? 'Book demo' : 'Contact'}</span>
        <h2 className="public-h2">{demo ? 'See AuthClaw in your AI path.' : 'Talk to the AuthClaw team.'}</h2>
        <p className="public-lead">Review live redaction, HITL approvals, signed audit exports, and how AuthClaw fits your current providers and compliance controls.</p>
      </div>
      <div className="callout reveal">
        <span className="eyebrow">Next step</span>
        <p className="public-lead">Use the console login for an existing workspace, or contact the team to schedule a guided implementation walkthrough.</p>
        <div className="cta-row public-cta-row">
          <Link className="btn btn-primary" to="/login">Log in</Link>
          <a className="btn btn-ghost" href="mailto:hello@authclaw.ai">hello@authclaw.ai</a>
        </div>
      </div>
    </div>
  </section>
);

const FinalCta = () => (
  <section className="finalcta">
    <div className="wrap">
      <span className="eyebrow" style={{ color: 'var(--gold)' }}>Get started</span>
      <h2>Put AuthClaw in front of your models.</h2>
      <p>See a live redaction, an approved remediation, and a verifiable audit export in one walkthrough.</p>
      <div className="cta-row">
        <Link className="btn btn-gold" to="/products">Explore product</Link>
        <Link className="btn btn-light" to="/security">Review security</Link>
      </div>
    </div>
  </section>
);

const PublicFooter = () => (
  <footer className="ft">
    <div className="wrap">
      <div className="ft-grid">
        <div>
          <div className="brand"><span className="mark"></span>AuthClaw<span className="ai">.ai</span></div>
          <p className="desc">The runtime layer for AI compliance. Redact in real time, remediate with human approval, and prove it with a tamper-proof trail.</p>
        </div>
        <div><h5>Pages</h5><ul><li><Link to="/products">Product</Link></li><li><Link to="/pricing">Pricing</Link></li><li><Link to="/company">Company</Link></li><li><Link to="/security">Security</Link></li></ul></div>
        <div><h5>Console</h5><ul><li><Link to="/login">Login</Link></li></ul></div>
      </div>
      <div className="ft-base">
        <span>2026 AuthClaw. All rights reserved.</span>
        <span className="made">A product by <b>AgentsArchitects.ai</b></span>
      </div>
    </div>
  </footer>
);

const PublicPage = ({ page = 'home' }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMasked, setIsMasked] = useState(false);
  const [latencyIndex, setLatencyIndex] = useState(0);
  const latencies = useMemo(() => ['+38ms', '+41ms', '+36ms', '+44ms', '+39ms'], []);

  useEffect(() => {
    document.title = pageTitles[page] || pageTitles.home;
  }, [page]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setIsMasked(true);
      window.setTimeout(() => {
        setIsMasked(false);
        setLatencyIndex((prev) => (prev + 1) % latencies.length);
      }, 1400);
    }, 3200);
    return () => window.clearInterval(interval);
  }, [latencies.length]);

  useEffect(() => {
    const reveals = document.querySelectorAll('.public-container .reveal');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14 }
    );
    reveals.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [page]);

  const closeMenu = () => setMenuOpen(false);

  const renderPage = () => {
    switch (page) {
      case 'products':
      case 'solutions':
        return (
          <>
            <PageHead eyebrow={page === 'solutions' ? 'Solutions' : 'Products'} title="One service in the path. Enforcement, remediation, and proof.">
              AuthClaw is a low-latency service between your applications and every model you call.
            </PageHead>
            <ProductModules />
            <FinalCta />
          </>
        );
      case 'platform':
      case 'frameworks':
        return (
          <>
            <PageHead eyebrow={page === 'frameworks' ? 'Frameworks' : 'Platform'} title="The runtime platform for governed AI traffic.">
              Inspect, redact, route, approve, and audit every model call from one in-line service.
            </PageHead>
            <PlatformContent />
            <FinalCta />
          </>
        );
      case 'pricing':
        return (
          <>
            <PageHead eyebrow="Pricing" title="Priced on the value you protect, not the tokens you spend.">
              Bring your own provider keys and keep your model spend separate.
            </PageHead>
            <PricingCards />
            <FinalCta />
          </>
        );
      case 'security':
      case 'trust-center':
        return (
          <>
            <PageHead eyebrow="Trust Center" title="Security is not a feature here. It is the product.">
              AuthClaw is engineered as a zero-trust system: least privilege, encrypted secrets, tenant isolation, and verifiable evidence.
            </PageHead>
            <SecurityContent />
            <FinalCta />
          </>
        );
      case 'resources':
      case 'blog':
        return (
          <>
            <PageHead eyebrow={page === 'blog' ? 'Blog' : 'Resources'} title="Guides for shipping governed AI.">
              Practical resources for implementation, security review, audit readiness, and runtime operations.
            </PageHead>
            <ResourcesContent />
            <FinalCta />
          </>
        );
      case 'documentation':
        return (
          <>
            <PageHead eyebrow="Documentation" title="Technical documentation for AuthClaw teams.">
              Implementation notes for routing, providers, policies, approvals, audit exports, and observability.
            </PageHead>
            <ResourcesContent documentation />
            <FinalCta />
          </>
        );
      case 'contact':
        return (
          <>
            <PageHead eyebrow="Contact" title="Talk to AuthClaw.">
              Bring your provider stack, compliance scope, and rollout goal. We will map the safest path.
            </PageHead>
            <ContactContent />
          </>
        );
      case 'about':
      case 'company':
        return (
          <>
            <PageHead eyebrow="About" title="Built for regulated AI teams.">
              AuthClaw helps engineering, security, and compliance teams meet at the runtime layer.
            </PageHead>
            <AboutContent />
            <FinalCta />
          </>
        );
      case 'demo':
        return (
          <>
            <PageHead eyebrow="Book demo" title="See AuthClaw in front of your models.">
              Walk through live redaction, HITL remediation, and verifiable audit evidence.
            </PageHead>
            <ContactContent demo />
          </>
        );
      case 'home':
      default:
        return (
          <>
            <section className="hero">
              <div className="wrap hero-in">
                <div className="h-copy">
                  <span className="eyebrow">The runtime layer for AI compliance</span>
                  <h1>Stop sensitive data <span className="hl">before</span> it reaches the model.</h1>
                  <p className="sub">
                    AuthClaw sits in the live path between your applications and AI. It removes PII and PHI in real time,
                    fixes compliance gaps with human approval, and keeps a tamper-proof record your auditors can trust.
                  </p>
                  <div className="cta-row">
                    <Link className="btn btn-primary" to="/products">Explore product</Link>
                    <Link className="btn btn-ghost" to="/pricing">View pricing</Link>
                  </div>
                  <p className="microcopy">No card required. 14-day trial. Deploys in your VPC.</p>
                  <div className="trust">
                    <div className="t-label">Built for teams shipping AI in regulated environments</div>
                    <div className="badge-row">
                      <span className="fw">SOC 2</span>
                      <span className="fw">HIPAA</span>
                      <span className="fw">GDPR</span>
                      <span className="fw">ISO 42001</span>
                      <span className="fw">EU AI Act</span>
                    </div>
                  </div>
                </div>
                <HeroVisual isMasked={isMasked} latency={latencies[latencyIndex]} />
              </div>
            </section>
            <FeatureOverview />
            <ShortProductIntro />
            <FinalCta />
          </>
        );
    }
  };

  return (
    <div className="public-container">
      <div className="topstrip">
        <b>New</b> AuthClaw is now SOC 2 Type II certified
        <span className="dot">.</span>
        <Link to="/security">Read the security overview</Link>
      </div>

      <header className="nav">
        <div className="wrap nav-in">
          <Link className="brand" to="/">
            <span className="mark"></span>
            AuthClaw
            <span className="ai">.ai</span>
          </Link>

          <nav className="links">
            {navItems.map(([label, to]) => (
              <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
            ))}
          </nav>

          <div className="nav-cta">
            <Link className="login" to="/login">Log in</Link>
            <button className="burger" onClick={() => setMenuOpen((open) => !open)} aria-label="Menu">
              <span></span>
            </button>
          </div>
        </div>

        <div className={`mobilemenu ${menuOpen ? 'open' : ''}`}>
          {navItems.map(([label, to]) => (
            <Link key={to} to={to} onClick={closeMenu}>{label}</Link>
          ))}
          <div className="mm-cta">
            <Link className="btn btn-ghost" to="/login" onClick={closeMenu}>Log in</Link>
          </div>
        </div>
      </header>

      <main>{renderPage()}</main>
      <PublicFooter />
    </div>
  );
};

export default PublicPage;
