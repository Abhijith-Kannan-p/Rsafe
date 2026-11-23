// Landing-page copy. Swap MOTTO for one of the alternates to change the hero line.
export const MOTTO = "Every record, right before it counts.";

export const MOTTO_ALTERNATES = [
  "Clean data. Safe students.",
  "Catch it before the portal does.",
] as const;

export const SYNTHETIC_LINE = "Prototype with synthetic data.";

export const TEAM = "kabhijith447";
export const EVENT = "PRASUNEX INNOVATHON 2026";

/**
 * Landing showcase. `file` names must match what scripts/make_screenshots.mjs writes into
 * frontend/public/shots/. A file missing from shots/manifest.json shows a placeholder frame.
 */
export const SHOWCASE = [
  {
    file: "01-upload.png",
    path: "/app/upload",
    title: "Upload a messy school file",
    caption:
      "Drop in the school's own export. Rsafe maps the columns, lists blocking errors and warnings by row number, and saves nothing until a person confirms. Every rule runs on import.",
  },
  {
    file: "02-dashboard.png",
    path: "/app/dashboard",
    title: "Readiness score and issue list",
    caption:
      "One number for how close the school is to a clean submission, with every open problem listed by severity, rule and record.",
  },
  {
    file: "03-issue.png",
    path: "/app/dashboard?issue=…",
    title: "Every flag explains itself",
    caption:
      "Open a high-severity issue to see the rule that fired, the evidence it used, the record's own values with the problem field highlighted, and a suggested fix to approve, edit or hold.",
  },
  {
    file: "04-held.png",
    path: "/app/dashboard?issue=…",
    title: "Dropout flags wait for a person",
    caption:
      "A possible dropout is never removed automatically. Rsafe holds it, and only the principal can release it after checking with the family.",
  },
  {
    file: "05-duplicates.png",
    path: "/app/duplicates",
    title: "One student, two schools",
    caption:
      "The same child enrolled in two schools is found by a keyed token of the ID, not by name, so look-alike names are not merged and raw IDs never leave the school.",
  },
  {
    file: "06-audit.png",
    path: "/app/audit",
    title: "A log that shows tampering",
    caption:
      "Each audit row's hash covers the row before it. Edit one row directly in the database and Verify chain points straight at it.",
  },
  {
    file: "07-cluster.png",
    path: "/app/cluster",
    title: "The whole cluster at a glance",
    caption:
      "The MIS coordinator sees every school as ready, fixing or blocked, and can open any school to see what is holding it back.",
  },
] as const;
