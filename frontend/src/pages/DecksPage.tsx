import { Presentation } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { api, type DeckSummary } from '../api';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { UploadButton } from '../components/UploadButton';
import { VisibilityBadge } from '../deck/VisibilityBadge';
import { Page } from '../layout/AppShell';
import { useLoad } from '../lib/useLoad';

const SOURCE = {
  html: { label: 'HTML', tone: 'cyan' },
  pptx: { label: 'PowerPoint', tone: 'orange' },
  gslides: { label: 'Google Slides', tone: 'teal' },
} as const;

function DeckCard({ deck }: { deck: DeckSummary }) {
  const source = SOURCE[deck.source] ?? SOURCE.html;
  return (
    <li>
      <Link to={`/deck/${deck.id}`} className="group block h-full rounded-lg border border-line-soft bg-surface transition-shadow hover:shadow-card focus-visible:shadow-card">
        <div className="flex aspect-video items-center justify-center rounded-t-lg bg-gradient-to-br from-brand-soft to-surface-sunken">
          <Presentation className="h-10 w-10 text-brand/60 transition-transform group-hover:scale-110" aria-hidden />
        </div>
        <div className="p-4">
          <h2 className="truncate font-display text-base font-medium text-ink-strong group-hover:text-brand">{deck.title}</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <StatusBadge tone={source.tone}>{source.label}</StatusBadge>
            <VisibilityBadge visibility={deck.visibility} />
          </div>
        </div>
      </Link>
    </li>
  );
}

/** Every deck as a card, with the upload button. */
export function DecksPage() {
  const { data, error } = useLoad(api.listDecks);
  const navigate = useNavigate();
  const upload = (
    <UploadButton label="Upload deck" variant="primary" accept=".html,.htm,.pptx,.json" upload={api.uploadDeck} onDone={(d) => navigate(`/deck/${d.id}`)} />
  );
  return (
    <Page>
      <PageHeader title="Decks" description="Upload an HTML artifact, a PowerPoint file or a Google Slides export. Every slide gets its own agent." actions={upload} />
      <ErrorText>{error}</ErrorText>
      {!data && !error && <p className="text-ink-muted" role="status">Loading decks…</p>}
      {data?.length === 0 && <EmptyState title="No decks yet" description="Upload one, or run make seed on the server." action={upload} />}
      {data && data.length > 0 && (
        <ul aria-label="Decks" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {data.map((d) => <DeckCard key={d.id} deck={d} />)}
        </ul>
      )}
    </Page>
  );
}
