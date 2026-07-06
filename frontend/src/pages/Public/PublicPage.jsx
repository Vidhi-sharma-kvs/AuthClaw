import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import './PublicPage.css';

const PublicPage = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMasked, setIsMasked] = useState(false);
  const [latencyIndex, setLatencyIndex] = useState(0);
  const latencies = ['+38ms', '+41ms', '+36ms', '+44ms', '+39ms'];

  // Redaction animation loop
  useEffect(() => {
    const interval = setInterval(() => {
      setIsMasked(true);
      
      // Unmask after 1.4 seconds
      const timeout = setTimeout(() => {
        setIsMasked(false);
        setLatencyIndex((prev) => (prev + 1) % latencies.length);
      }, 1400);

      return () => clearTimeout(timeout);
    }, 3200);

    return () => clearInterval(interval);
  }, []);

  // IntersectionObserver for scroll-reveal animations
  useEffect(() => {
    const reveals = document.querySelectorAll('.reveal');
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
  }, []);

  return (
    <div className="public-container">
      {/* Announcement Strip */}
      <div className="topstrip">
        <b>AuthClaw</b> is the live gateway for AI compliance
        <span className="dot">•</span> SOC 2 <span class="dot">·</span> HIPAA <span class="dot">·</span> GDPR <span class="dot">·</span> ISO 42001 ready
      </div>

      {/* Navigation Header */}
      <header className="nav">
        <div className="wrap nav-in">
          <a className="brand" href="#top">
            <span className="mark"></span>
            AuthClaw
            <span className="ai">.ai</span>
          </a>
          
          <nav className="links">
            <a href="#platform">Platform</a>
            <a href="#how">How it works</a>
            <a href="#modules">Product</a>
            <a href="#frameworks">Frameworks</a>
            <a href="#why">Why AuthClaw</a>
          </nav>

          <div className="nav-cta">
            <Link className="login" to="/login">Log in</Link>
            <a className="btn btn-primary" href="#demo">Book a demo</a>
            <button 
              className="burger" 
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Menu"
            >
              <span></span>
            </button>
          </div>
        </div>

        {/* Mobile Navigation Menu */}
        <div className={`mobilemenu ${menuOpen ? 'open' : ''}`}>
          <a href="#platform" onClick={() => setMenuOpen(false)}>Platform</a>
          <a href="#how" onClick={() => setMenuOpen(false)}>How it works</a>
          <a href="#modules" onClick={() => setMenuOpen(false)}>Product</a>
          <a href="#frameworks" onClick={() => setMenuOpen(false)}>Frameworks</a>
          <a href="#why" onClick={() => setMenuOpen(false)}>Why AuthClaw</a>
          <div className="mm-cta">
            <Link className="btn btn-ghost" to="/login" onClick={() => setMenuOpen(false)}>Log in</Link>
            <a className="btn btn-primary" href="#demo" onClick={() => setMenuOpen(false)}>Book a demo</a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main id="top">
        
        {/* HERO SECTION */}
        <section className="hero" id="platform">
          <div className="wrap hero-in">
            <div className="h-copy">
              <span className="eyebrow">The runtime layer for AI compliance</span>
              <h1>Stop sensitive data <span className="hl">before</span> it reaches the model.</h1>
              <p className="sub">
                AuthClaw sits in the live path between your applications and AI. It removes PII and PHI in real time, fixes compliance gaps with human approval, and keeps a tamper-proof record your auditors can trust.
              </p>
              <div className="cta-row">
                <a className="btn btn-primary" href="#demo">Book a demo</a>
                <a className="btn btn-ghost" href="#how">See how it works</a>
              </div>
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

            {/* Signature Live Redaction Gateway Card */}
            <div className="gw" aria-label="Live redaction gateway demonstration">
              <div className="lat">{latencies[latencyIndex]}</div>
              <div className="gw-bar">
                <i></i>
                <i></i>
                <i className="g"></i>
                <span className="gw-title">authclaw · in-line gateway</span>
              </div>
              <div className="gw-flow">
                <div className="node">
                  <div className="nlabel">
                    <span>Inbound prompt</span>
                    <span>app → authclaw</span>
                  </div>
                  <div className="code">
                    <span className="tok">summarize the chart for patient </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '••••••' : 'Priya Nair'}
                    </span>
                    <span className="tok">, dob </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '••••••' : '04/12/1986'}
                    </span>
                    <span className="tok">, mrn </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '••••••' : '8830-221'}
                    </span>
                  </div>
                </div>
                <div className="arrow">↓</div>
                <div className="node gwcore">
                  <div className="nlabel">
                    <span>AuthClaw</span>
                    <span>redact · enforce · log</span>
                  </div>
                  <div className="gw-chips">
                    <span className="chip v">Presidio + NER</span>
                    <span className="chip v">policy: PHI-block</span>
                    <span className="chip ok">audit ✓ chained</span>
                  </div>
                </div>
                <div className="arrow">↓</div>
                <div className="node">
                  <div className="nlabel">
                    <span>Forwarded to model</span>
                    <span>authclaw → provider</span>
                  </div>
                  <div className="code">
                    <span className="tok">summarize the chart for patient </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '[NAME]' : 'Priya Nair'}
                    </span>
                    <span className="tok">, dob </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '[DATE]' : '04/12/1986'}
                    </span>
                    <span className="tok">, mrn </span>
                    <span className={`pii ${isMasked ? 'masked' : ''}`}>
                      {isMasked ? '[ID]' : '8830-221'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CONTRAST GRID SECTION */}
        <section className="contrast band-tight">
          <div className="wrap">
            <div className="reveal">
              <span className="eyebrow" style={{ color: 'var(--violet-300)' }}>Posture tools prove yesterday</span>
              <h2>Most compliance tools tell you what happened. <span className="kv">AuthClaw acts on every request</span>, right now.</h2>
              <p className="lead">
                Dashboards and audits describe your posture after the fact. AuthClaw is the enforcement point: it inspects each call to a model, strips what should never leave, and blocks what breaks your rules, before anything reaches an external provider.
              </p>
            </div>
            <div className="stat-grid reveal">
              <div className="stat">
                <div className="n">&lt;50<span className="u">ms</span></div>
                <div className="l">added latency per request</div>
              </div>
              <div className="stat">
                <div className="n">99.99<span className="u">%</span></div>
                <div className="l">uptime target, multi-region</div>
              </div>
              <div className="stat">
                <div className="n">100<span className="u">%</span></div>
                <div className="l">of prompts and responses inspected</div>
              </div>
              <div className="stat">
                <div className="n">1<span class="u">-click</span></div>
                <div className="l">verifiable audit export</div>
              </div>
            </div>
          </div>
        </section>

        {/* PILLARS SECTION */}
        <section className="band">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">One gateway, three jobs</span>
              <h2>Everything AI touches, governed in one place.</h2>
              <p className="sub">
                AuthClaw runs as a single in-line service. It protects data on the way out, fixes the gaps it finds, and records proof of both.
              </p>
            </div>
            <div className="pillars">
              <div className="pcard reveal">
                <div className="top-accent"></div>
                <div className="pnum">01 / Gateway</div>
                <div className="picon">▤</div>
                <h3>The checkpoint</h3>
                <p>
                  Every prompt and response passes through AuthClaw first. Sensitive data is detected and masked, hashed, or replaced before it leaves your environment. Rules block anything that should never be sent.
                </p>
              </div>
              <div className="pcard reveal">
                <div className="top-accent"></div>
                <div className="pnum">02 / Agent</div>
                <div className="picon">◈</div>
                <h3>The remediation agent</h3>
                <p>
                  An AI agent scans your cloud, explains in plain language where you fall short of GDPR, HIPAA, and SOC 2, and prepares the fix. Nothing risky runs until a person approves it, with a security check.
                </p>
              </div>
              <div className="pcard reveal">
                <div className="top-accent"></div>
                <div className="pnum">03 / Audit</div>
                <div className="picon">⛭</div>
                <h3>The audit recorder</h3>
                <p>
                  Every request, decision, and approval is written to a tamper-proof, hash-chained log. Export verifiable evidence for auditors and customers, or publish a live trust page, in one click.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* LIFECYCLE STEPS SECTION */}
        <section className="band-tight" id="how" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)' }}>
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">The request lifecycle</span>
              <h2>Four steps, on every call.</h2>
            </div>
            <div className="steps">
              <div className="step reveal">
                <div className="sn">1</div>
                <h4>Intercept</h4>
                <p>Requests reach the gateway over HTTPS or gRPC, native provider format preserved.</p>
              </div>
              <div className="step reveal">
                <div className="sn">2</div>
                <h4>Redact and enforce</h4>
                <p>Presidio and NER strip sensitive data. Policy rules block traffic that breaks your standards.</p>
              </div>
              <div className="step reveal">
                <div className="sn">3</div>
                <h4>Forward</h4>
                <p>The clean payload goes to OpenAI, Anthropic, Azure, or Cohere with nothing sensitive attached.</p>
              </div>
              <div className="step reveal">
                <div className="sn">4</div>
                <h4>Record</h4>
                <p>A hash-chained audit entry is written for the request, the response, and every decision made.</p>
              </div>
            </div>
          </div>
        </section>

        {/* PRODUCT MODULES SECTION */}
        <section className="band" id="modules">
          <div className="wrap">
            <div className="sec-head center reveal">
              <span className="eyebrow">The platform</span>
              <h2>Four products. One in-line service.</h2>
            </div>

            {/* Module 1 */}
            <div className="module reveal">
              <div className="m-copy">
                <span className="eyebrow">In-line gateway</span>
                <h3>A safe path to every model.</h3>
                <p className="md">
                  Reverse-proxy the major providers without changing your API calls. AuthClaw redacts in real time and holds the line on policy, even on streaming responses, token by token.
                </p>
                <ul className="mlist">
                  <li><span className="tk">▸</span> Multi-model proxy for OpenAI, Anthropic, Azure OpenAI, and Cohere</li>
                  <li><span className="tk">▸</span> Masking, salted hashing, or synthetic replacement per field</li>
                  <li><span className="tk">▸</span> Policy-as-code with topic and pattern blocking</li>
                </ul>
              </div>
              <div className="m-visual">
                <div className="mv-head">
                  <span><span className="dotpill"></span>gateway · live traffic</span>
                  <span>redaction on</span>
                </div>
                <div className="rowline">
                  <span>prompt · support-bot</span>
                  <span className="pill appr">2 fields masked</span>
                </div>
                <div className="rowline">
                  <span>prompt · billing-agent</span>
                  <span className="pill block">blocked · card number</span>
                </div>
                <div className="rowline">
                  <span>response · claims-llm</span>
                  <span className="pill appr">clean</span>
                </div>
                <div className="rowline">
                  <span>prompt · intake-form</span>
                  <span className="pill appr">1 field hashed</span>
                </div>
              </div>
            </div>

            {/* Module 2 */}
            <div className="module rev reveal">
              <div className="m-copy">
                <span className="eyebrow">Agentic remediation</span>
                <h3>The agent proposes. A human decides.</h3>
                <p className="md">
                  The remediation agent finds gaps, drafts the exact change as a Terraform or CLI diff, and waits. Consequential actions sit in an approval state, expire if untouched, and only run after a person clears a security check.
                </p>
                <ul className="mlist">
                  <li><span className="tk">▸</span> Orchestrator with short-lived, scoped workers</li>
                  <li><span className="tk">▸</span> Human approval with MFA on every change</li>
                  <li><span className="tk">▸</span> Approvals expire automatically after 30 minutes</li>
                </ul>
              </div>
              <div className="m-visual">
                <div className="mv-head">
                  <span><span className="dotpill" style={{ background: 'var(--gold)' }}></span>remediation · pending</span>
                  <span>1 awaiting approval</span>
                </div>
                <div className="rowline">
                  <span>Restrict S3 bucket policy</span>
                  <span className="pill wait">awaiting approval</span>
                </div>
                <div className="rowline">
                  <span>Rotate exposed API key</span>
                  <span className="pill appr">approved · applied</span>
                </div>
                <div className="rowline">
                  <span>Enable audit logging</span>
                  <span className="pill appr">approved · applied</span>
                </div>
                <div className="rowline">
                  <span>Delete public snapshot</span>
                  <span className="pill wait">needs MFA</span>
                </div>
              </div>
            </div>

            {/* Module 3 */}
            <div className="module reveal">
              <div className="m-copy">
                <span className="eyebrow">Continuous audit &amp; trust center</span>
                <h3>Proof that cannot be quietly changed.</h3>
                <p className="md">
                  Every action lands in an append-only log, each entry chained to the last with a SHA-256 hash. Export a signed evidence bundle for an auditor, or publish a live trust page for buyers, without assembling anything by hand.
                </p>
                <ul className="mlist">
                  <li><span className="tk">▸</span> Tamper-evident, hash-chained records</li>
                  <li><span className="tk">▸</span> Cryptographically verifiable export</li>
                  <li><span className="tk">▸</span> Buyer-ready trust center, always current</li>
                </ul>
              </div>
              <div className="m-visual">
                <div className="mv-head">
                  <span><span className="dotpill"></span>audit trail · verified</span>
                  <span>chain intact</span>
                </div>
                <div className="rowline">
                  <span className="code" style={{ fontSize: '12.5px' }}>#4471 · redaction · gateway</span>
                  <span className="pill appr">✓ hash</span>
                </div>
                <div className="rowline">
                  <span className="code" style={{ fontSize: '12.5px' }}>#4472 · approval · user</span>
                  <span className="pill appr">✓ hash</span>
                </div>
                <div className="rowline">
                  <span className="code" style={{ fontSize: '12.5px' }}>#4473 · execute · agent</span>
                  <span className="pill appr">✓ hash</span>
                </div>
                <div className="rowline">
                  <span className="code" style={{ fontSize: '12.5px' }}>#4474 · export · SOC 2</span>
                  <span className="pill appr">✓ signed</span>
                </div>
              </div>
            </div>

            {/* Module 4 */}
            <div className="module rev reveal">
              <div className="m-copy">
                <span className="eyebrow">Framework scoring</span>
                <h3>Readiness you can read at a glance.</h3>
                <p className="md">
                  See live readiness for SOC 2, GDPR, and the HIPAA Security Rule, scored from real signals across your systems, not a survey filled in once a quarter.
                </p>
                <ul className="mlist">
                  <li><span className="tk">▸</span> Real-time scores per framework</li>
                  <li><span className="tk">▸</span> Control-by-control mapping and evidence links</li>
                  <li><span className="tk">▸</span> Upload any regulation or contract to add controls</li>
                </ul>
              </div>
              <div className="m-visual">
                <div className="mv-head">
                  <span><span className="dotpill"></span>readiness · this org</span>
                  <span>updated live</span>
                </div>
                <div className="scorecard">
                  <div className="srow">
                    <div className="top"><span>SOC 2 Type II</span><b>92%</b></div>
                    <div className="meter"><i style={{ width: '92%' }}></i></div>
                  </div>
                  <div className="srow">
                    <div className="top"><span>GDPR</span><b>88%</b></div>
                    <div className="meter"><i style={{ width: '88%' }}></i></div>
                  </div>
                  <div className="srow">
                    <div className="top"><span>HIPAA Security Rule</span><b>81%</b></div>
                    <div className="meter"><i style={{ width: '81%' }}></i></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FRAMEWORKS & MODELS RAIL */}
        <section className="rail band-tight" id="frameworks">
          <div className="wrap grid2">
            <div className="reveal">
              <h4>Speaks every major model</h4>
              <div className="taglist">
                <span className="tag"><span className="d">◆</span>OpenAI</span>
                <span className="tag"><span class="d">◆</span>Anthropic</span>
                <span className="tag"><span className="d">◆</span>Azure OpenAI</span>
                <span className="tag"><span className="d">◆</span>Cohere</span>
                <span className="tag"><span className="d">◆</span>AWS Bedrock</span>
              </div>
              <h4 style={{ marginTop: '26px' }}>Connects your environment</h4>
              <div className="taglist">
                <span className="tag"><span className="d">◇</span>AWS</span>
                <span className="tag"><span class="d">◇</span>GCP</span>
                <span className="tag"><span className="d">◇</span>Azure</span>
                <span className="tag"><span className="d">◇</span>GitHub</span>
              </div>
            </div>
            <div className="reveal">
              <h4>Maps every framework</h4>
              <div className="taglist">
                <span className="tag">SOC 2</span>
                <span className="tag">HIPAA</span>
                <span className="tag">GDPR</span>
                <span className="tag">ISO 27001</span>
                <span className="tag">ISO 42001</span>
                <span className="tag">NIST AI RMF</span>
                <span className="tag">EU AI Act</span>
                <span className="tag">PCI DSS</span>
              </div>
              <p style={{ color: 'var(--slate)', fontSize: '15px', marginTop: '18px' }}>
                Upload any additional regulation or contract, and AuthClaw turns it into controls it can score and enforce.
              </p>
            </div>
          </div>
        </section>

        {/* WHY / COMPARISON SECTION */}
        <section className="band" id="why">
          <div className="wrap">
            <div className="sec-head reveal">
              <span className="eyebrow">Why AuthClaw</span>
              <h2>Other tools describe risk. AuthClaw removes it in the path.</h2>
              <p className="sub">
                Posture platforms and model-testing tools each cover one slice. AuthClaw is the live layer where enforcement, remediation, and proof come together.
              </p>
            </div>
            <table className="cmp reveal">
              <thead>
                <tr>
                  <th></th>
                  <th>Traditional GRC &amp; AI testing tools</th>
                  <th className="us">AuthClaw</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Sensitive data</td>
                  <td className="them">Reviewed after the fact</td>
                  <td className="us">Removed in real time, before egress</td>
                </tr>
                <tr>
                  <td>Compliance gaps</td>
                  <td className="them">Flagged in a report</td>
                  <td className="us">Fixed with human approval</td>
                </tr>
                <tr>
                  <td>Audit evidence</td>
                  <td className="them">Assembled by hand</td>
                  <td className="us">Recorded automatically, tamper-proof</td>
                </tr>
                <tr>
                  <td>AI traffic</td>
                  <td className="them">Outside their view</td>
                  <td className="us">Inspected on every request</td>
                </tr>
                <tr>
                  <td>Human role</td>
                  <td className="them">Doing the work</td>
                  <td className="us">Approving the decisions</td>
                </tr>
              </tbody>
            </table>

            <div className="quotes">
              <div className="quote reveal">
                <div className="mark">”</div>
                <p>AuthClaw is the first tool that actually sits in the request path. We can show customers that nothing sensitive ever leaves our walls.</p>
                <div className="who"><b>Head of Security</b><br />Series C healthtech</div>
              </div>
              <div className="quote reveal">
                <div className="mark">”</div>
                <p>The approval workflow is what sold our board. The agent proposes the change, and a person is always the one who decides.</p>
                <div className="who"><b>VP Engineering</b><br />Financial services platform</div>
              </div>
            </div>
          </div>
        </section>

        {/* FINAL CTA SECTION */}
        <section className="finalcta" id="demo">
          <div className="wrap">
            <span className="eyebrow" style={{ color: 'var(--gold)' }}>Get started</span>
            <h2>Put AuthClaw in front of your models.</h2>
            <p>See a live redaction, an approved remediation, and a verifiable audit export, in one walkthrough.</p>
            <div className="cta-row">
              <a className="btn btn-gold" href="#">Book a demo</a>
              <a className="btn btn-light" href="#">Talk to the team</a>
            </div>
          </div>
        </section>

      </main>

      {/* FOOTER */}
      <footer className="ft">
        <div className="wrap">
          <div className="ft-grid">
            <div>
              <div className="brand">
                <span className="mark"></span>
                AuthClaw
                <span className="ai">.ai</span>
              </div>
              <p className="desc">
                The runtime layer for AI compliance. Redact in real time, remediate with human approval, and prove it with a tamper-proof trail.
              </p>
            </div>
            <div>
              <h5>Platform</h5>
              <ul>
                <li><a href="#">In-line gateway</a></li>
                <li><a href="#">Agentic remediation</a></li>
                <li><a href="#">Audit &amp; trust center</a></li>
                <li><a href="#">Framework scoring</a></li>
              </ul>
            </div>
            <div>
              <h5>Frameworks</h5>
              <ul>
                <li><a href="#">SOC 2</a></li>
                <li><a href="#">HIPAA</a></li>
                <li><a href="#">GDPR</a></li>
                <li><a href="#">ISO 42001</a></li>
                <li><a href="#">EU AI Act</a></li>
              </ul>
            </div>
            <div>
              <h5>Company</h5>
              <ul>
                <li><a href="#">About</a></li>
                <li><a href="#">Careers</a></li>
                <li><a href="#">Security</a></li>
                <li><a href="#">Contact</a></li>
              </ul>
            </div>
            <div>
              <h5>Resources</h5>
              <ul>
                <li><a href="#">Docs</a></li>
                <li><a href="#">Blog</a></li>
                <li><a href="#">Trust center</a></li>
                <li><a href="#">Book a demo</a></li>
              </ul>
            </div>
          </div>
          <div className="ft-base">
            <span>© 2026 AuthClaw. All rights reserved.</span>
            <span className="made">A product by <b>AgentsArchitects.ai</b></span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PublicPage;
