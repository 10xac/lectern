import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { chipLabel, CitationChip } from './CitationChip';

describe('CitationChip', () => {
  it('labels every kind of block id', () => {
    expect(chipLabel('slide:4:notes')).toBe('slide 4 · notes');
    expect(chipLabel('att:2:0')).toBe('data 2 · part 1');
    expect(chipLabel('deck:outline')).toBe('outline');
  });

  it('calls onJump with its citation', () => {
    const onJump = vi.fn();
    const citation = { block_id: 'slide:2:body', slide: 2, attachment: null };
    render(<CitationChip citation={citation} onJump={onJump} />);
    const chip = screen.getByRole('button', { name: 'slide 2 · body' });
    expect(chip.getAttribute('title')).toBe('slide:2:body');
    fireEvent.click(chip);
    expect(onJump).toHaveBeenCalledWith(citation);
  });
});
