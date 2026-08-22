let meta = #{
    name: "dayflow-frontend",
    description: "TDD Odoo/shadcn Vue slices; implementer-only; PR and merge-on-green",
    when_to_use: "Build Dayflow Vue UI with Odoo 19 product chrome, shadcn-vue, and per-feature PRs",
    phases: [
        #{ title: "foundation", detail: "shadcn-vue plus Odoo tokens" },
        #{ title: "auth-ui", detail: "sign-in and activation" },
        #{ title: "shell-dashboards", detail: "control panel plus dashboards" },
        #{ title: "people", detail: "directory and profile" },
        #{ title: "attendance", detail: "employee and HR attendance" },
        #{ title: "time-off", detail: "requests and approvals" },
        #{ title: "payroll", detail: "payslips, HR control, settings" },
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
    p += "Repo: " + root_json + ". Read AGENTS.md, docs/UI.md, docs/PRODUCT.md, and frontend/src before editing.\n";
    p += "You are a worker. Do not spawn agents.\n";
    p += "Own only frontend/ plus docs/UI.md if tokens must stay in sync. Do not edit backend/, docker-compose.yml, AGENTS.md, docs/STATE.md, or .github/workflows/.\n";
    p += "Do not revert unrelated work. Do not git stash, reset --hard, or checkout other stacks' files.\n";
    p += "TDD: one failing Vitest test at the named seam, confirm red, then the smallest UI that turns it green. Repeat per required state.\n";
    p += "Test rendered text, roles, routes, validation, disabled actions. Mock fetch at the network seam only. No tautologies. No emoji in UI or tests.\n";
    p += "UI is Odoo 19 product: 46px plum #714B67 bar, white control panel, canvas #F8F9FA, white sheets, 14px system font, 1px #DEE2E6 borders, 3-6px radii. Primary plum, action teal #017E84. Status is color plus text.\n";
    p += "No decorative cards. No WorkCard wrappers. Tables for lists, sheets for forms. shadcn-vue components from @/components/ui.\n";
    p += "Employees see Overview, Attendance, Time off, Payroll, My profile. HR also People and Settings.\n";
    p += "Call /api auth, dashboard, employees, attendance, time-off, payroll contracts. If a mutation 501s, keep the UI wired and mock JSON in tests.\n";
    p += "Commands: npm --prefix frontend run test:unit -- --run AND npm --prefix frontend run type-check.\n";
    p
}

fn deliver_git(root_json, slice_id, owned, commit_scope) {
    let p = "";
    p += "After tests and type-check pass, deliver this slice to GitHub. Repo: " + root_json + ".\n";
    p += "Never commit to main. Never force-push main. Never git add -A. Never add Co-Authored-By or AI attribution. No emoji.\n";
    p += "Owned paths only: " + owned + "\n";
    p += "Do not git add backend/ or other stacks. Do not stash, reset --hard, or discard unstaged files you do not own.\n";
    p += "If there is nothing to commit in owned paths, set merged=false and say so in summary.\n";
    p += "Git steps:\n";
    p += "1. git fetch origin.\n";
    p += "2. git switch -c feat/frontend-" + slice_id + ". If that name exists, use feat/frontend-" + slice_id + "-2.\n";
    p += "3. git add the owned paths only. Conventional commit: feat(" + commit_scope + "): <imperative summary of this slice>.\n";
    p += "4. git fetch origin. git rebase origin/main. If rebase is blocked only by unstaged files you do not own, skip rebase and continue. If rebase conflicts in owned files, fix them. If conflicts in files you do not own, abort rebase and report — do not delete other-stack work.\n";
    p += "5. git push -u origin HEAD. gh pr create --base main with title matching the commit and body sections Summary, Changes, Why, Testing, Checklist.\n";
    p += "6. Wait for GitHub Actions: timeout 900 gh pr checks --watch. If all required checks succeed, squash-merge: gh pr merge --squash --delete-branch. If merge is blocked only by missing reviews, retry with --admin. Never merge red CI.\n";
    p += "7. If CI fails: one local fix in owned paths, commit, push, watch again. If still red, leave the PR open.\n";
    p += "8. After GitHub merge, git fetch origin. Do not checkout main if that would destroy uncommitted backend files.\n";
    p
}

fn implement(root_json, slice_id, seam, done_when, owned, commit_scope) {
    let p = "";
    p += "You are the Dayflow frontend TDD implementer for slice `" + slice_id + "`.\n";
    p += "Hackathon speed: finish this slice, open a PR, merge it if CI is green. No reviewer.\n";
    p += rules(root_json);
    p += "Seam: " + seam + "\nDone when: " + done_when + "\n";
    p += "Replace placeholder views. Keep AppShell skip-link and session store unless this slice must extend them.\n";
    p += "If origin/main already contains this slice, do not rebuild it; report that and skip git.\n";
    p += deliver_git(root_json, slice_id, owned, commit_scope);
    p += "Return JSON: slice, pr_url (empty string if none), merged (true only after squash-merge), ci (green/red/skipped/none), summary (files + test command + pass/fail + PR result).\n";
    p
}

fn run_slice(root_json, slice_id, seam, done_when, owned, commit_scope, model_name, slice_schema) {
    phase(slice_id);
    log("Frontend implementer " + slice_id + " on " + model_name);
    let impl = agent(implement(root_json, slice_id, seam, done_when, owned, commit_scope), #{
        label: "fe-impl-" + slice_id,
        capability_mode: "all",
        model: model_name,
        output_schema: slice_schema,
    });
    let out = #{ slice: slice_id, merged: false, summary: "implementer failed" };
    if impl != () && impl.success && impl.output != () {
        out = impl.output;
        log("Frontend " + slice_id + " done");
    } else {
        log("Frontend implementer failed " + slice_id);
    }
    out
}

let results = [];

results.push(run_slice(
    root_json,
    "foundation",
    "shadcn-vue plus Odoo 19 tokens and shell chrome",
    "Tailwind v4 and shadcn-vue are initialized (npx shadcn-vue@latest init; install the CLI if needed). CSS variables match docs/UI.md. AppShell is a 46px plum bar plus white control panel, not a card grid. WorkCard is removed. Existing CI test frontend-ci.spec.ts and router.spec.ts still pass. type-check passes.",
    "frontend/ docs/UI.md",
    "web",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "auth-ui",
    "SignInView and ActivateAccountView",
    "Sign-in: default, bad credentials, locked/disabled, forgot-password entry. Activation: valid, expired, already used, verification sent, verified. shadcn Input/Button/Alert. Tests drive those states. No cards, no emoji.",
    "frontend/",
    "web",
    "grok-4.5",
    slice_schema
));

results.push(run_slice(
    root_json,
    "shell-dashboards",
    "AppShell nav and /dashboard employee plus HR frames",
    "Employee nav has no People or Settings. HR has both. Control panel holds breadcrumbs and the page action. Employee dashboard leads with attendance action and states not checked in/checked in/checked out/on leave/incomplete profile. HR dashboard: headcount, coverage, pending approvals, exceptions, empty queue, payroll due. Tests cover role nav and two states per dashboard.",
    "frontend/",
    "web",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "people",
    "/employees table and /employees/:employeeId form sheet",
    "HR directory is a dense table: loading, empty, no results, inactive. Profile is a form sheet with Personal/Job/Salary/Documents tabs and view/edit/unsaved/missing document/access denied. Employee opening another id sees access denied. Documents tab is an explicit deferred state. Tests cover HR list and access denied.",
    "frontend/",
    "web",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "attendance",
    "/attendance employee and HR",
    "Employee: check-in/out on the control panel, week or list, states present/late/missing check-out/leave/half-day/correction requested. HR: filterable table for missing check-out and corrections. Status text plus color. Tests cover check-in CTA and an HR exception row.",
    "frontend/",
    "web",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "time-off",
    "/time-off employee and HR",
    "Employee: balances, request form, draft/overlap/insufficient/pending/approved/rejected. HR: pending table, approve, reject with required comment, conflict warning. Tests cover validation and reject requiring a comment.",
    "frontend/",
    "web",
    "grok-4.6",
    slice_schema
));

results.push(run_slice(
    root_json,
    "payroll",
    "/payroll employee and HR plus /settings deferred",
    "Employee: current/prior/no published payslip. HR: draft/validation/finalized/published/correction needed; salary editable only in draft. Settings is HR-only with a seeded-policy deferred state. Tests cover published-only employee view and HR draft vs finalized.",
    "frontend/",
    "web",
    "grok-4.6",
    slice_schema
));

complete(#{ stack: "frontend", slices: results });
