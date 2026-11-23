# Rsafe: five-minute demo script

A click-by-click story for the PRASUNEX INNOVATHON 2026 demo. Every number below comes from a dry run on
freshly seeded data. If you reset before presenting, you will see the same numbers.

## Before you start (2 minutes, off stage)

```
npm run seed    # resets the demo: fresh data, empty audit log
npm run dev     # leave running
```

- Open http://127.0.0.1:5173 in a browser window about 1440 px wide, zoom 100%.
- Close other tabs. Keep this script on a second screen.
- If something goes wrong mid-demo, reset: as Admin, **System → Reset demo data** (or `npm run seed`), then
  reload. That takes about 3 seconds.
- **Short on time or presenting alone?** Press **Tour** in the top bar (or "Or take the guided tour" on the
  landing page). A card walks this same story in 10 steps, switching role and screen for you and
  outlining what to look at. Step 1 offers **Reset demo data first**.

## The story

### 0:00 – Landing (30 s)

- **Show:** the "Rsafe" title fading in, then the motto.
- **Say:** "Every year schools submit records to UDISE+. Wrong names, impossible birth dates, duplicate
  enrolments and wrong dropout flags get rejected, or worse, accepted wrong. Rsafe catches them while the
  school can still fix them, and a person decides every fix."
- **Click:** **Scroll down**, and let two or three showcase steps slide in.
- **Scroll** to **How it works** and point at the saffron marker: "Raw IDs stop at the school. Aadhaar
  becomes keyed tokens on import, and only the last four digits are kept."
- **Click:** **Enter Rsafe**, then **Principal → Enter**.

### 0:30 – Principal imports the school's file (45 s)

- **You land on** the Dashboard for *Govt UP School Hillview (SYN-0002)*: readiness **87%**, 61 students,
  6 high and 6 medium issues.
- **Click:** **Upload** in the sidebar, then **Load sample messy file**.
- **Say:** "This is the school's own export, with its own column names. Rsafe matched the columns itself.
  Nothing is saved yet."
- **Point at:**
  - **Error summary:** row 22 has '31/02/2015', which is not a real date, and row 25 has an empty date of
    birth.
  - **Row preview:** the Aadhaar column shows only `XXXX XXXX` and the last four digits.
- **Click:** **Import and validate**, then **Import 61 records**. Every rule has now run on every record.
- **Click:** **Review issues →**.

### 1:15 – Explain and fix (60 s)

- **Set** the **Rule** filter to **STU-005** and click **Ananya Kumar**. The issue panel opens.
- **Say:** "Every flag explains itself:
  - the rule ID and version,
  - the reason in plain language,
  - the evidence it used: the admission register says 'Ananya R. Kumar',
  - and a suggested fix, shown as a word diff."
- **Open** "Why was this flagged? How Rsafe decided" for a moment. It shows the rule version, the check
  that ran, the data it read and the rule's settings.
- **Type a note** (optional), for example "Matches the admission register", then click **Approve fix**.
  The toast reads "Written to the audit log as entry #…".
- **Press Esc.** Set **Rule** to **STU-002** and click the **31/02/2015** row.
- **Point at** the smart suggestion: **25/07/2016**, with "Why this value: High: taken from the school's
  admission register".
- **Say:** "Rsafe only suggests what it can back with evidence. If the suggestion were wrong I could press
  Reject suggestion and type the right date. Here the register is right, so I approve it."
- **Click:** **Approve fix**. The readiness ring and the **Readiness over time** line both rise to **89%**.
  Hover over the last point: the tooltip names the fix that caused the change.
- **Say:** "Nothing changed by itself. Both changes are in the audit log under my name."
- **Optional:** type an Aadhaar-like number into a note. Rsafe refuses it, because notes are kept forever.

### 2:15 – A dropout flag that Rsafe will not apply (30 s)

- **In the top bar**, switch school to **SYN-0001 · Govt Model School Riverside**.
- **Point at:** the **Held dropout flags** panel, with two students.
- **Say:** "Both are marked as dropouts, but the attendance register shows 13 days in the last month.
  Marking a child who still attends as a dropout can cut them off from benefits."
- **Click** a card and point at the banner: "Held for a person to review. Rsafe has not applied this flag
  and has not changed the record."

### 2:45 – The same child in two schools (45 s)

- **Click:** **Duplicates** in the sidebar.
- **Point at** the pair ending **3125**: SYN-0001 and SYN-0002.
- **Say:** "Here the names are 'Bhavya Rao' and 'Bhavya R.'; in the other pair, 'Sachin Gupta' and
  'SACHIN GUPTA'. Name matching is fragile, so Rsafe never matches on names. Each school turns the Aadhaar
  number into a token with a cluster key. Same child, same token, and no raw ID ever left either school."
- **Point at** the other school's side, which reads "Not in your scope": this principal sees only their own
  student.

### 3:30 – The MIS coordinator's cluster view (30 s)

- **Switch** "Demo as" to **MIS Coordinator**. You land on the Cluster screen.
- **Say:** "All three schools are Blocked: each still has a high-severity or held issue. Old Town has
  merged into Riverside, so it shows greyed out."
- **Hover over** *Govt High School Lakeside* to show its blocking reasons, then click it to drill in.
- **Say:** "As schools decide their flags, tiles turn Fixing, then Ready." The landing page's last
  screenshot shows that mix.

### 4:00 – Proof that nobody quietly edited anything (40 s)

- **Switch** to **Admin**. You land on the Audit log.
- **Point at:** the rows from this demo:
  - `data.import`
  - `issue.approve` (Ananya)
  - `issue.edit` (the date)
  - a `validation.run` after each one
- **Click:** **Verify chain**. It reports "Chain intact: N rows verified".
- **Say:** "Each row's hash covers the row before it. Now I'll play an attacker who edits the database
  directly."
- **Click:** **Tamper row (demo)**, then **Verify chain**. You see "Tampering detected at row #…", and the
  row is highlighted as BROKEN.

### 4:40 – Close (20 s)

- **Say:** "Rsafe checks every record before it counts, and leaves every decision to a person. Everything
  you saw ran locally on synthetic data, with no calls to UIDAI or any portal. A person exports the clean
  file and uploads it to UDISE+ by hand."

## If you have extra time

- **Parent view:** switch to **Student and Parent**.
  - Ananya's name now shows as "Ananya R. Kumar", and that check reads "Sorted".
  - Switch the language picker to **हिन्दी** or **മലയാളം**. The reasons change language, each marked
    "Machine translation. Not yet reviewed".
  - Click **Something is wrong**, type a short comment, then **Send me a code**.
  - Type the demo code shown on screen and click **Verify and send**.
  - Say: "This is a mockup. No SMS is sent, and the reply goes to the audit log without changing the record."
- **Test submit:** as **Principal**, open **Export** and press **Test submit**. Every rule runs again and
  each row shows whether it would be sent, sent with a flag, likely rejected or held back. Nothing is
  exported.
- **Report:** on the same screen, **Open report**. The one-page readiness report has an audit summary
  (who did what, and readiness from the first run to now), the chain's head hash, and the decisions, held
  flags and parent replies.
- **Command palette:** press **Ctrl+K** and type "bhavya" or "STU-007" to jump straight to a student or rule.
- **Coverage:** **Coverage** in the sidebar groups the rules by the failure reason each one addresses, with
  what each has caught.
- **System (Admin):** live validation timings per 1,000 records, and **Reset demo data**.
- **Teacher:** switch to **Teacher** to see *My classes*: only their own students, each problem as a rule
  badge.
- **Rules:** the **Rules** screen lists all 11 rules with their version and the government failure reason
  each one addresses.

## Likely questions

- **"Can tokens be reversed?"**
  - With the key, yes: 12-digit numbers are few enough to brute-force. Tokens are pseudonyms that protect IDs
    only while the keys stay secret.
  - A real deployment keeps each school's key at the school. The README's privacy section covers the limits.
- **"Does it verify Aadhaar?"** No. It checks only that the number has 12 digits. It makes no UIDAI calls.
- **"How fast is it?"** On 5,004 synthetic students, the rule engine takes 0.1 to 0.3 s and a full validation
  0.7 to 1.8 s on a laptop (`npm run bench`).
- **"Is it accessible?"** Lighthouse accessibility scores 100 on every main screen.
- **"What if Rsafe is wrong?"** Nothing is applied without a person. Every decision can be traced in the
  audit log. Dropout flags are always held.
