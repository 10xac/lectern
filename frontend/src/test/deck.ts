import type { Answer, Deck } from '../api';

export const DECK: Deck = {
  id: 7,
  title: 'Test deck',
  source: 'html',
  outline: '1. Intro\n2. Plan\n3. Risks',
  slides: [
    { n: 1, title: 'Intro', body: 'Hello', notes: 'Say hi', html: '<section><h1>Intro</h1></section>', persona: null },
    { n: 2, title: 'Plan', body: 'Step one\nStep two', notes: '', html: null, persona: null },
    { n: 3, title: 'Risks', body: 'Weather', notes: 'Bring umbrellas', html: null, persona: null },
  ],
  attachments: [{ id: 4, deck_id: 7, name: 'data.csv', chunks: 2 }],
};

export function answerFor(slide: number, question: string): Answer {
  return {
    answer: `Answer to "${question}" on ${slide}. [slide:3:notes]`,
    citations: [
      { block_id: 'slide:3:notes', slide: 3, attachment: null },
      { block_id: 'att:4:1', slide: null, attachment: 4 },
    ],
    agent: `slide-${slide}`,
    trace_id: 11,
    outcome: 'done',
  };
}
