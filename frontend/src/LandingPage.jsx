import React, { useMemo, useState } from "react";

const DIRECTIONS = [
  { id: "northbound", label: "Northbound", value: "508", color: "teal" },
  { id: "southbound", label: "Southbound", value: "396", color: "lime" },
  { id: "eastbound", label: "Eastbound", value: "142", color: "amber" },
  { id: "westbound", label: "Westbound", value: "120", color: "orange" },
];

const WORKFLOW = [
  { number: "01", title: "Sources", text: "Connect a recording, RTSP feed, or live stream.", icon: "camera" },
  { number: "02", title: "Geometry", text: "Draw ROI, lanes, counting lines, and direction vectors.", icon: "geometry" },
  { number: "03", title: "Run", text: "Process frames with a resilient computer-vision pipeline.", icon: "play" },
  { number: "04", title: "Report", text: "Inspect counts, exports, logs, and live health signals.", icon: "chart" },
];

function LandingPage({ onLaunch }) {
  const [activeDirection, setActiveDirection] = useState("northbound");
  const selectedDirection = useMemo(
    () => DIRECTIONS.find((direction) => direction.id === activeDirection) || DIRECTIONS[0],
    [activeDirection],
  );

  const jumpTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="landing-shell">
      <div className="landing-grain" aria-hidden="true" />
      <header className="landing-nav">
        <a className="landing-brand" href="#top" aria-label="TrafficFlow home">
          <LogoMark />
          <span>TrafficFlow</span>
        </a>
        <nav className="landing-links" aria-label="Primary navigation">
          <a href="#product">Product</a>
          <a href="#workflow">Workflow</a>
          <a href="#monitor">Live monitor</a>
        </nav>
        <button className="landing-button landing-button-primary landing-nav-cta" type="button" onClick={onLaunch}>
          Launch console <Arrow />
        </button>
      </header>

      <main id="top">
        <section className="landing-hero landing-container" id="product">
          <div className="landing-hero-copy">
            <p className="landing-kicker"><span className="landing-kicker-dot" /> Real-time computer vision</p>
            <h1>See the road<br />in <span>motion.</span></h1>
            <p className="landing-hero-lede">Count every lane.<br />Understand every moment.</p>
            <p className="landing-hero-body">TrafficFlow turns any camera feed into reliable traffic intelligence. Built for developers, operators, and teams who need the signal behind the stream.</p>
            <div className="landing-hero-actions">
              <button className="landing-button landing-button-primary" type="button" onClick={onLaunch}>Launch console <Arrow /></button>
              <a className="landing-text-link" href="#monitor">Live monitor <Arrow /></a>
            </div>
            <CodeSnippet />
            <div className="landing-proof-row" aria-label="Platform highlights">
              <Proof icon="crosshair" title="High accuracy" text="> 97% vehicle detection" />
              <Proof icon="clock" title="Low latency" text="< 800ms end-to-end" />
              <Proof icon="shield" title="Privacy first" text="On-prem or VPC" />
            </div>
          </div>
          <MonitorPreview activeDirection={selectedDirection} onDirectionChange={setActiveDirection} />
        </section>

        <section className="landing-workflow landing-container" id="workflow">
          <div className="landing-section-intro">
            <p className="landing-kicker">Developer workflow</p>
            <h2>From camera to insight<br />in four steps.</h2>
            <p>A simple, repeatable pipeline to go live fast and scale with confidence.</p>
            <div className="landing-flow-text" aria-label="Workflow sequence">Sources <span>→</span> Geometry <span>→</span> Run <span>→</span> Report</div>
          </div>
          <div className="landing-workflow-grid">
            <div className="landing-flow-line" aria-hidden="true" />
            {WORKFLOW.map((item) => (
              <article className="landing-workflow-card" key={item.title}>
                <span className="landing-step-number">{item.number}</span>
                <div className="landing-feature-icon"><FeatureIcon name={item.icon} /></div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-features landing-container" id="monitor">
          <div className="landing-section-heading">
            <div>
              <p className="landing-kicker">Built for real-world traffic intelligence</p>
              <h2>Reliable signals,<br />wherever the road goes.</h2>
            </div>
            <p>One focused workspace for ingest, geometry, inference, monitoring, and diagnostics.</p>
          </div>
          <div className="landing-bento-grid">
            <article className="landing-bento-card landing-bento-accuracy">
              <div className="landing-bento-copy">
                <FeatureIcon name="brain" />
                <h3>Accurate by design</h3>
                <p>Advanced computer-vision models optimized for intersections, highways, and complex scenes.</p>
                <div className="landing-bento-stats"><span><strong>&gt;97%</strong>Detection accuracy</span><span><strong>&lt;2%</strong>False positive rate</span></div>
              </div>
              <RoadDiagram />
            </article>
            <FeatureCard icon="cloud" title="Deploy anywhere" text="Cloud, on-prem, or edge. Your data, your environment." tags={["AWS", "Azure", "GCP", "On-prem"]} />
            <FeatureCard icon="code" title="Developer first" text="Clean API, SDKs, webhooks, and docs that get you moving." link="View API docs" />
            <FeatureCard icon="shield" title="Privacy by default" text="No raw frame storage by default. Process locally and keep data in your control." tag="No PII retention" />
            <FeatureCard icon="bolt" title="Real-time at scale" text="Sub-second insights with high throughput and built-in reliability." tag="99.9% uptime" accent="lime" />
          </div>
        </section>

        <section className="landing-final-cta landing-container">
          <div>
            <h2>Ready to see the road<br />in <span>motion?</span></h2>
            <p>Launch the console and start analyzing traffic in minutes.</p>
          </div>
          <button className="landing-button landing-button-primary" type="button" onClick={onLaunch}>Launch console <Arrow /></button>
        </section>
      </main>

      <footer className="landing-footer landing-container">
        <div className="landing-footer-brand">
          <a className="landing-brand" href="#top" aria-label="TrafficFlow home"><LogoMark /><span>TrafficFlow</span></a>
          <p>Developer platform for vehicle counting and traffic intelligence.<br />See the road in motion.</p>
          <div className="landing-footer-status"><span className="landing-kicker-dot" /> Status <span className="landing-footer-separator" /> Docs <span className="landing-footer-separator" /> API</div>
        </div>
        <FooterColumn title="Product" links={["Overview", "Live monitor", "Features", "Integrations"]} />
        <FooterColumn title="Developer" links={["API docs", "SDKs", "Webhooks", "Changelog"]} />
        <FooterColumn title="Company" links={["About", "Security", "Privacy", "Contact"]} />
        <div className="landing-subscribe">
          <h3>Stay updated</h3>
          <form onSubmit={(event) => event.preventDefault()}>
            <label className="sr-only" htmlFor="landing-email">Email address</label>
            <input id="landing-email" type="email" placeholder="Email address" required />
            <button type="submit" aria-label="Subscribe"><Arrow /></button>
          </form>
          <p>Get product updates and new features.</p>
        </div>
        <div className="landing-footer-bottom"><span>© 2024 TrafficFlow. All rights reserved.</span><span>Terms&nbsp;&nbsp;&nbsp;&nbsp; Privacy</span></div>
      </footer>
    </div>
  );
}

function MonitorPreview({ activeDirection, onDirectionChange }) {
  return (
    <div className="monitor-shell" aria-label="Live traffic analytics preview">
      <div className="monitor-toolbar">
        <span className="monitor-live"><i /> Live monitor</span><span className="monitor-state"><i /> LIVE</span>
        <span className="monitor-camera">Camera: INT_01⌄</span><span className="monitor-tool monitor-settings" aria-hidden="true" /><span className="monitor-tool monitor-expand" aria-hidden="true" />
      </div>
      <div className="traffic-scene">
        <TrafficScene activeDirection={activeDirection} />
        <SceneLabel className="scene-label scene-label-north" value="174" direction="↑ N" />
        <SceneLabel className="scene-label scene-label-north-east" value="236" direction="↑ N" />
        <SceneLabel className="scene-label scene-label-east" value="98" direction="↑ N" />
        <SceneLabel className="scene-label scene-label-west" value="142" direction="← W" />
        <SceneLabel className="scene-label scene-label-right" value="120" direction="→ E" />
        <SceneLabel className="scene-label scene-label-south-left" value="189" direction="↓ S" />
        <SceneLabel className="scene-label scene-label-south" value="207" direction="↓ S" />
        <span className="traffic-caption">INT_01 / NORTHBOUND / LANE 2</span>
      </div>
      <div className="monitor-insights">
        <div className="monitor-chart panel-dark"><div className="monitor-panel-title">Vehicles (last 5 min)</div><strong>1,166 <small>↗ 18.6%</small></strong><MiniChart /></div>
        <div className="monitor-directions panel-dark"><div className="monitor-panel-title">By direction</div><div className="donut-chart"><span>1,166<small>TOTAL</small></span></div><div className="direction-list">{[...DIRECTIONS].map((direction) => <button className={direction.id === activeDirection.id ? "active" : ""} key={direction.id} type="button" onClick={() => onDirectionChange(direction.id)}><i className={`direction-dot ${direction.color}`} />{direction.label.replace("bound", "")} <b>{direction.value}</b></button>)}</div></div>
      </div>
      <div className="monitor-feed panel-dark"><div className="monitor-feed-head"><span>Activity feed</span><button type="button">View all events</button></div><FeedRow time="12:43:10" text="Count update" meta="INT_01 · Northbound · Lane 2" result="+1" type="Car" /><FeedRow time="12:42:59" text="Count update" meta="INT_01 · Eastbound · Lane 1" result="+1" type="Truck" /><FeedRow time="12:42:41" text="Occlusion detected" meta="INT_01 · Westbound · Lane 3" result="Medium" type="" warning /></div>
    </div>
  );
}

function TrafficScene({ activeDirection }) {
  return <svg className="traffic-scene-svg" viewBox="0 0 720 390" role="img" aria-label={`Traffic camera view, ${activeDirection.label} selected`}>
    <defs><linearGradient id="road" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#1c2527" /><stop offset="1" stopColor="#10191d" /></linearGradient><linearGradient id="city" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#243832" /><stop offset="1" stopColor="#172426" /></linearGradient><filter id="sceneGlow"><feGaussianBlur stdDeviation="2" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
    <rect width="720" height="390" fill="url(#city)" /><path d="M0 34h720M0 74h720M0 338h720M0 372h720" stroke="#365246" strokeWidth="5" opacity=".38" /><path d="M22 0l110 150M107 0l105 150M616 0L512 150M700 0L571 155M0 308l170-135M0 370l214-164M720 306L554 172M720 380L518 196" stroke="#55715c" strokeWidth="3" opacity=".3" /><path d="M290 -30l88 220M430 -30L340 190M290 420l88-230M430 420l-88-230M-40 193h800" stroke="#c1b989" strokeWidth="2" opacity=".2" /><path d="M0 205h720M360 0v390" stroke="#f3ecd0" strokeWidth="34" opacity=".22" /><path d="M0 205h720M360 0v390" stroke="#28383a" strokeWidth="30" /><path d="M0 205h720M360 0v390" stroke="#a3b4a1" strokeWidth="1" strokeDasharray="15 12" opacity=".7" /><path d="M360 0v390" stroke="#a3b4a1" strokeWidth="1" strokeDasharray="15 12" opacity=".7" /><path d="M78 179h560M78 232h560M333 20v350M389 20v350" stroke="#e7e6cb" strokeWidth="2" strokeDasharray="8 7" opacity=".65" /><path d="M84 182h552M84 229h552M337 19v352M385 19v352" stroke="#33e4d0" strokeWidth="1" opacity=".78" filter="url(#sceneGlow)" /><g fill="#55e6c1" opacity=".14"><path d="M64 170h590v68H64z" /><path d="M325 8h70v375h-70z" /></g><g stroke="#55e6c1" strokeWidth="2" fill="none" opacity=".85"><path d="M101 171h160v67H101z" /><path d="M459 171h160v67H459z" /><path d="M325 72h70v100h-70z" /><path d="M325 238h70v100h-70z" /></g><g fill="#c8ff63" stroke="#d7ff93" strokeWidth="1.2"><Car x="246" y="140" rotate="-2" /><Car x="445" y="251" rotate="4" /><Car x="318" y="125" rotate="90" /><Car x="407" y="269" rotate="90" /></g><g fill="#4d7680" stroke="#72e5d4" strokeWidth="1"><Car x="194" y="218" rotate="-90" /><Car x="523" y="196" rotate="90" /><Car x="365" y="70" rotate="0" /><Car x="365" y="330" rotate="180" /></g><g fill="none" stroke="#ffb86b" strokeWidth="2" opacity=".9"><rect x="229" y="128" width="36" height="26" rx="2" /><rect x="428" y="239" width="36" height="26" rx="2" /><rect x="304" y="107" width="27" height="39" rx="2" /><rect x="394" y="249" width="27" height="39" rx="2" /></g><path d="M357 185l-6-13h12zM405 207l13 6-13 6zM327 233l-6 13h12z" fill="#ffb86b" /><text x="20" y="365" fill="#b9d7cd" fontFamily="monospace" fontSize="10">CAMERA INT_01 · 12:43:10 · 30 FPS</text>
  </svg>;
}

function Car({ x, y, rotate = 0 }) { return <rect x={x} y={y} width="20" height="34" rx="5" transform={`rotate(${rotate} ${x + 10} ${y + 17})`} />; }
function SceneLabel({ className, value, direction }) { return <div className={className}><strong>{value}</strong><span>{direction}</span></div>; }
function MiniChart() { return <svg className="mini-chart" viewBox="0 0 320 66" preserveAspectRatio="none" aria-label="Vehicles trending upward"><path d="M0 54L18 42L32 47L50 29L67 39L82 25L101 42L120 31L138 34L156 18L173 27L194 11L212 18L228 8L246 13L260 5L279 9L294 1L320 -4V66H0Z" fill="rgba(85,230,193,.16)" /><path d="M0 54L18 42L32 47L50 29L67 39L82 25L101 42L120 31L138 34L156 18L173 27L194 11L212 18L228 8L246 13L260 5L279 9L294 1L320 -4" fill="none" stroke="#55e6c1" strokeWidth="2" /></svg>; }
function FeedRow({ time, text, meta, result, type, warning }) { return <div className="feed-row"><i className={warning ? "feed-dot warning" : "feed-dot"} /><time>{time}</time><span>{text}<small>{meta}</small></span><b className={warning ? "warning-text" : ""}>{result}</b><em>{type}</em></div>; }

function CodeSnippet() { return <div className="landing-code"><span>01</span><code><b>curl</b> https://api.trafficflow.dev/v1/counts \<br />  -H <i>"Authorization: Bearer live_xxx"</i> \<br />  -H <i>"Content-Type: application/json"</i> \<br />  -d <i>'{`{ "camera_id": "int_01", "interval": "60s" }`}'</i></code></div>; }
function Proof({ icon, title, text }) { return <div className="landing-proof"><FeatureIcon name={icon} /><span><strong>{title}</strong><small>{text}</small></span></div>; }
function FeatureCard({ icon, title, text, tags, link, tag, accent }) { return <article className={`landing-bento-card landing-feature-card ${accent ? `accent-${accent}` : ""}`}><FeatureIcon name={icon} /><h3>{title}</h3><p>{text}</p>{tags && <div className="feature-tags">{tags.map((item) => <span key={item}>{item}</span>)}</div>}{link && <a href="#product">{link} <Arrow /></a>}{tag && <span className="feature-tag">{tag}</span>}</article>; }
function RoadDiagram() { return <svg className="road-diagram" viewBox="0 0 400 190" aria-hidden="true"><path d="M-20 175C75 98 142 69 419 16M-20 196C70 120 144 91 419 39M-20 218C73 142 148 111 419 61" fill="none" stroke="#176e6c" strokeWidth="1" strokeDasharray="3 5" /><path d="M33 158c35-25 58-35 80-43l9 12-74 48zM181 95l25-12 12 17-28 14zM272 59l23-7 11 17-27 8z" fill="#c8ff63" stroke="#55e6c1" strokeWidth="1" /><path d="M51 155h30M202 92h24M286 54h23" stroke="#ffb86b" strokeWidth="2" /></svg>; }
function FeatureIcon({ name }) { const paths = { camera: <><rect x="3" y="6" width="12" height="11" rx="2" /><path d="M15 9l6-3v11l-6-3z" /></>, geometry: <><path d="M4 19L19 4M3 9l4-4M15 20l5-5" /><path d="M3 15h5M12 4v5M15 12h6" /></>, play: <><path d="M7 4l11 8-11 8z" /></>, chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2" /></>, brain: <><path d="M9 5a3 3 0 0 1 5-1 3 3 0 0 1 4 3 3 3 0 0 1 2 5 3 3 0 0 1-3 5 3 3 0 0 1-5 1 3 3 0 0 1-5-1 3 3 0 0 1-2-5 3 3 0 0 1 2-5 3 3 0 0 1 2-2z" /><path d="M12 5v14M8 9h4M12 14h4" /></>, cloud: <><path d="M7 18h11a4 4 0 0 0 .5-7.97A6 6 0 0 0 7.13 8.4 4.8 4.8 0 0 0 7 18z" /></>, code: <><path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" /></>, shield: <><path d="M12 3l7 3v5c0 4.6-3 8.2-7 10-4-1.8-7-5.4-7-10V6z" /><path d="M9 12l2 2 4-4" /></>, bolt: <path d="M13 2L4 14h6l-1 8 9-12h-6z" />, crosshair: <><circle cx="12" cy="12" r="6" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></>, clock: <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></> }; return <svg className="feature-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.chart}</svg>; }
function LogoMark() { return <svg className="landing-logo-mark" viewBox="0 0 34 28" fill="none" aria-hidden="true"><path d="M3 5h26M8 11h18M13 17h10M18 23h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><path d="M5 5l-1 18M12 5l-1 12M19 5l-1 6" stroke="currentColor" strokeWidth="1.4" /></svg>; }
function Arrow() { return <svg className="arrow-icon" viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="M3 9h11M9 4l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>; }
function FooterColumn({ title, links }) { return <div className="landing-footer-column"><h3>{title}</h3>{links.map((link) => <a href="#product" key={link}>{link}</a>)}</div>; }

export default LandingPage;
