import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, Languages, Loader2, MessageSquarePlus, Paperclip, Search, Send, Sparkles } from 'lucide-react';
import messaging, { type AiSummary, type AiTranslation, type ChatMessage, type Contact, type ConversationSummary } from '@/services/messaging.service';
import { useAuth } from '@/contexts/AuthContext';
import { Modal } from '@/components/ui/Modal';
import DraftWithAi from '@/components/messages/DraftWithAi';

const when = (d: string) => {
  const date = new Date(d);
  const today = new Date();
  return date.toDateString() === today.toDateString()
    ? date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

/** Inbox: private conversations between families, teachers and the office. */
export default function MessagesPage() {
  const { user, role } = useAuth();
  const [params, setParams] = useSearchParams();
  const openId = params.get('c');
  const [list, setList] = useState<ConversationSummary[] | null>(null);
  const [thread, setThread] = useState<(ConversationSummary & { messages: ChatMessage[] }) | null>(null);
  const [reply, setReply] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [composing, setComposing] = useState(false);
  const [search, setSearch] = useState('');
  const [threadSummary, setThreadSummary] = useState<AiSummary | null>(null);
  const [summarizingThread, setSummarizingThread] = useState(false);
  const [msgTranslations, setMsgTranslations] = useState<Record<string, AiTranslation>>({});
  const [translatingMsg, setTranslatingMsg] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState<Record<string, boolean>>({});
  const bottom = useRef<HTMLDivElement>(null);

  const loadList = useCallback(() => messaging.conversations().then(setList).catch(() => setList([])), []);
  const loadThread = useCallback(async (id: string) => {
    try { setThread(await messaging.thread(id)); } catch { toast.error('Could not open the conversation.'); setParams({}); }
  }, [setParams]);

  useEffect(() => { loadList(); const t = window.setInterval(loadList, 20000); return () => window.clearInterval(t); }, [loadList]);
  useEffect(() => {
    setThreadSummary(null);
    setMsgTranslations({});
    setShowOriginal({});
    if (!openId) { setThread(null); return; }
    loadThread(openId);
    const t = window.setInterval(() => loadThread(openId), 15000);
    return () => window.clearInterval(t);
  }, [openId, loadThread]);

  const summarizeThread = async () => {
    if (!thread) return;
    setSummarizingThread(true);
    try {
      setThreadSummary(await messaging.summarizeConversation(thread.id));
    } catch (e: any) {
      toast.error(e?.response?.data?.error || 'Could not summarise this conversation.');
    } finally {
      setSummarizingThread(false);
    }
  };

  const translateMessage = async (messageId: string) => {
    if (!thread) return;
    setTranslatingMsg(messageId);
    try {
      const result = await messaging.translateMessage(thread.id, messageId);
      setMsgTranslations((t) => ({ ...t, [messageId]: result }));
    } catch (e: any) {
      toast.error(e?.response?.data?.error || 'Could not translate this message.');
    } finally {
      setTranslatingMsg(null);
    }
  };
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [thread?.messages.length]);

  const send = async () => {
    if (!thread || (!reply.trim() && !file)) return;
    try {
      await messaging.reply(thread.id, reply.trim(), file);
      setReply(''); setFile(null);
      loadThread(thread.id); loadList();
    } catch (e: any) { toast.error(e?.response?.data?.error || 'Could not send the message.'); }
  };

  const rank = (c: ConversationSummary) => ({ urgent: 2, frustrated: 1 }[c.urgency || 'normal'] ?? 0);
  const shown = (list || []).filter((c) => !search || `${c.subject} ${c.participants.map((p) => p.name).join(' ')} ${c.student?.full_name || ''}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => rank(b) - rank(a));   // stable: urgent first, then newest
  const others = (c: ConversationSummary) => c.participants.filter((p) => p.id !== String(user?.id)).map((p) => p.name).join(', ');

  return (
    <div className="p-4 max-w-6xl mx-auto text-slate-800">
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-xl font-bold">Messages</h1>
        {role !== 'student' && <button onClick={() => setComposing(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand text-white text-sm font-semibold"><MessageSquarePlus className="w-4 h-4" /> New message</button>}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[320px_1fr] gap-4 min-h-[70vh]">
        <aside className={`bg-white rounded-xl border border-slate-200 overflow-hidden flex flex-col ${openId ? 'hidden md:flex' : ''}`}>
          <div className="p-2 border-b border-slate-100 relative">
            <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="w-full rounded-lg border border-slate-200 pl-8 pr-3 py-2 text-sm" placeholder="Search messages" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search messages" />
          </div>
          {!list ? <div className="py-10 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-brand" /></div> : (
            <ul className="divide-y divide-slate-100 overflow-y-auto flex-1">
              {shown.map((c) => (
                <li key={c.id}>
                  <button onClick={() => setParams({ c: c.id })} className={`w-full text-left px-3 py-2.5 ${openId === c.id ? 'bg-brand-soft' : 'hover:bg-slate-50'}`}>
                    <div className="flex justify-between gap-2"><span className={`text-sm truncate ${c.unread ? 'font-bold' : 'font-semibold'}`}>{others(c) || 'Just you'}</span><span className="text-xs text-slate-500 shrink-0">{when(c.last_message_at)}</span></div>
                    {c.urgency && c.urgency !== 'normal' && (
                      <span className={`inline-block mb-0.5 px-1.5 rounded text-[10px] font-bold ${c.urgency === 'urgent' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-800'}`}>{c.urgency === 'urgent' ? 'Urgent' : 'Upset'}</span>
                    )}
                    <p className="text-sm truncate">{c.subject}{c.student ? <span className="text-slate-500"> · {c.student.full_name}</span> : null}</p>
                    <div className="flex justify-between gap-2"><p className="text-xs text-slate-500 truncate">{c.last_message?.body}</p>{c.unread > 0 && <span className="shrink-0 min-w-[20px] h-5 px-1.5 rounded-full bg-brand text-white text-[11px] font-bold flex items-center justify-center">{c.unread}</span>}</div>
                  </button>
                </li>
              ))}
              {shown.length === 0 && <li className="p-6 text-sm text-slate-500 text-center">No messages yet.</li>}
            </ul>
          )}
        </aside>
        <section className={`bg-white rounded-xl border border-slate-200 flex flex-col ${!openId ? 'hidden md:flex' : ''}`}>
          {!thread ? <div className="flex-1 flex items-center justify-center text-sm text-slate-500 p-8">{openId ? <Loader2 className="w-5 h-5 animate-spin text-brand" /> : 'Choose a conversation, or start a new message.'}</div> : (
            <>
              <header className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
                <button onClick={() => setParams({})} className="md:hidden p-1.5 rounded hover:bg-slate-100" aria-label="Back to messages"><ArrowLeft className="w-4 h-4" /></button>
                <div className="min-w-0 flex-1">
                  <p className="font-bold truncate">{thread.subject}</p>
                  <p className="text-xs text-slate-500 truncate">{thread.participants.map((p) => `${p.name}${p.role ? ` (${p.role})` : ''}`).join(', ')}{thread.student ? ` · about ${thread.student.full_name}` : ''}</p>
                </div>
                {(thread.messages.length > 4 || role === 'admin' || role === 'teacher') && (
                  <button onClick={summarizeThread} disabled={summarizingThread}
                    className="shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline disabled:opacity-50">
                    {summarizingThread ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />} Summarise
                  </button>
                )}
              </header>
              {threadSummary && (
                <div className="mx-4 mt-3 rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2 text-xs">
                  <p className="font-bold inline-flex items-center gap-1"><Sparkles className="w-3 h-3" /> {threadSummary.summary}</p>
                  {threadSummary.key_points.length > 0 && (
                    <ul className="list-disc pl-4 mt-1 space-y-0.5">{threadSummary.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul>
                  )}
                  {threadSummary.suggested_reply && (
                    <div className="mt-2 border-t border-indigo-100 pt-2">
                      <p className="font-semibold">Suggested reply <span className="font-normal text-slate-500">(a draft: read and edit it before you send)</span></p>
                      <p className="mt-0.5 whitespace-pre-wrap">{threadSummary.suggested_reply}</p>
                      <button onClick={() => setReply(threadSummary.suggested_reply || '')} className="mt-1 font-semibold text-brand hover:underline">Put in my reply box</button>
                    </div>
                  )}
                </div>
              )}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[60vh]">
                {thread.messages.map((m) => {
                  const mine = m.sender.id === String(user?.id);
                  return (
                    <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm ${mine ? 'bg-brand text-white rounded-br-sm' : 'bg-slate-100 rounded-bl-sm'}`}>
                        {!mine && <p className="text-xs font-semibold mb-0.5">{m.sender.name}</p>}
                        <p className="whitespace-pre-wrap break-words">{msgTranslations[m.id] && msgTranslations[m.id].source === 'ai' && !showOriginal[m.id] ? msgTranslations[m.id].translated_text : m.body}</p>
                        {m.attachment && <a href={m.attachment.url} target="_blank" rel="noreferrer" className={`mt-1 inline-flex items-center gap-1 text-xs underline ${mine ? 'text-white' : 'text-brand'}`}><Paperclip className="w-3 h-3" />{m.attachment.name}</a>}
                        {msgTranslations[m.id]?.source === 'template' && (
                          <p className={`mt-1 text-xs italic whitespace-pre-wrap ${mine ? 'text-white/90' : 'text-slate-600'}`}>{msgTranslations[m.id].translated_text}</p>
                        )}
                        {msgTranslations[m.id]?.source === 'ai' && (
                          <p className={`mt-1 text-[10px] ${mine ? 'text-white/80' : 'text-slate-500'}`}>
                            {showOriginal[m.id] ? 'Original' : 'Machine translated'}{' · '}
                            <button className="underline font-semibold" onClick={() => setShowOriginal((o) => ({ ...o, [m.id]: !o[m.id] }))}>{showOriginal[m.id] ? 'Show translation' : 'Show original'}</button>
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <p className={`text-[10px] ${mine ? 'text-white/70' : 'text-slate-500'}`}>{new Date(m.at).toLocaleString()}</p>
                          {!msgTranslations[m.id] && <button onClick={() => translateMessage(m.id)} disabled={translatingMsg === m.id}
                            className={`inline-flex items-center gap-0.5 text-[10px] font-semibold hover:underline disabled:opacity-50 ${mine ? 'text-white/80' : 'text-brand'}`}>
                            {translatingMsg === m.id ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Languages className="w-2.5 h-2.5" />} Translate
                          </button>}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={bottom} />
              </div>
              <footer className="p-3 border-t border-slate-100 space-y-2">
                {file && <p className="text-xs text-slate-600">Attached: {file.name} <button onClick={() => setFile(null)} className="underline">remove</button></p>}
                <div className="flex gap-2 items-end">
                  <label className="p-2 rounded-lg hover:bg-slate-100 cursor-pointer" aria-label="Attach a file"><Paperclip className="w-4 h-4" /><input type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
                  <textarea rows={2} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm resize-none" placeholder="Write a reply" value={reply} aria-label="Reply"
                    onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send(); }} />
                  <button onClick={send} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold"><Send className="w-4 h-4" /> Send</button>
                </div>
                <p className="text-[11px] text-slate-400">Ctrl + Enter to send. Everyone in the conversation gets an email and a notice.</p>
              </footer>
            </>
          )}
        </section>
      </div>
      {composing && <Compose onClose={() => setComposing(false)} onStarted={(id) => { setComposing(false); loadList(); setParams({ c: id }); }} />}
    </div>
  );
}

function Compose({ onClose, onStarted }: { onClose: () => void; onStarted: (id: string) => void }) {
  const { role } = useAuth();
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [to, setTo] = useState<string[]>([]);
  const [find, setFind] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  useEffect(() => { messaging.contacts().then(setContacts).catch(() => setContacts([])); }, []);
  const matches = useMemo(() => (contacts || []).filter((c) => !to.includes(c.id) && (!find || `${c.name} ${c.email} ${c.about.join(' ')}`.toLowerCase().includes(find.toLowerCase()))).slice(0, 30), [contacts, to, find]);
  const send = async () => {
    try { const c = await messaging.start({ participants: to, subject, body }); toast.success('Message sent'); onStarted(c.id); }
    catch (e: any) { toast.error(e?.response?.data?.error || 'Could not send the message.'); }
  };
  return (
    <Modal open onClose={onClose} title="New message" size="lg"
      footer={<div className="flex justify-end gap-2"><button onClick={onClose} className="px-4 py-2 rounded-lg bg-slate-100 text-sm font-semibold">Cancel</button><button disabled={!to.length || !subject.trim() || !body.trim()} onClick={send} className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-50">Send</button></div>}>
      <div className="space-y-3 text-sm">
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1" htmlFor="cm-to">To</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {to.map((id) => { const c = contacts?.find((x) => x.id === id); return <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-soft text-xs font-semibold">{c?.name}<button onClick={() => setTo(to.filter((x) => x !== id))} aria-label={`Remove ${c?.name}`}>×</button></span>; })}
          </div>
          <input id="cm-to" className="w-full rounded-lg border border-slate-300 px-3 py-2" placeholder="Search teachers, parents or the office" value={find} onChange={(e) => setFind(e.target.value)} />
          <ul className="mt-1 max-h-44 overflow-y-auto border border-slate-100 rounded-lg divide-y divide-slate-50">
            {!contacts ? <li className="p-2"><Loader2 className="w-4 h-4 animate-spin" /></li> : matches.map((c) => (
              <li key={c.id}><button onClick={() => { setTo([...to, c.id]); setFind(''); }} className="w-full text-left px-3 py-1.5 hover:bg-slate-50"><b>{c.name}</b> <span className="text-xs text-slate-500">{c.role}{c.about.length ? ` · ${c.about.join(', ')}` : ''}</span></button></li>
            ))}
            {contacts && matches.length === 0 && <li className="px-3 py-2 text-slate-500">No one matches.</li>}
          </ul>
        </div>
        {(role === 'teacher' || role === 'admin') && <DraftWithAi onDraft={(d) => { setSubject(d.subject); setBody(d.body); }} />}
        <div><label className="block text-xs font-semibold text-slate-600 mb-1" htmlFor="cm-sub">Subject</label><input id="cm-sub" className="w-full rounded-lg border border-slate-300 px-3 py-2" value={subject} onChange={(e) => setSubject(e.target.value)} /></div>
        <div><label className="block text-xs font-semibold text-slate-600 mb-1" htmlFor="cm-body">Message</label><textarea id="cm-body" rows={5} className="w-full rounded-lg border border-slate-300 px-3 py-2" value={body} onChange={(e) => setBody(e.target.value)} /></div>
      </div>
    </Modal>
  );
}
