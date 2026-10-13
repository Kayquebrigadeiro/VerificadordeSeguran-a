import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  api, Artifact, Environment, fmt, Profile, Project, Run, RunDetail,
  SessionInfo, setCsrf, Tool,
} from "./api";

type View = "overview" | "projects" | "runs" | "tools" | "imports" | "audit";
type ImportRow = { id: string; run_id: string | null; format: string; source_name: string; records: number; created_at: string; warnings: string[] };
type AuditRow = { id: number; ts: string; action: string; entity: string; entity_id: string | null; detail: Record<string, unknown> };
type CompareData = { runs: Record<string, unknown>[]; metrics: Record<string, unknown>[]; checks: Record<string, unknown>[]; note?: string };

const FINAL = new Set(["passed", "failed", "cancelled", "timed_out", "interrupted", "error"]);
const NAV: { id: View; label: string; mark: string }[] = [
  { id: "overview", label: "Visão geral", mark: "01" },
  { id: "projects", label: "Projetos", mark: "02" },
  { id: "runs", label: "Execuções", mark: "03" },
  { id: "tools", label: "Ferramentas", mark: "04" },
  { id: "imports", label: "Importações", mark: "05" },
  { id: "audit", label: "Auditoria", mark: "06" },
];

function Badge({ state }: { state: string }) {
  const labels: Record<string, string> = {
    passed: "aprovada", failed: "falhou", queued: "na fila", running: "executando",
    cancelled: "cancelada", timed_out: "timeout", interrupted: "interrompida", error: "erro",
    pass: "passou", fail: "falhou", skip: "ignorado", available: "disponível",
    catalogued: "catalogada", unavailable: "indisponível",
  };
  return <span className={`badge ${state}`}>{labels[state] ?? state}</span>;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty"><span>∅</span>{children}</div>;
}

function ErrorNotice({ error, clear }: { error: string; clear: () => void }) {
  return <div className="error-box" role="alert"><strong>Operação não concluída</strong><span>{error}</span><button onClick={clear} aria-label="Fechar">×</button></div>;
}

function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  return <div className="modal-backdrop" onMouseDown={close} role="presentation">
    <section className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={e => e.stopPropagation()}>
      <header><div><small>NOVO REGISTRO</small><h2>{title}</h2></div><button className="icon-btn" onClick={close} aria-label="Fechar">×</button></header>
      {children}
    </section>
  </div>;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

function App() {
  const [view, setView] = useState<View>("overview");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [imports, setImports] = useState<ImportRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<CompareData | null>(null);
  const [modal, setModal] = useState<"project" | "environment" | "profile" | "import" | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const s = await api.get<SessionInfo>("/api/session");
      setCsrf(s.csrf_token); setSession(s);
      const [p, e, pf, r, t, im, au] = await Promise.all([
        api.get<{ projects: Project[] }>("/api/projects"),
        api.get<{ environments: Environment[] }>("/api/environments"),
        api.get<{ profiles: Profile[] }>("/api/profiles"),
        api.get<{ runs: Run[] }>("/api/runs?limit=100"),
        api.get<{ tools: Tool[] }>("/api/tools"),
        api.get<{ imports: ImportRow[] }>("/api/imports"),
        api.get<{ events: AuditRow[] }>("/api/audit?limit=80"),
      ]);
      setProjects(p.projects); setEnvironments(e.environments); setProfiles(pf.profiles);
      setRuns(r.runs); setTools(t.tools); setImports(im.imports); setAudit(au.events);
      setSelectedProject(old => old || p.projects[0]?.id || "");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!runs.some(r => r.state === "queued" || r.state === "running")) return;
    const timer = window.setInterval(() => void refresh(), 1200);
    return () => window.clearInterval(timer);
  }, [runs, refresh]);

  const openRun = async (id: string) => {
    try { setSelectedRun(await api.get<RunDetail>(`/api/runs/${id}`)); setView("runs"); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const mutate = async (fn: () => Promise<unknown>) => {
    try { await fn(); setModal(null); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const project = projects.find(p => p.id === selectedProject);
  const filteredRuns = selectedProject ? runs.filter(r => r.project_id === selectedProject) : runs;
  const filteredEnvs = environments.filter(e => e.project_id === selectedProject);
  const filteredProfiles = profiles.filter(p => p.project_id === selectedProject);
  const active = runs.filter(r => r.state === "running" || r.state === "queued").length;

  return <div className="app-shell">
    <aside className="rail">
      <div className="brand"><span className="brand-mark">V<span>L</span></span><div><strong>VerificaLab</strong><small>controle local / v{session?.version ?? "…"}</small></div></div>
      <nav aria-label="Principal">{NAV.map(n => <button key={n.id} className={view === n.id ? "active" : ""} onClick={() => setView(n.id)}><em>{n.mark}</em><span>{n.label}</span></button>)}</nav>
      <div className="rail-status"><span className={session?.lab.running ? "pulse online" : "pulse"} /><div><strong>Laboratório</strong><small>{session?.lab.running ? session.lab.endpoint : "desligado"}</small></div></div>
      <p className="rail-note">Execução restrita a loopback.<br/>Nenhum destino externo.</p>
    </aside>

    <main>
      <header className="topbar">
        <div><p className="eyebrow">ESTAÇÃO DE VERIFICAÇÃO · {active ? `${active} EM ATIVIDADE` : "EM REPOUSO"}</p><h1>{NAV.find(n => n.id === view)?.label}</h1></div>
        <div className="top-actions">
          <select aria-label="Projeto ativo" value={selectedProject} onChange={e => setSelectedProject(e.target.value)}><option value="">Todos os projetos</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
          <button className="btn ghost" onClick={() => void refresh()} disabled={loading}>Atualizar</button>
          <button className="btn primary" onClick={() => setModal("project")}>+ Projeto</button>
        </div>
      </header>
      {error && <ErrorNotice error={error} clear={() => setError("")} />}
      {loading ? <div className="loading"><span/><p>Conferindo registros locais…</p></div> : <>
        {view === "overview" && <Overview projects={projects} runs={runs} tools={tools} session={session} openRun={openRun} setView={setView} />}
        {view === "projects" && <ProjectsView project={project} projects={projects} envs={filteredEnvs} profiles={filteredProfiles} runs={filteredRuns} select={setSelectedProject} modal={setModal} run={id => mutate(() => api.post("/api/runs", id))} uploadLogs={(env,file) => mutate(() => api.upload(`/api/environments/${env}/logs?filename=${encodeURIComponent(file.name)}`, file))} />}
        {view === "runs" && <RunsView runs={filteredRuns} detail={selectedRun} open={openRun} close={() => setSelectedRun(null)} cancel={id => mutate(() => api.post(`/api/runs/${id}/cancel`))} correlate={id => mutate(() => api.post(`/api/runs/${id}/correlate`))} compareIds={compareIds} setCompareIds={setCompareIds} comparison={comparison} compare={async () => { try { setComparison(await api.get<CompareData>(`/api/compare?a=${compareIds[0]}&b=${compareIds[1]}`)); } catch(e) { setError(e instanceof Error ? e.message : String(e)); } }} />}
        {view === "tools" && <ToolsView tools={tools} />}
        {view === "imports" && <ImportsView imports={imports} runs={runs} openModal={() => setModal("import")} />}
        {view === "audit" && <AuditView rows={audit} />}
      </>}
    </main>
    {modal === "project" && <ProjectForm close={() => setModal(null)} submit={body => mutate(() => api.post("/api/projects", body))} />}
    {modal === "environment" && <EnvironmentForm project={selectedProject} close={() => setModal(null)} submit={body => mutate(() => api.post("/api/environments", body))} />}
    {modal === "profile" && <ProfileForm project={selectedProject} session={session} close={() => setModal(null)} submit={body => mutate(() => api.post("/api/profiles", body))} />}
    {modal === "import" && <ImportForm runs={runs} close={() => setModal(null)} submit={(url, file) => mutate(() => api.upload(url, file))} />}
  </div>;
}

function Overview({ projects, runs, tools, session, openRun, setView }: { projects: Project[]; runs: Run[]; tools: Tool[]; session: SessionInfo | null; openRun: (id:string)=>void; setView:(v:View)=>void }) {
  const finished = runs.filter(r => FINAL.has(r.state));
  const passed = finished.filter(r => r.state === "passed").length;
  return <div className="page-grid overview">
    <section className="hero panel"><div><p className="kicker">EVIDÊNCIA, NÃO SUPOSIÇÃO</p><h2>Observe o sistema.<br/><i>Preserve os sinais.</i></h2><p>Contratos HTTP, carga leve e suítes locais em um fluxo rastreável. Uma falha permanece falha.</p></div><div className="scope-stamp"><span>ESCOPO</span><strong>127.0.0.1</strong><small>piloto restrito</small></div></section>
    <section className="stat-strip">
      <article><small>EXECUÇÕES</small><strong>{runs.length.toString().padStart(2,"0")}</strong><span>{runs.filter(r=>r.state==="running").length} em curso</span></article>
      <article><small>APROVAÇÃO</small><strong>{finished.length ? Math.round(passed / finished.length * 100) : "—"}<sup>{finished.length ? "%" : ""}</sup></strong><span>{finished.length} finalizadas</span></article>
      <article><small>PROJETOS</small><strong>{projects.length.toString().padStart(2,"0")}</strong><span>ambientes explícitos</span></article>
      <article><small>CATÁLOGO</small><strong>{tools.length.toString().padStart(2,"0")}</strong><span>leitura estática</span></article>
    </section>
    <section className="panel span-2"><PanelHead index="A" title="Atividade recente" action={<button className="text-btn" onClick={()=>setView("runs")}>ver histórico →</button>} />
      {runs.length ? <div className="run-list">{runs.slice(0,6).map(r => <button key={r.id} onClick={()=>openRun(r.id)}><span className={`state-dot ${r.state}`}/><div><strong>{r.summary || r.kind}</strong><small>{r.kind.toUpperCase()} · {fmt.date(r.queued_at)}</small></div><Badge state={r.state}/><span className="arrow">→</span></button>)}</div> : <Empty>Nenhuma execução registrada.</Empty>}
    </section>
    <section className="panel"><PanelHead index="B" title="Estação local" /><dl className="facts"><div><dt>Laboratório</dt><dd><span className={session?.lab.running?"ok-text":"warn-text"}>{session?.lab.running?"operante":"parado"}</span></dd></div><div><dt>Limite de carga</dt><dd>{session?.limits.load_max_rps} req/s</dd></div><div><dt>Concorrência</dt><dd>{session?.limits.load_max_concurrency} workers</dd></div><div><dt>Retenção</dt><dd>{session?.limits.retention ?? "—"}</dd></div></dl></section>
  </div>;
}

function PanelHead({ index, title, action }: { index: string; title: string; action?: ReactNode }) { return <header className="panel-head"><span>{index}</span><h3>{title}</h3>{action}</header>; }

function ProjectsView({ project, projects, envs, profiles, runs, select, modal, run, uploadLogs }: { project?: Project; projects: Project[]; envs: Environment[]; profiles: Profile[]; runs: Run[]; select:(id:string)=>void; modal:(m:"environment"|"profile")=>void; run:(body:unknown)=>void; uploadLogs:(env:string,file:File)=>void }) {
  if (!project) return <section className="panel"><PanelHead index="02" title="Projetos cadastrados" />{projects.length ? <div className="tile-grid">{projects.map(p=><button className="project-tile" key={p.id} onClick={()=>select(p.id)}><small>{p.id}</small><strong>{p.name}</strong><p>{p.description || "Sem descrição"}</p><span>{p.environments} ambientes · {p.runs} execuções</span></button>)}</div> : <Empty>Crie o primeiro projeto para iniciar.</Empty>}</section>;
  return <div className="page-grid project-page">
    <section className="panel span-2 project-title"><p className="kicker">{project.id}</p><h2>{project.name}</h2><p>{project.description || "Sem descrição."}</p></section>
    <section className="panel"><PanelHead index="C" title="Ambientes" action={<button className="text-btn" onClick={()=>modal("environment")}>+ cadastrar</button>} />{envs.length ? envs.map(e=><div className="record" key={e.id}><div><strong>{e.name}</strong><code>{e.scheme}://{e.host}:{e.port}</code></div><label className="file-action">+ logs<input type="file" accept=".log,.txt,.jsonl" onChange={x=>{const f=x.target.files?.[0];if(f)uploadLogs(e.id,f);x.target.value=""}} /></label></div>) : <Empty>Nenhum endpoint cadastrado.</Empty>}</section>
    <section className="panel"><PanelHead index="D" title="Perfis de teste" action={<button className="text-btn" onClick={()=>modal("profile")}>+ configurar</button>} />{profiles.length ? profiles.map(p=><div className="record profile" key={p.id}><div><strong>{p.name}</strong><small>{p.kind.toUpperCase()} · configuração validada</small></div><button className="btn compact" disabled={!envs[0]} onClick={()=>run({profile_id:p.id, environment_id:envs[0]?.id})}>Executar</button></div>) : <Empty>Nenhum perfil configurado.</Empty>}</section>
    <section className="panel span-2"><PanelHead index="E" title="Resumo do projeto" /><div className="mini-stats"><div><strong>{envs.length}</strong><span>ambientes</span></div><div><strong>{profiles.length}</strong><span>perfis</span></div><div><strong>{runs.length}</strong><span>execuções</span></div><div><strong>{runs.filter(r=>r.state==="failed").length}</strong><span>falhas visíveis</span></div></div></section>
  </div>;
}

function RunsView({ runs, detail, open, close, cancel, correlate, compareIds, setCompareIds, comparison, compare }: { runs:Run[]; detail:RunDetail|null; open:(id:string)=>void; close:()=>void; cancel:(id:string)=>void; correlate:(id:string)=>void; compareIds:string[]; setCompareIds:(v:string[])=>void; comparison:CompareData|null; compare:()=>void }) {
  const toggle = (id:string) => setCompareIds(compareIds.includes(id) ? compareIds.filter(x=>x!==id) : [...compareIds.slice(-1), id]);
  if (detail) return <RunDetailView data={detail} close={close} cancel={cancel} correlate={correlate}/>;
  return <section className="panel"><PanelHead index="03" title="Histórico de execuções" action={<div className="compare-action"><span>{compareIds.length}/2 selecionadas</span><button className="btn compact" disabled={compareIds.length!==2} onClick={compare}>Comparar</button></div>} />
    {comparison && <details className="comparison" open><summary>Comparação calculada</summary><pre>{JSON.stringify(comparison,null,2)}</pre></details>}
    <div className="table-wrap"><table><thead><tr><th aria-label="Comparar"></th><th>Estado</th><th>Tipo</th><th>Resumo</th><th>Início</th><th>Progresso</th><th></th></tr></thead><tbody>{runs.map(r=><tr key={r.id}><td><input type="checkbox" aria-label={`Comparar ${r.id}`} checked={compareIds.includes(r.id)} onChange={()=>toggle(r.id)}/></td><td><Badge state={r.state}/></td><td><code>{r.kind}</code></td><td>{r.summary}</td><td>{fmt.date(r.started_at||r.queued_at)}</td><td><div className="progress"><i style={{width:`${r.progress}%`}}/></div></td><td><button className="text-btn" onClick={()=>open(r.id)}>abrir →</button></td></tr>)}</tbody></table></div>
    {!runs.length && <Empty>Nenhuma execução neste recorte.</Empty>}
  </section>;
}

function RunDetailView({ data, close, cancel, correlate }: { data:RunDetail; close:()=>void; cancel:(id:string)=>void; correlate:(id:string)=>void }) {
  const r=data.run;
  return <div className="run-detail"><button className="back" onClick={close}>← histórico</button><section className="panel run-banner"><div><p className="kicker">{r.id}</p><h2>{r.summary || "Execução"}</h2><p>{r.kind.toUpperCase()} · {fmt.date(r.started_at)} → {fmt.date(r.finished_at)}</p></div><div className="run-controls"><Badge state={r.state}/>{!FINAL.has(r.state)&&<button className="btn danger" onClick={()=>cancel(r.id)}>Cancelar</button>}<button className="btn ghost" onClick={()=>correlate(r.id)}>Correlacionar logs</button><a className="btn" href={`/api/runs/${r.id}/report?format=html`}>Exportar HTML</a></div></section>
    <section className="panel"><PanelHead index="R1" title="Verificações" />{data.checks.length?<div className="check-list">{data.checks.map(c=><details key={c.id}><summary><Badge state={c.status}/><strong>{c.name}</strong><span>{c.message}</span><em>{c.duration_ms===null?"—":`${fmt.num(c.duration_ms)} ms`}</em></summary><pre>{JSON.stringify(c.evidence,null,2)}</pre></details>)}</div>:<Empty>Nenhuma verificação persistida.</Empty>}</section>
    <div className="page-grid"><section className="panel"><PanelHead index="R2" title="Métricas" />{data.metrics.length?<dl className="metrics">{data.metrics.map(m=><div key={m.id}><dt>{m.name}<small>{m.origin}</small></dt><dd>{fmt.num(m.value)} <small>{m.unit}</small><span>{m.samples??"—"} amostras</span></dd></div>)}</dl>:<Empty>Sem observações mensuráveis.</Empty>}</section><section className="panel"><PanelHead index="R3" title="Achados e hipóteses" />{data.findings.length?data.findings.map(f=><article className="finding" key={f.id}><Badge state={f.severity}/><strong>{f.title}</strong><p>{f.description}</p>{Boolean(f.hypothesis)&&<small>Hipótese; não representa causa comprovada.</small>}</article>):<Empty>Nenhum achado registrado.</Empty>}</section></div>
    <section className="panel"><PanelHead index="R4" title="Linha do tempo" /><div className="event-log">{data.events.map(e=><div key={e.id}><time>{fmt.date(e.ts)}</time><span className={e.level}>{e.level}</span><p>{e.message}</p></div>)}</div></section>
    <section className="panel"><PanelHead index="R5" title="Artefatos" />{data.artifacts.length?<div className="artifact-list">{data.artifacts.map((a:Artifact)=><a key={a.id} href={`/api/artifacts/${a.id}/download`}><span>↓</span><div><strong>{a.filename}</strong><small>{a.kind} · {a.size} bytes · sha256 {a.sha256.slice(0,12)}…</small></div></a>)}</div>:<Empty>Nenhum artefato associado.</Empty>}</section></div>;
}

function ToolsView({tools}:{tools:Tool[]}) { return <section className="panel"><PanelHead index="04" title="Catálogo inspecionado" /><div className="notice">Inventário por leitura estática. Presença em disco não comprova funcionamento, autorização ou segurança.</div><div className="tool-grid">{tools.map(t=><article key={t.id}><header><div><small>{t.language} · {t.license||"licença não confirmada"}</small><h3>{t.name}</h3></div><Badge state={t.status}/></header><p>{t.notes}</p><footer><span>CAPACIDADES</span>{t.capabilities.map(c=><code key={c}>{c}</code>)}{t.import_formats.map(f=><code className="importable" key={f}>importa: {f}</code>)}</footer></article>)}</div></section>; }

function ImportsView({imports,runs,openModal}:{imports:ImportRow[]; runs:Run[]; openModal:()=>void}) { return <section className="panel"><PanelHead index="05" title="Relatórios externos" action={<button className="btn primary compact" onClick={openModal}>Importar arquivo</button>} /><div className="notice">Importar preserva procedência; não comprova que o teste original foi autorizado ou corretamente medido.</div>{imports.length?<div className="table-wrap"><table><thead><tr><th>Formato</th><th>Origem</th><th>Registros</th><th>Execução</th><th>Data</th></tr></thead><tbody>{imports.map(i=><tr key={i.id}><td><code>{i.format}</code></td><td>{i.source_name}</td><td>{i.records}</td><td>{runs.find(r=>r.id===i.run_id)?.summary||i.run_id||"não vinculada"}</td><td>{fmt.date(i.created_at)}</td></tr>)}</tbody></table></div>:<Empty>Nenhum relatório importado.</Empty>}</section>; }

function AuditView({rows}:{rows:AuditRow[]}) { return <section className="panel"><PanelHead index="06" title="Trilha de auditoria" />{rows.length?<div className="audit-list">{rows.map(e=><details key={e.id}><summary><time>{fmt.date(e.ts)}</time><code>{e.action}</code><span>{e.entity} / {e.entity_id||"—"}</span></summary><pre>{JSON.stringify(e.detail,null,2)}</pre></details>)}</div>:<Empty>Nenhum evento de auditoria.</Empty>}</section>; }

function ProjectForm({close,submit}:{close:()=>void;submit:(b:unknown)=>void}) { const [name,setName]=useState("");const [description,setDescription]=useState("");return <Modal title="Cadastrar projeto" close={close}><form onSubmit={e=>{e.preventDefault();submit({name,description})}}><Field label="Nome"><input required maxLength={80} autoFocus value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Descrição"><textarea maxLength={2000} value={description} onChange={e=>setDescription(e.target.value)}/></Field><FormActions close={close}/></form></Modal>; }

function EnvironmentForm({project,close,submit}:{project:string;close:()=>void;submit:(b:unknown)=>void}) { const [name,setName]=useState("Laboratório local");const [endpoint,setEndpoint]=useState("http://127.0.0.1:8477");return <Modal title="Cadastrar ambiente" close={close}><form onSubmit={e=>{e.preventDefault();submit({project_id:project,name,endpoint,kind:"lab"})}}><Field label="Nome"><input required value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Endpoint" hint="Somente IP literal de loopback com porta explícita."><input required value={endpoint} onChange={e=>setEndpoint(e.target.value)}/></Field><FormActions close={close}/></form></Modal>; }

function ProfileForm({project,session,close,submit}:{project:string;session:SessionInfo|null;close:()=>void;submit:(b:unknown)=>void}) { const [name,setName]=useState("Contrato básico");const [kind,setKind]=useState<"http"|"load"|"suite">("http"); const [jsonError,setJsonError]=useState(""); const defaults=useMemo(()=>({http:{checks:[{name:"GET /ok retorna 200",type:"status",path:"/ok",expected_status:200},{name:"Resposta é JSON",type:"content_type",path:"/ok",expected_content_type:"application/json"}],include_config_checks:true,timeout_s:5},load:{path:"/ok",method:"GET",rps:session?.limits.load_default_rps??1,duration_s:5,concurrency:1,max_attempts:10,timeout_s:5,expect_status:200},suite:{command:["python3","-m","pytest","-q"],cwd:"",timeout_s:120}}),[session]); const [config,setConfig]=useState(JSON.stringify(defaults.http,null,2)); const change=(k:"http"|"load"|"suite")=>{setKind(k);setConfig(JSON.stringify(defaults[k],null,2));setJsonError("")}; return <Modal title="Configurar perfil" close={close}><form onSubmit={e=>{e.preventDefault();try{submit({project_id:project,name,kind,config:JSON.parse(config)});setJsonError("")}catch{setJsonError("JSON inválido: revise chaves, aspas e vírgulas.")}}}><div className="form-row"><Field label="Nome"><input required value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Executor"><select value={kind} onChange={e=>change(e.target.value as typeof kind)}><option value="http">Contrato HTTP</option><option value="load">Carga leve</option><option value="suite">Suíte pytest</option></select></Field></div><Field label="Configuração JSON" hint="Os limites também são validados no backend; valores excessivos são recusados."><textarea className="code" required value={config} onChange={e=>setConfig(e.target.value)}/></Field>{jsonError&&<p className="form-error">{jsonError}</p>}<FormActions close={close}/></form></Modal>; }

function ImportForm({runs,close,submit}:{runs:Run[];close:()=>void;submit:(u:string,f:File)=>void}) { const [format,setFormat]=useState("junit-xml");const [run,setRun]=useState("");const [file,setFile]=useState<File|null>(null);return <Modal title="Importar evidência" close={close}><form onSubmit={e=>{e.preventDefault();if(file){const q=new URLSearchParams({format,filename:file.name});if(run)q.set("run_id",run);submit(`/api/imports?${q}`,file)}}}><Field label="Formato"><select value={format} onChange={e=>setFormat(e.target.value)}><option value="junit-xml">JUnit XML</option><option value="json">JSON genérico</option><option value="jsonl">JSON Lines</option><option value="ddoslayer-json">DDoSlayer JSON confirmado</option></select></Field><Field label="Vincular à execução"><select value={run} onChange={e=>setRun(e.target.value)}><option value="">Não vincular</option>{runs.map(r=><option key={r.id} value={r.id}>{r.summary||r.id}</option>)}</select></Field><Field label="Arquivo"><input type="file" required onChange={e=>setFile(e.target.files?.[0]||null)}/></Field><FormActions close={close}/></form></Modal>; }

function FormActions({close}:{close:()=>void}) { return <div className="form-actions"><button type="button" className="btn ghost" onClick={close}>Cancelar</button><button className="btn primary" type="submit">Salvar registro</button></div>; }

export default App;
