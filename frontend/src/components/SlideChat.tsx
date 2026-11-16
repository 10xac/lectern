import { useState, type FormEvent } from 'react';
import type { Citation } from '../api';
import { useSlideChat } from '../hooks/useSlideChat';
import { CitationChip } from './CitationChip';
import { ConfidenceChips } from './Confidence';
import { JobLanes } from './JobLanes';

/** Citation markers like [slide:4:notes] are shown as chips, so they are removed from the text. */
export const stripMarkers = (text: string) => text.replace(/\s*\[[a-z]+(?::[\w.-]+)+\]/g, '').trim();

interface Props {
  deckId: number;
  slide: number;
  onJump: (citation: Citation) => void;
  onTrace: (traceId: number) => void;
}

/** The chat with the current slide's agent. */
export function SlideChat({ deckId, slide, onJump, onTrace }: Props) {
  const { messages, jobs, send } = useSlideChat(deckId, slide);
  const [draft, setDraft] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    void send(draft.trim());
    setDraft('');
  };

  return (
    <section className="chat" aria-label={`Chat with slide ${slide}`}>
      <h2>Ask slide {slide}</h2>
      <ul className="messages">
        {messages.map((m, i) => (
          <li key={i} className={`message ${m.role}${m.failed ? ' failed' : ''}`}>
            {m.agent && <span className="agent">{m.agent}</span>}
            <p>{m.role === 'agent' ? stripMarkers(m.text) : m.text}</p>
            {m.citations && m.citations.length > 0 && (
              <div className="chips">
                {m.citations.map((c) => (
                  <CitationChip key={c.block_id} citation={c} onJump={onJump} />
                ))}
              </div>
            )}
            {m.confidence && <ConfidenceChips confidence={m.confidence} jobId={m.jobId} />}
            {m.traceId != null && (
              <button type="button" className="link" onClick={() => onTrace(m.traceId!)}>
                trace
              </button>
            )}
          </li>
        ))}
      </ul>
      <JobLanes jobs={jobs} />
      <form onSubmit={submit}>
        <input
          aria-label="Question"
          value={draft}
          placeholder="What does this slide mean?"
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit">Ask</button>
      </form>
    </section>
  );
}
