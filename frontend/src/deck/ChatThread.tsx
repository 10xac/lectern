import { Bot, Send, TriangleAlert } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import type { Citation } from '../api';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { TextArea } from '../components/ui/Field';
import type { Message, useSlideChat } from '../hooks/useSlideChat';
import { cn } from '../lib/cn';
import { CitationChip, stripMarkers } from './Citations';
import { ConfidenceChips, Votes } from './Confidence';
import { JobLanes } from './JobLanes';

interface Props {
  /** The thread, from `useSlideChat` (kept by the caller so running questions survive a tab switch). */
  chat: ReturnType<typeof useSlideChat>;
  /** The slide being asked; null for the whole deck. */
  slide: number | null;
  onJump: (citation: Citation) => void;
  onTrace: (traceId: number) => void;
}

function Bubble({ m, onJump, onTrace }: { m: Message } & Pick<Props, 'onJump' | 'onTrace'>) {
  if (m.role === 'user') {
    return <li className="ml-auto max-w-[85%] rounded-lg rounded-br-sm bg-brand px-3 py-2 text-sm text-white">{m.text}</li>;
  }
  return (
    <li className={cn('max-w-[95%] rounded-lg rounded-bl-sm border bg-surface px-3 py-2 text-sm', m.failed ? 'border-danger-line bg-danger-soft' : 'border-line-soft')}>
      {m.agent && (
        <span className="mb-1 flex items-center gap-1 text-xs text-ink-muted"><Bot className="h-3 w-3" aria-hidden />{m.agent}</span>
      )}
      {m.failed && <TriangleAlert className="mr-1 inline h-3.5 w-3.5 text-danger" aria-hidden />}
      <p className="whitespace-pre-wrap text-ink">{stripMarkers(m.text)}</p>
      {m.citations && m.citations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{m.citations.map((c) => <CitationChip key={c.block_id} citation={c} onJump={onJump} />)}</div>
      )}
      {(m.confidence || m.jobId || m.traceId != null) && (
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-line-soft pt-2">
          {m.confidence && <ConfidenceChips confidence={m.confidence} />}
          <span className="ml-auto flex items-center gap-2">
            {m.jobId && <Votes jobId={m.jobId} />}
            {m.traceId != null && <Button variant="link" size="sm" onClick={() => onTrace(m.traceId!)}>trace</Button>}
          </span>
        </div>
      )}
    </li>
  );
}

/** A conversation with one slide's agent (or the deck's): the thread, running questions, the ask box. */
export function ChatThread({ chat, slide, onJump, onTrace }: Props) {
  const { messages, jobs, send } = chat;
  const [draft, setDraft] = useState('');
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Scroll only the thread (never the page, as scrollIntoView would on phones).
    const node = list.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, jobs.length]);
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!draft.trim()) return;
    void send(draft.trim());
    setDraft('');
  };
  const who = slide === null ? 'the deck' : `slide ${slide}`;
  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label={slide === null ? 'Chat with the deck' : `Chat with slide ${slide}`}>
      <div ref={list} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && jobs.length === 0 && (
          <EmptyState icon={<Bot className="h-8 w-8" />} title={`Ask ${who}`} description="Answers cite the slides, data and references they used." className="py-6" />
        )}
        <ul className="flex flex-col gap-3">{messages.map((m, i) => <Bubble key={i} m={m} onJump={onJump} onTrace={onTrace} />)}</ul>
        <JobLanes jobs={jobs} />
      </div>
      <form onSubmit={submit} className="flex items-end gap-2 border-t border-line-soft p-3">
        <TextArea aria-label="Question" compact rows={1} className="max-h-40 flex-1" placeholder={slide === null ? 'Ask about the whole deck…' : 'What does this slide mean?'}
          value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }} />
        <Button type="submit" variant="primary" aria-label="Ask" disabled={!draft.trim()}><Send className="h-4 w-4" aria-hidden /> Ask</Button>
      </form>
    </section>
  );
}
