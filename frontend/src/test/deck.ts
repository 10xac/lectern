import type { Answer, Deck } from '../api';

export const DECK: Deck = {
  id: 7,
  title: 'Test deck',
  source: 'html',
  visibility: 'private',
  outline: '1. Intro\n2. Plan\n3. Risks',
  slides: [
    { n: 1, title: 'Intro', body: 'Hello', notes: 'Say hi', html: '<section><h1 data-lectern-id="s1.title">Intro</h1></section>', persona: null },
    { n: 2, title: 'Plan', body: 'Step one\nStep two', notes: '', html: null, persona: null },
    { n: 3, title: 'Risks', body: 'Weather', notes: 'Bring umbrellas', html: null, persona: null },
  ],
  attachments: [{ id: 4, deck_id: 7, name: 'data.csv', chunks: 2 }],
};

export function answerFor(slide: number | null, question: string): Answer {
  return {
    answer: `Answer to "${question}" on ${slide ?? 'deck'}. [slide:3:notes]`,
    citations: [
      { block_id: 'slide:3:notes', slide: 3, attachment: null },
      { block_id: 'att:4:1', slide: null, attachment: 4 },
    ],
    agent: `slide-${slide ?? 'deck'}`,
    trace_id: 11,
    outcome: 'done',
    confidence: {
      verdict: 'answer', why: 'the deck holds it',
      triage: { by: 'rules', class: 'deck', engage: 1, hops: 1, note: '' },
      fusion: { best: 'K', p_best: 0.82, z: 1.1, kappa: 0.1 },
      sources: [{ source: 'K', status: 'done', r: 0.9, g: 0.1, reason: '' }],
    },
  };
}
