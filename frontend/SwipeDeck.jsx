import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Globe, Plane, ShieldCheck, ShieldAlert, MapPin, Wifi,
  X, Heart, RotateCcw, Layers, ArrowLeft, Check,
} from "lucide-react";

/* ------------------------------------------------------------------ *
 * JobSwipe — swipe deck
 * Eligibility-first job cards. The "checkpoint" strip (visa + clearance)
 * is the signature: it answers "can I even apply?" before anything else.
 * Mock data is on-schema, so wiring this to /jobs/next is a fetch swap.
 * ------------------------------------------------------------------ */

const RESUME_SKILLS = ["Python", "React", "TypeScript", "SQL", "Git", "AWS", "Node.js"];

const JOBS = [
  { _id: "1", title: "Software Engineer, New Grad", employer: "Stripe", source: "greenhouse",
    location: "San Francisco, CA", remote: false, experienceLevel: "Entry",
    salaryMin: 130000, salaryMax: 165000,
    requiredSkills: ["Python", "TypeScript", "React", "PostgreSQL", "REST APIs"],
    visaSponsorship: true, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Join the payments platform team building APIs used by millions of businesses. You'll ship product features end to end and grow with mentorship from senior engineers." },
  { _id: "2", title: "Software Engineer I", employer: "Anduril Industries", source: "lever",
    location: "Costa Mesa, CA", remote: false, experienceLevel: "Entry",
    salaryMin: 120000, salaryMax: 150000,
    requiredSkills: ["C++", "Python", "Linux", "distributed systems"],
    visaSponsorship: false, citizenshipRequired: true, clearanceRequired: true, clearanceLevel: "Secret",
    description: "Build software for autonomous defense systems. Must be a U.S. person; active Secret clearance required or obtainable." },
  { _id: "3", title: "Associate Data Engineer", employer: "Databricks", source: "greenhouse",
    location: "Remote (US)", remote: true, experienceLevel: "Entry",
    salaryMin: 125000, salaryMax: 155000,
    requiredSkills: ["Python", "Spark", "SQL", "AWS", "Airflow"],
    visaSponsorship: null, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Work on the lakehouse data platform. Build pipelines and tooling that power analytics for thousands of enterprises." },
  { _id: "4", title: "Frontend Engineer, New Grad", employer: "Notion", source: "ashby",
    location: "New York, NY", remote: false, experienceLevel: "Entry",
    salaryMin: 135000, salaryMax: 170000,
    requiredSkills: ["TypeScript", "React", "Next.js", "GraphQL"],
    visaSponsorship: true, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Craft the editor experience millions use daily. Care deeply about interaction detail, performance, and polish." },
  { _id: "5", title: "Forward Deployed Engineer", employer: "Palantir", source: "greenhouse",
    location: "Washington, DC", remote: false, experienceLevel: "Entry",
    salaryMin: 128000, salaryMax: 160000,
    requiredSkills: ["Python", "TypeScript", "SQL", "distributed systems"],
    visaSponsorship: false, citizenshipRequired: true, clearanceRequired: true, clearanceLevel: "TS/SCI",
    description: "Deploy data platforms in the field with government partners. U.S. citizenship and eligibility for a TS/SCI clearance required." },
  { _id: "6", title: "Junior Full Stack Engineer", employer: "Vercel", source: "ashby",
    location: "Remote (US)", remote: true, experienceLevel: "Entry",
    salaryMin: 120000, salaryMax: 150000,
    requiredSkills: ["TypeScript", "React", "Next.js", "Node.js"],
    visaSponsorship: true, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Build the platform that ships the web. Work across the frontend cloud, from framework internals to the dashboard." },
  { _id: "7", title: "Robotics Software Engineer, New Grad", employer: "Nuro", source: "lever",
    location: "Mountain View, CA", remote: false, experienceLevel: "Entry",
    salaryMin: 135000, salaryMax: 175000,
    requiredSkills: ["C++", "Python", "Linux", "machine learning"],
    visaSponsorship: false, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Write software for autonomous delivery vehicles. We are unable to sponsor work visas for this role at this time." },
  { _id: "8", title: "Associate Backend Engineer", employer: "Coinbase", source: "greenhouse",
    location: "Remote (US)", remote: true, experienceLevel: "Entry",
    salaryMin: 130000, salaryMax: 162000,
    requiredSkills: ["Go", "Python", "PostgreSQL", "Kafka", "AWS"],
    visaSponsorship: true, citizenshipRequired: false, clearanceRequired: false, clearanceLevel: "None",
    description: "Build the APIs behind a crypto platform serving 100M+ users. Focus on reliability, security, and scale." },
];

/* derive the two checkpoint rows from a job's eligibility flags */
function checkpoint(job) {
  let visa;
  if (job.visaSponsorship === true) visa = { tone: "go", Icon: Globe, label: "Sponsors visas" };
  else if (job.citizenshipRequired) visa = { tone: "stop", Icon: Plane, label: "U.S. citizens only" };
  else if (job.visaSponsorship === false) visa = { tone: "stop", Icon: Globe, label: "No visa sponsorship" };
  else visa = { tone: "warn", Icon: Globe, label: "Sponsorship not stated" };

  let clear;
  if (!job.clearanceRequired) clear = { tone: "go", Icon: ShieldCheck, label: "No clearance needed" };
  else if (job.clearanceLevel === "Secret" || job.clearanceLevel === "Public Trust")
    clear = { tone: "warn", Icon: ShieldAlert, label: `${job.clearanceLevel} clearance` };
  else clear = { tone: "stop", Icon: ShieldAlert, label: `${job.clearanceLevel} clearance` };

  return [visa, clear];
}

const money = (n) => "$" + (n / 1000).toFixed(0) + "k";
const THRESHOLD = 120;

export default function SwipeDeck() {
  const [i, setI] = useState(0);
  const [history, setHistory] = useState([]); // {job, dir}
  const [drag, setDrag] = useState({ x: 0, y: 0, active: false });
  const [exit, setExit] = useState(null); // 'left' | 'right'
  const [view, setView] = useState("deck");
  const start = useRef(null);

  const remaining = JOBS.length - i;
  const top = JOBS[i];

  const commit = useCallback((dir) => {
    if (!JOBS[i] || exit) return;
    setExit(dir);
    setHistory((h) => [...h, { job: JOBS[i], dir }]);
    setTimeout(() => {
      setI((n) => n + 1);
      setDrag({ x: 0, y: 0, active: false });
      setExit(null);
    }, 280);
  }, [i, exit]);

  const undo = useCallback(() => {
    if (!history.length) return;
    setHistory((h) => h.slice(0, -1));
    setI((n) => Math.max(0, n - 1));
    setDrag({ x: 0, y: 0, active: false });
    setExit(null);
  }, [history]);

  // keyboard: ← pass, → like, ↩ undo
  useEffect(() => {
    if (view !== "deck") return;
    const h = (e) => {
      if (e.key === "ArrowLeft") commit("left");
      else if (e.key === "ArrowRight") commit("right");
      else if (e.key === "Backspace") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [commit, undo, view]);

  const onDown = (e) => {
    if (exit) return;
    start.current = { x: e.clientX, y: e.clientY };
    setDrag((d) => ({ ...d, active: true }));
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e) => {
    if (!drag.active || !start.current) return;
    setDrag({ x: e.clientX - start.current.x, y: e.clientY - start.current.y, active: true });
  };
  const onUp = () => {
    if (!drag.active) return;
    if (drag.x > THRESHOLD) commit("right");
    else if (drag.x < -THRESHOLD) commit("left");
    else setDrag({ x: 0, y: 0, active: false });
    start.current = null;
  };

  const liked = history.filter((h) => h.dir === "right").map((h) => h.job);

  return (
    <div className="sh-root">
      <style>{CSS}</style>

      <div className="sh-phone">
        <header className="sh-bar">
          <div className="sh-brand">
            <span className="sh-logo" aria-hidden>◗</span>
            <span className="sh-wordmark">jobswipe</span>
          </div>
          {view === "deck" ? (
            <span className="sh-count">{remaining > 0 ? `${remaining} roles left` : "done"}</span>
          ) : (
            <button className="sh-textbtn" onClick={() => setView("deck")}>
              <ArrowLeft size={15} /> deck
            </button>
          )}
        </header>

        {view === "deck" ? (
          <>
            <div className="sh-stage">
              {remaining > 0 ? (
                JOBS.slice(i, i + 3).reverse().map((job, idx, arr) => {
                  const depth = arr.length - 1 - idx; // 0 = top
                  const isTop = depth === 0;
                  const dx = isTop ? drag.x : 0;
                  const dy = isTop ? drag.y : 0;
                  const rot = dx * 0.05;
                  const flyX = exit === "right" ? 600 : exit === "left" ? -600 : dx;
                  const flyR = exit === "right" ? 22 : exit === "left" ? -22 : rot;
                  const [visa, clear] = checkpoint(job);
                  const style = isTop
                    ? {
                        transform: `translate(${exit ? flyX : dx}px, ${exit ? -40 : dy}px) rotate(${exit ? flyR : rot}deg)`,
                        transition: drag.active ? "none" : "transform .28s cubic-bezier(.22,1,.36,1), opacity .28s",
                        opacity: exit ? 0 : 1,
                        zIndex: 3,
                      }
                    : {
                        transform: `translateY(${depth * 14}px) scale(${1 - depth * 0.05})`,
                        zIndex: 3 - depth,
                        opacity: 1 - depth * 0.15,
                      };
                  return (
                    <article
                      key={job._id}
                      className="sh-card"
                      style={style}
                      onPointerDown={isTop ? onDown : undefined}
                      onPointerMove={isTop ? onMove : undefined}
                      onPointerUp={isTop ? onUp : undefined}
                      onPointerCancel={isTop ? onUp : undefined}
                    >
                      {isTop && (
                        <>
                          <span className="sh-stamp sh-like" style={{ opacity: Math.max(0, Math.min(1, drag.x / THRESHOLD)) }}>save</span>
                          <span className="sh-stamp sh-nope" style={{ opacity: Math.max(0, Math.min(1, -drag.x / THRESHOLD)) }}>pass</span>
                        </>
                      )}

                      <div className="sh-cardtop">
                        <span className="sh-employer">{job.employer}</span>
                        <span className="sh-src">{job.source}</span>
                      </div>

                      <h2 className="sh-title">{job.title}</h2>

                      <div className="sh-meta">
                        <span><MapPin size={13} /> {job.location.replace(" (US)", "")}</span>
                        {job.remote && <span className="sh-remote"><Wifi size={13} /> Remote</span>}
                        {job.salaryMin && <span className="sh-salary">{money(job.salaryMin)}–{money(job.salaryMax)}</span>}
                      </div>

                      {/* SIGNATURE: eligibility checkpoint */}
                      <div className="sh-check">
                        <div className="sh-checkhead">can you apply?</div>
                        {[visa, clear].map((r, k) => (
                          <div className={`sh-row sh-${r.tone}`} key={k}>
                            <span className="sh-dot" />
                            <r.Icon size={16} className="sh-rowicon" />
                            <span className="sh-rowlabel">{r.label}</span>
                          </div>
                        ))}
                      </div>

                      <div className="sh-skills">
                        {job.requiredSkills.slice(0, 6).map((s) => (
                          <span key={s} className="sh-skill">{s}</span>
                        ))}
                      </div>

                      <p className="sh-desc">{job.description}</p>
                    </article>
                  );
                })
              ) : (
                <div className="sh-empty">
                  <Layers size={30} />
                  <p className="sh-emptybig">You're all caught up.</p>
                  <p className="sh-emptysub">{liked.length} role{liked.length === 1 ? "" : "s"} saved.</p>
                  <button className="sh-primary" onClick={() => setView("matches")}>View matches</button>
                </div>
              )}
            </div>

            {remaining > 0 && (
              <div className="sh-actions">
                <button className="sh-act sh-pass" onClick={() => commit("left")} aria-label="Pass"><X size={24} /></button>
                <button className="sh-act sh-undo" onClick={undo} disabled={!history.length} aria-label="Undo"><RotateCcw size={19} /></button>
                <button className="sh-act sh-save" onClick={() => commit("right")} aria-label="Save"><Heart size={22} /></button>
              </div>
            )}

            <button className="sh-matchestab" onClick={() => setView("matches")}>
              Matches <span className="sh-badge">{liked.length}</span>
            </button>
          </>
        ) : (
          <Matches liked={liked} />
        )}
      </div>
    </div>
  );
}

function Matches({ liked }) {
  if (!liked.length) {
    return (
      <div className="sh-stage">
        <div className="sh-empty">
          <Heart size={28} />
          <p className="sh-emptybig">No saved roles yet.</p>
          <p className="sh-emptysub">Swipe right to build your list.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="sh-matchlist">
      {liked.map((job) => {
        const have = new Set(RESUME_SKILLS);
        const matched = job.requiredSkills.filter((s) => have.has(s));
        const missing = job.requiredSkills.filter((s) => !have.has(s));
        const [visa, clear] = checkpoint(job);
        return (
          <div className="sh-match" key={job._id}>
            <div className="sh-matchhead">
              <div>
                <div className="sh-employer">{job.employer}</div>
                <div className="sh-matchtitle">{job.title}</div>
              </div>
              {job.salaryMin && <span className="sh-salary">{money(job.salaryMin)}–{money(job.salaryMax)}</span>}
            </div>

            <div className="sh-matchchips">
              <span className={`sh-chip sh-${visa.tone}`}><visa.Icon size={12} /> {visa.label}</span>
              <span className={`sh-chip sh-${clear.tone}`}><clear.Icon size={12} /> {clear.label}</span>
            </div>

            <p className="sh-why">
              Surfaced because it echoes roles you liked in {matched[0] || job.requiredSkills[0]}
              {matched.length > 1 ? ` and ${matched[1]}` : ""}.
            </p>

            <div className="sh-gap">
              <div className="sh-gaprow">
                <span className="sh-gaplabel sh-go">on your resume</span>
                <div className="sh-gapskills">
                  {matched.length ? matched.map((s) => <span key={s} className="sh-skill sh-skillgo"><Check size={11} /> {s}</span>)
                    : <span className="sh-none">none matched</span>}
                </div>
              </div>
              <div className="sh-gaprow">
                <span className="sh-gaplabel sh-stop">gaps to close</span>
                <div className="sh-gapskills">
                  {missing.length ? missing.map((s) => <span key={s} className="sh-skill sh-skillstop">{s}</span>)
                    : <span className="sh-none">you're covered</span>}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.sh-root{
  --ink:#0d1c24; --ink2:#123039;
  --card:#ffffff; --slate:#17262e; --mute:#6b8089; --line:#e7ecee;
  --go:#0fae74; --gobg:#e6f6ef; --stop:#e8505b; --stopbg:#fdecee; --warn:#e8973b; --warnbg:#fdf1e3;
  --gold:#f2b134;
  --disp:'Space Grotesk',ui-sans-serif,system-ui,sans-serif;
  --body:'Inter',ui-sans-serif,system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  min-height:100vh; display:flex; align-items:center; justify-content:center;
  padding:24px 16px; box-sizing:border-box;
  background:radial-gradient(120% 90% at 50% -10%, #16323c 0%, var(--ink) 55%, #091319 100%);
  font-family:var(--body); color:var(--slate);
}
.sh-root *{box-sizing:border-box;}
.sh-phone{width:100%; max-width:400px; display:flex; flex-direction:column; gap:16px;}

.sh-bar{display:flex; align-items:center; justify-content:space-between; padding:2px 4px;}
.sh-brand{display:flex; align-items:center; gap:8px;}
.sh-logo{color:var(--gold); font-size:20px; line-height:1; transform:translateY(1px);}
.sh-wordmark{font-family:var(--disp); font-weight:700; letter-spacing:-.02em; font-size:19px; color:#eef4f5;}
.sh-count{font-family:var(--mono); font-size:12px; color:#8fa7af; letter-spacing:.02em;}
.sh-textbtn{background:none; border:none; color:#9fb6bd; font-family:var(--mono); font-size:12px; display:flex; align-items:center; gap:5px; cursor:pointer; padding:4px;}
.sh-textbtn:hover{color:#eef4f5;}

.sh-stage{position:relative; height:544px;}
.sh-card{
  position:absolute; inset:0; background:var(--card); border-radius:22px;
  padding:22px 22px 18px; box-shadow:0 24px 60px -20px rgba(0,0,0,.55), 0 2px 0 rgba(255,255,255,.04);
  display:flex; flex-direction:column; touch-action:none; cursor:grab; user-select:none;
  border:1px solid rgba(255,255,255,.06); will-change:transform;
}
.sh-card:active{cursor:grabbing;}

.sh-cardtop{display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;}
.sh-employer{font-family:var(--disp); font-weight:600; font-size:14px; color:var(--slate); letter-spacing:-.01em;}
.sh-src{font-family:var(--mono); font-size:10px; color:var(--mute); text-transform:lowercase; border:1px solid var(--line); border-radius:5px; padding:2px 6px;}

.sh-title{font-family:var(--disp); font-weight:700; font-size:26px; line-height:1.12; letter-spacing:-.025em; margin:0 0 12px; color:#0f1f27;}

.sh-meta{display:flex; flex-wrap:wrap; gap:8px 14px; margin-bottom:16px; font-size:13px; color:var(--mute);}
.sh-meta span{display:inline-flex; align-items:center; gap:4px;}
.sh-remote{color:var(--go); font-weight:500;}
.sh-salary{font-family:var(--mono); font-weight:500; color:var(--slate);}

.sh-check{background:#f7f9fa; border:1px solid var(--line); border-radius:14px; padding:12px; margin-bottom:15px;}
.sh-checkhead{font-family:var(--mono); font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--mute); margin-bottom:9px;}
.sh-row{display:flex; align-items:center; gap:9px; padding:7px 9px; border-radius:9px; font-size:14px; font-weight:500;}
.sh-row + .sh-row{margin-top:5px;}
.sh-rowicon{flex:none;}
.sh-dot{width:8px; height:8px; border-radius:50%; flex:none;}
.sh-go{background:var(--gobg); color:#0a7a52;} .sh-go .sh-dot{background:var(--go);} .sh-go .sh-rowicon{color:var(--go);}
.sh-stop{background:var(--stopbg); color:#b8323c;} .sh-stop .sh-dot{background:var(--stop);} .sh-stop .sh-rowicon{color:var(--stop);}
.sh-warn{background:var(--warnbg); color:#a5651c;} .sh-warn .sh-dot{background:var(--warn);} .sh-warn .sh-rowicon{color:var(--warn);}

.sh-skills{display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px;}
.sh-skill{font-family:var(--mono); font-size:11px; color:var(--slate); background:#eef2f3; border-radius:6px; padding:3px 8px;}

.sh-desc{font-size:13.5px; line-height:1.5; color:#55666e; margin:auto 0 0; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;}

.sh-stamp{position:absolute; top:22px; font-family:var(--disp); font-weight:700; font-size:26px; letter-spacing:.05em; text-transform:uppercase; padding:4px 14px; border-radius:10px; border:3px solid; pointer-events:none;}
.sh-like{right:20px; color:var(--go); border-color:var(--go); transform:rotate(12deg);}
.sh-nope{left:20px; color:var(--stop); border-color:var(--stop); transform:rotate(-12deg);}

.sh-actions{display:flex; align-items:center; justify-content:center; gap:20px;}
.sh-act{width:60px; height:60px; border-radius:50%; border:none; background:var(--card); display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 10px 26px -10px rgba(0,0,0,.5); transition:transform .12s;}
.sh-act:hover{transform:translateY(-2px);} .sh-act:active{transform:scale(.92);}
.sh-act:disabled{opacity:.35; cursor:not-allowed; transform:none;}
.sh-pass{color:var(--stop);} .sh-save{color:var(--go);} .sh-save svg{fill:currentColor;}
.sh-undo{width:48px; height:48px; color:var(--mute);}
.sh-act:focus-visible{outline:3px solid var(--gold); outline-offset:3px;}

.sh-matchestab{align-self:center; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); color:#cfe0e5; font-family:var(--mono); font-size:12px; padding:8px 16px; border-radius:999px; cursor:pointer; display:flex; align-items:center; gap:8px;}
.sh-matchestab:hover{background:rgba(255,255,255,.1);}
.sh-badge{background:var(--gold); color:#3a2b06; border-radius:999px; min-width:18px; height:18px; padding:0 5px; font-weight:600; display:inline-flex; align-items:center; justify-content:center;}

.sh-empty{position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; color:#9fb6bd; text-align:center;}
.sh-emptybig{font-family:var(--disp); font-weight:600; font-size:20px; color:#eef4f5; margin:8px 0 0;}
.sh-emptysub{font-size:13px; margin:0;}
.sh-primary,.sh-none{font-family:var(--body);}
.sh-primary{margin-top:14px; background:var(--gold); color:#3a2b06; border:none; font-weight:600; font-size:14px; padding:11px 20px; border-radius:11px; cursor:pointer;}
.sh-primary:hover{filter:brightness(1.05);}

.sh-matchlist{display:flex; flex-direction:column; gap:12px; max-height:600px; overflow-y:auto; padding:2px;}
.sh-match{background:var(--card); border-radius:16px; padding:16px; box-shadow:0 16px 40px -22px rgba(0,0,0,.5);}
.sh-matchhead{display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:11px;}
.sh-matchtitle{font-family:var(--disp); font-weight:600; font-size:16px; letter-spacing:-.01em; color:#0f1f27; margin-top:2px;}
.sh-matchchips{display:flex; flex-wrap:wrap; gap:7px; margin-bottom:11px;}
.sh-chip{display:inline-flex; align-items:center; gap:5px; font-size:11.5px; font-weight:500; padding:4px 9px; border-radius:7px;}
.sh-chip.sh-go{background:var(--gobg); color:#0a7a52;} .sh-chip.sh-stop{background:var(--stopbg); color:#b8323c;} .sh-chip.sh-warn{background:var(--warnbg); color:#a5651c;}
.sh-why{font-size:13px; line-height:1.45; color:#55666e; font-style:italic; margin:0 0 12px; padding-left:10px; border-left:2px solid var(--gold);}
.sh-gap{display:flex; flex-direction:column; gap:9px;}
.sh-gaprow{display:flex; gap:10px; align-items:flex-start;}
.sh-gaplabel{font-family:var(--mono); font-size:9.5px; letter-spacing:.1em; text-transform:uppercase; padding-top:4px; flex:none; width:88px;}
.sh-gaplabel.sh-go{color:var(--go);} .sh-gaplabel.sh-stop{color:var(--stop);}
.sh-gapskills{display:flex; flex-wrap:wrap; gap:5px;}
.sh-skillgo{display:inline-flex; align-items:center; gap:3px; background:var(--gobg); color:#0a7a52;}
.sh-skillstop{background:var(--stopbg); color:#b8323c;}
.sh-none{font-size:12px; color:var(--mute); padding-top:3px;}

@media (prefers-reduced-motion: reduce){
  .sh-card,.sh-act{transition:none !important;}
}
`;
