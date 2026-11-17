// Testing Library only cleans up automatically when vitest globals are on; we keep them off.
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// The first render in a file also loads the app's modules; on a busy CI machine that can take
// longer than the default one second that findBy* waits.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());
