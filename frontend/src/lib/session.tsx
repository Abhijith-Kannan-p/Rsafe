import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, post, type Identity, type Role } from "./api";

type Ctx = {
  identity: Identity | null;
  loading: boolean;
  signIn: (role: Role, schoolCode?: string) => Promise<Identity>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<Ctx | null>(null);

export const HOME: Record<Role, string> = {
  principal: "/app/dashboard",
  teacher: "/app/classes",
  mis_coordinator: "/app/cluster",
  admin: "/app/audit",
  student_parent: "/app/my-record",
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{ identity: Identity | null }>("/session/status")
      .then((r) => setIdentity(r.identity))
      .catch(() => setIdentity(null))
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (role: Role, schoolCode?: string) => {
    const id = await post<Identity>("/session", schoolCode ? { role, school_code: schoolCode } : { role });
    setIdentity(id);
    return id;
  }, []);

  const signOut = useCallback(async () => {
    await api("/session", { method: "DELETE" });
    setIdentity(null);
  }, []);

  const value = useMemo(() => ({ identity, loading, signIn, signOut }), [identity, loading, signIn, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}

/** Same identity, guaranteed present: use inside the signed-in app shell only. */
export function useIdentity(): Identity {
  const { identity } = useSession();
  if (!identity) throw new Error("useIdentity used without a session");
  return identity;
}

export const can = {
  act: (r: Role) => r === "principal" || r === "teacher",
  hold: (r: Role) => r === "principal",
  validate: (r: Role) => r === "principal" || r === "mis_coordinator" || r === "admin",
  upload: (r: Role) => r === "principal",
  export: (r: Role) => r === "principal" || r === "mis_coordinator",
  audit: (r: Role) => r === "admin",
  cluster: (r: Role) => r === "mis_coordinator" || r === "admin",
  pickSchool: (r: Role) => r === "principal" || r === "teacher",
};
