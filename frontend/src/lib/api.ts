// Thin fetch wrapper. Requests go through the Vite proxy (/api -> :8765) with cookies.
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const OFFLINE_MESSAGE = "Can't reach the Rsafe server. Is npm run dev still running?";
/** Fired when the server says the session is gone, so the app can send the user back to /enter. */
export const SESSION_LOST = "rsafe:session-lost";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      credentials: "include",
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, OFFLINE_MESSAGE);
  }
  // the Vite proxy answers 502/503/504 (or 500 with no JSON body) when the API process is down
  if ([502, 503, 504].includes(res.status) || (res.status === 500 && !res.headers.get("content-type")?.includes("json"))) {
    throw new ApiError(res.status, OFFLINE_MESSAGE);
  }
  if (res.status === 401 && !path.startsWith("/session")) window.dispatchEvent(new Event(SESSION_LOST));
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg ?? detail : detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

export const post = <T>(path: string, body: unknown = {}) => api<T>(path, { method: "POST", body: JSON.stringify(body) });

export const qs = (params: Record<string, string | undefined | null>) => {
  const p = Object.entries(params).filter(([, v]) => v) as [string, string][];
  return p.length ? `?${new URLSearchParams(p)}` : "";
};

export type Health = { status: string; version: string; synthetic: boolean };

export type Role = "principal" | "teacher" | "mis_coordinator" | "admin" | "student_parent";

export type Identity = {
  role: Role;
  actor: string;
  school_code: string | null;
  cluster: string | null;
  teacher_ref: string | null;
  student_ref: string | null;
};

export type Severity = "high" | "medium" | "low";
export type IssueStatus = "open" | "held" | "approved" | "edited" | "resolved";

export type SchoolSummary = {
  school_code: string;
  name: string;
  students: number;
  readiness: number;
  by_severity: Partial<Record<Severity, number>>;
  by_status: Partial<Record<IssueStatus, number>>;
  active: number;
  held: number;
};

export type Issue = {
  id: number;
  rule_id: string;
  rule_version: string;
  severity: Severity;
  entity: "student" | "teacher" | "facility";
  entity_ref: string;
  school_code: string;
  title: string;
  message: string;
  detail: string;
  fix: string;
  confidence: string | null;
  suggested_value: string | null;
  suggested_field: string | null;
  evidence: Record<string, unknown>;
  status: IssueStatus;
  note: string | null;
  acted_by: string | null;
  created_at: string;
  updated_at: string;
};

export type IssueDetail = Issue & {
  record: Record<string, string | number | null>;
  editable_fields: string[];
  rule: { id: string; version: string; title: string; addresses: string } | null;
};

export type ActionResult = { issue: Issue; audit_id: number; summary: SchoolSummary };

export type Rule = {
  id: string;
  version: string;
  title: string;
  severity: Severity;
  entity: string;
  scope: string;
  check: string;
  message: string;
  fix: string;
  addresses: string;
  hold: boolean;
  params: Record<string, unknown>;
};
export type RuleDetail = Rule & { source: string };

export type AuditRow = {
  id: number;
  ts: string;
  actor: string;
  role: string;
  action: string;
  record_ref: string;
  payload: Record<string, unknown>;
  hash: string;
  short_hash: string;
  prev_hash: string;
};

export type ChainReport = {
  ok: boolean;
  checked: number;
  first_broken_id: number | null;
  reason: string | null;
  head_hash: string | null;
};

export type UploadProblem = { row: number; field: string; level: "error" | "warning"; message: string };
export type UploadPreview = {
  headers: string[];
  fields: { field: string; label: string; required: boolean }[];
  mapping: Record<string, string>;
  rows_total: number;
  rows: { row: number; values: Record<string, string>; problems: UploadProblem[] }[];
  problems: UploadProblem[];
  file_errors: string[];
  counts: { errors: number; warnings: number; rows_with_problems: number };
  can_import: boolean;
};
export type UploadResult = {
  imported: number;
  replaced: number;
  summary: SchoolSummary;
  changes: { added: number; reopened: number; resolved: number };
};

export const ROLE_LABEL: Record<Role, string> = {
  principal: "Principal",
  teacher: "Teacher",
  mis_coordinator: "MIS Coordinator",
  admin: "Admin",
  student_parent: "Student and Parent",
};

/** Students-weighted readiness across several schools. */
export function overallReadiness(schools: SchoolSummary[]): number {
  const n = schools.reduce((a, s) => a + s.students, 0);
  if (!n) return 100;
  return Math.round(schools.reduce((a, s) => a + s.readiness * s.students, 0) / n);
}

export type SchoolOption = { code: string; name: string; cluster: string };

export type ClusterStatus = "ready" | "fixing" | "blocked";
export type ClusterReason = { rule_id: string; title: string; severity: Severity; count: number; held: number; blocking: boolean };
export type OpenTile = SchoolSummary & { cluster: string; status: ClusterStatus; reasons: ClusterReason[]; decided: number; resolved: number };
export type ClosedTile = { school_code: string; name: string; cluster: string; status: "merged" | "closed"; merged_into: string | null };
export type ClusterTile = OpenTile | ClosedTile;
export type ClusterView = { cluster: string; counts: Partial<Record<string, number>>; students: number; schools: ClusterTile[] };
export const isOpenTile = (t: ClusterTile): t is OpenTile => "readiness" in t;

export type IssueBrief = { id: number; rule_id: string; severity: Severity; status: IssueStatus; title: string };
export type ClassRoster = {
  class_grade: number;
  section: string;
  subjects: string[];
  active: number;
  students: { student_ref: string; name: string; gender: string; dob: string; issues: IssueBrief[]; active: number }[];
};
export type MyClasses = {
  teacher: { teacher_ref: string; name: string; subjects: string[] };
  school_code: string;
  classes: ClassRoster[];
  own_issues: IssueBrief[];
};

export type Confirmation = { ts: string; outcome: "correct" | "needs_change"; comment: string; audit_id: number };
export type MyRecord = {
  student: {
    student_ref: string;
    name: string;
    dob: string;
    gender: string;
    class_grade: number | null;
    section: string;
    guardian_name: string;
    aadhaar: string | null;
    aadhaar_status: string;
    enrolment_status: string;
  };
  school: { code: string; name: string };
  issues: { id: number; rule_id: string; severity: Severity; status: IssueStatus; title: string; message: string; fix: string }[];
  confirmation: Confirmation | null;
};
