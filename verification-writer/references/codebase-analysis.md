# Codebase Analysis Reference

Detailed heuristics for each analysis layer. The skill's SKILL.md provides the overview; this reference provides the how.

## Layer 1: User Types and Access

### Discovery strategies

Scan in this order — stop when you have a complete picture:

1. **Database schema** — look for `users`, `profiles`, `roles`, or `user_roles` tables in migration files or schema definitions. Enum columns on role fields list all user types.
2. **Auth middleware** — files like `middleware.ts`, `middleware.js`, or `app/api/auth/` often contain role checks. Extract the role values being compared.
3. **Route guards / HOCs** — components like `RequireAuth`, `RoleGuard`, `withAuth`, or similar wrappers name the roles they accept.
4. **Navigation config** — sidebar or nav config files often map roles to available routes.
5. **Seed data** — seed scripts or fixture files often create one user per role.

### Building the access matrix

For each route discovered in Layer 2, determine access:

```
Route             | admin | educator | student | guardian | public
/admin/dashboard  | yes   | no       | no      | no       | no
/educator/classes | no    | yes      | no      | no       | no
/student/profile  | no    | no       | yes     | no       | no
/login            | yes   | yes      | yes     | yes      | yes
/                 | yes   | yes      | yes     | yes      | yes
```

This matrix drives auth boundary verification items.

## Layer 2: Route Discovery

### Next.js App Router conventions

```
app/
├── page.tsx              → /
├── layout.tsx            → Layout wrapper for /
├── loading.tsx           → Loading state for /
├── error.tsx             → Error boundary for /
├── not-found.tsx         → 404 for /
├── admin/
│   ├── page.tsx          → /admin
│   ├── layout.tsx        → Layout for /admin/*
│   ├── users/
│   │   ├── page.tsx      → /admin/users
│   │   └── [id]/
│   │       └── page.tsx  → /admin/users/:id
│   └── settings/
│       └── page.tsx      → /admin/settings
├── (educator)/           → Route group (no URL segment)
│   └── classes/
│       └── page.tsx      → /classes (under educator layout)
├── api/
│   └── users/
│       ├── route.ts      → GET/POST /api/users
│       └── [id]/
│           └── route.ts  → GET/PUT/DELETE /api/users/:id
```

### What to record per route

- **Path**: The URL path
- **Page file**: The file that renders the page
- **Layout**: The nearest layout.tsx in the directory tree
- **Error boundary**: The nearest error.tsx (or null — this is a finding if null)
- **Loading state**: The nearest loading.tsx (or null — check if needed)
- **API endpoints called**: Trace from the page's fetch/API calls
- **Auth requirement**: From middleware or route guards
- **Dynamic segments**: `[id]`, `[...slug]`, etc. — these need items that test with valid IDs, invalid IDs, and missing IDs

### route-scanner.py

The script walks the `app/` directory and produces JSON:

```json
[
  {
    "path": "/admin/users",
    "file": "app/admin/users/page.tsx",
    "layout": "app/admin/layout.tsx",
    "error_boundary": "app/admin/error.tsx",
    "loading": null,
    "dynamic_segments": [],
    "api_dir": false
  }
]
```

The skill uses this as a starting point and enriches it with semantic analysis.

## Layer 3: Component Analysis

### Tracing imports

From each page file, follow imports to build a component tree:

1. Read the page file
2. Extract all import statements
3. For each imported component, read its file
4. Categorize by type (see below)
5. For shared components (imported from `components/`, `lib/`, `hooks/`), note all routes that import them

### Component categories and what to look for

**Forms:**
- Identify: JSX with `<form>`, `onSubmit`, `useForm`, `handleSubmit`, form libraries (react-hook-form, formik, zod)
- Record: field names, field types, validation rules (required, min/max, pattern), submit handler
- Check: does validation exist? Client-side only, server-side only, or both?

**Tables/Lists:**
- Identify: JSX with `<table>`, mapping over arrays, DataTable components, list renderers
- Record: columns/fields displayed, sorting capability, filtering, pagination
- Check: empty state when no data? Loading state? Error state?

**CRUD Operations:**
- Identify: API calls (fetch, axios, useSWR, useQuery) that create, read, update, or delete
- Record: which operations exist, the API endpoints they hit, optimistic updates
- Check: confirmation before delete? Success/error feedback? Revalidation after mutation?

**Modals/Dialogs:**
- Identify: dialog/modal components, portals, overlay patterns
- Record: trigger, content, actions, dismiss behavior
- Check: can be closed? Handles escape key? Form inside modal has validation?

**Navigation:**
- Identify: links, router.push, redirects, tabs, breadcrumbs
- Record: destinations, conditions (role-based nav)
- Check: dead links? Links to non-existent routes?

**State-dependent UI:**
- Identify: conditional renders based on data state (loading, error, empty, populated)
- Record: what states are handled
- Check: are ALL states handled? Common miss: no empty state, no error state

## Layer 4: Error Path Analysis

### For each interaction point, check these patterns

**Form submissions:**
```
Good:
- Client validation prevents bad data from reaching server
- Server validation returns structured errors
- UI displays specific field-level errors
- Submit button disabled during submission (prevents double-submit)
- Network failure shows retry option

Bad (findings):
- No validation at all
- Only client validation (server accepts anything)
- Generic "something went wrong" with no details
- Console logs the error but UI shows nothing
- Form resets on error (user loses input)
```

**API calls:**
```
Good:
- try/catch or .catch() around every fetch
- Error boundary in component tree above the fetch
- Loading state shown during fetch
- Error state shown on failure with retry option
- 404s handled differently from 500s

Bad (findings):
- Unhandled promise rejection
- No error boundary in route's component tree
- No loading state (content pops in)
- White screen on API failure
- Same error message for all failure types
```

**Auth boundaries:**
```
Good:
- Middleware checks role before rendering
- Unauthorized redirects to appropriate page
- No flash of unauthorized content
- API endpoints also check auth (not just UI)
- Expired sessions redirect to login with return URL

Bad (findings):
- Client-side only role check (API returns data anyway)
- Flash of protected content before redirect
- No handling of expired sessions
- API endpoint returns 500 instead of 401/403
```

**Destructive actions:**
```
Good:
- Confirmation dialog with clear description of consequences
- Cancel option that does nothing
- Action failure shows error and doesn't complete
- Success feedback after completion
- Undo option if feasible

Bad (findings):
- No confirmation, immediate execution
- Confirmation but action can't be cancelled mid-flight
- Failure leaves system in inconsistent state
- No feedback after action
```

### Severity classification

- **High**: User-facing crash, data loss risk, security boundary missing, no error handling on destructive action
- **Medium**: Poor error UX (generic messages, lost input), missing loading/empty states, partial validation
- **Low**: Missing confirmation on non-destructive action, inconsistent error message style, minor UX gaps
