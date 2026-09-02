# Getting Things Done with jtask‑gui

A hands‑on, step‑by‑step guide to running a full **GTD** (Getting Things Done)
workflow in the jtask desktop app — capture, clarify, organise, review, engage —
without ever leaving the UI.

> jtask stores everything in plain Taskwarrior. Nothing in this guide writes a
> special file or a hidden format: the GTD board is just saved Taskwarrior
> filters, and "contexts", "waiting", "someday" are ordinary tags and
> Taskwarrior contexts. You can drop to `task` on the command line at any time
> and see the same data.

---

## 1. How GTD maps onto jtask

| GTD idea | In jtask | Mechanism |
|---|---|---|
| **Inbox** (capture everything) | Quick‑add bar / **Inbox** board column | a pending task with *no project and no tags* |
| **Next Actions** | **Next Actions** board column, `Ctrl+2` view | pending, not blocked/waiting/someday, **has a project or a tag** |
| **Waiting For** (delegated / blocked on someone) | **Waiting For** column, sidebar *Waiting For* | the `waiting` tag |
| **Someday / Maybe** | **Someday / Maybe** column, `jtask someday` | the `someday` tag |
| **Projects** (outcomes needing >1 step) | Taskwarrior `project:` + the Projects sidebar / report | the `project` attribute (supports `Parent.Child`) |
| **Contexts** (`@home`, `@calls`, `@office`) | Taskwarrior **contexts** *or* `@`‑style tags | sidebar *Contexts* section / `+@calls` tags |
| **Tickler / start date** | `scheduled:` or `wait:` date | task hidden until the date, then reappears |
| **Weekly Review** | walk the board + Reports + `jtask review` | — |
| **Engage** | Star, Timer, Mark‑done | `Ctrl+.`, `Ctrl+S`, `Ctrl+D` |

The **GTD board** is the home base. Everything below is reachable from it.

---

## 2. One‑time setup

1. Launch the app: `jtask-gui` (add a menu entry + icon once with
   `jtask-gui --install-desktop`).
2. Open the **GTD board**: press **`Ctrl+B`**, or in the left sidebar open
   **Boards → GTD**. The first time you toggle the board it loads the built‑in
   GTD preset automatically.
3. You'll see five columns, right‑to‑left in the Persian UI, left‑to‑right in
   English:

   ```
   Inbox → Next Actions → Waiting For → Someday / Maybe → Done
   ```

4. *(Optional, recommended)* Define a couple of **contexts** so you can focus
   the whole app on one area at a time. Contexts are defined in the **Raw
   Command Console** (`` Ctrl+` `` to open/close it):

   ```
   context define work    project:Work or +@office
   context define personal project:Home or +errand
   ```

   They then appear in the sidebar **Contexts** section — click one to activate,
   click **(No context)** to clear. An active context filters *every* view,
   the board included.

---

## 3. Step 1 — Capture (get it out of your head)

The goal is speed: never stop to categorise while capturing.

### 3a. Quick‑add bar (fastest)

The input strip at the very top is always available. Press **`Ctrl+N`** to jump
to it, type a line, press **Enter**. It stays focused so you can rattle off ten
things in a row.

- Plain text → lands in **Inbox** (no project, no tags):

  ```
  Call the landlord about the boiler
  ```

- You *may* pre‑classify inline with Taskwarrior syntax — a live preview shows
  what will be created:

  | you type | effect |
  |---|---|
  | `+errand` | adds tag `errand` |
  | `project:Home` | sets the project |
  | `pri:H` / `priority:H` | priority High |
  | `due:tomorrow` / `due:فردا` | due date (Jalali or relative accepted) |
  | `wait:1405-07-01` | hide until that date (tickler) |
  | `scheduled:monday` | start‑working date |

  Example: `Book dentist +calls project:Health due:friday`

### 3b. Full **Add Task** dialog

For anything that needs more than one field: press **`Ctrl+Shift+N`** or click
**Add task** in the toolbar. Fields: Description, Project, Tags, Priority
(High / Medium / Low), Due, Scheduled, Wait, Recurrence, Dependencies. Use the
**Templates ▾** menu to reuse a common shape (see §9).

### 3c. Raw Command Console

`` Ctrl+` `` opens a real `task` prompt for anything the UI doesn't surface —
`task add …`, bulk edits, `import`, and so on. Changes made here refresh the
UI immediately.

**Capture rule of thumb:** during a capture sweep, use 3a and dump everything
into Inbox. Classify in Step 2.

---

## 4. Step 2 — Clarify & Organise (process the Inbox to zero)

Work the **Inbox** column top to bottom. **Double‑click a card** to open it in
the edit panel (the app switches back to the list with the detail panel open on
the right; `Esc` closes it). For each item ask *"What is it? Is it actionable?"*
and apply one outcome:

| Decision | Do this in the edit panel | Card moves to |
|---|---|---|
| **Not actionable — trash** | select the row, press **`Del`** (confirms) | gone |
| **Not actionable — reference** | give it a `reference` tag (or park it in a "Reference" project) and mark it done, or keep it out of the way with `+someday` | out of Inbox |
| **Someday / maybe** | add the **`someday`** tag | **Someday / Maybe** |
| **Actionable, < 2 minutes** | just do it now, then **`Ctrl+D`** (mark done) | **Done** |
| **Actionable, delegate it** | add the **`waiting`** tag; add an annotation *"→ Sara, asked 1405‑06‑20"* (Annotations tab) | **Waiting For** |
| **Actionable, single next step** | set a **Project** *or* at least one **context tag** (e.g. `@calls`, `errand`) | **Next Actions** |
| **Actionable, multi‑step outcome** | set a **Project** name; add the *very next* physical action as its own task in that project (optionally tag it `next`) | **Next Actions** |
| **Do it at a specific time** | set **Due** (hard deadline) or **Scheduled** (when you'll start) | stays, shows in *Today* / *This Week* |
| **Do it after a date** | set **Wait** — it disappears until then | hidden (tickler) |

Why the mechanics work:

- **Inbox** = `status:pending -PROJECT -TAGGED`. The moment a task has *any*
  project or *any* tag it leaves Inbox.
- **Next Actions** = `status:pending -BLOCKED -waiting -someday ( +PROJECT or +TAGGED )`.
- Dragging a card between columns applies that column's action for you:
  **Waiting For** adds `waiting` (and clears `someday`), **Someday / Maybe**
  adds `someday` (and clears `waiting`), **Next Actions** clears both,
  **Done** completes the task. Dragging an Inbox card straight to *Next
  Actions* only clears waiting/someday — you still need to give it a project or
  tag, so prefer opening it.

Process until Inbox is empty. Do this at least once a day.

---

## 5. Step 3 — Organise projects

- Name projects as `Area.Project` for hierarchy, e.g. `Home.Kitchen`,
  `Work.Q3Launch`. The **Projects** section in the sidebar shows the tree with
  task counts; click one to filter the list to it.
- A **project is not a task** — it's the collection. Keep exactly **one Next
  Action** per active project in your Next Actions list; the rest of the
  project's steps can wait (tag them `someday`, or give them a `wait:` /
  `scheduled:` date, or make them depend on the current step so they show as
  **Blocked**).
- Use the **Dependencies** field (edit panel) to chain steps: `task B depends on
  task A` → B shows as Blocked and stays out of Next Actions until A is done.
- Right‑click a project in the sidebar to **rename** (updates sub‑projects
  and tasks), **set a colour**, or **delete**.

---

## 6. Step 4 — Contexts (choose actions by where/what you can do)

Two interchangeable styles — pick one and be consistent:

**A. Taskwarrior contexts** (recommended, they filter the whole app)
Define once in the console (`context define …`), then click in the sidebar
**Contexts** section. While *work* is active you literally cannot see personal
tasks anywhere — board, lists, reports.

**B. `@`‑style tags** (lightweight, per‑action)
Tag actions `@calls`, `@errands`, `@office`, `@home`, `@waiting`. To "enter" a
context, type its tag in the **filter field** (`Ctrl+F`): `+@calls`. Save that
as a named filter (see §8) so it's one click next time.

You can combine: a Taskwarrior context for the *area* (work vs personal) and
`@` tags for the *mode* (calls vs computer vs errands).

---

## 7. Step 5 — Engage (do the work)

From the **Next Actions** column (or the `Ctrl+2` list view):

| Action | How |
|---|---|
| Mark the 1–3 things you'll do next | select, **`Ctrl+.`** to **Star** — they show in the *Starred* view and a gold star on the card |
| Start a timer on a task | select, **`Ctrl+S`** — the running task + elapsed time show in the status bar; click it or **`Ctrl+Shift+S`** to stop |
| Complete a task | **`Ctrl+D`**, or drag the card to **Done**, or right‑click → done |
| Open / edit | **`Return`** or **`Ctrl+E`** or double‑click |
| Undo the last change | **`Ctrl+Z`** |
| See just today's agenda | sidebar **Today** (`Ctrl+1`) — due today; **This Week** for the week; **Overdue** for anything past due |

Bulk edits: select several rows (Ctrl/Shift‑click), right‑click → **Bulk
edit…**, or **Append / Prepend / Annotate** text on all of them at once.

---

## 8. Saved filters (your custom lists)

Any list you look at often can be a one‑click sidebar entry:

1. Press **`Ctrl+F`**, type a Taskwarrior filter — e.g. `+@calls status:pending`
   or `project:Work.Q3Launch -BLOCKED`. Or click the **filter builder** button
   for a guided form.
2. Click **Save** in the filter bar, give it a name. Use `Area/Name` to file it
   in a folder.
3. It appears under **Saved filters** with a live count.

Useful GTD ones:

| Name | Filter |
|---|---|
| `Agenda/Calls` | `+@calls status:pending` |
| `Agenda/Errands` | `+@errands status:pending` |
| `Review/No next action` | `status:pending +PROJECT` (then scan by project) |
| `Review/Stuck` | `status:pending +BLOCKED` |
| `Waiting/Overdue follow‑up` | `+waiting status:pending` |

---

## 9. Task templates (repeatable inputs)

For recurring *shapes* (not recurring tasks): open **Add Task**
(`Ctrl+Shift+N`), fill Project / Tags / Priority the way you want, then
**Templates ▾ → Save as a task template…**. Later, **Templates ▾ → <name>**
pre‑fills the form. You can also right‑click any task in the list → **Save as a
task template…**.

For truly repeating work (weekly report, monthly rent) use the **Recurrence**
field instead — that creates a Taskwarrior recurring task.

---

## 10. Step 6 — The Weekly Review

Do this once a week. The board makes it a walk from right to left (or left to
right in English):

1. **Get clear**
   - Empty the **Inbox** column (process every card — §4).
   - Empty your head: one more capture sweep into Inbox, then process.
   - Clear **Overdue** (sidebar) — reschedule or do.

2. **Get current**
   - **Next Actions**: is every entry still the *real* next physical action?
     Delete stale ones. Check every **active project** has exactly one.
   - **Waiting For**: for each, has it been long enough to nudge? Add/append an
     annotation with the date you followed up. Anything received → move on.
   - **Calendar / This Week**: look at what's actually scheduled.
   - **Projects** sidebar: scan the list. Any project with **no** task in Next
     Actions needs a next action added now.

3. **Get creative**
   - **Someday / Maybe**: skim it. Anything ready to activate? Remove `someday`,
     give it a project/tag → it moves to Next Actions.

4. **Numbers** (optional): open **Reports & charts** in the sidebar —
   *Burndown*, *History*, *Timesheet*, *Projects*, *Tags* — for a sense of
   throughput.

### Command‑line shortcut for the review

The CLI has a guided walkthrough that prints each review section as a table:

```bash
jtask review        # overdue, due this week, waiting‑for, someday,
                    # projects with no next action, stale (>30 days)
jtask someday       # just the Someday/Maybe list
jtask waiting       # just the Waiting‑For list
jtask projects      # project summary with progress
```

---

## 11. Customising the board

The GTD preset is a starting point. **Boards → Manage boards…** (or the board
toolbar menu) opens the editor:

- **New ▾ → from a preset** to copy GTD, then tweak.
- Each **column** = a title + a Taskwarrior filter (raw, or via the filter
  builder) + an optional **drop action** that runs when you drag a card in:
  - *add / remove tags* (e.g. Waiting For = add `waiting`)
  - *set an attribute* (e.g. a "This week" column that sets `scheduled:`)
  - *set a UDA*
  - *run a verb* — `start`, `stop`, `done`, or `reopen` (moves a completed task
    back to pending)
- Reorder columns with ↑ ↓. **Export / Import** a board as JSON to share it.

Ideas: split **Next Actions** into `@calls` / `@computer` / `@errands` columns;
add an **Agenda** column filtered `+@agenda`; add a **This Week** column whose
drop sets `scheduled:` to today.

To send a **completed** task back to active: drag it out of Done on a board that
has a `reopen` drop, or in the console: `task <id> modify status:pending`.

---

## 12. Keyboard cheat‑sheet

Press **`?`** any time for this list in the app.

| Key | Action |
|---|---|
| `Ctrl+N` | focus the quick‑add field (capture) |
| `Ctrl+Shift+N` | open the full **Add Task** dialog |
| `Ctrl+B` | toggle the **board** view |
| `` Ctrl+` `` | show / hide the **command console** |
| `Ctrl+K` | command palette (jump to anything) |
| `Ctrl+F` | focus the filter field |
| `Ctrl+1 / 2 / 3` | Today / Next Actions / Completed views |
| `↑ / ↓` | move the selection |
| `Return` / `Ctrl+E` | open the edit panel |
| `Ctrl+D` | mark done |
| `Ctrl+S` / `Ctrl+Shift+S` | start / stop the timer |
| `Ctrl+.` | star / unstar |
| `Del` | delete (asks to confirm) |
| `Ctrl+Z` | undo the last change |
| `Esc` | close the edit panel / dialog |

---

## 13. Daily & weekly rhythm

**Every morning (2 min)**
`Ctrl+1` Today → star the 1–3 you'll actually do → work from the Starred view.

**Throughout the day**
Capture into Inbox with `Ctrl+N`. Don't process yet.

**Every evening (5–10 min)**
`Ctrl+B` → process **Inbox** to zero. Glance at **Waiting For**.

**Once a week (30–45 min)**
The full **Weekly Review** in §10.

---

## 14. FAQ

**A task with only the `waiting` tag and no project — where is it?**
In **Waiting For**. `+waiting` counts as "tagged", so it's out of Inbox, and the
Waiting column filter picks it up.

**I gave an Inbox task a tag but it's still in Inbox.**
Refresh (the board reloads on changes); make sure the tag actually saved (open
the card again). Inbox is *strictly* "no project **and** no tag".

**Difference between Due, Scheduled and Wait?**
*Due* = hard deadline (drives Overdue). *Scheduled* = the day you plan to start
(informational). *Wait* = hide the task entirely until that date — the GTD
tickler file.

**Can I use this alongside the `task` CLI / Taskwarrior sync?**
Yes. jtask never touches the data store directly — it shells out to `task`.
Taskwarrior sync, hooks, and the CLI all keep working. The board is stored in
jtask‑gui's own settings, not in Taskwarrior.

**Where do contexts get defined?**
In the Raw Command Console (`context define <name> <filter>`). Once defined they
show in the sidebar for one‑click switching.
