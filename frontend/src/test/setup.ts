// Testing Library only cleans up automatically when vitest globals are on; we keep them off.
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => cleanup());
