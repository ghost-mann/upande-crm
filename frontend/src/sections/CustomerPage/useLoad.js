import { useEffect, useState } from 'react';

// Fetch-on-mount for a tab: re-runs when `deps` change, ignores late answers
// from a previous customer, and keeps the last good data while reloading.
export default function useLoad(fn, deps) {
  const [state, setState] = useState({ data: null, err: '', loading: true });
  useEffect(() => {
    let dead = false;
    setState((s) => ({ ...s, loading: true, err: '' }));
    fn()
      .then((data) => { if (!dead) setState({ data, err: '', loading: false }); })
      .catch((e) => { if (!dead) setState((s) => ({ ...s, err: e.message || 'Could not load', loading: false })); });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
