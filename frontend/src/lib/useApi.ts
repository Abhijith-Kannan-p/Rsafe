import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** GET a path; re-fetches when the path changes or `reload()` is called. Keeps old data while reloading. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [tick, setTick] = useState(0);
  const latest = useRef(0);

  useEffect(() => {
    if (path === null) return;
    const id = ++latest.current;
    setLoading(true);
    api<T>(path)
      .then((d) => {
        if (id === latest.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: Error) => id === latest.current && setError(e))
      .finally(() => id === latest.current && setLoading(false));
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
