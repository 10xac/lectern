// The api module with every client function replaced by a vi.fn(); types and ApiError stay real.
// Use with: vi.mock('../api', () => import('../test/apiMock')).
import { vi } from 'vitest';

const real = await vi.importActual<typeof import('../api')>('../api');

export const ApiError = real.ApiError;
export const setCsrf = vi.fn();
export const api = Object.fromEntries(Object.keys(real.api).map((name) => [name, vi.fn()])) as unknown as typeof real.api;
