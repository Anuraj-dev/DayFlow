let meta = #{
    name: "dayflow-backend",
    description: "TDD FastAPI slices; implementer-only; PR and merge-on-green",
    when_to_use: "Build or extend Dayflow API, authz, attendance, leave, payroll, or backend tests",
    phases: [
        #{ title: "auth", detail: "invite activation and session" },
        #{ title: "employees", detail: "directory and profile authz" },
        #{ title: "attendance", detail: "sessions and corrections" },
        #{ title: "leave", detail: "requests, balances, audit" },
        #{ title: "payroll", detail: "periods, salary, publish" },
    ],
};

let root = "/home/raja/Anuraj-Dev/DayFlow";
if args != () && args.root != () { root = args.root; }
let root_json = json_encode(root);

let slice_schema = #{
    "type": "object",
    "required": ["slice", "merged", "summary"],
    "properties": #{
        "slice": #{ "type": "string" },
        "pr_url": #{ "type": "string" },
        "merged": #{ "type": "boolean" },
        "ci": #{ "type": "string" },
        "summary": #{ "type": "string" },
    },
};

fn rules(root_json) {
    let p = "";
    p += "Repo: " + root_json + ". Read AGENTS.md, docs/DOMAIN.md, docs/PRODUCT.md, and the existing backend before editing.\n";
    p += "You are a worker. Do not spawn agents.\n";
    p += "Own only backend/. Do not edit frontend/, docker-compose.yml, AGENTS.md, docs/STATE.md, or .github/workflows/.\n";
    p += "Do not revert unrelated work. Do not touch Docker projects other than compose project dayflow. Host Postgres is 5433; never bind 5432.\n";
    p += "TDD: one failing test at the named seam, run it, confirm red, then the smallest implementation that turns it green. Repeat. No bulk tests then bulk code.\n";
    p += "Tests hit public HTTP or domain functions. No tautological expects. No mocking the code under test. Expected values are literals from the spec.\n";
    p += "Invariants: server authorizes every read and mutation; every business row is organization-scoped; HR is never chosen at public signup; privileged changes write audit_events; attendance times come from the server; finalized payroll is immutable.\n";
    p += "Keep one HR role. Settings stay seeded. Documents stay deferred. Email stays ConsoleEmailAdapter except activation/reset payloads.\n";
    p += "Preferred test command: docker compose exec -T backend pytest -q. If dayflow compose is down, docker compose up -d db backend, wait healthy, then pytest. Do not docker compose down other projects.\n";
    p += "API contracts to implement and keep stable:\n";
    p += "POST /api/auth/sign-in, GET /api/auth/me, POST /api/auth/activate-account.\n";
    p += "GET /api/dashboard. GET/PATCH /api/employees, GET /api/employees/{id}.\n";
    p += "GET /api/attendance, POST /api/attendance/check-in, POST /api/attendance/check-out, POST /api/attendance/corrections, POST /api/attendance/corrections/{id}/review.\n";
    p += "GET /api/time-off, POST /api/time-off/requests, POST /api/time-off/requests/{id}/cancel, POST /api/time-off/requests/{id}/approve, POST /api/time-off/requests/{id}/reject.\n";
    p += "GET /api/payroll, PATCH /api/payroll/salary-components, POST /api/payroll/periods/{id}/finalize, POST /api/payroll/periods/{id}/publish.\n";
    p += "Use grep and read_file. Run the tests.\n";
    p
}

fn deliver_git(root_json, slice_id, owned, commit_scope) {
    let p = "";
    p += "After pytest is green for this slice, deliver it to GitHub. Repo: " + root_json + ".\n";
    p += "Never commit to main. Never force-push main. Never git add -A. Never add Co-Authored-By or AI attribution. No emoji.\n";
    p += "Owned paths only: " + owned + "\n";
    p += "Do not git add frontend/ or other stacks. Do not stash, reset --hard, or discard unstaged files you do not own.\n";
    p += "If there is nothing to commit in owned paths, set merged=false and say so in summary.\n";
    p += "Git steps:\n";
    p += "1. git fetch origin.\n";
    p += "2. git switch -c feat/backend-" + slice_id + ". If that name exists, use feat/backend-" + slice_id + "-2.\n";
    p += "3. git add the owned paths only. Conventional commit: feat(" + commit_scope + "): <imperative summary of this slice>.\n";
    p += "4. git fetch origin. git rebase origin/main. If rebase is blocked only by unstaged files you do not own, skip rebase and continue. If rebase conflicts in owned files, fix them. If conflicts in files you do not own, abort rebase and report — do not delete other-stack work.\n";
    p += "5. git push -u origin HEAD. gh pr create --base main with title matching the commit and body sections Summary, Changes, Why, Testing, Checklist.\n";
    p += "6. Wait for GitHub Actions: timeout 900 gh pr checks --watch. If all required checks succeed, squash-merge: gh pr merge --squash --delete-branch. If merge is blocked only by missing reviews, retry with --admin. Never merge red CI.\n";
    p += "7. If CI fails: one local fix in owned paths, commit, push, watch again. If still red, leave the PR open.\n";
    p += "8. After GitHub merge, git fetch origin. Do not checkout main if that would destroy uncommitted frontend files.\n";
    p
}

fn implement(root_json, slice_id, seam, done_when, owned, commit_scope) {
    let p = "";
    p += "You are the Dayflow backend TDD implementer for slice `" + slice_id + "`.\n";
    p += "Hackathon speed: finish this slice, open a PR, merge it if CI is green. No reviewer.\n";
    p += rules(root_json);
    p += "Seam under test: " + seam + "\n";
    p += "Done when: " + done_when + "\n";
    p += "If a test is already green for the seam, write the next failing behavior in this slice, then implement. Do not skip red.\n";
    p += "If origin/main already contains this slice, do not rebuild it; report that and skip git.\n";
    p += "If a prior slice is missing on origin/main, implement only the minimum blocker this seam needs.\n";
    p += deliver_git(root_json, slice_id, owned, commit_scope);
    p += "Return JSON: slice, pr_url (empty string if none), merged (true only after squash-merge), ci (green/red/skipped/none), summary (files + test command + pass/fail + PR result).\n";
    p
}

fn run_slice(root_json, slice_id, seam, done_when, owned, commit_scope, model_name, slice_schema) {
    phase(slice_id);
    log("Backend implementer " + slice_id + " on " + model_name);
    let impl = agent(implement(root_json, slice_id, seam, done_when, owned, commit_scope), #{
        label: "be-impl-" + slice_id,
        capability_mode: "all",
        model: model_name,
        output_schema: slice_schema,
    });
    let out = #{ slice: slice_id, merged: false, summary: "implementer failed" };
    if impl != () && impl.success && impl.output != () {
        out = impl.output;
        log("Backend " + slice_id + " done");
    } else {
        log("Backend implementer failed " + slice_id);
    }
    out
}

let results = [];

results.push(run_slice(
    root_json,
    "auth",
    "POST /api/auth/sign-in, GET /api/auth/me, POST /api/auth/activate-account",
    "Seeded HR and employee can sign in and reach /me. Bad credentials 401. Disabled account 403. Activate-account accepts a valid unused invite (employee_code + email + token + password >= 12), rejects expired and already-used invites, never assigns HR from a public body field. Tests cover those cases.",
    "backend/",
    "api",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "employees",
    "GET /api/employees, GET /api/employees/{id}, PATCH /api/employees/{id}",
    "HR lists org employees. Employee listing 403. Employee can GET self and PATCH address/phone only. Employee GET of another id is 403 even with a guessed UUID. HR can PATCH job and salary-adjacent employee fields. Queries filter organization_id. Tests prove isolation and the 403.",
    "backend/",
    "api",
    "grok-4.5",
    slice_schema
));

results.push(run_slice(
    root_json,
    "attendance",
    "GET /api/attendance, POST check-in, POST check-out, correction request and HR review",
    "Check-in uses server time and opens one session. Second check-in with an open session fails. Check-out after check-in closes it and stores worked_minutes. On-leave blocks check-in. Employees see only their sessions. HR sees org sessions and can review corrections. Historical punches change only via correction + audit. Tests cover open-session, order, and authz.",
    "backend/",
    "api",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "leave",
    "GET /api/time-off, POST requests, cancel pending, HR approve/reject",
    "Employee submits paid/sick/unpaid range with reason. Counted days exclude weekends/holidays. Overlap of pending/approved fails. Insufficient paid balance fails. Employee cancels pending only. HR approve updates used_days and writes leave_request_events + audit in one transaction. Reject requires comment. Tests cover overlap, rejection comment, and authz.",
    "backend/",
    "api",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "payroll",
    "GET /api/payroll, PATCH salary-components, finalize, publish, GET /api/dashboard",
    "Employee GET returns only own published records. HR sees org periods/records and can PATCH salary while draft. Finalize locks. Publish makes payslips visible. Mutating a finalized period 409s. Dashboard returns HR vs employee payloads from real counts. Tests cover isolation, immutability, and role payloads.",
    "backend/",
    "api",
    "grok-4.6",
    slice_schema
));

complete(#{ stack: "backend", slices: results });
