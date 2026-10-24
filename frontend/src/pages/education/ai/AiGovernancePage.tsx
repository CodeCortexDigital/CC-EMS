// AI approvals and school documents (administrators).
// The assistant can only ask for an action; it happens after an administrator approves it here. The documents are what the assistant
// may quote when it answers questions about how the school works.
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, FileText, Search, Trash2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { Empty, Field, PageHead, Pill, Spinner, Tabs, btn, btnDanger, btnGhost, card, errorText, fmtDateTime, input } from '@/components/common/kit';
import ai, { AUDIENCE_LABEL, STATUS_LABEL, type ApprovalRequest, type Audience, type KnowledgeDoc, type Passage, type RequestStatus } from '@/services/aiGovernance.service';

type TabKey = 'approvals' | 'documents';
const TONE: Record<RequestStatus, 'green' | 'amber' | 'red' | 'blue' | 'slate'> = { pending: 'amber', executed: 'green', failed: 'red', rejected: 'slate', expired: 'slate' };

function Approvals() {
  const [rows, setRows] = useState<ApprovalRequest[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [note, setNote] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    try { setRows(await ai.approvals(showAll ? 'all' : 'pending')); } catch (e) { toast.error(errorText(e, 'Could not load the requests.')); setRows([]); }
  }, [showAll]);
  useEffect(() => { setRows(null); load(); }, [load]);

  const decide = async (r: ApprovalRequest, verb: 'approve' | 'reject') => {
    setBusy(r.id);
    try {
      const done = await (verb === 'approve' ? ai.approve : ai.reject)(r.id, note[r.id] || '');
      toast[done.status === 'failed' ? 'error' : 'success'](verb === 'reject' ? 'Rejected. Nothing was done.' : done.status === 'failed' ? (done.result.error || 'It did not work.') : (done.result.note || 'Approved and done.'));
      await load();
    } catch (e) { toast.error(errorText(e, 'That did not work.')); await load(); } finally { setBusy(''); }
  };

  if (!rows) return <Spinner />;
  return (
    <section aria-label="Approvals" className="space-y-3">
      <p className="text-sm text-slate-600 max-w-3xl">
        The AI assistant cannot change anything by itself. When someone asks it to do something, it only sends a request here. Nothing happens until an
        administrator approves it, and every request, decision and result is kept in the audit log.
      </p>
      <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Also show decided and expired requests
      </label>
      {rows.length === 0 && <Empty>{showAll ? 'No requests yet.' : 'Nothing is waiting for approval.'}</Empty>}
      {rows.map((r) => (
        <div key={r.id} className={card} data-testid="approval-row">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-bold mr-auto">{r.label}</h3>
            <Pill tone={TONE[r.status]}>{STATUS_LABEL[r.status]}</Pill>
          </div>
          <p className="text-sm mt-1">{r.summary}</p>
          <p className="text-xs text-slate-500 mt-1">Asked by {r.requested_by || 'unknown'} ({r.requester_role || 'role unknown'}) on {fmtDateTime(r.created_at)}
            {r.status === 'pending' && <>, expires {fmtDateTime(r.expires_at)}</>}</p>
          {r.status !== 'pending' && (
            <p className="text-xs text-slate-600 mt-1">
              {r.decided_by ? `Decided by ${r.decided_by} on ${fmtDateTime(r.decided_at)}.` : ''} {r.decision_note && `Note: ${r.decision_note}. `}
              {r.result?.note || r.result?.error || ''}
            </p>
          )}
          {r.can_decide && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input className={`${input} max-w-xs`} placeholder="Note (optional)" aria-label={`Note for ${r.summary}`} value={note[r.id] || ''}
                onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} />
              <button className={btn} disabled={busy === r.id} onClick={() => decide(r, 'approve')}><CheckCircle2 className="w-3.5 h-3.5 inline mr-1" />Approve and run</button>
              <button className={btnDanger} disabled={busy === r.id} onClick={() => decide(r, 'reject')}><XCircle className="w-3.5 h-3.5 inline mr-1" />Reject</button>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

function DocumentForm({ doc, onClose, onSaved }: { doc: KnowledgeDoc | null; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(doc?.title || '');
  const [body, setBody] = useState(doc?.body || '');
  const [audience, setAudience] = useState<Audience>(doc?.audience || 'everyone');
  const [saving, setSaving] = useState(false);

  const readFile = async (file?: File | null) => {
    if (!file) return;
    if (!/\.(txt|md|csv)$/i.test(file.name)) { toast.error('Please choose a .txt, .md or .csv file, or paste the text.'); return; }
    setBody(await file.text());
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ''));
  };
  const save = async () => {
    setSaving(true);
    try {
      if (doc) await ai.editDocument(doc.id, { title, body, audience }); else await ai.addDocument({ title, body, audience });
      toast.success('Saved'); onSaved();
    } catch (e) { toast.error(errorText(e, 'Could not save the document.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={doc ? 'Edit document' : 'Add a school document'} size="lg"
      footer={<><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !title.trim() || body.trim().length < 20} onClick={save}>Save</button></>}>
      <div className="space-y-3">
        <Field label="Title"><input className={input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Student handbook, attendance policy…" /></Field>
        <Field label="Who may be shown it by the assistant">
          <select className={input} value={audience} onChange={(e) => setAudience(e.target.value as Audience)}>
            {(Object.keys(AUDIENCE_LABEL) as Audience[]).map((a) => <option key={a} value={a}>{AUDIENCE_LABEL[a]}</option>)}
          </select>
        </Field>
        <Field label="Text (paste it, or load a .txt / .md file)">
          <textarea className={`${input} h-56`} aria-label="Document text" value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <input type="file" accept=".txt,.md,.csv,text/plain" aria-label="Load a text file" onChange={(e) => readFile(e.target.files?.[0])} className="text-xs" />
        <p className="text-xs text-slate-500">Do not put private records of students or staff in a document: it is for policies, rules and how-to text.</p>
      </div>
    </Modal>
  );
}

function Documents() {
  const [docs, setDocs] = useState<KnowledgeDoc[] | null>(null);
  const [editing, setEditing] = useState<KnowledgeDoc | 'new' | null>(null);
  const [query, setQuery] = useState('');
  const [asRole, setAsRole] = useState('');
  const [found, setFound] = useState<{ as_role: string; passages: Passage[] } | null>(null);

  const load = useCallback(async () => {
    try { setDocs(await ai.documents()); } catch (e) { toast.error(errorText(e, 'Could not load the documents.')); setDocs([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const open = async (d: KnowledgeDoc) => {
    try { setEditing(await ai.document(d.id)); } catch (e) { toast.error(errorText(e, 'Could not open the document.')); }
  };
  const remove = async (d: KnowledgeDoc) => {
    if (!window.confirm(`Delete "${d.title}"? The assistant will no longer be able to quote it.`)) return;
    try { await ai.removeDocument(d.id); toast.success('Deleted'); await load(); } catch (e) { toast.error(errorText(e, 'Could not delete it.')); }
  };
  const toggle = async (d: KnowledgeDoc) => {
    try { await ai.editDocument(d.id, { is_active: !d.is_active }); await load(); } catch (e) { toast.error(errorText(e, 'Could not change it.')); }
  };
  const test = async () => {
    try { setFound(await ai.trySearch(query, asRole || undefined)); } catch (e) { toast.error(errorText(e, 'Search failed.')); }
  };

  if (!docs) return <Spinner />;
  return (
    <section aria-label="School documents" className="space-y-3">
      <p className="text-sm text-slate-600 max-w-3xl">
        Add the school's own documents and the assistant answers questions about them, naming the document it used. It says so when nothing matches, and it only
        shows each person the documents their audience setting allows.
      </p>
      <button className={btn} onClick={() => setEditing('new')}><FileText className="w-3.5 h-3.5 inline mr-1" />Add a document</button>
      {docs.length === 0 && <Empty>No documents yet. Add a handbook or policy to get started.</Empty>}
      <div className="grid gap-3 md:grid-cols-2">
        {docs.map((d) => (
          <div key={d.id} className={card} data-testid="document-row">
            <div className="flex items-center gap-2">
              <h3 className="font-bold mr-auto">{d.title}</h3>
              <Pill tone={d.is_active ? 'green' : 'slate'}>{d.is_active ? 'In use' : 'Switched off'}</Pill>
            </div>
            <p className="text-xs text-slate-500 mt-1">{AUDIENCE_LABEL[d.audience]}, {d.passages} passage{d.passages === 1 ? '' : 's'}, updated {fmtDateTime(d.updated_at)}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className={btnGhost} onClick={() => open(d)}>Open</button>
              <button className={btnGhost} onClick={() => toggle(d)}>{d.is_active ? 'Switch off' : 'Switch on'}</button>
              <button className={btnDanger} onClick={() => remove(d)} aria-label={`Delete ${d.title}`}><Trash2 className="w-3.5 h-3.5 inline" /></button>
            </div>
          </div>
        ))}
      </div>

      <div className={card}>
        <h3 className="font-bold mb-2"><Search className="w-4 h-4 inline mr-1" />Try a question</h3>
        <div className="flex flex-wrap gap-2">
          <input className={`${input} max-w-md`} placeholder="What would a parent ask?" aria-label="Question to try" value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && query.trim()) test(); }} />
          <select className={`${input} max-w-[10rem]`} aria-label="Ask as" value={asRole} onChange={(e) => setAsRole(e.target.value)}>
            <option value="">As administrator</option><option value="teacher">As teacher</option><option value="parent">As parent</option><option value="student">As student</option>
          </select>
          <button className={btn} disabled={!query.trim()} onClick={test}>Search</button>
        </div>
        {found && (found.passages.length === 0
          ? <Empty>Nothing matches. The assistant would say it could not find it.</Empty>
          : <ul className="mt-3 space-y-2" aria-label="Search results">{found.passages.map((p, i) => (
            <li key={i} className="text-sm border-l-4 border-emerald-500 pl-3"><b>{p.title}</b> <span className="text-xs text-slate-500">(part {p.ordinal})</span><p className="whitespace-pre-wrap">{p.text}</p></li>
          ))}</ul>)}
      </div>

      {editing && <DocumentForm doc={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </section>
  );
}

export default function AiGovernancePage() {
  const [tab, setTab] = useState<TabKey>('approvals');
  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <PageHead title="AI approvals and school documents" hint="You stay in control: the assistant only asks, and quotes only what you give it." />
      <Tabs value={tab} onChange={(v) => setTab(v as TabKey)} tabs={[['approvals', 'Approvals'], ['documents', 'School documents']]} />
      {tab === 'approvals' ? <Approvals /> : <Documents />}
    </div>
  );
}
