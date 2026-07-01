# The Complete Tutorial to the Network Test Orchestration Platform

> A from-the-ground-up explanation of **every** part of this repository — the
> concepts, the decisions, the code, and the *why* behind it all.
>
> **Who this is for:** You can write basic Python, but you're fuzzy on
> architecture, data structures, web frameworks, databases, async systems, and
> "how real apps are built." By the end of this document you should understand
> every file in this repo, be able to answer questions about it, and be able to
> rebuild it from scratch knowing *why* each piece exists.
>
> Take your time. This is long on purpose. Read it like a textbook, not a memo.

---

## Table of Contents

1. [What this application actually does](#1-what-this-application-actually-does)
2. [The 30,000-foot mental model](#2-the-30000-foot-mental-model)
3. [Foundational concepts you need first](#3-foundational-concepts-you-need-first)
4. [The technology stack, explained](#4-the-technology-stack-explained)
5. [How the repository is organized](#5-how-the-repository-is-organized)
6. [Backend, part 1: configuration, logging, errors](#6-backend-part-1-configuration-logging-errors)
7. [Backend, part 2: security (passwords & JWT)](#7-backend-part-2-security-passwords--jwt)
8. [Backend, part 3: the database layer](#8-backend-part-3-the-database-layer)
9. [Backend, part 4: the models (your tables)](#9-backend-part-4-the-models-your-tables)
10. [Backend, part 5: the schemas (Pydantic)](#10-backend-part-5-the-schemas-pydantic)
11. [Backend, part 6: the services (business logic)](#11-backend-part-6-the-services-business-logic)
12. [Backend, part 7: dependencies & auth wiring](#12-backend-part-7-dependencies--auth-wiring)
13. [Backend, part 8: the API routes](#13-backend-part-8-the-api-routes)
14. [Backend, part 9: the main app](#14-backend-part-9-the-main-app)
15. [Backend, part 10: background jobs (the heart of it)](#15-backend-part-10-background-jobs-the-heart-of-it)
16. [Backend, part 11: integrations (mock & real devices)](#16-backend-part-11-integrations-mock--real-devices)
17. [Backend, part 12: the seed script](#17-backend-part-12-the-seed-script)
18. [Backend, part 13: database migrations (Alembic)](#18-backend-part-13-database-migrations-alembic)
19. [Backend, part 14: the tests](#19-backend-part-14-the-tests)
20. [Frontend, part 1: how a React app boots](#20-frontend-part-1-how-a-react-app-boots)
21. [Frontend, part 2: routing & auth](#21-frontend-part-2-routing--auth)
22. [Frontend, part 3: the API client & data fetching](#22-frontend-part-3-the-api-client--data-fetching)
23. [Frontend, part 4: pages & components](#23-frontend-part-4-pages--components)
24. [Infrastructure: Docker, Compose, CI](#24-infrastructure-docker-compose-ci)
25. [Five end-to-end walkthroughs](#25-five-end-to-end-walkthroughs)
26. [How to build this whole thing from scratch](#26-how-to-build-this-whole-thing-from-scratch)
27. [Glossary](#27-glossary)
28. [Interview-style questions & answers](#28-interview-style-questions--answers)

---

## 1. What this application actually does

Imagine you work on a team that manages **network equipment**: switches,
routers, firewalls, wireless controllers, access points. A company might have
hundreds or thousands of these devices. Periodically, someone needs to check:

- "Is this switch reachable?"
- "Does it have VLAN 1718 configured?"
- "Is telnet (an insecure protocol) accidentally turned on?"
- "Are all the network interfaces up?"
- "Is the RADIUS (login) server reachable from this device?"

Doing this **by hand** — logging into each device, typing commands, reading the
output, writing down pass/fail — is slow, boring, and error-prone. This project
is an **internal tool** that automates it. The domain word for that is
**orchestration**: coordinating many small tasks into a controlled, repeatable
workflow.

Here's the workflow the app supports:

1. **Register devices** — store metadata about each device (hostname, IP,
   vendor, type, etc.).
2. **Define test suites** — a *test suite* is a named, reusable collection of
   *test cases*. A test case is one check, like "ping the device" or "config
   contains `aaa new-model`."
3. **Run a job** — pick a device + a test suite and press "Run." The system
   executes every test case against that device and records the result of each.
4. **View results & reports** — see which checks passed/failed, read logs, and
   download a JSON or CSV report.
5. **Dashboard** — see high-level metrics (device count, pass rate, recent jobs).

A crucial detail: the app ships with a **mock device client**. Instead of
actually SSHing into real hardware (which you don't have on your laptop), it
generates *fake but realistic* responses. This means the entire system runs
locally with zero network gear — perfect for a demo or a portfolio project. The
code is structured so you *could* swap in real SSH/SNMP later.

There's also **authentication** (you log in) and **authorization** (what you're
allowed to do depends on your role: `admin`, `engineer`, or `viewer`).

> **Why does this project exist?** It's a portfolio piece. It deliberately
> demonstrates the skills a backend/full-stack engineer is expected to have:
> API design, database modeling, async job processing, auth, testing, Docker,
> CI, and a clean React frontend. Understanding it teaches you how a *real*
> internal platform is structured.

### 1.1 The networking words, so the domain makes sense

You don't need to be a network engineer to understand this codebase — the actual
network logic is *mocked* — but the domain vocabulary shows up in model fields,
seed data, and test-case names, so here's just enough to never feel lost. None of
these are deep; they're the nouns the app organizes work around.

- **Switch / router / firewall / access point** — kinds of network *devices*. A
  **switch** connects devices within a local network; a **router** connects
  different networks (and to the internet); a **firewall** filters traffic for
  security; an **access point** provides Wi-Fi. In this app they're all just rows
  in the `devices` table distinguished by a `device_type` field — the code treats
  them uniformly.
- **Hostname** — a human-readable name for a device (e.g. `core-sw-01`), like a
  computer's name. The app uses it as the primary human identifier and indexes it
  for fast lookup.
- **IP address / management IP** — the numeric network address (e.g. `10.0.1.1`)
  you use to reach a device. The **management IP** specifically is the address an
  administrator connects to in order to configure the device.
- **Vendor** — who makes the device (Cisco, Juniper, Arista, Palo Alto…).
  Different vendors speak slightly different command "dialects," which is why
  real device automation cares about vendor; here it's an `enum` field.
- **VLAN (Virtual LAN)** — a way to split one physical network into separate
  logical networks. A test like "is VLAN 1718 configured?" checks that a device
  has been set up with the right segmentation. You only need to know it's a
  configuration item you can check for.
- **Telnet vs. SSH** — two ways to log into a device's command line remotely.
  **Telnet** is old and sends everything (including passwords) in plain text, so
  it's insecure; **SSH** is encrypted and the modern standard. A test like "is
  telnet disabled?" is a security check.
- **RADIUS** — a server that centralizes login/authentication for network gear,
  so engineers use one account across many devices. "Is the RADIUS server
  reachable?" checks that centralized login will work.
- **Ping / ICMP** — the simplest reachability check: send a tiny packet and see
  if the device answers. "Is the device reachable?" is essentially a ping.
- **Interface** — a physical or logical port on a device. "Are all interfaces
  up?" checks that the connections are live rather than down.
- **SNMP (Simple Network Management Protocol)** — a protocol for *reading*
  metrics and status from devices (interface counters, CPU, uptime). One of the
  two real integration stubs (§16) is an SNMP client; in the mock it's simulated.
- **SSH client / config** — logging into a device over SSH to read or check its
  **configuration** (the text file describing how the device is set up). Many
  test cases are "does the config contain line X?" The other integration stub is
  an SSH client.

With those nouns in hand, the whole product reads plainly: *register devices,
group security/health checks into reusable suites, run a suite against a device,
and record pass/fail per check.* Everything technical from here on is about how to
build that cleanly — the networking itself stays shallow on purpose.

### 1.2 The roles, and what each can do

Because the app has authorization (§3.6, §12), it helps to know the three roles
up front, since they appear in seed data, route guards, and the UI:

- **viewer** — read-only. Can see devices, suites, jobs, and results, but cannot
  change anything. The "auditor" persona.
- **engineer** — the everyday user. Can create/edit devices and suites and *run*
  jobs (the core workflow), but can't manage other users.
- **admin** — full control, including user management. The "superuser."

The roles form a rough ladder of privilege, and you'll see them enforced at the
route layer with a small reusable guard (`require_roles`, §12) rather than scattered
`if` checks. Keeping the role list short and the permissions coarse is a
deliberate MVP choice — real systems often grow finer-grained permissions, but
three roles are enough to demonstrate the *pattern* of role-based access control
without drowning the project in permission plumbing.

---

## 2. The 30,000-foot mental model

Before any code, hold this picture in your head. The system is made of **five
running programs** (plus your browser):

```mermaid
flowchart LR
    user([You, in a browser]) --> fe[React Frontend<br/>port 5173]
    fe -->|HTTP requests| api[FastAPI Backend<br/>port 8000]
    api --> db[(PostgreSQL<br/>the database)]
    api -->|"enqueue job"| redis[(Redis<br/>the job queue)]
    worker[Background Worker] -->|"pick up job"| redis
    worker --> db
    worker --> mock[Mock Device Client]
```

1. **The browser** runs the **frontend** (React). It draws the UI and talks to
   the backend over HTTP.
2. **The backend** (FastAPI) is the "brain." It receives HTTP requests, checks
   permissions, reads/writes the database, and returns JSON.
3. **PostgreSQL** is the **database** — permanent storage for users, devices,
   suites, jobs, and results.
4. **Redis** is a **queue** — a temporary holding line for "jobs that need to be
   run." It's how the backend hands work off to the worker.
5. **The worker** is a *separate* program that watches the queue, picks up jobs,
   actually runs the test cases (against the mock client), and writes the
   results back to the database.

The single most important architectural idea here is **#4 and #5: asynchronous
background jobs.** Running a test suite could take a while. You don't want the
user's "Run" button to freeze for 30 seconds. So the backend doesn't run the
tests itself — it just *records that a job should happen* and *drops a note in
the queue*, then immediately responds "OK, job #42 is queued." A separate worker
process does the slow work in the background. The frontend then *polls* (asks
repeatedly) "is job #42 done yet?" until it is.

If you understand that one paragraph, you understand the soul of this project.

**Why five programs instead of one?** A beginner's instinct is to put everything
in a single program — and for a tiny app you could. But each split here buys
something concrete. The **frontend** is separate from the **backend** because they
do fundamentally different jobs (drawing pixels vs. enforcing rules and storing
data) and even run in different places (the frontend runs in the user's browser,
on their machine; the backend runs on your server). Keeping the database in its
own process (**PostgreSQL**) means a dedicated, battle-tested engine handles the
hard problems of durable, concurrent, queryable storage — you'd never want to
reinvent that. The **worker** is separate from the backend so that slow work
doesn't clog the fast request/response path: the web server stays snappy and
responsive while heavy lifting happens elsewhere. And **Redis** sits between them
as a neutral hand-off point so the backend and worker don't have to know about
each other or run at the same instant. Each boundary is a deliberate division of
labor, and the cost — more moving parts to run — is exactly what Docker Compose
(§24) exists to manage.

**The data's journey, in one sentence each.** Trace a single test run through the
five programs and the whole system snaps into focus. You click "Run" in the
**browser**, which sends an HTTP request to the **backend**. The backend checks
you're allowed, writes a new `job` row marked `queued` into **PostgreSQL**, drops
the job's id into the **Redis** queue, and instantly replies "queued." The
**worker**, which has been watching Redis, picks up the id, loads the job from
Postgres, runs each test against the **mock device client**, and writes a result
row per test plus a final status back into Postgres. Meanwhile your browser has
been **polling** the backend every 1.5 seconds — "done yet? done yet?" — and the
moment the worker marks the job `passed`, the next poll sees it and the UI lights
up with results. Every concept in this document is a detail of some step in that
journey.

**A note on "stateless" backend, "stateful" database.** A subtle but important
property: the backend itself stores *nothing* permanent in its own memory. Every
fact that must survive — users, devices, jobs, results — lives in PostgreSQL.
This is why you can run several copies of the backend (or restart it) without
losing anything, and why the worker can be an entirely separate process yet still
"see" the same jobs: they share the database, not memory. Pushing all durable
state into the database and keeping the application processes *stateless* is a
foundational pattern for systems that need to scale or survive restarts, and
you'll see it reflected everywhere in the code (e.g. the queue carries only an
id, and the worker re-reads state from the database rather than trusting anything
held in memory).

---

## 3. Foundational concepts you need first

This section is a mini-textbook of the general computer-science ideas the rest
of the document assumes. The goal is that after reading it you can *explain each
idea out loud* — "what is it, how does it work, why do we use it" — without
looking anything up. Read it slowly; everything later builds on it.

### 3.1 Networks, client–server, and HTTP (how two programs talk)

**The problem being solved.** Your browser is one program running on your
laptop. The backend is another program running somewhere else (in development,
also your laptop, but conceptually "elsewhere"). They are separate processes
with separate memory — they cannot just call each other's functions. They need a
way to send messages over a network. That way is a *stack of protocols*.

**A protocol** is just an agreed-upon set of rules for formatting and exchanging
messages, so two machines built by different people can understand each other.
The relevant layers, bottom to top:

1. **IP (Internet Protocol)** gives every machine an **address** (e.g.
   `93.184.216.34`, or `127.0.0.1` which always means "this same machine,"
   nicknamed *localhost*). IP's job is to route a packet of bytes from one
   address to another. IP alone is unreliable — packets can be lost, duplicated,
   or arrive out of order.
2. **TCP (Transmission Control Protocol)** sits on top of IP and adds
   *reliability*. It establishes a **connection** between two machines (via a
   "three-way handshake"), splits your data into numbered packets, re-sends lost
   ones, and reassembles them in order on the other side. So TCP gives you a
   reliable, ordered, two-way stream of bytes. TCP also introduces **ports**: a
   single machine can run many programs, so a port number (like `8000` or
   `5432`) says *which* program on that machine the connection is for. An address
   + port (`127.0.0.1:8000`) uniquely identifies one program's "phone line."
3. **HTTP (HyperText Transfer Protocol)** sits on top of TCP and defines the
   *format* of request and response messages for the web. This is the layer you
   actually work with.

So when the frontend calls the backend, the chain is: HTTP message → chopped into
TCP packets → addressed and routed by IP → reassembled → handed to the backend
program listening on port 8000. You almost never think about IP/TCP directly —
but knowing they're there is what lets you answer "what actually happens when I
make a request."

**Client vs. server.** A **server** is a program that starts up, *listens* on a
port, and waits for incoming requests, handling each and sending a response. A
**client** is a program that *initiates* requests. Your browser is a client; the
FastAPI backend is a server. (Confusingly, the backend is *also* a client of
PostgreSQL and Redis — "client" and "server" are roles in a conversation, not
fixed identities.)

**The anatomy of an HTTP request.** A request is plain text (conceptually) with
these parts:

- A **method** (a verb describing intent): `GET` (read something), `POST`
  (create something / submit data), `PATCH` (partially update), `PUT` (replace
  entirely), `DELETE` (remove). Methods have *semantics* the whole web agrees on
  — e.g. `GET` should never change data (it's "safe"), and `GET`/`PUT`/`DELETE`
  should be **idempotent** (doing them twice has the same effect as once),
  whereas `POST` is not (POST twice = two things created).
- A **path / URL** (the address of the resource): `/api/devices`, `/api/jobs/42`.
  It can carry **query parameters** after a `?`: `/api/devices?limit=20&search=core`.
- **Headers** (key–value metadata about the request): e.g.
  `Authorization: Bearer <token>` (who you are), `Content-Type: application/json`
  (the body is JSON), `Accept: application/json` (please respond in JSON).
- An optional **body** (the actual payload), used by `POST`/`PATCH`/`PUT`,
  usually JSON in this app.

**The anatomy of an HTTP response:**

- A **status code** — a 3-digit number with a precise, web-wide meaning, grouped
  by first digit: **2xx** = success (`200 OK`, `201 Created`, `204 No Content`),
  **3xx** = redirection, **4xx** = *you* (the client) did something wrong (`400
  Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409
  Conflict`, `422 Unprocessable Entity` for validation errors), **5xx** = *the
  server* failed (`500 Internal Server Error`). Choosing the correct code is part
  of good API design because clients (and humans) rely on it to react correctly.
- **Headers** (metadata about the response, e.g. `Content-Type`,
  `Content-Disposition` to trigger a file download).
- An optional **body** (the returned data, usually JSON).

**HTTP is stateless.** This is a crucial property: each request is independent
and the server remembers *nothing* about previous requests by default. The
server doesn't "know" you're logged in from one request to the next. That's
*why* authentication tokens exist (§3.6): since the server forgets you instantly,
you must re-prove who you are on *every single request* by attaching your token.
Statelessness is what lets you run many identical copies of a server behind a
load balancer — any copy can handle any request because none of them hold
private memory of you.

You will see every one of these concepts — methods, paths, query params,
headers, status codes, statelessness — used deliberately throughout this
codebase.

### 3.2 REST and JSON (how we organize an API)

**REST** (REpresentational State Transfer) is a *style* — a set of conventions —
for designing HTTP APIs. It isn't a library or a standard you install; it's a way
of thinking. The core idea: model your application as a collection of
**resources** (nouns — things you can name) and manipulate them with the
*standard HTTP methods* (verbs) rather than inventing your own.

The naive, non-REST way is to invent a function-style URL for every action:
`/getAllDevices`, `/createNewDevice`, `/deleteDeviceById`, `/updateDevicePartial`.
This works but every API ends up arbitrary and you must read docs for each call.

The REST way says: there's a resource called `devices`. You express *what you
want to do* through the method, and *which resource* through the path:

| Intent | Method + Path | Returns |
|---|---|---|
| List devices | `GET /api/devices` | a page of devices |
| Get one device | `GET /api/devices/42` | device 42 |
| Create a device | `POST /api/devices` | the new device (`201`) |
| Update a device | `PATCH /api/devices/42` | the updated device |
| Delete a device | `DELETE /api/devices/42` | nothing (`204`) |

Notice the *same path* (`/api/devices/42`) does different things depending on the
verb. This is predictable: once you learn the pattern for one resource, you know
it for all of them (`/api/jobs`, `/api/test-suites`, etc.). That consistency is
the entire payoff of REST, and this project follows it faithfully.

**Why this matters for "why did you build it this way":** REST gives you a
uniform, self-documenting, cacheable, stateless interface that any client (a
browser, a script, a mobile app, `curl`) can use. It maps cleanly onto CRUD
(§3.3) and onto database operations, which is why it dominates web APIs.

**JSON** (JavaScript Object Notation) is the **data format** used to carry
information in request and response bodies. It is just text, structured as
nested key–value objects and arrays — it looks almost exactly like a Python
`dict`/`list`:

```json
{
  "id": 42,
  "hostname": "core-sw-01",
  "vendor": "cisco",
  "tags": ["prod", "hq"],
  "active": true,
  "notes": null
}
```

JSON has exactly six value types: string, number, boolean (`true`/`false`),
`null`, object (`{}`), and array (`[]`). That's it — no dates, no custom types
(dates are sent as strings). It became the universal web format because it's
human-readable, maps naturally onto the data structures of nearly every language,
and is far lighter than the older XML. **Serialization** is the act of turning an
in-memory object into a JSON string to send; **deserialization** (or *parsing*)
is turning a received JSON string back into objects. Both the Python backend and
the TypeScript frontend serialize/deserialize JSON constantly — Pydantic does it
on the backend, `JSON.stringify`/`JSON.parse` (wrapped by the fetch layer) on the
frontend. The fact that both ends agree on JSON is what lets two programs written
in two different languages exchange structured data.

### 3.3 Relational databases and SQL (the deep version)

This is the most important foundational topic, so we go deep. By the end you
should be able to answer "what is SQL," "what is a relational database," "how do
joins/indexes/transactions work," and "why Postgres."

#### What a database even is, and why not just files

Your app needs to *persist* data — keep it after the program stops. You could
write it to files yourself, but then you'd have to solve, by hand: how to find a
record quickly without reading the whole file, how to let many users read and
write at once without corrupting each other's changes, how to make sure a
half-finished update doesn't leave garbage if the power dies, and how to enforce
rules (no duplicate emails). A **database management system (DBMS)** is a program
that solves all of these for you. A **database** is the organized collection of
data it manages.

#### "Relational" = data as tables of rows

A **relational database** organizes data into **tables** (also called
*relations*). A table is like a strict spreadsheet:

- **Columns** define the *shape*: each has a name and a **data type** (integer,
  text/`VARCHAR`, boolean, timestamp, etc.). The type is enforced — you cannot
  put text in an integer column.
- **Rows** (also called *records*) are the actual data; each row is one entity
  (one device, one user).

This project has tables `users`, `devices`, `test_suites`, `test_cases`, `jobs`,
and `test_results`. Example of the `devices` table:

| id | hostname    | management_ip | vendor | status |
|----|-------------|---------------|--------|--------|
| 1  | core-sw-01  | 10.0.1.1      | cisco  | active |
| 2  | edge-rt-01  | 10.0.2.1      | juniper| active |

The word *relational* comes from this table-of-rows structure (a mathematical
"relation"), and from the fact that tables can **relate** to one another via keys
(below).

#### Keys and relationships (the heart of "relational")

- A **primary key** is the column (almost always `id`) that *uniquely* identifies
  each row. No two rows share an `id`. The database auto-generates it (1, 2, 3, …)
  and uses it as the row's permanent handle.
- A **foreign key** is a column in one table that stores the primary key of a row
  in *another* table, creating a link. Example: each row in `test_cases` has a
  `test_suite_id` column holding the `id` of the suite it belongs to. That's how
  the database represents "this test case belongs to that suite."

This models real relationships:

- **One-to-many:** one suite has many cases (the *many* side, `test_cases`, holds
  the foreign key). One device has many jobs.
- **Many-to-one** is just the same relationship viewed from the other end (many
  cases belong to one suite).
- **Many-to-many** (e.g. devices ↔ tags, where a device has many tags and a tag
  applies to many devices) needs a third "join table." This project *deliberately
  avoids* that by storing tags as a comma-separated string — a simplification
  noted honestly in the code.

Foreign keys also enforce **referential integrity**: the database refuses to
create a test case pointing at a suite that doesn't exist, and can automatically
clean up children when a parent is deleted (the `ON DELETE CASCADE` rule — see
§9).

#### SQL: the language you talk to the database with

**SQL (Structured Query Language)** is the standard language for relational
databases. You send it text commands; the database executes them and returns
results. SQL has two halves worth naming:

- **DDL (Data Definition Language)** — commands that define *structure*:
  `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, `CREATE INDEX`. (Alembic
  migrations, §18, are essentially managed DDL.)
- **DML (Data Manipulation Language)** — commands that work with *data*. The four
  you'll use constantly map exactly onto CRUD:

```sql
-- CREATE: insert a new row
INSERT INTO devices (hostname, management_ip, vendor, status)
VALUES ('sw-01', '10.0.0.1', 'cisco', 'active');

-- READ: select rows, optionally filtered, sorted, limited
SELECT id, hostname, vendor
FROM devices
WHERE status = 'active'
ORDER BY id DESC
LIMIT 20 OFFSET 0;

-- UPDATE: change existing rows that match a condition
UPDATE devices SET status = 'maintenance' WHERE id = 42;

-- DELETE: remove rows that match a condition
DELETE FROM devices WHERE id = 42;
```

Reading a `SELECT`: `SELECT` chooses *which columns*, `FROM` chooses *which
table*, `WHERE` filters *which rows*, `ORDER BY` sorts them, and `LIMIT`/`OFFSET`
return only a slice (this is exactly how pagination works — §11.2). `COUNT(*)`,
`SUM(...)`, etc., are **aggregate functions** that compute a single number over
many rows (used by the dashboard, §11.5).

> **You rarely write raw SQL in this project** because the ORM (§3.4) generates
> it for you. But the ORM is *only* generating SQL underneath — `db.get(Device,
> 42)` becomes `SELECT * FROM devices WHERE id = 42`. Understanding the SQL is
> understanding what your Python actually does.

#### Joins: combining related tables

Because data is split across tables, you often need to recombine it. A **JOIN**
matches rows from two tables on a key:

```sql
-- "For each test case, also show its suite's name"
SELECT test_cases.name, test_suites.name AS suite_name
FROM test_cases
JOIN test_suites ON test_cases.test_suite_id = test_suites.id;
```

This pairs each case with its suite by matching `test_case.test_suite_id` to
`test_suite.id`. Joins are powerful but can be slow if the join columns aren't
indexed — which is one reason this project indexes foreign keys. (The ORM often
hides joins behind `relationship()` and *eager loading*; see the N+1 discussion
in §11.3.)

#### Indexes: how lookups stay fast

Imagine finding a device by hostname in a million-row table. Without help, the
database must read *every* row and check — a **full table scan**, O(n), slow. An
**index** fixes this. An index is a separate, sorted data structure (almost
always a **B-tree** — a balanced tree kept in sorted order) that maps a column's
values to the locations of the matching rows. Looking up a value in a balanced
tree takes O(log n) steps — for a million rows that's ~20 comparisons instead of
a million. It's exactly like the index at the back of a textbook: instead of
reading the whole book to find "Redis," you jump to the sorted index and it tells
you the page.

The trade-offs (and why you don't just index everything):

- Indexes **speed up reads** (searches, filters, joins, sorts on that column).
- Indexes **cost storage** (the tree is extra data on disk).
- Indexes **slow down writes** slightly, because every `INSERT`/`UPDATE`/`DELETE`
  must also update the index trees.

So you index the columns you frequently *search or filter by*, and not the rest.
This project indexes `hostname`, `management_ip`, job `status`, job `created_at`,
and the foreign keys — precisely the columns the list/search endpoints filter on.
A **unique index** additionally enforces no duplicates (used on `email` and
`username`).

#### Transactions and ACID: all-or-nothing correctness

A **transaction** is a group of SQL statements treated as a single, indivisible
unit. Consider creating a test suite *and* its three test cases (§11.3). If the
suite is inserted but the server crashes before the cases, you'd have a broken
half-created suite. A transaction prevents that: you do all the work, then
`COMMIT` (make it permanent) — or if anything goes wrong, `ROLLBACK` (undo it all
as if nothing happened). SQLAlchemy's `session.commit()` is committing a
transaction.

Relational databases guarantee transactions are **ACID**:

- **Atomicity** — all statements in the transaction succeed, or none do. No
  half-states. (The suite+cases example.)
- **Consistency** — the database moves from one valid state to another; all
  rules (types, foreign keys, uniqueness, `NOT NULL`) hold before and after.
- **Isolation** — concurrent transactions don't see each other's uncommitted,
  in-progress changes; the result is as if they ran one at a time. This is what
  lets many users hit the app at once without corrupting data.
- **Durability** — once committed, the data survives crashes and power loss
  (it's safely written to disk).

ACID is the big reason to use a relational database for important data (users,
jobs, results) rather than a plain file or a cache — you get correctness
guarantees you would otherwise have to build yourself, and get subtly wrong.

#### Normalization (a one-paragraph mention)

**Normalization** is the practice of structuring tables so each fact lives in
exactly one place (e.g. a job stores a `device_id`, *not* a copy of the device's
hostname), which prevents update anomalies and saves space. This project is
mostly normalized, with two *deliberate* exceptions for good reasons: the
comma-separated `tags` (simplicity) and the duplicated `test_case_name` on
`test_results` (historical accuracy — §9.5). Knowing the rule *and* when to break
it on purpose is the skill.

#### Why PostgreSQL specifically

PostgreSQL ("Postgres") is the relational DBMS this project uses in production.
Why it, among the options:

- It is **fully ACID-compliant** and famously reliable with data.
- It is **free and open source** with no licensing cost.
- It is **feature-rich**: real `ENUM` types (which this project uses for
  vendors/statuses), a native `JSON`/`JSONB` column type (used for
  `metadata_json`), powerful indexing, and strong standards compliance.
- It handles **concurrency** well via **MVCC (Multi-Version Concurrency
  Control)**: instead of locking a row so readers must wait for writers, Postgres
  keeps multiple versions of a row, so readers see a consistent snapshot while a
  writer works. This means heavy reading and writing can happen at the same time
  without blocking each other — important for a web app with many simultaneous
  users.

(In *tests*, the project swaps Postgres for **SQLite**, a tiny database that
lives in a single file with no separate server — fast and disposable. This is
possible only because the ORM abstracts away the specific database. The trade-off
is SQLite isn't 100% identical to Postgres, which is why CI *also* runs the tests
against real Postgres — §24.3.)

### 3.4 ORM: talking to the database with objects

Writing raw SQL strings in your application code has real problems: the SQL is
just text, so the compiler can't catch typos or type errors; you have to manually
convert query results (rows of values) into Python objects and back; and if you
build SQL by gluing user input into strings, you open yourself to **SQL
injection** (an attacker types `'; DROP TABLE users; --` into a search box and
your concatenated query executes it). An **ORM (Object–Relational Mapper)** solves
all three.

An ORM is a library that **maps** the relational world (tables/rows/columns) onto
the object world (classes/instances/attributes), and generates the SQL for you:

| Database concept | Python concept |
|---|---|
| table `devices` | class `Device` |
| one row | one `Device` instance |
| column `hostname` | attribute `device.hostname` |
| `SELECT … WHERE id = 42` | `db.get(Device, 42)` |
| `INSERT …` | `db.add(Device(...)); db.commit()` |

This project uses **SQLAlchemy**, the de-facto standard Python ORM. The benefits
you get for free:

- **Type safety and autocomplete** — you work with real Python classes, so your
  editor and type checker understand them.
- **Automatic object ↔ row conversion** — query results come back as `Device`
  objects, not raw tuples you have to unpack.
- **SQL-injection protection** — the ORM sends your values as *parameters*
  separate from the query text, so user input can never be interpreted as SQL
  commands. This is a security win you get just by using the ORM correctly.
- **Database portability** — the same model code generates Postgres SQL in
  production and SQLite SQL in tests, because the ORM speaks a common dialect and
  translates.

The mental cost: an ORM is a **leaky abstraction**. It hides SQL, but to use it
*well* you must still understand the SQL it generates — otherwise you write code
that accidentally runs hundreds of queries (the N+1 problem, §11.3) or loads huge
tables into memory. So the right framing is: the ORM saves you from *writing*
SQL, not from *understanding* it. Everything `db.execute(select(Device)...)` does
is ultimately a `SELECT` you could have written by hand.

### 3.5 Concurrency, async, queues, and workers (the deep version)

This is the second big foundational topic, and it's the architectural soul of the
project. We'll build it up from first principles so you can explain processes vs.
threads, blocking vs. non-blocking, and exactly why a queue + worker exists.

#### Processes and threads

A **process** is a running program with its own private memory. Your backend is
one process; the worker is another; Postgres is another. Processes are isolated —
one crashing doesn't corrupt another's memory — but they can't share data
directly; they communicate over channels like network connections or a queue.

A **thread** is a single sequence of execution *inside* a process. A process can
have multiple threads sharing the same memory, allowing it to do several things
at once. (Python has a famous quirk, the *GIL* — Global Interpreter Lock — that
limits threads from running Python code truly in parallel, which is part of why
this project scales work by running *separate worker processes* rather than
threads.)

#### Synchronous vs. asynchronous; blocking vs. non-blocking

**Synchronous** means "do this now, and don't move on until it finishes." If a
function makes a synchronous network call, the calling code **blocks** — it
literally sits and waits, doing nothing else, until the response comes back.

**Asynchronous** means "start this now, and let it complete later while I get on
with other things." The work happens in the background; you're notified when it's
done.

Why this matters for a web server: a request handler that does something slow
*synchronously* holds that request's "line" open the whole time. If running a
test suite took 30 seconds and you did it inside the request, then for 30 seconds
that user's browser would show a spinner, *and* a server worker would be tied up
unable to serve anyone else. Do that a few times and the whole site stalls.

There are two distinct "async" ideas in this codebase; don't conflate them:

1. **Async I/O within one process** (the event loop). Modern servers can handle
   thousands of simultaneous connections on a few threads by never blocking:
   while one request waits on the database, the server's **event loop** switches
   to progress another request, and comes back when the database answers. FastAPI
   is built for this style (it runs on an ASGI server, uvicorn). Think of one
   chef who, instead of standing idle while water boils, starts chopping
   vegetables for the next order and returns when the water's ready.
2. **Offloading slow work to a different process entirely** (the queue + worker —
   the focus here). Even with a fast event loop, you do *not* want a genuinely
   long, heavy task (running a whole test suite) happening inside the web server
   at all. You want to hand it to a *separate* program so the web server stays
   free to answer requests instantly.

#### The task-queue pattern (producer → broker → consumer)

The standard solution to #2 is a **task queue**, with three roles:

1. **Producer** — here, the FastAPI backend. When a user triggers a run, the
   producer does *not* execute it. It records intent (creates a `queued` job row
   in Postgres) and then **enqueues** a small message ("run job 42") onto the
   queue. Then it immediately returns `201 Created` to the user. Total time: a few
   milliseconds.
2. **Broker / queue** — here, **Redis**. This is the middle-man that *holds* the
   list of pending job messages. A queue is conceptually a **FIFO** structure
   (First In, First Out — like a line at a checkout): messages are processed in
   the order they arrived.
3. **Consumer / worker** — here, a separate Python process running RQ. It sits in
   a loop, **dequeues** the next message from Redis, and actually does the slow
   work (runs the test cases, writes results to Postgres). When done, it grabs the
   next message.

```
[User] → POST /api/jobs → [Backend/Producer] → enqueue "job 42" → [Redis/Queue]
                                   │                                     │
                                   └── returns 201 immediately          ▼
                                                              [Worker/Consumer] → runs job → writes results to DB
```

The payoffs — and the answers to "why is it built this way":

- **Responsiveness:** the user gets an instant response; the slow work happens
  out of band.
- **Decoupling:** producing work and doing work are separate concerns, separately
  deployable and changeable.
- **Scalability:** if jobs pile up, you start *more worker processes* (or more
  worker machines) all pulling from the same queue — work is distributed
  automatically. The web tier and the worker tier scale independently.
- **Resilience / buffering:** if workers are momentarily down or busy, messages
  wait safely in Redis instead of being lost; work resumes when a worker is free.
- **Smoothing load spikes:** a sudden burst of 500 job requests doesn't crush the
  system; they queue up and drain at a sustainable rate.

The frontend's job, meanwhile, is to **poll**: since the result isn't ready when
the request returns, the browser periodically re-asks "is job 42 done yet?" until
the status becomes terminal (§22.3). (A fancier system might push updates over a
WebSocket instead of polling; the README lists that as a future improvement.)

#### What Redis actually is (so you can explain it)

**Redis (REmote DIctionary Server)** is an **in-memory data store**. Three ideas
unlock it:

- **In-memory:** Redis keeps its data in **RAM**, not on disk. RAM is orders of
  magnitude faster than disk, so Redis operations are extremely fast
  (sub-millisecond). The trade-off is RAM is volatile (lost on power-off) and
  smaller than disk — so Redis is for data that is small and/or transient, not
  your system of record. (Redis *can* optionally save snapshots to disk for
  durability, but speed is its identity.)
- **Key–value with rich data structures:** at its core Redis is a giant
  dictionary mapping string keys to values. But unlike a plain cache, the
  *values* can be rich types: strings, **lists** (which is exactly what a queue
  needs — push onto one end, pop from the other), hashes, sets, sorted sets, and
  more. RQ implements the job queue using Redis lists plus some bookkeeping keys.
- **Single-threaded event loop:** Redis processes commands one at a time on a
  single thread. That sounds like a limitation but is a strength: because only
  one command runs at a time, individual operations are **atomic** (no
  half-applied state, no locking needed), which makes it a safe coordination
  point for many producers and consumers. And since everything is in RAM, one
  thread is still blazingly fast.

**Why Redis here, specifically:** the project needs a fast, reliable place to
hand off job messages between the backend process and the worker process. Redis
is the de-facto standard for exactly this — it's lightweight, fast, has the
list/queue operations RQ needs built in, and is trivially run as one small
container. The project uses Redis purely as the **message broker** for the job
queue. (Redis is *also* commonly used as a cache and for rate-limiting and
sessions; this project doesn't, but that's why you've heard the name in many
contexts — it's a versatile in-memory tool.)

> **Database vs. Redis, in one line:** PostgreSQL is the durable, ACID *system of
> record* for data you must never lose (users, jobs, results); Redis is the fast,
> in-memory *coordination/queue* layer for transient hand-offs. Different jobs,
> used together.

### 3.6 Authentication, authorization, hashing, and JWT (the deep version)

Two words that sound alike but mean different things:

- **Authentication (authN)** = "Who are you?" — proving identity, i.e. logging
  in.
- **Authorization (authZ)** = "What are you allowed to do?" — permissions, here
  driven by your **role** (`admin`, `engineer`, `viewer`).

You authenticate *once* to establish identity, then every subsequent request is
*authorized* based on that identity.

#### Why you must hash passwords, and what hashing is

If you stored users' passwords as plain text and your database leaked, every
account would be instantly compromised — and because people reuse passwords,
you'd endanger their other accounts too. So you must never store the password
itself. Instead you store a **hash** of it.

A **cryptographic hash function** takes input of any size and produces a
fixed-size output (the "hash" or "digest") with these properties:

- **Deterministic** — the same input always yields the same hash.
- **One-way** — given the hash, you cannot feasibly compute the original input.
  (Easy forward, infeasible backward.)
- **Avalanche** — changing one character of input changes the hash completely.
- **Collision-resistant** — it's infeasible to find two inputs with the same
  hash.

So at registration you store `hash(password)`. At login you compute
`hash(typed_password)` and compare it to the stored hash. If they match, the
password was right — and you never had to keep the password around. A leak now
exposes only hashes, which can't be reversed.

#### Why bcrypt and not SHA-256/MD5

General-purpose hashes (MD5, SHA-256) are designed to be *fast* — good for
checksums, bad for passwords, because "fast" means an attacker who steals your
hashes can try *billions* of guesses per second against them. Password hashing
needs two more properties:

- **Salting:** a **salt** is a random value generated per user and mixed into the
  hash. It means two users with the same password get *different* hashes, and it
  defeats **rainbow tables** (giant precomputed tables of hash→password). The salt
  isn't secret; it's stored alongside the hash (bcrypt embeds it in the hash
  string itself).
- **Deliberate slowness (work factor):** **bcrypt** is engineered to be
  *intentionally* slow and to have a tunable **cost/work factor** — you can dial
  up how much CPU each hash takes. A single login hashing once in ~0.2s is
  invisible to a real user, but it caps an attacker at a handful of guesses per
  second per core instead of billions. As computers get faster, you raise the
  cost factor to keep pace.

So the chain is: never store the password → store a **salted**, **slow** hash →
use **bcrypt** because it provides both. This project uses `passlib` (a wrapper
that manages bcrypt cleanly and can upgrade algorithms over time).

#### Sessions vs. tokens, and why JWT here

Once you've authenticated, the server must recognize you on later requests — but
remember HTTP is **stateless** (§3.1), so the server forgets you instantly. Two
classic approaches:

- **Server-side sessions:** the server stores "session abc123 = user 42" in a
  database/Redis and gives the browser a cookie with `abc123`. Every request, it
  looks up the session. Simple, easy to revoke, but requires a shared session
  store and a lookup on every request.
- **Tokens (JWT):** the server gives the browser a self-contained, signed token
  that *itself* encodes who you are. The server doesn't store anything; it just
  verifies the token's signature on each request. This is **stateless auth**, and
  it's what this project uses.

#### What a JWT actually is, byte by byte

A **JWT (JSON Web Token)** is a string with three parts separated by dots:
`header.payload.signature`. Each part is **Base64URL-encoded** (Base64 is a way
to represent bytes as URL-safe text — it is *encoding, not encryption*; anyone
can decode and read it).

- **Header** — JSON saying the token type and signing algorithm, e.g.
  `{"alg": "HS256", "typ": "JWT"}`.
- **Payload** — JSON holding the **claims** (facts about the token). Standard
  claims include `sub` (subject — *who* the token is about; here the user's id)
  and `exp` (expiration timestamp). This app adds a custom `role` claim. Because
  the payload is only encoded, **never put secrets in it** — assume the client can
  read it.
- **Signature** — this is the security. The server computes
  `HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)` and appends
  it. **HMAC** is a keyed hash: it mixes the message with a secret key so that
  only someone who knows the key can produce a valid signature, *and* anyone can
  verify it by recomputing it (since they'd need the same secret — which only the
  server has). `HS256` names this scheme (HMAC + SHA-256).

#### How verification works, and the trade-off

When a request arrives with a token, the server recomputes the signature from the
header+payload using its secret key and checks it matches the signature in the
token. If even one byte of the payload were altered (say, a user changing their
role to `admin`), the recomputed signature wouldn't match and the token is
rejected. It also checks `exp` to reject expired tokens. Crucially, this requires
**no database lookup and no stored session** — the token is a *self-contained,
tamper-proof, expiring ID card*. That's the appeal: it scales effortlessly across
many server instances because there's no shared session state.

The trade-off you must be able to state: because the server keeps no record of
issued tokens, you **cannot easily revoke** a token before it expires (e.g.
instantly log someone out everywhere). The standard mitigation is to keep token
lifetimes **short** — this project expires them after 60 minutes — so a stolen or
stale token is only useful briefly. (Bigger systems add refresh tokens and
denylists; that's beyond this MVP.)

The whole flow in one breath: log in with email+password → server verifies the
bcrypt hash → server signs a JWT containing your id+role+expiry → browser stores
it → browser attaches `Authorization: Bearer <token>` to every request → server
verifies the signature and reads your identity, statelessly, on each call.

### 3.7 Layered architecture (separation of concerns)

A core idea you'll see repeated: split code into **layers**, each with exactly
one job, talking only to the layer directly below it. This project's backend
layers are:

```
HTTP request
   │
   ▼
[ route ]        ← parse/validate input, check auth, shape the response (HTTP-aware)
   │
   ▼
[ service ]      ← business logic: "what should happen" (knows nothing about HTTP)
   │
   ▼
[ model / ORM ]  ← talk to the database (knows nothing about business rules)
   │
   ▼
PostgreSQL
```

Plus **schemas** (define the JSON shapes crossing the API boundary) and the
**worker** (runs jobs off to the side).

**Why bother — the principle is "separation of concerns."** Each layer has a
single responsibility and a clean boundary, which buys you concrete things:

- **Understandability:** to grasp how device creation works, you read three small
  focused pieces (route → service → model), not one 300-line function doing
  validation, business rules, and SQL all at once.
- **Changeability:** you can swap PostgreSQL for another database by changing the
  model/ORM layer without touching routes; you could add a CLI or a different API
  on top of the *same* services because the services don't know or care that HTTP
  called them.
- **Testability:** because the service layer has no HTTP and no framework in it,
  you can test business logic by calling plain Python functions — fast, simple,
  no web server needed. The route layer's auth and validation can be tested
  separately.
- **Reusability and no duplication:** the same service function is called by
  multiple routes (and by the worker), so business rules live in exactly one
  place. A rule like "a device hostname must be unique" is enforced once.

The discipline that makes it work: **dependencies point downward only.** A route
may call a service; a service may use a model. But a model never imports a route,
and a service never touches the HTTP request object. The route layer is the *only*
layer that knows the web exists; the model layer is the *only* layer that knows
the database exists. Everything in between is pure logic. That one-directional
flow is what keeps the layers from collapsing back into a tangled mess.

### 3.8 The Python language features this codebase leans on

You said you know Python only a little, so this subsection is a targeted primer
on the *specific* Python features the code uses heavily. The goal is that when
you hit a `@decorator`, a `yield`, a `with`, or a `Mapped[int]` later, you don't
have to stop and google — you recognize it. Each item is "what it looks like,
what it does, why it's here."

**Type hints (annotations).** You'll see `def get_device(device_id: int) ->
Device:` everywhere. The `: int` and `-> Device` are **type hints**: they
*declare* that `device_id` should be an integer and the function returns a
`Device`. Crucially, plain Python **does not enforce** these at runtime — they're
documentation that tools (your editor, the `mypy`/`pyright` type checkers) read to
catch mistakes before you run the code. But two libraries here *do* act on them:
**Pydantic** uses type hints to validate data, and **FastAPI** uses them to
validate requests and generate docs. So in this project type hints are not just
comments — they're load-bearing. Composite hints you'll see: `list[Device]` (a
list of devices), `dict[str, int]` (a dict mapping strings to ints), `int | None`
(an int *or* `None` — the modern way to say "optional"), and `Optional[int]`
(the older spelling of the same thing).

**Decorators (`@something`).** A **decorator** is a function that wraps another
function to add behavior, written with an `@` on the line above a `def`. When you
write:

```python
@router.get("/devices")
def list_devices(...):
    ...
```

the `@router.get("/devices")` *takes* your `list_devices` function and registers
it as the handler for `GET /devices`, returning a (possibly wrapped) function in
its place. You'll see decorators for routing (`@router.get`, `@router.post`),
caching (`@lru_cache` on `get_settings`, §6), and test fixtures (`@pytest.fixture`,
§19). The mental model: `@d` above `def f` means "replace `f` with `d(f)`." You
mostly *use* decorators others wrote rather than writing your own, but knowing
they're "a function wrapping a function" demystifies the `@` symbol completely.

**`yield` and generators.** A normal function `return`s a value once and is
finished. A function containing `yield` is a **generator** — calling it doesn't
run the body; it returns a special object you can step through, and the body runs
up to a `yield`, pauses there handing back a value, and resumes after the `yield`
later. This project uses the pattern for *setup/teardown*: `get_db` (§8) opens a
database session, `yield`s it to the endpoint, and the code *after* the `yield`
(closing the session) runs once the request is done. You'll also see it in test
fixtures. The key insight: `yield` lets one function bracket some other work —
"do setup, hand control away, get control back, do cleanup" — which is exactly
what resource management needs.

**`with` blocks (context managers).** A **context manager** guarantees cleanup
happens even if an error occurs. `with open(path) as f:` opens a file and
*guarantees* it gets closed when the block ends, error or not. The same pattern
manages database sessions and the in-memory `io.StringIO` buffer used to build CSV
reports (§11.6). The `with` statement is Python's structured answer to "I acquired
a resource; make absolutely sure I release it." Generators with `yield` (above)
are in fact one common way to *build* a context manager.

**f-strings.** `f"job {job_id} finished with {status}"` is an **f-string** —
prefix a string with `f` and any `{expression}` inside is evaluated and inserted.
It's the modern, readable way to build strings from values. (Note: the security
discussion in §3.4/§19 warns against building *SQL* with f-strings — that's the
one place you must not, because it enables injection. For logs and messages, they
are perfect.)

**Comprehensions.** `[r.status for r in results]` is a **list comprehension** — a
compact way to build a list by transforming each item of another iterable. Read it
right-to-left of the `for`: "for each `r` in `results`, collect `r.status`." There
are also dict comprehensions (`{k: v for ...}`) and generator expressions
(parentheses instead of brackets). They replace the verbose "make an empty list,
loop, append" pattern with one expressive line, and you'll see them when the code
shapes query results into response data.

**`*args` and `**kwargs`.** When you see a function defined as `def f(*args,
**kwargs)` or a call like `Device(**data)`, the `*` and `**` are
**unpacking/packing** operators. `*args` collects extra positional arguments into
a tuple; `**kwargs` collects extra keyword arguments into a dict. Used the other
way, `**data` *spreads* a dict's key–value pairs as named arguments — so
`Device(**{"hostname": "sw1", "vendor": "cisco"})` is the same as
`Device(hostname="sw1", vendor="cisco")`. This is how the code turns a validated
schema's fields into a model constructor call concisely.

**Classes, `self`, and `__init__`.** A **class** is a blueprint; an **instance**
is one object built from it. `__init__` is the constructor (runs when you create
an instance), and `self` is the conventional name for "this particular instance"
— every method takes `self` as its first parameter so it can read/write that
instance's own attributes. The ORM models (`class Device(Base):`), the Pydantic
schemas (`class DeviceOut(BaseModel):`), and the custom error classes (`class
AppError(Exception):`) are all classes. **Inheritance** (`class
DeviceOut(BaseModel)`) means "DeviceOut *is a* BaseModel and gets all its
behavior" — that's how Pydantic and SQLAlchemy give your classes their powers:
you inherit from their base class.

**Enums.** An `Enum` is a fixed set of named constant values, e.g. `JobStatus`
with members `QUEUED`, `RUNNING`, `PASSED`, `FAILED`, `CANCELLED`. Instead of
passing around bare strings like `"queued"` (easy to typo into `"queed"` with no
warning), you use `JobStatus.QUEUED`. The benefits: typos become errors, your
editor autocompletes the options, and the valid set is documented in one place.
This project uses enums for job statuses and for vendor/status fields, and maps
them to real database `ENUM` types (§9).

**Truthiness and `None`.** Python treats many values as "falsy": `None`, `0`,
empty string `""`, empty list `[]`, empty dict `{}`. So `if not results:` means
"if results is empty (or None)." `None` is Python's "no value" (like `null`
elsewhere); you'll see `x is None` / `x is not None` checks constantly, especially
around optional fields and "did this lookup find anything?" The dashboard's
division-by-zero guard (§11.5) and the "user not found" auth paths (§11.1) both
hinge on these `None`/empty checks.

**Modules, packages, and imports.** A `.py` file is a **module**; a folder with an
`__init__.py` is a **package**. `from app.models.device import Device` reaches into
the `app/models/device.py` module and pulls out the `Device` class. The dotted
path mirrors the folder structure (§5). Understanding imports is understanding how
the layered architecture physically connects: routes `import` services, services
`import` models, and the dependency direction in those import lines *is* the
layering from §3.7 made literal.

---

## 4. The technology stack, explained

Every tool here was chosen for a reason. This section gives each one the
"what is it / how does it work / why this over the alternatives" treatment so you
can defend the choices in an interview.

### Backend

#### Python 3.12
The language the backend is written in. Python is **interpreted** (run by the
Python interpreter rather than compiled to a standalone executable up front),
**dynamically typed** (variable types are checked as the program runs, not by a
compiler beforehand — though we add optional type hints that tools can check),
and prized for readability. Its giant ecosystem of libraries (PyPI) is why it
dominates web backends, data, and scripting. *Why here:* fast to write, batteries
included, and every tool we need (FastAPI, SQLAlchemy, RQ) is a mature Python
library.

#### FastAPI — the web framework
A **web framework** is a library that handles the grunt work of being a web
server: accepting HTTP requests, routing each URL to the right function, parsing
the body, and writing the response. FastAPI's distinctive features:

- **Type-hint-driven validation:** you declare a function's inputs with Python
  type hints and Pydantic models, and FastAPI *automatically* validates incoming
  data, rejects bad requests with a clear `422` error, and converts the response
  to JSON. You write less boilerplate and get correctness for free.
- **Automatic interactive docs:** because the types fully describe the API,
  FastAPI generates an **OpenAPI** spec and serves browsable, runnable docs at
  `/docs`. No separate documentation step.
- **Built on ASGI / async:** FastAPI runs on an **ASGI** server (uvicorn here).
  ASGI (Asynchronous Server Gateway Interface) is the modern standard that lets a
  Python web app handle many concurrent connections on an **event loop** (§3.5)
  instead of one-thread-per-request. That's the "fast" in FastAPI: while one
  request waits on the database, the server progresses others.

*Why over alternatives:* Flask is simpler but lacks built-in validation/async/docs;
Django is heavier and more opinionated (full ORM, admin, templates) than this API
needs. FastAPI hits the sweet spot for a typed JSON API.

#### Pydantic v2 — data validation and serialization
A library where you declare the **shape** of data as a Python class with typed
fields, and it enforces that shape at runtime: coercing/validating types, applying
constraints (e.g. "this string must be an email"), and **serializing** to/from
JSON. FastAPI is built on top of it — your request/response models *are* Pydantic
models. v2's core is written in Rust, making validation very fast. *Why:* it
turns "is this incoming JSON valid?" from hand-written `if` checks into a
declarative class, and gives one consistent definition of every data shape that
crosses the API boundary.

#### SQLAlchemy 2 — the ORM
The de-facto standard Python ORM (§3.4): it maps classes↔tables and generates SQL,
giving type safety, object↔row conversion, SQL-injection protection, and database
portability (Postgres in prod, SQLite in tests). *Why over alternatives:* it's the
most mature, powerful, and widely understood option; lighter ORMs exist but
SQLAlchemy's flexibility (you can drop to raw SQL when needed) makes it the safe
industry choice.

#### Alembic — database migrations
A **migration** is a versioned, ordered script that changes the database *schema*
(adds a table, adds a column, etc.). As the models evolve, the live database's
structure must evolve in lockstep — and you can't just drop and recreate it
without destroying data. Alembic (made by SQLAlchemy's author) records each schema
change as a numbered script with `upgrade()`/`downgrade()` steps, so every
environment (your laptop, CI, production) can be brought to the exact same schema
version reproducibly, and changes can be rolled back. *Why:* without migrations,
keeping schemas in sync across environments is error-prone and irreversible; this
is the standard, safe way (more in §18).

#### PostgreSQL 16 — the production database
A mature, open-source **relational database** (§3.3). It's fully ACID-compliant,
handles concurrency with **MVCC** (Multi-Version Concurrency Control — readers and
writers don't block each other because each transaction sees a consistent
snapshot), and supports rich types including the `JSON`/`JSONB` columns this
project uses for flexible metadata. *Why over alternatives:* compared to MySQL,
Postgres has stronger standards-compliance and richer features; compared to a
NoSQL store, our data is highly relational (users → jobs → results), so a
relational DB with real foreign keys and transactions is the right fit.

#### Redis 7 — the queue broker
An **in-memory key–value data store** (covered deeply in §3.5). Used here purely
as the **message broker** holding the list of pending jobs between the backend
(producer) and the worker (consumer). It's blazing fast because data lives in RAM
and commands run atomically on a single thread, and it has the list operations a
queue needs built in. *Why:* it's the lightweight, battle-tested standard for task
queues, and runs as one tiny container.

#### RQ (Redis Queue) — background jobs
A small Python library implementing the producer/broker/consumer task-queue
pattern on top of Redis. The backend calls `queue.enqueue(...)` to push a job; a
separate `rq worker` process pops jobs and runs them. *Why over alternatives:*
**Celery** is the heavyweight standard but is complex to configure; RQ is
deliberately minimal and easy to understand, which suits an MVP. The project even
adds a `SYNC_JOBS` switch so tests can run jobs inline without a real worker.

#### passlib + bcrypt — password hashing
`bcrypt` is the slow, salted, tunable-cost password-hashing algorithm (§3.6);
`passlib` is a friendly wrapper that manages it and can transparently upgrade
algorithms over time. *Why:* you must never store raw passwords, and bcrypt is the
proven choice for making stolen hashes practically uncrackable.

#### python-jose — JWT tokens
A library that **creates and verifies JWTs** (§3.6): it Base64URL-encodes the
header/payload and computes/checks the HMAC-SHA256 signature with the secret key.
*Why:* hand-rolling token signing is a security footgun; jose is a standard,
audited implementation.

#### structlog — structured logging
Ordinary logging emits free-form text lines that are hard for machines to parse.
**Structured logging** emits each log as a set of key/value pairs (rendered as
JSON here), so logs can be searched, filtered, and aggregated by field (e.g. "show
all logs where `job_id=42`") in tools like the ELK stack or Datadog. *Why:* in any
real system you need to query logs, and JSON logs make that trivial.

#### paramiko / pysnmp — real device hooks
`paramiko` is a real **SSH** library (run commands on a remote device);
`pysnmp` speaks **SNMP** (Simple Network Management Protocol, used to query
network gear). They're present as *optional* real-mode integrations — the project
defaults to a **mock** device client so it runs with zero real hardware. *Why:*
they show the seam where real network I/O would plug in, without requiring it for
the demo.

#### pytest + httpx — testing
`pytest` is Python's most popular **testing framework** (you write test functions,
it discovers and runs them and reports failures). `httpx` is an HTTP client that
can call the FastAPI app **in-process** (no real network), so tests exercise the
real routing/validation/auth stack end-to-end, fast. *Why:* pytest's fixtures and
plain-function style make tests easy to write; httpx's test client makes API tests
realistic yet fast.

### Frontend

#### React 18 — the UI library
React builds the interface from **components** — reusable, self-contained pieces of
UI (a button, a table, a whole page) that are just functions returning markup.
React's big idea is being **declarative**: you describe *what* the UI should look
like for the current data, and React figures out *how* to update the screen. It
does this efficiently with a **virtual DOM** — an in-memory representation of the
UI. When your data changes, React builds a new virtual DOM, **diffs** it against
the previous one (this is called *reconciliation*), and applies only the minimal
real changes to the actual browser DOM (which is slow to touch). State inside
components is managed with **hooks** like `useState` and `useEffect`. *Why over
alternatives:* React is the dominant UI library with the largest ecosystem; its
component + declarative model scales from tiny widgets to large apps.

#### TypeScript — typed JavaScript
Browsers only run **JavaScript**, which is dynamically typed (no compile-time type
checking), making large codebases bug-prone. **TypeScript** is a superset of
JavaScript that adds **static types**; a compiler checks them and then *erases*
them, emitting plain JavaScript the browser can run. *Why:* it catches whole
classes of bugs (typos, wrong shapes, null mistakes) before the code ever runs,
and makes editor autocomplete and refactoring reliable — essential on a typed API
where the frontend and backend data shapes must match.

#### Vite — build tool and dev server
A browser can't directly run a project of many TypeScript/JSX files and npm
imports; they must be transformed and bundled. **Vite** is the **build tool** that
does this. In development it serves files using the browser's native **ES modules**
and offers **HMR** (Hot Module Replacement — your code edits appear in the browser
in milliseconds without a full reload). For production it **bundles** everything
into a few optimized static files. *Why over alternatives:* older bundlers
(Webpack) rebuild the whole app on every change and start slowly; Vite's
native-ESM dev server is near-instant.

#### React Router — client-side routing
A **single-page application (SPA)** loads one HTML page and then swaps content via
JavaScript instead of fetching a new page from the server per click. **React
Router** maps the browser URL to which React component to show, and updates the URL
without a full page reload — so `/devices` and `/jobs/42` feel like separate pages
but never round-trip to the server for HTML. *Why:* it's the standard way to give
an SPA real, bookmarkable URLs and back-button support.

#### TanStack Query (React Query) — server-state management
Fetching data from an API and keeping the UI in sync involves a lot of fiddly
state: loading flags, errors, caching, re-fetching, and **polling**. TanStack
Query manages all of that declaratively: you describe a query (a key + a fetch
function) and it handles caching, background refetching, and — crucially here —
**polling** on an interval. *Why here specifically:* the job-queue design means
results aren't ready immediately, so the UI must repeatedly ask "is job 42 done
yet?"; React Query's `refetchInterval` powers that auto-refresh with almost no
code (§22.3).

### Infrastructure

#### Docker — containers
Software that runs on your machine often breaks on another because of different OS
versions, installed libraries, or config — the "works on my machine" problem.
**Docker** packages an app *together with* its dependencies and environment into a
**container** that runs identically everywhere.

- **Container vs. virtual machine:** a **VM** virtualizes an entire operating
  system (its own kernel), making it heavy (gigabytes, slow to boot). A
  **container** shares the host's OS kernel and isolates just the app using Linux
  features — **namespaces** (give the container its own view of processes,
  network, filesystem) and **cgroups** (limit its CPU/memory). So containers are
  lightweight (megabytes, start in seconds) yet still isolated.
- **Image vs. container:** an **image** is the read-only blueprint (the app + its
  filesystem), built from a `Dockerfile` of instructions. A **container** is a
  running instance of an image. Images are built in **layers** (each Dockerfile
  step is a cached layer), so rebuilds are fast and layers are shared between
  images.

*Why:* it makes "it works on my machine" actually transferable to CI and
production, and lets each of our five services run in its own clean environment.

#### Docker Compose — multi-container orchestration
This project has five services (backend, worker, frontend, Postgres, Redis).
Starting and wiring them by hand would be tedious. **Docker Compose** declares all
of them in one `docker-compose.yml` — their images, environment variables,
ports, dependencies, and a shared network so they can find each other by name —
and starts the whole system with `docker compose up`. *Why:* one command brings up
the entire stack reproducibly; it's the standard for local multi-service dev.

#### GitHub Actions — CI
**Continuous Integration (CI)** is the practice of automatically building and
testing your code on every push, so bugs are caught immediately rather than in
production. **GitHub Actions** is GitHub's built-in CI system: a YAML workflow
defines jobs (here: run the backend pytest suite, build the frontend) that run on
GitHub's servers whenever you push. *Why:* it guarantees that broken code is
flagged automatically, keeping the main branch healthy without manual effort.

---

## 5. How the repository is organized

```
network-test-orchestrator/
├── docker-compose.yml        # defines & wires the 5 services
├── README.md                 # human overview
├── backend/                  # the Python API + worker
│   ├── Dockerfile            # how to containerize the backend
│   ├── requirements.txt      # Python dependencies
│   ├── alembic.ini           # migration config
│   └── app/
│       ├── main.py           # FastAPI app entrypoint
│       ├── seed.py           # demo data loader
│       ├── core/             # config, security, errors, logging (cross-cutting)
│       ├── db/               # database engine, session, base, migrations
│       ├── models/           # SQLAlchemy ORM classes (tables)
│       ├── schemas/          # Pydantic classes (JSON shapes)
│       ├── services/         # business logic
│       ├── api/              # routes (HTTP endpoints) + deps
│       ├── workers/          # queue, worker, task runner
│       ├── integrations/     # device clients (mock + real)
│       └── tests/            # pytest tests
└── frontend/                 # the React app
    ├── Dockerfile
    ├── package.json          # JS dependencies & scripts
    ├── vite.config.ts
    └── src/
        ├── main.tsx          # React entrypoint
        ├── App.tsx           # route table
        ├── api/              # functions that call the backend
        ├── auth/             # login state (React context)
        ├── components/       # reusable UI pieces
        ├── pages/            # one component per screen
        └── styles/           # CSS
```

The structure itself is a lesson: files are grouped **by responsibility**, not
dumped in one folder. When you want to change how the database is shaped, you go
to `models/`. When you want to change a URL, you go to `api/routes/`. This is
called a **package-by-layer** layout and it's extremely common.

**Package-by-layer vs. package-by-feature, and why this choice.** There are two
classic ways to organize a codebase. **Package-by-layer** (what this project
uses) groups files by their *technical role*: all the models together, all the
schemas together, all the services together. **Package-by-feature** would instead
group by *domain concept*: a `devices/` folder containing the device model,
schema, service, and routes all together, then a `jobs/` folder with its model,
schema, service, and routes. Neither is universally "correct." Package-by-layer
shines for a project this size and for *learning*, because it makes the
architecture itself visible — you can see the layers (models → schemas → services
→ routes) as folders, and a newcomer immediately understands the shape of the
system. Its weakness shows in very large codebases, where changing one feature
means touching five scattered folders; that's when teams often switch to
package-by-feature. Knowing both, and being able to say *why* a project picked
one, is exactly the kind of judgment these layouts are meant to teach.

**Read the tree top-down as a dependency gradient.** Within `app/`, the folders
are roughly ordered from most foundational to most outward-facing, and that's not
an accident — it mirrors the build order from §26. `core/` holds cross-cutting
utilities everything depends on (config, security, errors). `db/` is the storage
foundation. `models/` defines the domain shapes. `schemas/` defines the API
shapes. `services/` holds logic that uses models. `api/` exposes that logic over
HTTP. `workers/` runs logic in the background. `integrations/` reaches out to the
external world. `tests/` verifies it all. When you open the project fresh, reading
the folders in roughly this order means each one builds on concepts from the last
— which is also exactly the order this tutorial walks through them.

**One mental rule for "where does this code go?"** When you're unsure where a new
piece of code belongs, ask what *kind* of thing it is, not what feature it serves.
Is it a database shape? `models/`. A request/response shape? `schemas/`. A rule or
calculation? `services/`. A URL? `api/routes/`. A cross-cutting helper used
everywhere? `core/`. Background work? `workers/`. This single question keeps the
layered structure clean over time and prevents the slow slide into a junk-drawer
codebase where business logic leaks into routes and database details leak into the
UI. The discipline of the folder layout is really the discipline of the
architecture made visible.

Now we go file by file.

---

## 6. Backend, part 1: configuration, logging, errors

These live in `backend/app/core/` — the "cross-cutting" utilities used
everywhere.

### 6.1 `core/config.py` — settings

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/network_orchestrator"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEVICE_EXECUTION_MODE: str = "mock"
    BACKEND_CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:5173", ...])
    LOG_LEVEL: str = "INFO"
```

**What it is:** a single object holding every configurable value for the app.

**Why it exists — the Twelve-Factor principle of config in the environment:** You
should *never* hard-code things like database passwords or secret keys into your
source code. They differ between your laptop, CI, and production, and secrets
must not be committed to git. Instead, you read them from **environment
variables** (or a local `.env` file). `BaseSettings` (from `pydantic-settings`)
does exactly this: each field's *default* is used if no environment variable
overrides it. So `DATABASE_URL` defaults to a local Postgres, but in Docker it's
overridden to point at the `postgres` container.

**What is an environment variable, really?** When any program starts, the
operating system hands it a little dictionary of string key/value pairs called
the *environment*. It's part of the process's startup context, separate from the
program's code and from its command-line arguments. You can set one in PowerShell
with `$env:DATABASE_URL = "..."` before launching, or Docker can inject them, or a
`.env` file can be loaded. The key insight is that the **same compiled code** can
behave differently in different places purely because the environment around it
differs — no code change, no rebuild. That is exactly what you want: one artifact,
many environments.

**Why this is called "Twelve-Factor."** The *Twelve-Factor App* is a famous set of
twelve guidelines (written by engineers at Heroku) for building software that
deploys cleanly to the cloud. Factor III is "store config in the environment."
The reasoning: things that change between deploys (database location, secret
keys, feature flags) are *config*; things that stay the same (your business
logic) are *code*. Mixing them means you'd have to edit and re-commit source code
just to point at a different database — error-prone and a security hazard (secrets
in git history live forever). Separating them means a single immutable build can
be promoted unchanged from your laptop → CI → staging → production, with only the
environment differing. This is one of the most important operational habits in
modern backend work.

**Why a typed Settings class instead of reading `os.environ` directly?** You
*could* sprinkle `os.environ["DATABASE_URL"]` throughout the code, but then: every
value is a raw string (no `int`/`bool`/list parsing), a typo in a key isn't
caught until that line runs, and there's no single place to see every knob the app
has. `BaseSettings` fixes all three. It reads each declared field from the
environment, **coerces** it to the declared type (so `ACCESS_TOKEN_EXPIRE_MINUTES`
becomes a real `int`, not `"60"`), validates it once at startup, and gives you one
authoritative, autocompleting object. If a required value is malformed, the app
**fails fast** at boot with a clear error instead of crashing mysteriously deep
inside a request later — "fail fast" is the principle that it's far better to die
immediately and loudly at startup than to limp along and break unpredictably.

**Key details:**

- `env_file=".env"` — automatically loads a `.env` file if present.
- `extra="ignore"` — unknown env vars don't crash the app.
- The `field_validator` for `BACKEND_CORS_ORIGINS` lets you specify origins
  either as a real list *or* a comma-separated string (`"a,b,c"`), splitting the
  string into a list. This is a small convenience because env vars are always
  strings.
- **CORS** = Cross-Origin Resource Sharing. Browsers block a page served from
  `localhost:5173` from calling an API on `localhost:8000` *unless the API
  explicitly allows it*. This list is that allowlist.

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

`@lru_cache` means "remember the result of this function." Settings are read
once and reused — you don't re-parse the environment on every call. `settings`
is the shared instance everything imports.

**How `lru_cache` actually works.** LRU stands for *Least Recently Used*. It's a
decorator from Python's standard `functools` that wraps a function in a **cache**:
the first time you call it with a given set of arguments, it runs the function and
*stores* the return value keyed by those arguments; every later call with the same
arguments returns the stored value instantly without re-running the body. ("Least
Recently Used" refers to the eviction policy when the cache hits its size limit —
it throws out the entry that hasn't been used in the longest time. Here the
function takes no arguments, so there's only ever one cached entry and nothing is
evicted.) The practical effect is that `get_settings()` behaves like a **lazy
singleton**: the `Settings()` object is constructed exactly once, the first time
anyone asks, and reused forever after. Why bother? Constructing `Settings()` reads
and parses the environment and `.env` file, which you don't want to repeat on
every request; and you want every part of the app to share *the same* settings
object, not subtly different copies.

> **Decision to remember:** Configuration is data, not code. Centralize it, give
> safe defaults, and source secrets from the environment.

> **Security flag worth stating out loud:** `JWT_SECRET_KEY` defaults to
> `"change-me"`. That default is fine for local development but would be a serious
> vulnerability in production — anyone who knows the secret can forge valid tokens
> for any user and any role (§3.6). The safe-default-but-must-override pattern is
> deliberate: the app runs out of the box, but a real deployment is expected to
> set a long, random secret via the environment. If an interviewer asks "what's a
> security weakness in this codebase?", this is the honest answer to give.

### 6.2 `core/logging.py` — structured logging

```python
def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(processors=[..., structlog.processors.JSONRenderer()], ...)
```

**What it is:** sets up logging so that log lines come out as **JSON** with
fields like timestamp, level, and any extra key/values you attach.

**Why structured logging?** A plain log line like `job 42 done in 1200ms` is
fine for a human but painful for a machine. JSON logs like
`{"event": "job_completed", "job_id": 42, "duration_ms": 1200}` can be searched,
filtered, and aggregated by log tools. In production you'd ship these to
something like Datadog or CloudWatch.

**Why logging at all, instead of `print()`?** Beginners reach for `print()` to
see what's happening, but logging is `print()` grown up. A real logging system
gives you four things `print` can't: **levels** (tag each message as DEBUG, INFO,
WARNING, ERROR, or CRITICAL, so you can show everything in development but only
warnings-and-worse in production by setting one `LOG_LEVEL`); **routing** (send
logs to the console, a file, or a remote service without changing the call
sites); **structure** (attach machine-readable fields); and **consistency**
(every line automatically carries a timestamp and level). `print` writes
unstructured text to one place and has no notion of severity.

**Why JSON, line by line.** Imagine production is throwing errors and you need to
find every log for job 42. With free-text logs you'd write fragile text searches
and hope the format never changed. With JSON logs, every line is a structured
object, so a log tool can do the equivalent of `WHERE job_id = 42` — exact,
fast, and reliable. This is the same idea as structured *data* in a database,
applied to *logs*. The cost is that JSON is slightly less pleasant to read raw in
a terminal; the payoff is that at any real scale you're searching logs with tools,
not eyeballs, and structure is what makes that possible.

**What "processors" are.** structlog builds each log line by passing it through a
*pipeline* of small functions called **processors** — one adds the timestamp,
another adds the log level, another finally renders the whole thing as JSON
(`JSONRenderer`). This is the **pipeline pattern**: a series of steps each
transforming the data a bit before handing it to the next. You can insert or
remove a step (say, switch `JSONRenderer` for a pretty colored console renderer in
development) without touching any of the `log.info(...)` calls scattered through
the app.

`get_logger(name)` returns a logger you can call like
`log.info("job_started", job_id=job.id, mode="mock")`. Notice the **event name**
is the first argument and everything else is structured context — that's the
structlog style. Compare it to the old way, `log.info(f"job {job.id} started in
{mode} mode")`, where the values are *baked into a sentence* and have to be
re-extracted with text parsing later. In the structured style the values stay as
first-class fields (`job_id=42`, `mode="mock"`), which is exactly what makes them
queryable downstream.

### 6.3 `core/errors.py` — typed application errors

```python
class AppError(HTTPException):
    code: str = "APP_ERROR"
    def __init__(self, detail: str, status_code: int = 400, code: str | None = None):
        super().__init__(status_code=status_code, detail={"detail": detail, "code": code or self.code})

class NotFoundError(AppError):
    code = "NOT_FOUND"
    def __init__(self, detail="Resource not found"):
        super().__init__(detail, status.HTTP_404_NOT_FOUND)
# ConflictError (409), UnauthorizedError (401), ForbiddenError (403), BadRequestError (400)...
```

**What it is:** a small family of custom exception classes, each tied to an HTTP
status code and a short machine-readable `code` string.

**Why it exists:** Instead of scattering `raise HTTPException(status_code=404,
detail="...")` everywhere, the service layer can `raise NotFoundError("Device
not found")`. This is cleaner and **consistent**: every error response has the
same shape, `{"detail": "<message>", "code": "<CODE>"}`. The frontend can rely
on that shape (we saw `body.detail?.code` in the API client). It inherits from
FastAPI's `HTTPException`, so FastAPI knows how to turn it into the right HTTP
response automatically.

This is a good example of **don't repeat yourself (DRY)** and **designing your
error contract** as deliberately as your success responses.

**Why model errors as a class hierarchy.** Notice the shape: a base `AppError`
holds the common behavior (build that `{detail, code}` body, default to status
400), and each specific error (`NotFoundError`, `ConflictError`, ...) is a
**subclass** that just fixes the status code and `code` string. This is
**inheritance** used exactly as intended: put shared behavior in the parent,
specialize in the children. Adding a new error type later is a three-line
subclass, and it automatically gets the consistent body shape for free.

**Why raise exceptions instead of returning error values?** In Python the
idiomatic way to signal "this can't proceed" is to **raise an exception**, which
immediately stops the current function and unwinds the call stack until something
*catches* it. The elegance here is that the service layer, buried several calls
deep, can simply `raise NotFoundError(...)` and doesn't need to know anything
about HTTP — yet because `AppError` *is a* FastAPI `HTTPException`, FastAPI's
outermost layer catches it and turns it into the correct HTTP response
automatically. So the error travels cleanly from deep business logic up to the
edge of the system without every intermediate function having to check a return
code and pass it along. This keeps the "happy path" code readable: functions
return the thing they compute, and exceptional cases jump out of the flow.

**Why a machine-readable `code` *and* a human `detail`?** The `detail` string
("Device not found") is for a developer reading logs or an error toast. The `code`
("NOT_FOUND") is for *the frontend's logic* — code can branch on a stable
identifier (`if code === "CONFLICT"`) without fragile string-matching on a message
that might be reworded tomorrow. Giving every error both a human face and a
stable machine handle is a small thing that makes the API far nicer to build
against.

---

## 7. Backend, part 2: security (passwords & JWT)

`backend/app/core/security.py` — the cryptography helpers.

### 7.1 Password hashing

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

**The rule:** Never store passwords. Store a **hash** of the password.

A **hash** is a one-way function: easy to compute forward (password → hash),
practically impossible to reverse (hash → password). When a user logs in, you
hash what they typed and compare it to the stored hash. If your database ever
leaks, attackers get hashes, not passwords.

**bcrypt** specifically is a *slow, salted* hashing algorithm designed for
passwords:

- **Salted** — a random value is mixed in, so two users with the same password
  get different hashes (defeats precomputed "rainbow table" attacks). The salt
  is stored inside the hash string itself.
- **Slow (deliberately)** — it's tuned to take a fraction of a second. That's
  invisible to a legitimate login but makes brute-forcing billions of guesses
  infeasible.

`passlib`'s `CryptContext` wraps all of this. `deprecated="auto"` means if you
later upgrade hashing schemes, old hashes are recognized and can be upgraded on
next login.

**What the stored hash actually looks like, decoded.** A bcrypt hash is a single
string like `$2b$12$Nq3...<22 chars of salt>...<31 chars of hash>`. The parts
between the `$` signs are self-describing: `2b` is the bcrypt variant, `12` is the
**cost factor** (meaning 2¹² = 4096 internal rounds of the key-setup step), then
the next 22 characters are the random **salt**, and the rest is the actual hash.
This is why `verify_password` doesn't need a separately stored salt — when it
verifies, it reads the cost and salt straight out of the stored string, re-runs
bcrypt on the typed password with those exact parameters, and checks whether the
result matches. Everything needed to verify (except the password itself) lives
inside that one self-contained string.

**Why the cost factor is the whole game.** That `12` is a dial. Raise it to `13`
and every hash takes *twice* as long; `14` is four times as long, and so on — it's
exponential. You tune it so a single login costs maybe 100–300 milliseconds on
your server: unnoticeable to a real user logging in once, but catastrophic for an
attacker who stole your hash table and wants to try a billion guesses. At ~5
guesses/second/core instead of billions/second, a strong password becomes
effectively uncrackable. And because the cost is embedded in each hash, you can
raise it over the years as hardware gets faster, and old hashes still verify fine
at their original cost — then `deprecated="auto"` quietly re-hashes them at the new
cost the next time those users log in.

**Why `verify_password` is also slow on purpose, and constant-time.** Verifying
runs the same expensive bcrypt computation, so login is intentionally not instant.
The comparison of the final hashes is also done in **constant time** — it doesn't
return early at the first differing byte. If it *did* stop early, an attacker
could measure tiny timing differences to learn how many leading bytes they got
right (a **timing attack**); constant-time comparison leaks nothing.

> **Never** use general-purpose hashes like MD5 or SHA-256 for passwords — they
> are *fast*, which is exactly wrong for this job.

### 7.2 JWT creation and verification

```python
def create_access_token(subject: str | int, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
```

A JWT has three parts joined by dots: `header.payload.signature`.

- The **payload** holds **claims** — facts about the token. Standard claims
  include `sub` (subject = who the token is about; here the user id) and `exp`
  (expiration time). This app also adds a custom `role` claim via `extra`.
- The **signature** is computed from the header + payload + the secret key using
  the `HS256` algorithm. On `decode`, the library recomputes the signature and
  rejects the token if it doesn't match (forged or tampered) or if it's expired.

So a token is a **self-contained, tamper-proof, expiring ID card**. The server
doesn't store sessions; it just trusts any token it can verify. The tradeoff:
you can't easily "revoke" a token before it expires (a known JWT limitation),
which is why the expiry is short (60 minutes here).

**A concrete token, taken apart.** To make this real, here's what one of this
app's tokens actually looks like and means. The string the server sends back at
login is three Base64URL chunks joined by dots:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3IiwiZXhwIjoxNzAwMDAzNjAwLCJyb2xlIjoiZW5naW5lZXIifQ.3qZ8s...signature...
```

Decode the first chunk (the **header**) and you get JSON describing how the token
is signed:

```json
{ "alg": "HS256", "typ": "JWT" }
```

Decode the second chunk (the **payload**) and you get this app's claims — the
user id in `sub`, the expiry in `exp` (a Unix timestamp), and the custom `role`:

```json
{ "sub": "7", "exp": 1700003600, "role": "engineer" }
```

The third chunk is the **signature** — raw bytes, not JSON. Two things are worth
seeing here. First, you can decode the header and payload *yourself* with nothing
but a Base64 decoder (try it on jwt.io); that's the point of "encoding, not
encryption" (§3.6) and exactly why you must never put a secret in the payload —
the client can read it. Second, what you *cannot* do without the server's secret
key is produce a *valid signature*. If an attacker decoded the payload, changed
`"role": "engineer"` to `"role": "admin"`, and re-encoded it, the signature would
no longer match the tampered payload, and `decode_access_token` would reject it.
That single property — anyone can read it, only the server can mint or validate it
— is the whole security model in one sentence.

**Walking the `create_access_token` code line by line.** `datetime.now(timezone.utc)`
gets the current time *as an explicit UTC time* (never use naive local time for
security timestamps — servers in different timezones must agree on when a token
dies). Adding `timedelta(minutes=...)` produces the absolute moment the token
expires. That goes into the payload under the standard claim name `exp`. The
library serializes `exp` as a Unix timestamp (seconds since Jan 1 1970 UTC — the
universal machine representation of time), and on `decode` it compares that
against "now" and rejects the token if it has passed. `"sub"` (subject) is the
standard claim for *who the token is about*; we store the user id, stringified
because the JWT spec wants `sub` to be a string. `extra` lets the caller fold in
additional claims — the auth service passes `{"role": ...}` so authorization
checks later don't need a database hit.

**Why `jwt.decode` does verification, not just parsing.** It would be easy to
assume `decode` merely Base64-decodes the payload back into a dict. It does far
more: using the secret key and the declared algorithm, it **recomputes the
signature** over the header and payload and checks it byte-for-byte against the
signature in the token, *and* checks `exp`. Only if both pass does it return the
claims. Passing `algorithms=[...]` explicitly (rather than trusting the
algorithm named in the token's own header) closes a classic JWT vulnerability
where an attacker sets the header algorithm to `none` or swaps signing schemes to
bypass verification. Pinning the allowed algorithm server-side defeats that.

`raise ... from exc` preserves the original error as the "cause" — good practice
for debugging. When this `ValueError` is later printed or logged, Python shows
both it *and* the underlying `JWTError` it came from ("The above exception was the
direct cause of..."), so you don't lose the real reason the token was rejected.
The code deliberately catches the library's specific `JWTError` and re-raises a
generic `ValueError` so the rest of the app isn't coupled to the `python-jose`
library — a small example of not letting a third-party's exception types leak
throughout your codebase.

---

## 8. Backend, part 3: the database layer

`backend/app/db/`.

### 8.1 `db/base.py` — the declarative base + timestamp mixin

```python
class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

`Base` is the **declarative base class**. Every model inherits from it. Behind
the scenes, SQLAlchemy uses it to keep a registry of all tables (the
`Base.metadata`) — which is how migrations and `create_all()` know what tables
exist.

`TimestampMixin` is a **mixin** — a small class meant to be *mixed into* others
to add shared behavior, here two columns: `created_at` and `updated_at`. Any
model that inherits it automatically gets both.

- `server_default=func.now()` — the **database** fills in the current time on
  insert (not Python). More reliable across timezones and clients.
- `onupdate=func.now()` — `updated_at` refreshes automatically on every update.
- `DateTime(timezone=True)` — store timezone-aware timestamps (always use UTC in
  storage; convert to local time only for display).

This is **DRY** again: instead of copying these two columns into six models, you
write them once.

**Why a mixin instead of a base class or copy-paste?** You have three ways to
share those two columns: copy them into every model (violates DRY — change the
definition once and you must hunt down six copies), put them on the `Base` class
(forces *every* table to have them, even ones where timestamps make no sense), or
use a **mixin** that models opt into by inheriting. The mixin is the Goldilocks
choice: shared, defined once, but only applied where you write
`class Job(Base, TimestampMixin)`. Python supports a model inheriting from
*multiple* classes at once (**multiple inheritance**), which is what lets a model
pull in both `Base` (the ORM machinery) and `TimestampMixin` (the timestamp
columns) together.

**Why let the database set the time (`server_default`) instead of Python?** If
Python computed `datetime.now()` and sent it in the INSERT, then the timestamp
would reflect *the app server's* clock — and with several app servers, their
clocks may drift apart by seconds. Letting the database stamp the row with its own
`func.now()` means there is one authoritative clock for all writers, so ordering
by `created_at` is trustworthy. `func.now()` isn't a Python call; it's SQLAlchemy
emitting the SQL function `now()` into the statement for the database to execute.
`onupdate=func.now()` wires `updated_at` to be refreshed automatically on every
UPDATE, so you never forget to touch it by hand.

### 8.2 `db/session.py` — engine and sessions

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Three concepts:

- **Engine** — the object that manages the actual connection to PostgreSQL,
  including a **connection pool** (a set of reusable open connections, so you
  don't pay the cost of opening a new one per request). `pool_pre_ping=True`
  checks a connection is alive before using it (handles dropped connections
  gracefully).
- **Session** — your **unit of work** with the database. You add/modify objects
  through a session and then `commit()` to save them as one transaction (all or
  nothing). `SessionLocal` is a *factory* that produces new sessions.
- **`get_db`** — a **dependency**. FastAPI calls it for each request, hands the
  endpoint a fresh session via `yield`, and — crucially — the `finally: db.close()`
  runs *after the response is sent*, guaranteeing the connection always returns
  to the pool even if the endpoint raised an error. This `yield`-based pattern is
  a generator used as a context manager; it's the standard FastAPI way to manage
  per-request resources.

`expire_on_commit=False` is a quality-of-life setting: after `commit()`, you can
still read an object's attributes without SQLAlchemy issuing another query to
"refresh" them.

**Why connection pooling matters (the cost it hides).** Opening a brand-new
connection to PostgreSQL is surprisingly expensive: a TCP handshake (§3.1), then
authentication, then session setup — easily several milliseconds, which is an
eternity if you do it on every request. A **connection pool** keeps a handful of
connections permanently open and *lends* one out for the duration of a request,
then takes it back (not closing it) when done. So the handshake cost is paid once
at startup, not per request. `pool_pre_ping=True` adds a tiny "is this connection
still alive?" check before lending one out — important because a database restart
or an idle-timeout could have silently killed a pooled connection, and you'd
rather discover that with a cheap ping than with a failed query mid-request.

**What "unit of work" really means.** The `Session` implements a pattern called
*unit of work*: instead of writing to the database the instant you change
something, the session **tracks** all your additions, modifications, and
deletions in memory, and then flushes them all to the database together when you
`commit()`. This is what makes a request's database writes **atomic** (§3.3) —
they succeed or fail as one transaction. It also lets SQLAlchemy be smart about
ordering and batching the SQL. `autoflush=False` and `autocommit=False` mean the
session won't sneak writes out early or commit behind your back; *you* decide the
transaction boundary by calling `commit()` (or `rollback()`).

**Why `get_db` is a generator, and what `yield` does here.** A normal function
`return`s once and is done. A function with `yield` is a **generator**: it runs up
to the `yield`, *pauses* there handing the yielded value to the caller, and
resumes *after* the `yield` later. FastAPI exploits exactly this: it calls
`get_db`, receives the session at the `yield`, injects it into your endpoint, lets
the endpoint run, and — only after the response is built — resumes the generator,
which falls into the `finally` block and closes the session (returning the
connection to the pool). The `try/finally` guarantees that cleanup happens **even
if the endpoint raised an exception**. This "set up a resource, yield it, tear it
down afterward no matter what" shape is the standard way to manage per-request
resources, and it's why you never see a connection leak even when requests error
out.

> **Mental model:** one HTTP request = one session = one transaction (usually).
> The session is born when the request starts, does all its work inside one
> transaction, and is closed when the response is sent. Nothing leaks between
> requests because each gets its own fresh session.

---

## 9. Backend, part 4: the models (your tables)

`backend/app/models/`. Each file defines one or more ORM classes. These classes
are the **single source of truth** for your data shape on the database side.

Before the per-file detail, here is the whole data model at a glance — the six
tables and how they relate. If you can redraw this from memory, you understand the
domain:

```mermaid
erDiagram
    USERS ||--o{ JOBS : "triggers (SET NULL)"
    DEVICES ||--o{ JOBS : "is tested by"
    TEST_SUITES ||--o{ JOBS : "is run as"
    TEST_SUITES ||--o{ TEST_CASES : "contains (CASCADE)"
    JOBS ||--o{ TEST_RESULTS : "produces (CASCADE)"
    TEST_CASES ||--o{ TEST_RESULTS : "is recorded as (SET NULL)"

    USERS {
        int id PK
        string email UK
        string username UK
        string hashed_password
        enum role
    }
    DEVICES {
        int id PK
        string hostname
        string management_ip
        enum vendor
        enum device_type
        enum status
        string tags "comma-separated"
    }
    TEST_SUITES {
        int id PK
        string name
        string description
    }
    TEST_CASES {
        int id PK
        int test_suite_id FK
        string name
        int order_index
        bool enabled
    }
    JOBS {
        int id PK
        int device_id FK
        int test_suite_id FK
        int triggered_by_user_id FK "nullable"
        enum status
        datetime started_at
        datetime completed_at
    }
    TEST_RESULTS {
        int id PK
        int job_id FK
        int test_case_id FK "nullable"
        string test_case_name "denormalized"
        enum status
        json metadata_json
    }
```

Read the crow's-foot notation as "one-to-many": one `TEST_SUITE` contains many
`TEST_CASES`; one `JOB` produces many `TEST_RESULTS`; and so on. The labels in
parentheses are the **delete behavior** (§9) — `CASCADE` means children die with
the parent (cases without their suite are meaningless), while `SET NULL` keeps the
child but nulls the link (a job should outlive the user who triggered it, for
audit history). Notice `JOBS` is the hub that ties a device, a suite, and a user
together into "this run," and `TEST_RESULTS` is the leaf recording what actually
happened per check. Every relationship choice on this diagram is explained in the
subsections below.

A recurring pattern you'll see:

```python
class UserRole(str, enum.Enum):
    admin = "admin"
    engineer = "engineer"
    viewer = "viewer"
```

This is a **Python enum** that also subclasses `str`. An **enumeration** is a
fixed set of named choices. Using an enum (instead of free-form strings) means
the only legal roles are exactly these three — the type system and database both
enforce it. Subclassing `str` makes each member behave like its string value
(`UserRole.admin == "admin"`), which is handy for JSON.

**Why an enum instead of just strings?** Imagine roles were plain strings. Nothing
stops a typo like `"engneer"` from being saved, and nothing documents what the
legal values *are* — you'd have to grep the codebase and hope. An enum makes the
set of valid values **explicit and closed**: there is one authoritative list, your
editor autocompletes the members, a typo like `UserRole.engneer` is caught
immediately because that attribute doesn't exist, and (because this maps to a real
database `ENUM` type in Postgres) the *database itself* will reject any value
outside the set. This is the recurring theme of the whole codebase: **make illegal
states unrepresentable.** The more the type system and database forbid bad data,
the fewer runtime checks you have to write and the fewer bugs slip through.

**Why subclass `str`?** A bare `enum.Enum` member is its own opaque object;
serializing it to JSON or comparing it to a string would need extra conversion.
By declaring `class UserRole(str, enum.Enum)`, each member *is* a string as far as
the rest of Python is concerned, so `UserRole.admin == "admin"` is `True` and
turning it into JSON "just works." You get the safety of an enum and the
convenience of a string at once.

### 9.1 `models/user.py`

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.viewer, nullable=False)
```

Reading the syntax:

- `Mapped[int]` — a type hint telling SQLAlchemy (and you) this attribute is an
  `int`. The new SQLAlchemy 2.0 style.
- `mapped_column(...)` — the column definition.
- `primary_key=True` — this is the unique row id (auto-incrementing integer).
- `String(255)` — a `VARCHAR(255)` column (max 255 chars).
- `unique=True` — the database forbids duplicate emails/usernames.
- `index=True` — build an index for fast lookups (you log in by email, so it's
  searched constantly).
- `nullable=False` — the column is required (cannot be `NULL`).
- `default=UserRole.viewer` — new users are viewers unless told otherwise
  (**principle of least privilege**: default to the *least* powerful role).
- Notice there is **no** `password` column — only `hashed_password`. The design
  makes storing a plaintext password impossible.

**What "auto-incrementing primary key" really means.** When you mark `id` as
`primary_key=True` on an integer column, the database takes responsibility for
handing out a fresh, unique number every time you insert a row (1, then 2, then
3…). You never set it yourself; you insert a user with no `id` and read it back
afterward. Why integers and not, say, the email as the key? Because a primary key
should be **stable and meaningless** — an email can change, but a row's identity
should never change. A surrogate integer (or, in bigger systems, a random UUID)
gives every row a permanent handle that other tables can reference via foreign
keys without caring about the row's actual contents.

**Why `unique` and `index` together on `email`/`username`.** These two flags do
related but distinct jobs. `index=True` builds the sorted lookup structure (§3.3)
so "find the user with this email" is O(log n) instead of a full scan — important
because every single login does that lookup. `unique=True` additionally tells the
database to *reject* a second row with the same value, enforcing "no two accounts
share an email" at the lowest, most trustworthy level. (A unique constraint is
backed by an index anyway, so these reinforce each other.) Enforcing uniqueness in
the database — not just in Python — matters because two requests could try to
register the same email at the *exact* same moment; only the database, as the
single serialization point, can reliably block the duplicate.

**The `principle of least privilege`, stated fully.** Defaulting new users to
`viewer` (the weakest role) embodies a core security principle: give every actor
the *minimum* permissions they need, and grant more only deliberately. If you
defaulted to `admin`, a forgotten or mis-created account would be dangerous; by
defaulting to `viewer`, the worst case of "oops, I didn't set a role" is a
harmless read-only account.

### 9.2 `models/device.py`

Defines three enums — `Vendor` (cisco, juniper, aruba, …), `DeviceType` (switch,
router, firewall, …), `DeviceStatus` (active, inactive, maintenance, unknown) —
and the `Device` table with fields like `hostname`, `management_ip`, `vendor`,
`model`, `os_version`, `site`, `device_type`, `status`, `ssh_port` (default 22),
`snmp_port` (default 161), `snmp_community`, `tags`, `notes`.

Two design notes worth internalizing:

- `tags: Mapped[str | None] = mapped_column(String(512))  # comma-separated for simplicity`
  — a deliberate **simplification**. A "proper" design might use a separate
  `tags` table (many-to-many). Here they just store `"prod,hq"` as one string.
  The inline comment is honest about the tradeoff. Knowing *when* to simplify is
  a real engineering skill; for a portfolio app, a comma string is fine.
- `hostname` and `management_ip` are indexed because the device list supports
  searching by them.

**The tags simplification, examined honestly.** Storing tags as `"prod,hq"` in one
column is the kind of trade-off you should be able to defend *and* critique. The
upside: it's trivially simple — no extra table, no join, no extra queries, and for
a portfolio app nobody will ever have enough tags for it to matter. The downside,
and why a "real" system wouldn't do this: you can't efficiently ask "show me every
device tagged `prod`" because that requires a substring search (`LIKE '%prod%'`)
which can't use an index and which has false-positive hazards (a tag `production`
also matches `%prod%`). You also can't enforce a controlled vocabulary of tags, or
rename a tag everywhere at once. The "proper" design is a **many-to-many**
relationship: a `tags` table, a `devices` table, and a `device_tags` join table
with one row per (device, tag) pair — which makes "all devices with tag X" a fast,
indexed lookup. The lesson isn't "comma strings are bad"; it's that you choose the
simplest representation that meets the actual requirements, and you *know* what you
gave up so you can upgrade it when the requirements grow.

### 9.3 `models/test_suite.py` and `models/test_case.py` — relationships

A **test suite** has many **test cases**. This one-to-many link is modeled two
ways that must agree:

On the child (`TestCase`):
```python
test_suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
test_suite: Mapped["TestSuite"] = relationship("TestSuite", back_populates="test_cases")
```

On the parent (`TestSuite`):
```python
test_cases: Mapped[list["TestCase"]] = relationship(
    "TestCase", back_populates="test_suite",
    cascade="all, delete-orphan", order_by="TestCase.order_index",
)
```

Unpacking the important pieces:

- **`ForeignKey("test_suites.id")`** — the database-level link. Every test case
  *must* point to a real suite.
- **`ondelete="CASCADE"`** — if a suite is deleted, the database automatically
  deletes its test cases. No orphans.
- **`relationship(...)`** — the *ORM-level* convenience. Now in Python you can
  write `suite.test_cases` to get the list of cases, or `case.test_suite` to get
  the parent — no manual SQL joins. `back_populates` ties the two sides together
  so they stay consistent in memory.
- **`cascade="all, delete-orphan"`** — the ORM-side mirror of the cascade: remove
  a case from `suite.test_cases` and it gets deleted.
- **`order_by="TestCase.order_index"`** — cases always come back in their
  intended run order. Order matters: tests run sequentially by `order_index`.

**The two-level nature of a relationship (database vs. ORM).** There are really
*two* things being declared here and it's worth separating them. The
`ForeignKey(...)` is a **database** construct: a real constraint stored in
Postgres that says "the `test_suite_id` column must contain the id of a row that
actually exists in `test_suites`." It enforces **referential integrity** at the
lowest level — the database physically refuses to insert a case pointing at a
nonexistent suite, and refuses to delete a suite that still has cases unless you
tell it what to do with them. The `relationship(...)`, by contrast, is a
**Python/ORM** convenience that exists only in your application: it lets you write
`suite.test_cases` and get a Python list, or `case.test_suite` and get the parent
object, *without writing a single JOIN by hand*. The ORM notices you touched
`suite.test_cases` and silently runs the right `SELECT` for you. One is about data
integrity in storage; the other is about ergonomics in code. You need both, and
`back_populates` is just the string that tells SQLAlchemy these two
`relationship()` declarations are the two ends of *the same* link so it keeps them
in sync in memory.

**CASCADE explained twice, because it's declared twice.** Deletion behavior
appears in two places that must agree. `ondelete="CASCADE"` on the `ForeignKey` is
the *database's* rule: "if a suite row is deleted, automatically delete its case
rows too." `cascade="all, delete-orphan"` on the `relationship` is the *ORM's*
mirror of that, plus the "delete-orphan" part which means "if I remove a case from
`suite.test_cases` in Python, treat that case as deleted." Why bother stating it
in both places? Because the two layers act at different times — the ORM handles
objects you've loaded into a session, while the database handles raw SQL deletes
(and protects you even if someone deletes a suite through a tool that bypasses
your app). Keeping them consistent means there are never **orphan** rows (a case
whose suite no longer exists), which would be corrupt, meaningless data.

`TestType` enum lists the nine kinds of checks (ping_check, ssh_command,
snmp_check, vlan_check, interface_status, config_contains, config_not_contains,
mock_radius_check, log_scan). `Severity` ranks importance (info → critical). A
`TestCase` also has `command` (what to "run"), `expected_pattern` (a regex to
search for), `expected_value` (a literal to look for), `timeout_seconds`,
`order_index`, and `enabled`.

> **The `TYPE_CHECKING` trick:** Files use
> `if TYPE_CHECKING: from app.models.test_case import TestCase`. `TYPE_CHECKING`
> is `False` at runtime but `True` for type checkers. This lets the type hints
> reference each other (suite ↔ case) **without** creating a real **circular
> import** (file A imports B which imports A — a crash). The string form
> `"TestCase"` in annotations is a *forward reference* resolved lazily.

To unpack that last box: a **circular import** happens when module A needs module
B at import time and B needs A at import time — Python starts loading A, hits the
import of B, starts loading B, hits the import of A (which isn't finished yet),
and crashes. The `TestSuite` and `TestCase` files genuinely reference each other
(each relationship names the other class), so a naive pair of imports would
deadlock. The fix has two parts. First, `if TYPE_CHECKING:` is a special constant
that is `False` when the program actually runs (so the import simply doesn't
happen at runtime, breaking the cycle) but `True` when a type checker like mypy
analyzes the code (so it can still see the types). Second, writing the annotation
as the *string* `"TestSuite"` rather than the bare name `TestSuite` makes it a
**forward reference** — a promise "a class by this name will exist, resolve it
later" — so the line doesn't need the class to be imported yet. Together they let
two files depend on each other's types without a runtime import cycle.

### 9.4 `models/job.py`

```python
class JobStatus(str, enum.Enum):
    queued = "queued"; running = "running"; passed = "passed"
    failed = "failed"; partial = "partial"; canceled = "canceled"; error = "error"

class Job(Base, TimestampMixin):
    device_id, test_suite_id  # FKs (CASCADE) — what was run, against what
    triggered_by_user_id      # FK (SET NULL) — who ran it
    status                    # the JobStatus enum, indexed
    started_at, completed_at, duration_ms
    summary, error_message, logs   # human-readable text fields
    results = relationship("TestResult", back_populates="job", cascade="all, delete-orphan")
```

This is the central table. A **job** is "one run of one suite against one
device." Its `status` is a **state machine**: it starts `queued`, becomes
`running`, then ends in one of `passed`/`failed`/`partial`/`error`/`canceled`.
Tracking timestamps and `duration_ms` lets you report performance.

**What a "state machine" is, and why it's the right mental model.** A state
machine is a system that is always in exactly *one* of a fixed set of states, and
can only move between them along *allowed* transitions. Modeling the job's life
as a state machine isn't just vocabulary — it prevents nonsense. A job can go
`queued → running`, but it can never jump from `passed` back to `queued`, and you
can't cancel a job that already `error`ed. Writing the status as an enum with a
clear set of values makes those rules thinkable and checkable (you'll see
`cancel_job` in §11.4 explicitly refuse to cancel anything that isn't still
`queued` or `running`). Here is the legal flow:

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running
    queued --> canceled
    running --> passed
    running --> failed
    running --> partial
    running --> canceled
    running --> error
    passed --> [*]
    failed --> [*]
    partial --> [*]
    canceled --> [*]
    error --> [*]
```

The five terminal states carry distinct meaning: `passed` (every test passed),
`failed` (at least one failed), `partial` (a mix — some passed, some failed),
`error` (the run itself broke before producing clean results, e.g. an exception),
and `canceled` (a human stopped it). Distinguishing `failed` from `error` matters
operationally: a `failed` job did its job and found a real problem on the device;
an `error` job means *your system* malfunctioned and the result is untrustworthy.
The extra timestamps (`started_at`, `completed_at`) and `duration_ms` exist so the
dashboard and reports can answer "how long did this take?" and "how fresh is this
result?"

Notice the foreign keys use two different delete behaviors:

- `device_id` / `test_suite_id` → `ondelete="CASCADE"` (delete the device, its
  jobs go too).
- `triggered_by_user_id` → `ondelete="SET NULL"` (delete the user, but *keep*
  the job for history, just forget who triggered it). That field is also
  *nullable* (`int | None`). Choosing CASCADE vs SET NULL per relationship is a
  real modeling decision — you keep audit history even when users leave.

**Why the two choices are opposite on purpose.** Ask, for each link, "if the
thing I point at disappears, does *this* row still have meaning?" A job without a
device or suite is meaningless — it literally recorded "run *this* suite against
*that* device," and if either is gone the record is nonsense, so `CASCADE` (delete
the job too) is right. But a job without its *triggering user* still has plenty of
meaning — "the nightly compliance suite ran against core-sw-01 and 3 tests
failed" is valuable history regardless of whether the person who clicked Run still
works here. So `SET NULL` keeps the job and just blanks out the `who`. This is why
the column must be **nullable**: after the user is deleted, the value genuinely
becomes "unknown," and `NULL` is the database's representation of "no value /
unknown." Preserving records for audit and reporting even as related entities come
and go is a recurring need in real systems, and choosing your delete behavior
per-relationship is how you express it.

### 9.5 `models/test_result.py`

One row **per test case per job** — the granular outcome.

```python
class TestResultStatus(str, enum.Enum):
    passed = "passed"; failed = "failed"; skipped = "skipped"; error = "error"

class TestResult(Base, TimestampMixin):
    job_id            # FK (CASCADE), indexed
    test_case_id      # FK (SET NULL) — keep result even if the case is later deleted
    test_case_name    # snapshot of the name at run time
    status
    actual_output, expected_output, error_message
    started_at, completed_at, duration_ms
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
```

Two subtle, *important* design choices:

1. **`test_case_name` is duplicated here** even though there's a `test_case_id`
   link. Why store the name again? Because a test case might be **renamed or
   deleted** later, but a historical result should still show what it *was* when
   it ran. This is **denormalization for historical accuracy** — a deliberate,
   common pattern in audit/reporting data.
2. **`metadata_json` uses a `JSON` column.** Sometimes you want to attach
   flexible, structured extra data (here: `{"severity": ..., "test_type": ...}`)
   without adding a dedicated column for each. A JSON column is the escape hatch.
   Use it sparingly — columns are better when you'll query/filter on the value.

(`metadata_json` is named that, not `metadata`, because `metadata` is a reserved
attribute name on SQLAlchemy's `Base`.)

**Denormalization, and why it's not "breaking the rules."** Section 3.3 said
normalization means each fact lives in exactly one place — so storing
`test_case_name` here, when the name *also* lives on the `test_cases` row, looks
like a violation. It is, and it's deliberate. The normalized approach would join
`test_results` to `test_cases` to fetch the current name. But test results are
**historical records** — they describe what happened at a moment in the past. If
someone later renames the test case from "Ping check" to "ICMP reachability," or
deletes it entirely, a normalized join would make your old reports suddenly say
something different (or blank) than they did when the test actually ran. By
*snapshotting* the name onto the result row at run time, the historical record
stays frozen and truthful forever. This is the same reason your bank statement
shows the price you paid at the time, not today's price. The rule of thumb:
normalize **operational** data that should always reflect the current truth;
denormalize (snapshot) **historical/audit** data that should reflect the truth at
the time of the event. That's also why `test_case_id` is `SET NULL` rather than
`CASCADE` here — deleting a test case must not erase the history of every result
it ever produced.

**When a JSON column is the right escape hatch (and when it isn't).** A relational
database wants you to define a column per field, which is great when you know the
fields and want to filter/sort on them. But sometimes you have a small bag of
*incidental* extra data that varies and that you'll only ever read back wholesale,
never query by — here, `{"severity": ..., "test_type": ...}` attached to a result
for display. Making a dedicated column for each such field would clutter the table
and require a migration every time the bag changes. A `JSON` column lets you stash
arbitrary structured data in one field. The trade-off is exactly the thing you
give up: the database can't efficiently index or filter *inside* JSON (in standard
SQL), so if you ever need `WHERE severity = 'critical'` a lot, that data belongs in
a real column. The skill is knowing the boundary: structured-but-incidental →
JSON; structured-and-queryable → column.

---

## 10. Backend, part 5: the schemas (Pydantic)

`backend/app/schemas/`. **This is one of the most important concepts to grasp,
because beginners constantly confuse models and schemas.**

- **Models** (`app/models`) = the **database** shape (SQLAlchemy).
- **Schemas** (`app/schemas`) = the **API/JSON** shape (Pydantic).

They are *separate on purpose*. The data you store is not always the data you
send over the wire. The clearest example: a `User` model has
`hashed_password`, but the `UserOut` schema does **not** — you must never leak
password hashes in an API response. Schemas are your **contract with the
outside world**; models are your internal storage. Keeping them separate means
you can change one without accidentally exposing the other.

**Why not just return the database objects directly?** It's tempting — the `User`
model already has all the fields, why define a second `UserOut` class that
repeats most of them? Three reasons make the separation worth the duplication.
**Security:** if the API serialized models directly, adding a sensitive column to
a model (a password hash, an internal flag, an API key) would *instantly* leak it
to every client, silently. With an explicit `UserOut`, a field is exposed only if
you deliberately list it — safe by default. **Stability:** your database schema and
your public API are different things that change for different reasons. You might
split a column, rename an internal field, or add a cache table without wanting to
break every frontend and external consumer. The schema layer is a deliberate
*buffer* between "how we store" and "how we present," so internal refactors don't
ripple outward. **Shape:** the wire format often differs from storage — you may
want to flatten a relationship, compute a derived field, or omit nulls. Schemas
give you a place to express that. This separation is sometimes called the
Data Transfer Object (DTO) pattern: the objects that cross your API boundary are
their own type, distinct from your persistence objects.

### 10.1 The Create / Update / Out pattern

Look at `schemas/device.py`:

```python
class DeviceBase(BaseModel):       # shared fields
    hostname: str = Field(min_length=1, max_length=255)
    management_ip: str = Field(min_length=1, max_length=64)
    vendor: Vendor
    ...

class DeviceCreate(DeviceBase):    # what the client sends to CREATE
    pass

class DeviceUpdate(BaseModel):     # what the client sends to UPDATE — all optional
    hostname: str | None = None
    ...

class DeviceOut(DeviceBase):       # what the server sends BACK
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
```

Why three (or four) variants of nearly the same thing?

- **Create** — the fields a client supplies to make a new device. No `id` (the
  DB assigns it), no timestamps.
- **Update** — for a `PATCH`, *every* field is `Optional`/`None` by default, so
  the client can send *only the fields they want to change*. This is the essence
  of PATCH (partial update).
- **Out** — what you return. It *adds* server-generated fields (`id`,
  `created_at`, `updated_at`).
- **Base** — shared fields, inherited to avoid repetition.

**Validation for free:** `Field(min_length=1, max_length=255)` means FastAPI
rejects an empty or oversized hostname with a clear `422` error *before your
code even runs*. `vendor: Vendor` means only the allowed enum values are
accepted. You declare the rules once; Pydantic enforces them.

**How validation actually happens, step by step.** When a request arrives at a
route whose signature says `device: DeviceCreate`, FastAPI does not hand your
function the raw JSON. It first reads the request body, parses the JSON text into
a Python dict, and then calls `DeviceCreate(**data)` — which triggers Pydantic's
validation engine. Pydantic walks every field in the model: it checks the value is
present (unless it has a default), checks the type (coercing where sensible — the
string `"22"` becomes the int `22` for an `int` field, but the string `"banana"`
does not), and checks every `Field` constraint (`min_length`, `max_length`, `ge`,
`le`, regex patterns). For `vendor: Vendor` it confirms the string is one of the
enum's allowed members. If *anything* fails, Pydantic raises a
`ValidationError` that FastAPI catches and turns into a `422 Unprocessable
Entity` response containing a precise, machine-readable list of *which* fields
failed and *why* — for example `{"loc": ["body", "hostname"], "msg": "String
should have at least 1 character"}`. The crucial payoff: **by the time your route
body executes, the `device` object is guaranteed valid.** You never write
`if not hostname: ...` defensive checks inside your handler, because invalid
requests never reach it. Validation is pushed to the boundary, and everything
inside the boundary gets to trust its inputs.

**Why `DeviceUpdate` makes every field optional — and the subtlety of "optional
vs. absent."** A `PATCH` is a *partial* update: the client sends only the fields
they want to change. So `DeviceUpdate` declares each field as `... | None = None`,
meaning "if you don't send it, it defaults to `None`." But this creates a famous
ambiguity: when the service sees `status=None`, does that mean "the client didn't
mention status" or "the client explicitly wants to set status to null"? Pydantic
solves this with `model_dump(exclude_unset=True)`, which returns a dict containing
*only the fields the client actually sent* — fields left out are omitted entirely,
not included as `None`. The update service then loops over just those keys and
assigns them onto the ORM object, so untouched columns keep their existing values.
This is the difference between "set status to null" (send `{"status": null}`, which
*is* in the dump) and "leave status alone" (omit it, which is *not* in the dump).
Understanding this distinction is what separates a correct PATCH from one that
accidentally wipes fields the user never touched.

**`model_config = ConfigDict(from_attributes=True)`** is the magic that lets you
do `DeviceOut.model_validate(device_orm_object)`. Normally Pydantic reads from a
dict (it looks up `data["hostname"]`); `from_attributes=True` lets it read
straight from an object's *attributes* (it looks up `obj.hostname`). That matters
because a SQLAlchemy `Device` is an object, not a dict — its data lives in
attributes. So a route loads a `Device` from the database and then calls
`DeviceOut.model_validate(device)`: Pydantic reads each `DeviceOut` field off the
ORM object's attributes, re-validates them, and produces a clean schema instance
that FastAPI serializes to JSON. The re-validation is not wasted work — it's also
what *strips* any field not declared on `DeviceOut`. The `Device` model has a
`notes` column and internal bookkeeping; if `DeviceOut` doesn't list a field, it
simply never appears in the output. That is the security guarantee from §10
made concrete: the response contains exactly the fields you declared, no more.

### 10.2 Other schema files

- `schemas/common.py` — defines a **generic** `Page[T]`:
  ```python
  class Page(BaseModel, Generic[T]):
      items: List[T]; total: int; limit: int; offset: int
  ```
  A **generic** is a reusable shape parameterized by a type. `Page[DeviceOut]`
  and `Page[JobOut]` reuse the same pagination envelope. Every list endpoint
  returns this `{items, total, limit, offset}` structure — a *consistent*
  pagination contract (more in §13).

  **What a generic buys you, and why not just write it out each time.** Without
  generics you would need a separate `DevicePage`, `JobPage`, `UserPage`, and so
  on — each an identical copy of `{items, total, limit, offset}` differing only in
  the type of `items`. That is duplication that drifts: someone adds a `has_more`
  field to `DevicePage` and forgets the others, and now your pagination contract
  is inconsistent across endpoints. `Generic[T]` lets you write the envelope
  *once* and stamp out typed versions on demand: `Page[DeviceOut]` is "a page
  whose `items` is a `list[DeviceOut]`," `Page[JobOut]` is the same shape with
  `list[JobOut]`. The `T` is a **type variable** — a placeholder filled in at the
  point of use. The benefit is not just less typing; it's that your editor and
  type checker *know* `page.items[0]` is a `DeviceOut` and will autocomplete its
  fields and catch mistakes, while still guaranteeing every list endpoint speaks
  the same pagination language. One definition, many concrete types, full type
  safety — that is the whole point of generics.
- `schemas/user.py` — `UserCreate` (requires a `password`, min length 6),
  `UserOut` (no password), `UserBase`.
- `schemas/auth.py` — `LoginRequest` (email + password) and `TokenResponse`
  (`access_token`, `token_type="bearer"`, and the `user`). Note `email:
  EmailStr` — Pydantic validates it's a real email format. `EmailStr` is a
  purpose-built type that runs the value through an email-syntax validator, so a
  request with `"not-an-email"` is rejected at the boundary with a `422` before
  any of your code runs. It is a small but representative example of the Pydantic
  philosophy: encode the rule in the *type* and let the framework enforce it,
  rather than scattering `if "@" in email` checks through your handlers.
- `schemas/test_suite.py` — `TestCase*` and `TestSuite*` schemas. `TestSuiteOut`
  *nests* a `list[TestCaseOut]`, so fetching a suite returns its cases inline.
  `TestSuiteCreate` lets you create a suite *and* its initial cases in one call.

  **Nested schemas and how they serialize.** When `TestSuiteOut` declares
  `cases: list[TestCaseOut]`, Pydantic understands the nesting recursively: to
  serialize a suite it serializes each case with `TestCaseOut`'s rules, producing
  a single JSON document like `{"id": 1, "name": "...", "cases": [{...}, {...}]}`.
  This is why the API can return a suite *and* its ordered cases in one response
  with one round trip, instead of forcing the client to fetch the suite and then
  make a second request for its cases. The same `from_attributes=True` mechanism
  applies at every level, so `TestSuiteOut.model_validate(suite_orm)` reads
  `suite.cases` (the ORM relationship from §9.3), and for each `TestCase` object
  reads *its* attributes through `TestCaseOut`. Models map to schemas all the way
  down the tree.
- `schemas/job.py` — `JobCreate` (just `device_id` + `test_suite_id`) and
  `JobOut` (the full job state).
- `schemas/test_result.py` — `TestResultOut`.
- `schemas/dashboard.py` — `DashboardSummary` (the metrics bundle).

> **Decision to remember:** Separate your storage model from your API model.
> Use Create/Update/Out variants. Let Pydantic validate at the boundary so the
> rest of your code can trust its inputs.

---

## 11. Backend, part 6: the services (business logic)

`backend/app/services/`. A **service** is a plain module of functions that
contain the actual *logic* — "what should happen" — independent of HTTP. Routes
call services; services use models. This keeps routes thin and makes logic
reusable (e.g., the worker and a route can both call the same service).

### 11.1 `services/auth_service.py`

```python
def register_user(db, email, username, password, role=UserRole.viewer) -> User:
    existing = db.execute(select(User).where((User.email == email) | (User.username == username))).scalar_one_or_none()
    if existing:
        raise ConflictError("User with this email or username already exists")
    user = User(email=email, username=username, hashed_password=hash_password(password), role=role)
    db.add(user); db.commit(); db.refresh(user)
    return user

def authenticate(db, email, password) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    return user

def issue_token(user) -> str:
    return create_access_token(user.id, extra={"role": user.role.value})
```

Lessons here:

- **Registration** checks for an existing email *or* username first and raises
  `ConflictError` (→ HTTP 409) rather than letting the database throw a raw
  uniqueness error. Friendlier and intentional.
- The password is **hashed** before storing (`hash_password`). The raw password
  never touches the database.
- **Login** says "Invalid email or password" for *both* "no such user" and
  "wrong password." This is **intentional security**: revealing *which* one was
  wrong would let an attacker discover which emails are registered (user
  enumeration).
- `issue_token` bakes the user's `role` into the JWT, so later requests know the
  role without a DB lookup.
- The `db.add → db.commit → db.refresh` trio: stage the new row, save the
  transaction, then reload it so Python sees DB-generated fields (`id`,
  timestamps).
- `select(...).scalar_one_or_none()` is SQLAlchemy 2.0 query style: build a
  `SELECT`, execute it, and get a single object or `None`.

**The `add` / `commit` / `refresh` trio, slowed down.** These three calls map to
three distinct phases of saving a row, and knowing what each does prevents a lot
of confusion. `db.add(user)` does *not* talk to the database — it merely registers
the new object with the session's unit-of-work (§8.2) as "pending," something to
be inserted when the session next flushes. `db.commit()` is the moment of truth:
it flushes all pending changes as SQL `INSERT`/`UPDATE`/`DELETE` statements and
then commits the surrounding transaction, making the changes permanent and
visible to other connections. After a commit, SQLAlchemy *expires* the object's
attributes — it considers them potentially stale, because the database may have
filled in defaults (the auto-increment `id`, the `server_default` timestamps from
§8.1) that Python hasn't seen. `db.refresh(user)` issues a fresh `SELECT` to
re-load those server-generated values back into the Python object, so the `User`
you return actually has its real `id` and `created_at`. Skip the refresh and
`user.id` might be `None` or trigger a surprise query the moment you touch it.

**Why "Invalid email or password" is the same message for both failures.** This
looks like laziness but it's a deliberate defense against **user enumeration**. If
login said "no account with that email" for unknown addresses but "wrong password"
for known ones, an attacker could probe your login endpoint with a list of emails
and learn *which ones are registered* — a valuable target list for phishing or
credential-stuffing. By returning an identical `UnauthorizedError` whether the
email is unknown *or* the password is wrong, the endpoint leaks nothing about who
has an account. (A truly hardened login would also run the bcrypt verification
even when the user doesn't exist, so the *response time* is the same in both
cases — otherwise a fast "no such user" reply versus a slow "compare the hash"
reply becomes a timing side channel. This app keeps it simple, but knowing the
full threat model is the kind of thing that distinguishes a thoughtful answer in
an interview.)

**`scalar_one_or_none` and the SQLAlchemy 2.0 query vocabulary.** The chain
`db.execute(select(User).where(...)).scalar_one_or_none()` reads like a sentence
once you know the verbs. `select(User)` builds a query object (it runs nothing
yet). `.where(...)` narrows it. `db.execute(...)` actually sends the SQL and
returns a `Result` — a cursor-like object over rows, where each row is a tuple.
Because you selected whole `User` objects, each row is a one-element tuple
`(user,)`. `.scalars()` unwraps that first element so you get `User` objects
directly instead of tuples, and the `_one_or_none` suffix asserts the cardinality:
return exactly one object, or `None` if there were zero rows, and raise if there
were *more* than one (which would signal a bug, since email is unique). The
sibling methods round out the vocabulary: `.scalars().all()` for a list,
`.scalar_one()` when exactly one row must exist. This explicit style replaced the
older `db.query(User).filter(...).first()` API and is what you'll see throughout
this codebase.

### 11.2 `services/device_service.py` — CRUD + listing

**CRUD** = Create, Read, Update, Delete — the four basic operations on a
resource. This file is the canonical example:

```python
def list_devices(db, *, limit=20, offset=0, search=None, status=None):
    stmt = select(Device)
    count_stmt = select(func.count(Device.id))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Device.hostname.ilike(like), Device.management_ip.ilike(like)))
        count_stmt = count_stmt.where(or_(...))
    if status:
        stmt = stmt.where(Device.status == status); count_stmt = count_stmt.where(...)
    stmt = stmt.order_by(Device.id.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    total = db.execute(count_stmt).scalar_one()
    return items, total
```

The standout concept is **pagination**. You almost never want to return *all*
rows — there could be thousands. Instead:

- `limit` = how many rows to return (page size).
- `offset` = how many to skip (which page). Page 3 with size 20 → `offset=40`.
- You run **two** queries: one for the *page* of items, one for the *total
  count* (so the UI can show "showing 1–20 of 137"). Both apply the same
  filters.
- `ilike` = case-**i**nsensitive `LIKE`. `%search%` matches the term anywhere in
  the string. `or_(...)` lets the search match hostname *or* IP.
- `order_by(Device.id.desc())` — newest first (stable, predictable ordering;
  pagination without ordering is meaningless).

**Pagination, the math and the SQL.** `limit` and `offset` translate directly to
the SQL clauses `LIMIT 20 OFFSET 40`, which the database reads as "skip the first
40 matching rows, then return the next 20." The page-number arithmetic is
`offset = (page - 1) * page_size`: page 1 → offset 0, page 2 → offset 20, page 3 →
offset 40, and so on. The reason you must `ORDER BY` *before* you `LIMIT/OFFSET`
is subtle but important: a relational table has **no inherent row order**, so
without an explicit sort the database is free to return rows in any order it
likes — and that order can *change* between two requests, causing rows to be
skipped or shown twice as the user pages. Ordering by a stable, unique column
(`id desc`) pins the sequence so page 2 always continues exactly where page 1 left
off. One honest caveat worth knowing for interviews: `OFFSET` pagination gets
*slower* as the offset grows, because the database still has to walk and discard
all the skipped rows — `OFFSET 1000000` means counting past a million rows every
time. For huge datasets you'd switch to **keyset** ("cursor") pagination
(`WHERE id < :last_seen_id LIMIT 20`), which jumps straight to the right spot via
the index. For this app's scale, offset pagination is the right, simple choice.

**Why two queries instead of one.** Notice the function runs `stmt` (the page of
rows) *and* `count_stmt` (the total). They are genuinely different questions:
"give me 20 device objects" versus "how many devices match these filters in
total." You can't get the total from the page — the page is capped at 20 by
design. The total is what powers the UI's "showing 1–20 of 137" and lets the
frontend compute how many pages exist. Both queries apply the *same* `where`
filters so the count matches what's actually being paged; forgetting to filter
the count query the same way is a classic bug that makes the page numbers lie.

The rest is textbook:

```python
def get_device(db, device_id):
    device = db.get(Device, device_id)
    if not device: raise NotFoundError("Device not found")
    return device

def create_device(db, payload: DeviceCreate):
    device = Device(**payload.model_dump()); db.add(device); db.commit(); db.refresh(device); return device

def update_device(db, device_id, payload: DeviceUpdate):
    device = get_device(db, device_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(device, k, v)
    db.commit(); db.refresh(device); return device

def delete_device(db, device_id):
    device = get_device(db, device_id); db.delete(device); db.commit()
```

- `payload.model_dump()` turns the Pydantic schema into a dict; `Device(**dict)`
  spreads it into the model constructor.
- **`exclude_unset=True`** in update is the key to PATCH: it returns *only the
  fields the client actually sent*, so you only overwrite those. Fields left out
  keep their old values. Then `setattr` applies each change.
- `get_device` is reused by update/delete so the "does it exist?" 404 logic
  lives in exactly one place.

### 11.3 `services/test_suite_service.py`

Same CRUD shape, with two extra ideas:

```python
stmt = select(TestSuite).options(selectinload(TestSuite.test_cases))
```

`selectinload` is **eager loading** to avoid the **N+1 query problem**. If you
fetch 20 suites and then access `.test_cases` on each, a naive ORM would run 1
query for the suites + 20 more for the cases = 21 queries (N+1).
`selectinload` instead fetches all the related cases in *one* additional query.
Recognizing and preventing N+1 is a classic backend performance skill.

**The N+1 problem, traced out.** Picture the naive version with no eager loading.
You run `SELECT * FROM test_suites LIMIT 20` (that's the "1"). Then your code does
`for suite in suites: print(suite.test_cases)`. The ORM has *not* loaded the cases
yet, so the first time you touch `suite.test_cases` it lazily fires
`SELECT * FROM test_cases WHERE test_suite_id = 1`, then `... = 2`, then `... = 3`
— one query per suite, 20 in all (that's the "N"). Total: 21 queries, most of them
tiny round trips to the database, each paying network and parsing overhead. At
20 suites it's slow; at 1000 it's a disaster. `selectinload(TestSuite.test_cases)`
fixes this by being eager: right after loading the 20 suites it collects their ids
and runs *one* batched query, `SELECT * FROM test_cases WHERE test_suite_id IN
(1, 2, ..., 20)`, then distributes the cases to the right suite objects in memory.
Two queries total, regardless of how many suites. The lesson is that ORMs make it
*dangerously* easy to write code that looks like a simple attribute access but
secretly issues a query — so you learn to spot loops over relationships and reach
for eager loading.

```python
def create_suite(db, payload, user_id):
    data = payload.model_dump(); cases = data.pop("test_cases", [])
    suite = TestSuite(**data, created_by_user_id=user_id)
    db.add(suite); db.flush()                 # flush assigns suite.id without committing
    for idx, case in enumerate(cases):
        case.setdefault("order_index", idx)
        db.add(TestCase(test_suite_id=suite.id, **case))
    db.commit(); db.refresh(suite)
    return get_suite(db, suite.id)
```

`db.flush()` sends the INSERT to the DB so `suite.id` becomes available, but
*doesn't* commit — so if adding the cases fails, the whole thing rolls back as
one transaction (**atomicity**). The suite and all its cases are created
together or not at all.

**Flush versus commit, and why the order matters here.** The puzzle this code
solves: each `TestCase` needs a `test_suite_id`, but the suite's `id` is assigned
by the database, not by Python — so you can't set it until the suite row exists.
`db.flush()` resolves the deadlock. Flush pushes the pending `INSERT` for the
suite down to the database *within the current transaction*, which causes the
database to assign the auto-increment `id` and SQLAlchemy to populate `suite.id`
— but it does **not** commit, so nothing is permanent yet and the transaction is
still open. Now you can loop and insert the cases using that real `suite.id`.
Finally `db.commit()` makes the suite *and* all its cases permanent in a single
atomic transaction. Atomicity is the payoff: if inserting case #3 violates a
constraint and throws, the commit never happens, the transaction rolls back, and
the suite row you flushed earlier vanishes too — you never end up with a half-built
suite that has some cases but not others. It's all-or-nothing, which is exactly
what you want when creating a parent and its children together.

### 11.4 `services/job_service.py`

```python
def create_job(db, *, device_id, test_suite_id, user_id):
    if not db.get(Device, device_id): raise NotFoundError("Device not found")
    if not db.get(TestSuite, test_suite_id): raise NotFoundError("Test suite not found")
    job = Job(device_id=device_id, test_suite_id=test_suite_id, triggered_by_user_id=user_id, status=JobStatus.queued)
    db.add(job); db.commit(); db.refresh(job); return job
```

Note: `create_job` **validates** that the device and suite exist *before*
creating the job, and it sets `status=queued`. It does **not** run anything — it
just records intent. Enqueuing happens in the route. This separation is what
makes the system asynchronous.

**"Records intent" is the whole asynchronous idea in three words.** A synchronous
design would have `create_job` actually SSH into the device, run all the tests,
wait however many seconds or minutes that takes, and only then return a response.
That would make the HTTP request hang for the entire duration of the test run —
terrible for the user (a spinning browser) and fragile (any network hiccup kills
the whole thing). Instead, `create_job` does the fast part synchronously — write
a single `Job` row with `status=queued` — and returns immediately. The slow part
(the actual testing) is handed to a background worker later (§15). The `queued`
status is a *promise*: "this work has been accepted and will be done." The user
gets an instant response with a job id they can poll. This split between
"recording that work should happen" and "doing the work" is the beating heart of
every asynchronous, queue-backed system, and validating the device/suite up front
means you reject bad requests *before* making that promise rather than discovering
the device doesn't exist halfway through a background run.

```python
def cancel_job(db, job_id):
    job = get_job(db, job_id)
    if job.status in (JobStatus.queued, JobStatus.running):
        job.status = JobStatus.canceled; db.commit(); db.refresh(job)
    return job
```

Cancel only acts if the job is still `queued`/`running` — you can't cancel one
that already finished. `get_results` fetches all `TestResult` rows for a job,
ordered.

**The state guard, and why cancel is idempotent.** The `if job.status in
(queued, running)` check is a **state-machine guard** (recall the `JobStatus`
diagram from §9.4): canceling only makes sense from a non-terminal state. If the
job already `passed`, `failed`, or was previously `canceled`, the function quietly
does nothing and returns the job as-is. That "quietly does nothing" is deliberate
and valuable — it makes cancel **idempotent**: calling it once or five times on an
already-finished job produces the same result and never throws or corrupts state.
Idempotency matters because the real world retries — a user double-clicks the
cancel button, the frontend resends after a flaky connection — and an operation
that's safe to repeat is far more robust than one that errors or double-applies on
the second call. Guarding the transition also protects the invariant that you
can't drag a job *out* of a terminal state, which would be meaningless (you can't
un-finish a test run that already wrote its results).

### 11.5 `services/dashboard_service.py`

Computes the summary with **aggregate queries** — SQL that returns computed
numbers rather than rows:

```python
device_count = db.execute(select(func.count(Device.id))).scalar_one()
active_device_count = db.execute(select(func.count(Device.id)).where(Device.status == DeviceStatus.active)).scalar_one()
since = datetime.now(timezone.utc) - timedelta(hours=24)
jobs_last_24h = db.execute(select(func.count(Job.id)).where(Job.created_at >= since)).scalar_one()
completed = ... # jobs that ended in passed/failed/partial
passed = ...    # jobs that ended passed
pass_rate = (passed / completed) if completed else 0.0
recent = db.execute(select(Job).order_by(Job.created_at.desc()).limit(10)).scalars().all()
```

`func.count(...)` runs `COUNT(*)` in the database — *far* cheaper than loading
all rows into Python and counting. The `if completed else 0.0` guards against
**division by zero** when there are no completed jobs yet (a real edge case at
boundaries — exactly the kind of thing to validate). The result is returned as a
plain dict that the route wraps in the `DashboardSummary` schema.

**Push computation to the database.** The instinct of a beginner is to write
`len(db.execute(select(Device)).scalars().all())` — load every device into Python
and count the list. For a handful of rows it works; for a million it transfers a
million rows over the network and builds a million Python objects just to throw
them away after counting. `select(func.count(Device.id))` instead asks the
database to do the counting and return a *single integer*. Databases are
specialized, highly optimized engines for exactly this kind of set operation — let
them do the work where the data already lives, and move only the answer across the
wire. The same principle drives the filtered counts (`WHERE status = 'active'`)
and the time-window count (`WHERE created_at >= since`): each is one cheap
aggregate query rather than a bulk download plus Python-side filtering. As a
system grows, "where does the computation happen" becomes one of the most
important performance questions you can ask, and the answer is usually "as close
to the data as possible."

**The division-by-zero guard is a boundary check, not paranoia.** `pass_rate =
(passed / completed) if completed else 0.0` exists because the very first time the
app runs — a fresh database with zero completed jobs — `completed` is `0`, and
`passed / 0` would crash the entire dashboard with a `ZeroDivisionError`. Empty
is a *real, common* state (every system starts empty), not a hypothetical, so
handling it is correctness, not over-engineering. This is the kind of edge case
that lives at boundaries: zero items, the first request, an empty list. Defining
the pass rate as `0.0` when nothing has completed is a reasonable, explicit
choice; the alternative (returning `null` and handling it in the UI) would also be
valid, but the point is that you *decided* what empty means instead of letting the
program crash.

### 11.6 `services/report_service.py`

Builds a downloadable report. `build_report` gathers the job, its results, the
device, suite, and triggering user, counts pass/fail/error, and returns one big
dict. `report_to_csv` uses Python's built-in `csv` module writing into an
in-memory `io.StringIO` buffer to produce CSV text. Two output formats from one
data source — JSON for machines, CSV for spreadsheets.

**Why `io.StringIO` instead of writing a file.** The `csv` module's writer wants
something it can call `.write()` on — normally an open file on disk. But the
report isn't meant to live on the server's disk; it's meant to be streamed back
in the HTTP response and saved on the *user's* machine. `io.StringIO` is an
in-memory object that *behaves exactly like an open text file* — same `.write()`
interface — but accumulates everything in a string in RAM. You hand it to
`csv.writer`, write your header and rows, then call `.getvalue()` to pull out the
finished CSV as a plain string and put it in the response body. No temp files, no
cleanup, no disk permissions to worry about, no two requests clobbering each
other's file. This "file-like object in memory" pattern shows up constantly in
Python whenever a library wants a file but you'd rather keep the data in memory.

**One data source, two serializations.** Notice the separation: `build_report`
produces a neutral Python dict — the *content* of the report — and then
`report_to_csv` (and the JSON path) are pure *formatters* that turn that one dict
into a specific wire format. This is the same separation-of-concerns idea as the
model/schema split: gather the data once, then present it however the consumer
needs. A data scientist opening the file in Excel wants CSV; a script
programmatically ingesting results wants JSON. Because the content and the format
are decoupled, adding a third format (say, PDF) later means writing one new
formatter, not re-querying and re-assembling all the data.

> **The big service-layer lesson:** routes should be thin; put logic in services
> so it's testable and reusable, and so the same operation behaves identically
> no matter who calls it.

---

## 12. Backend, part 7: dependencies & auth wiring

`backend/app/api/deps.py`. This file is where **authentication and
authorization** plug into every endpoint, using FastAPI's **dependency
injection** (DI).

**Dependency injection** sounds fancy but means: instead of an endpoint
*creating* the things it needs (a DB session, the current user), it *declares*
them as parameters, and the framework *supplies* them. `db: Session =
Depends(get_db)` says "FastAPI, please run `get_db` and hand me the result."
This makes endpoints declarative and trivially testable (you can swap in fakes).

**Why injection beats just calling the function.** You might ask: why not have the
endpoint write `db = get_db()` in its first line instead of this `Depends`
ceremony? Two reasons. First, **lifecycle management** — `get_db` is a generator
that must be *cleaned up* (its `finally: db.close()` from §8.2) after the response
is sent. FastAPI understands the generator protocol: it runs `get_db` up to the
`yield`, injects the session, lets your endpoint run, and then — *after* the
response is built — resumes the generator to run the cleanup. If you called
`get_db()` by hand you'd have to remember to close it in every endpoint, and
you'd leak connections the moment you forgot. Second, **testability and
substitution** — because the dependency is declared, not hardcoded, a test can say
`app.dependency_overrides[get_db] = lambda: fake_session` and *every* endpoint
suddenly uses the fake, with zero changes to endpoint code. That single seam is
what makes the whole test suite (§19) possible. Injection turns "things my code
needs" into a list of declared requirements the framework fulfills, which is
cleaner, safer, and far more testable than reaching out and grabbing them.

**Dependencies that depend on dependencies — the chain.** Look closely:
`get_current_user` is itself declared with `Depends(oauth2_scheme)` and
`Depends(get_db)`. So when an endpoint declares `user: User =
Depends(get_current_user)`, FastAPI builds a small dependency *graph*: to give you
the user it first needs the token (from `oauth2_scheme`, which reads the header)
and a session (from `get_db`), so it resolves *those* first, then calls
`get_current_user` with them, then hands the resulting `User` to your endpoint.
Dependencies composing out of smaller dependencies is what lets you build rich,
reusable building blocks: `get_current_user` is written once and reused by dozens
of endpoints, and the role-checkers below build on top of *it* in turn. The
framework resolves the whole tree for every request and caches each dependency's
result within a single request (so `get_db` runs once even if three dependencies
ask for it).

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user
```

- `OAuth2PasswordBearer` knows how to pull the token out of the
  `Authorization: Bearer <token>` header.
- `get_current_user` is itself a dependency that *depends on* the token and a DB
  session — dependencies can chain. It decodes the JWT, extracts the user id,
  loads the user, and returns it. Any endpoint that wants "the logged-in user"
  just adds `user: User = Depends(get_current_user)`. If the token is missing or
  bad, it raises `401` and the endpoint never runs.

**What `OAuth2PasswordBearer` actually does — and what it doesn't.** Despite the
name, this class is not implementing the full OAuth2 protocol; it's a small
helper that does two things. At request time it knows the convention for where a
bearer token lives — the `Authorization: Bearer <token>` HTTP header — and extracts
the `<token>` string for you (returning `None` here because `auto_error=False`
lets `get_current_user` craft its own 401 instead of the default). At
documentation time it tells FastAPI's `/docs` page that these endpoints take a
bearer token, which is what makes the "Authorize" button appear in the interactive
docs. The `tokenUrl="/api/auth/login"` argument is purely informational — it tells
the docs *which endpoint hands out tokens* so the Swagger UI can offer a login
flow. The actual token *creation* still happens in your login route (§11.1); this
scheme only handles the *reading* side on subsequent requests.

**Decoding the token is verifying it, not just parsing it.** A subtle but crucial
point: `decode_access_token(token)` doesn't merely split the JWT and read its
fields — it *cryptographically verifies the signature* using the secret key, and
rejects the token if it was tampered with or has expired (§7.2). That's why the
`try/except` wraps it: a forged or expired token raises, and you convert that into
a clean `401`. So "who is this user" is answered by trusting the *signed* claims
inside the token (the `sub` user id), then loading that user from the database to
confirm they still exist. Note the order of failure modes — missing token, invalid
/expired token, deleted user — all collapse to `401`, because from the client's
perspective they all mean the same thing: "you are not authenticated, log in
again."

```python
def require_roles(*roles: UserRole):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Permission denied")
        return user
    return dep

require_admin = require_roles(UserRole.admin)
require_engineer_or_admin = require_roles(UserRole.admin, UserRole.engineer)
```

This is the **authorization** layer, and it's elegant. `require_roles` is a
**dependency factory**: a function that *builds* a dependency configured with
the allowed roles. It uses a **closure** — the inner `dep` "remembers" the
`roles` passed to the outer function. The result: a route protected with
`Depends(require_admin)` will only run for admins; everyone else gets `403
Forbidden`. `require_engineer_or_admin` allows two roles.

**The factory-and-closure pattern, unpacked.** Strip it to the mechanics.
`require_roles(UserRole.admin)` is a *call* that runs immediately and returns a
brand-new function `dep`. That returned `dep` is what you actually use as a
dependency. The magic is that `dep` references `roles` — a variable from its
enclosing function — and Python keeps that variable alive even after
`require_roles` has finished returning. That captured-variable arrangement is a
**closure**: the inner function "closes over" `roles` and carries it around like a
backpack. So `require_admin` is a `dep` whose backpack holds `(admin,)`, and
`require_engineer_or_admin` is a *different* `dep` whose backpack holds `(admin,
engineer)`. Why go to this trouble instead of writing two near-identical
hardcoded functions? Because the factory lets you stamp out as many role-checkers
as you need from one definition — the logic ("is the user's role in the allowed
set?") is written once, and only the *configuration* (which roles) varies per
instance. It's the same generics-style "write once, specialize many" idea you saw
with `Page[T]`, applied to behavior instead of types.

**Why `dep` takes `get_current_user` as its own dependency.** Notice the role
checker doesn't re-read the token or hit the database — it declares `user: User =
Depends(get_current_user)` and lets the chain from earlier do that work. By the
time `dep` runs, authentication has already succeeded and it's handed a real
`User`; its only job is the *authorization* decision: is `user.role` in the
allowed set? This cleanly separates the two questions — *authentication* ("who are
you?", handled by `get_current_user`) and *authorization* ("are you allowed?",
handled by `dep`) — and composes them by stacking dependencies. That separation is
exactly why a missing token yields `401` (authentication failed, raised deeper in
the chain) while a valid token with the wrong role yields `403` (authentication
succeeded, authorization failed, raised here).

This is **Role-Based Access Control (RBAC)** implemented at the *dependency
layer*, which means authorization is enforced declaratively right in the route
signature — you can see a route's permissions at a glance, and you can't forget
to check because the check *is* the way you get the user.

> **The distinction made concrete:** 401 Unauthorized = "I don't know who you
> are" (bad/missing token). 403 Forbidden = "I know who you are, but you're not
> allowed." Beginners mix these up constantly.

---

## 13. Backend, part 8: the API routes

`backend/app/api/routes/`. Each file groups related endpoints into a **router**
(a mini-app you later attach to the main app). Routes are the **thin** top
layer: validate input (via schemas), enforce auth (via deps), call a service,
shape the response (via schemas).

**The four-layer flow every route follows.** It's worth fixing the mental model
before reading any specific route, because they all follow the same assembly line.
(1) **Validate** — the request's query params and JSON body are parsed into typed
Python values and Pydantic schemas; anything malformed is rejected with `422`
before your code runs. (2) **Authorize** — the `Depends(...)` on the route runs the
auth chain from §12, so by the time your function body executes you *know* the
caller is logged in and has the right role. (3) **Delegate** — the body calls a
service function (§11) to do the actual work; the route itself contains almost no
logic. (4) **Shape** — the service's ORM objects are converted into `*Out` schemas
and returned, and FastAPI serializes them to JSON. A route that does more than
these four steps usually has business logic that belongs down in a service. This
thinness is the point: routes are wiring, not brains.

### 13.1 Anatomy of a route — `routes/devices.py`

```python
router = APIRouter(prefix="/api/devices", tags=["devices"])

@router.get("", response_model=Page[DeviceOut])
def list_devices(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    status_filter: DeviceStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Page[DeviceOut]:
    items, total = device_service.list_devices(db, limit=limit, offset=offset, search=search, status=status_filter)
    return Page(items=[DeviceOut.model_validate(i) for i in items], total=total, limit=limit, offset=offset)
```

Everything in this small function is intentional:

- `@router.get("")` + `prefix="/api/devices"` → handles `GET /api/devices`.
- `response_model=Page[DeviceOut]` → FastAPI validates and serializes the
  response to that schema, *and* documents it in `/docs`. Anything not in
  `DeviceOut` is stripped — a safety net against leaking fields.
- `limit: int = Query(20, ge=1, le=100)` → a **query parameter** (`?limit=20`)
  with a default and bounds (`ge` = ≥, `le` = ≤). FastAPI rejects `limit=99999`
  automatically. This caps how much a client can demand at once.
- `status_filter ... Query(None, alias="status")` → the URL uses `?status=` but
  the Python variable is `status_filter` (to avoid clashing with the imported
  `status` module). **Aliasing** bridges the two.
- `db: Session = Depends(get_db)` → injected session.
- `_: User = Depends(get_current_user)` → **requires login**, but the underscore
  name signals "I need this check to run, but I don't use the value." (Listing
  devices needs *any* logged-in user.)
- The body calls the service, then converts each ORM object to `DeviceOut` and
  wraps everything in the `Page` envelope.

**`response_model` does double duty — documentation and enforcement.** Declaring
`response_model=Page[DeviceOut]` is not just a type hint for humans. At runtime,
FastAPI takes whatever your function returns and *filters it through* that schema
before sending it — any attribute not declared on `DeviceOut` is silently dropped
from the JSON. That's the safety net mentioned in §10: even if a future change
made the service hand back a richer object with a sensitive field, the response
model would strip it. At documentation time, the same declaration is what lets
`/docs` show the exact JSON shape clients should expect. One declaration, two
guarantees: the response is *shaped* correctly and *documented* correctly, and
the two can never drift apart because they come from the same source.

**Query parameter validation is the same boundary discipline as body validation.**
`limit: int = Query(20, ge=1, le=100)` packs several decisions into one line. The
default `20` means the param is optional. `ge=1` and `le=100` are bounds the
framework enforces *before your code runs* — a request with `?limit=0` or
`?limit=99999` is rejected with `422`, never reaching your function. That upper
bound is a small but real defense: without it, a client could ask for a million
rows in one request and exhaust your memory and database. The `alias="status"`
trick on `status_filter` is the practical reality that the *URL* name a client
types (`?status=active`) sometimes can't be the *Python* variable name (because
`status` collides with the imported `status` module of HTTP codes); the alias
lets the public API stay clean while the code avoids the clash. Every one of
these is the same idea as schema validation — catch bad input at the edge so the
interior can trust what it gets.

The other device endpoints show the **RBAC pattern**:

```python
@router.post("", response_model=DeviceOut, status_code=201)
def create_device(payload: DeviceCreate, db=Depends(get_db), _: User = Depends(require_admin)):
    return DeviceOut.model_validate(device_service.create_device(db, payload))
```

Reading data uses `get_current_user` (any role). Creating/updating/deleting uses
`require_admin`. `payload: DeviceCreate` tells FastAPI to parse + validate the
JSON request body into that schema. `status_code=201` returns "Created" instead
of the default 200. The `DELETE` returns `204 No Content` with an empty body —
the correct REST convention for "deleted successfully, nothing to return."

**HTTP status codes carry meaning — use the right one.** REST leans on status
codes to communicate outcomes, and picking the correct one is part of designing a
clean API. `200 OK` is the generic success. `201 Created` specifically says "a
new resource now exists" and is the right answer to a successful `POST` — it tells
the client the create worked and (by convention) the body is the new object.
`204 No Content` says "success, and there's deliberately nothing in the body,"
which is exactly right for `DELETE`: the thing is gone, so there's nothing
meaningful to return. On the error side you've already met `401` (not
authenticated), `403` (authenticated but forbidden), `422` (validation failed),
and `404` (not found, raised by the service's `NotFoundError`). A client — human
or machine — can branch on these codes without parsing your prose, which is the
whole reason the categories exist (recall the 2xx/4xx/5xx families from §3.1).
Matching the verb to the right code is the difference between an API that *follows*
HTTP and one that merely tunnels through it.

**The RBAC pattern read off the signature.** Look at how the *only* difference
between "anyone logged in" and "admins only" is which dependency the route
declares: read endpoints carry `_: User = Depends(get_current_user)`, write
endpoints carry `_: User = Depends(require_admin)`. Permissions live right in the
function signature, visible at a glance, and they're impossible to forget because
the dependency that enforces the check is the *same* mechanism that would give you
the user. There's no separate, skippable "if not admin: reject" line buried in the
body that a tired developer might omit — the guard *is* the plumbing. That's the
payoff of doing authorization at the dependency layer.

### 13.2 `routes/auth.py`

`POST /api/auth/register` and `POST /api/auth/login` both return a
`TokenResponse` (token + user) so the frontend can log you in immediately after
either action. `GET /api/auth/me` returns the current user — used by the
frontend on startup to check "am I still logged in?" Note these endpoints are
*not* behind `require_*` (you can't require a login to log in), except `/me`
which uses `get_current_user`.

### 13.3 `routes/jobs.py` — where async kicks in

```python
@router.post("", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, db=Depends(get_db), user: User = Depends(require_engineer_or_admin)):
    job = job_service.create_job(db, device_id=payload.device_id, test_suite_id=payload.test_suite_id, user_id=user.id)
    enqueue_job(job.id)            # ← hand the work to the queue
    return JobOut.model_validate(job)
```

This is the producer side of the queue (§3.5). It (1) creates a `queued` job row
via the service, then (2) calls `enqueue_job(job.id)` to drop it on the Redis
queue, then (3) **immediately** returns the job to the caller — `201 Created`,
no waiting. The worker will do the actual running. Triggering a job requires
engineer or admin (viewers can look but not run).

**Notice what crosses the queue: just an id, not the job object.** `enqueue_job`
is handed `job.id` — a single integer — not the whole `Job` object. This is a
deliberate and important pattern in queue systems. The job's authoritative state
lives in the database; the queue message only needs to say "go process job
number 42." When the worker later picks up that message, it re-loads job 42 fresh
from the database, guaranteeing it works with the *current* state rather than a
stale snapshot serialized minutes ago. Passing only an id also keeps queue
messages tiny and avoids the headache of serializing a complex ORM object with
its relationships through Redis. The database is the single source of truth; the
queue is just a to-do list of ids. (The full producer → broker → consumer journey
is the subject of §15, the heart of the system.)

Other endpoints: `GET /api/jobs` (filtered, paginated list), `GET
/api/jobs/{id}` (the row the frontend polls), `GET /api/jobs/{id}/results`,
`GET /api/jobs/{id}/logs`, `POST /api/jobs/{id}/cancel`.

### 13.4 `routes/test_suites.py`, `routes/reports.py`, `routes/dashboard.py`, `routes/health.py`

- **test_suites** — manages suites *and* their nested test cases. Note the URLs:
  `POST /api/test-suites/{suite_id}/test-cases` (a case belongs to a suite) but
  `PATCH /api/test-cases/{test_case_id}` (operate on a case directly). This is
  thoughtful REST URL design reflecting the resource hierarchy. All writes are
  admin-only.
- **reports** — `GET /api/reports/jobs/{id}.json` returns the report dict.
  `GET /api/reports/jobs/{id}.csv` returns CSV via `PlainTextResponse` with a
  `Content-Disposition: attachment; filename=...` header — that header is what
  makes the browser **download a file** instead of displaying text.
- **dashboard** — `GET /api/dashboard/summary` returns the metrics. It wraps the
  service's recent-job dicts in `JobOut` before returning.
- **health** — `GET /api/health` returns `{"status": "ok"}`. A **health check**
  is a trivial endpoint that monitoring systems (and Docker, and CI) ping to ask
  "is this service alive?" Tiny but essential in real deployments.

---

## 14. Backend, part 9: the main app

`backend/app/main.py` — the entrypoint that assembles everything.

```python
configure_logging()
log = get_logger("api")

app = FastAPI(title="Network Test Orchestration Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(test_suites.router)
app.include_router(jobs.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
```

- `app = FastAPI(...)` creates the application object. `uvicorn app.main:app`
  (the server command) looks for this `app`.
- **Middleware** is code that wraps *every* request/response. `CORSMiddleware`
  adds the headers that tell browsers the frontend origin is allowed to call
  this API (recall §6.1). Without it, the browser blocks the frontend's
  requests.
- `include_router(...)` mounts each router's endpoints onto the app. This is why
  routes can live in separate files — they're composed here.
- `uvicorn` is the **ASGI server** that actually accepts network connections and
  runs the FastAPI app. FastAPI defines *what* to do; uvicorn handles the raw
  HTTP plumbing.

**Middleware is an onion around your routes.** Picture every request passing
through a series of concentric layers on the way *in* and the same layers on the
way *out*. Each piece of middleware is one layer: it can inspect or modify the
request before it reaches your route, and inspect or modify the response on the
way back out. `app.add_middleware(CORSMiddleware, ...)` adds one such layer that
runs for *every* endpoint, so you write the cross-cutting concern once instead of
repeating it in all forty routes. Common middleware jobs are exactly the things
that should apply uniformly — CORS headers, request logging, authentication
gates, response compression, timing. The mental model "request goes in through
the layers, response comes back out through them in reverse" is worth holding
onto; it's why the order you add middleware can matter.

**CORS, explained properly, because it confuses everyone.** Browsers enforce the
**same-origin policy**: JavaScript running on `http://localhost:5173` (the Vite
frontend) is, by default, *forbidden* from reading responses from a *different*
origin like `http://localhost:8000` (the API). "Origin" means the combination of
scheme + host + port, so different ports are different origins. This is a security
feature — it stops a malicious site you visit from quietly calling your bank's API
using your logged-in cookies. But our frontend and backend are *legitimately*
different origins, so we need to explicitly opt in. **CORS** (Cross-Origin
Resource Sharing) is the mechanism: the server sends headers like
`Access-Control-Allow-Origin: http://localhost:5173` that tell the browser "I
trust this origin, let it read my responses." `CORSMiddleware` adds those headers.
For certain requests the browser also sends a **preflight** — an automatic `OPTIONS`
request that asks "am I allowed to make this call?" before making the real one —
and the middleware answers that too. The single most common "my frontend can't
talk to my backend" bug is a missing or misconfigured CORS origin, and crucially,
it's enforced *by the browser*, not the server — which is why the same API call
works fine from `curl` or Postman but fails from the web page.

**`include_router` and why routes live in separate files.** Each route module
creates its own `APIRouter` — a self-contained collection of related endpoints
with a shared URL prefix and tag. `app.include_router(devices.router)` copies all
of that router's endpoints onto the main `app`, prefix and all. This is
composition: the application is *assembled* here from independent pieces, which
means the device endpoints, auth endpoints, and job endpoints can each live in
their own file, be developed and tested in isolation, and be wired together in
one readable list. It's the same modularity principle as services — small focused
units combined at a single assembly point — applied to the HTTP layer.

**FastAPI versus uvicorn — two different jobs.** It's a common confusion to think
FastAPI "runs" your server; it doesn't. FastAPI is a *framework* that decides
**what** to do with a request — which function handles `GET /api/devices`, how to
validate it, what to return. **uvicorn** is the *server* that handles the **how**
of networking: it opens the TCP socket, speaks the raw HTTP protocol, accepts
connections, and — critically — runs an **async event loop** that can juggle many
connections concurrently on a single thread (recall §3.5). The bridge between them
is **ASGI** (Asynchronous Server Gateway Interface), a standard contract that says
"a server like uvicorn will call an app like FastAPI in this agreed-upon way."
Because both sides speak ASGI, you could swap uvicorn for another ASGI server
without changing your FastAPI code. The command `uvicorn app.main:app` literally
means "uvicorn, import the `app` object from `app/main.py` and serve it."

---

## 15. Backend, part 10: background jobs (the heart of it)

`backend/app/workers/`. This is the most conceptually rich part. Four files
cooperate: `queue.py` (enqueue side), `worker.py` (the process), `tasks.py` (the
entry function), and `runner.py` (the actual test execution).

### 15.1 `workers/queue.py` — enqueuing

```python
JOB_QUEUE_NAME = "jobs"
def _redis() -> Redis: return Redis.from_url(settings.REDIS_URL)
def get_queue() -> Queue: return Queue(JOB_QUEUE_NAME, connection=_redis())

def enqueue_job(job_id: int) -> None:
    if os.getenv("SYNC_JOBS") == "1":
        from app.workers.tasks import run_job
        run_job(job_id)            # run inline, no Redis
        return
    get_queue().enqueue("app.workers.tasks.run_job", job_id, job_timeout=600)
```

When the route calls `enqueue_job(42)`, normally it pushes a message onto the
Redis `"jobs"` queue saying "call `app.workers.tasks.run_job(42)`." RQ
serializes that and a worker will pick it up.

**What RQ actually puts on the queue.** The string `"app.workers.tasks.run_job"`
is a *dotted import path* — it tells the worker exactly which function to import
and call. RQ packages that path together with the arguments (`42`) and some
metadata into a small serialized message and `LPUSH`es it onto a Redis list named
`rq:queue:jobs`. That's the entire "queue": a Redis list of pending job
descriptions. The reason the worker can import and call a function the producer
named by string is that *both processes run the same codebase* — they share the
Docker image — so `app.workers.tasks.run_job` resolves to the identical function
in both. This is why you pass a dotted path rather than the function object
itself: a function can't be sent over a network, but its *name* can, and the
worker reconstructs it on its end. (Redis here is the **broker** from §3.5 — the
intermediary that holds the to-do list so producer and consumer never have to be
running at the same instant.)

**The `SYNC_JOBS=1` branch is a brilliant testing trick.** In tests you don't
want to run Redis and a separate worker process — that's slow and flaky. So when
the `SYNC_JOBS` env var is set, `enqueue_job` just *runs the job immediately,
in-process*. The test calls `POST /api/jobs`, and by the time it gets the
response, the job has already fully executed. Same code path, deterministic
tests. This is **dependency seam** design: one toggle swaps async for sync.

**Why this seam is worth the two extra lines.** The hard thing to test in an
asynchronous system is the *timing*: in production, `POST /api/jobs` returns while
the job is still `queued`, and the results appear some unknown number of
milliseconds later when a worker gets around to it. A test would have to enqueue,
then *poll and wait*, then check — racy, slow, and dependent on a live Redis and a
running worker. The `SYNC_JOBS` toggle collapses that whole problem: when set, the
enqueue call runs `run_job` inline and only returns once the job has *completely
finished*, so the test can immediately assert on the results with no waiting and
no extra infrastructure. The beauty is that it's the *same* `run_job` function and
the *same* code path the real worker uses — you're not testing a fake, you're
testing the real execution logic, just synchronously. This kind of single-switch
"swap the hard-to-test boundary for a deterministic version" is a **seam**, and
learning to build them is one of the highest-leverage testing skills there is.

`job_timeout=600` means "kill the job if it runs longer than 600 seconds" — a
safety valve against a stuck job hogging a worker forever.

### 15.2 `workers/worker.py` — the worker process

```python
def main() -> None:
    configure_logging()
    conn = Redis.from_url(settings.REDIS_URL)
    queue = Queue(JOB_QUEUE_NAME, connection=conn)
    Worker([queue], connection=conn).work(with_scheduler=False)

if __name__ == "__main__":
    main()
```

This is a **separate program** you start with `python -m app.workers.worker`
(it's the `worker` service in Docker Compose). It connects to Redis, watches the
`"jobs"` queue, and `.work()` **blocks forever**, pulling jobs off the queue and
running them one at a time. This is the **consumer** from §3.5. Because it's a
separate process, slow jobs never block the web server, and you can scale by
running more worker containers.

**What `.work()` is doing while it "blocks forever."** The worker's main loop is
conceptually simple: ask Redis for the next job on the queue (using a *blocking*
pop, so if the queue is empty the worker sleeps efficiently instead of
busy-spinning), and when one arrives, import the named function, call it with the
saved arguments, record success or failure, and loop back for the next. It
processes jobs **one at a time, in order**, which is exactly what you want for
this app — test runs are independent and serial execution keeps things simple and
predictable. The phrase "separate process" is the whole point of the architecture:
the web server (uvicorn) and the worker are *different operating-system processes*,
possibly on different machines. A test run that takes thirty seconds ties up a
worker for thirty seconds but never touches the web server, which stays free to
answer `GET /api/jobs/{id}` polls instantly. And because the queue decouples them,
**scaling out** is trivial: start three worker containers and three jobs run
concurrently, each pulling from the same shared Redis queue, with no code change.
That is the payoff of the producer/broker/consumer split.

### 15.3 `workers/tasks.py` — the safe entry point

```python
def run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            log.warning("job_not_found", job_id=job_id); return
        if job.status == JobStatus.canceled:
            log.info("job_canceled_skip", job_id=job_id); return
        try:
            execute_job(db, job)
        except Exception as exc:
            log.exception("job_crashed", job_id=job_id)
            job.status = JobStatus.error; job.error_message = str(exc); db.commit()
    finally:
        db.close()
```

This is the function the worker calls for each job. Key responsibilities:

- It **creates its own DB session** (`SessionLocal()`). The worker is a separate
  process from the web app, so it can't reuse a request session. The `try/finally`
  guarantees the session is closed.
- It **re-checks the status**: if the job was canceled while sitting in the
  queue, skip it.
- It wraps `execute_job` in a `try/except` that **catches any crash**, marks the
  job `error`, and records the message. This is critical: a worker must never
  silently die on a bad job; it should record the failure and move on. **Robust
  error handling at the system boundary** (here, the boundary between "queue
  hands me a job" and "my code runs").

**Why the worker needs its own session, in plain terms.** Sessions (§8.2) are not
shareable across processes or threads — each one wraps a single database
connection and tracks its own set of in-flight objects. The web request's session
was created and *closed* back when the `POST /api/jobs` response was sent, long
before the worker ever picks up the job. So `run_job` opens a fresh
`SessionLocal()` of its own, scoped to this one job's execution, and the
`try/finally` makes sure that connection is returned to the pool no matter what —
success, failure, or crash. Forgetting that `finally` would leak a connection per
job until the pool is exhausted and the worker hangs.

**The re-check for cancellation closes a real race.** A job can sit in the queue
for a while before a worker frees up. During that gap a user might cancel it
(§11.4 flips the status to `canceled`). So the very first thing `run_job` does
after loading the job is check `if job.status == JobStatus.canceled: return` —
otherwise it would dutifully run a job the user explicitly stopped. This is the
consumer half of the cancellation feature: the producer marks intent, the
consumer honors it at pickup time.

**This `try/except` is the worker's last line of defense.** Think about what
happens without it: `execute_job` throws on some unexpected input, the exception
propagates up, and — depending on the setup — either the worker crashes or RQ marks
the job "failed" with no useful record in *your* database. The job would be stuck
appearing `running` forever, and the next job might never get processed. The
blanket `except Exception` converts any crash into a clean, recorded outcome: the
job row is set to `error`, the exception text is saved to `error_message` so a
human can debug it, and the worker survives to process the next job. This is the
golden rule of background workers — *a single poisonous job must never take down
the worker or vanish silently*. Catching broadly is normally a code smell, but at
this exact boundary (the outermost edge of an autonomous background task) it's
precisely the right move.

### 15.4 `workers/runner.py` — actually running the tests

This is the largest worker file and contains the real logic. `execute_job` is
the conductor; `_run_case` is the per-test logic.

**`execute_job(db, job)`:**

```python
job.status = JobStatus.running; job.started_at = _now(); db.commit()
device = db.get(Device, job.device_id); suite = db.get(TestSuite, job.test_suite_id)
if not device or not suite:
    job.status = JobStatus.error; ...; return
client = _get_client(device)                  # a MockDeviceClient
cases = sorted([c for c in suite.test_cases if c.enabled], key=lambda c: c.order_index)
```

1. Mark the job `running` and stamp `started_at`, then **commit immediately** so
   the polling frontend sees the status change in real time.
2. Load the device and suite; bail out as `error` if either vanished.
3. Build a device client (the mock).
4. Select **enabled** cases and sort them by `order_index` — tests run in a
   defined order.

Then it loops over cases:

```python
for case in cases:
    case_start = time.monotonic()
    try:
        status, output, err = _run_case(client, case)
    except Exception as exc:
        status, output, err = TestResultStatus.error, "", str(exc)
    duration_ms = int((time.monotonic() - case_start) * 1000)
    result = TestResult(job_id=job.id, test_case_id=case.id, test_case_name=case.name,
                        status=status, actual_output=output, expected_output=case.expected_pattern or case.expected_value,
                        error_message=err, started_at=..., completed_at=_now(), duration_ms=duration_ms,
                        metadata_json={"severity": case.severity.value, "test_type": case.test_type.value})
    db.add(result); db.commit()
    # tally pass/fail/error, append a human log line
```

For each case it: times it with `time.monotonic()` (a **monotonic clock** that
only moves forward — the correct tool for measuring durations, immune to system
clock changes), runs it, wraps any exception into an `error` result (one bad
case can't crash the whole job), writes a `TestResult` row, and appends a
log line. It commits per result so progress is visible as it goes.

Finally it computes the **overall job status** from the tallies:

```python
if err_count > 0 and pass_count == 0 and fail_count == 0:
    final = JobStatus.error          # everything errored
elif fail_count == 0 and err_count == 0:
    final = JobStatus.passed          # all good
elif pass_count == 0:
    final = JobStatus.failed          # nothing passed
else:
    final = JobStatus.partial         # mixed
job.status = final; job.completed_at = _now(); job.duration_ms = total_ms
job.summary = f"{pass_count} passed, {fail_count} failed, {err_count} errored out of {len(cases)} test cases"
job.logs = "\n".join(log_lines); db.commit()
```

This roll-up logic is a small **state-derivation** exercise: turn many
fine-grained results into one meaningful headline status. `partial` (some passed,
some failed) is a nice touch — real systems aren't binary.

**`_run_case(client, case)`** is a dispatch on `case.test_type`:

```python
if t == TestType.ping_check:
    r = client.ping()
    return (passed, r.output, None) if r.success else (failed, "", r.error)
if t == TestType.ssh_command:
    r = client.ssh_exec(case.command or "")
    if not r.success: return error, r.output, r.error
    if case.expected_pattern and not re.search(case.expected_pattern, r.output):
        return failed, r.output, f"Pattern not found: {case.expected_pattern}"
    return passed, r.output, None
# ... vlan_check, interface_status, config_contains, config_not_contains, mock_radius_check, log_scan
```

The patterns to notice:

- Each test type maps "device response" → pass/fail/error. A connection problem
  is `error` (couldn't even test); a working connection with the wrong result is
  `failed` (tested, didn't pass). That distinction is meaningful and consistent.
- `re.search(pattern, output)` uses **regular expressions** to check whether the
  output contains an expected pattern. `config_contains` fails if the pattern is
  *absent*; `config_not_contains` fails if it's *present* (e.g., ensuring telnet
  is **not** configured). `log_scan` fails if a *bad* pattern (like
  `AUTHMGR-5-FAIL`) **is** found.
- `vlan_check` does a literal substring check for `expected_value`;
  `interface_status` fails if any interface is "down" when `expected_value ==
  "all_up"`.
- `_run_case` returns a tuple `(status, output, error)` — a simple, uniform
  contract the caller relies on regardless of test type.

This is a clean example of the **strategy/dispatch pattern**: one function with
a branch per type, each branch implementing that type's rule, all returning the
same shape.

**Why "commit per result" matters for the user experience.** Inside the case
loop, each `TestResult` is written and committed *individually* rather than
batched up and saved once at the end. That's a deliberate choice serving the
polling frontend: as each test finishes, its result becomes immediately visible to
anyone querying `GET /api/jobs/{id}/results`, so the UI can show progress
ticking by — "3 of 10 passed so far" — instead of a long silence followed by a
sudden dump. The same reasoning drove the early `commit` that flips the job to
`running`: commit the state change the instant it happens so observers see
reality in near real time. The trade-off (more commits = more database round
trips) is well worth it here because live visibility into a running job is a
core feature, not a nicety.

**The monotonic clock, and why not `datetime.now()`.** Timing each case uses
`time.monotonic()`, not the wall clock. A wall clock (`datetime.now()`) can jump
— NTP corrections, daylight-saving changes, an admin resetting the system time —
and if it jumps *backwards* mid-test you could compute a *negative* duration,
which is nonsense. `time.monotonic()` is guaranteed to only ever move forward at a
steady rate; its absolute value is meaningless (it's not "the time"), but the
*difference* between two readings is a rock-solid elapsed-duration measurement.
The rule to remember: wall-clock time for "*when* did this happen" (the
`started_at`/`completed_at` timestamps), monotonic time for "*how long* did this
take" (the `duration_ms`). Using the wrong one is a subtle bug that only bites
occasionally, which makes it especially nasty.

---

## 16. Backend, part 11: integrations (mock & real devices)

`backend/app/integrations/`. An **integration** is code that talks to an
*external system* — here, network devices. Isolating it in its own folder means
the rest of the app doesn't care *how* device communication works.

### 16.1 `integrations/mock_device_client.py`

```python
@dataclass
class MockResponse:
    success: bool
    output: str
    error: str | None = None

def _seed_for(hostname: str) -> random.Random:
    h = int(hashlib.sha256(hostname.encode()).hexdigest(), 16)
    return random.Random(h)

class MockDeviceClient:
    def __init__(self, hostname, management_ip, vendor, status="active"):
        ...
        self.rng = _seed_for(hostname)
    def ping(self): ...
    def ssh_exec(self, command): ...
    def snmp_get(self, oid="sysDescr"): ...
    def radius_check(self): ...
```

This class **fakes a real device**. Highlights:

- `@dataclass` auto-generates `__init__`/`__repr__` for `MockResponse` — a tidy
  way to define a small data holder.
- **Deterministic randomness via seeding.** `_seed_for(hostname)` turns the
  hostname into a number (via SHA-256) and seeds a `random.Random` with it. That
  means the *same* device always produces the *same* "random" results across
  runs — outputs feel varied between devices but are **reproducible** for a given
  device. Reproducibility matters for demos and debugging.
- `ssh_exec` inspects the command string and returns **vendor-flavored fake
  output**: `show vlan` returns a VLAN list (always including 1718, which the
  seeded Cisco suite checks for), `show running-config` returns a config with
  `aaa new-model`, `show logging` sometimes injects an `AUTHMGR-5-FAIL` line
  (~30% chance) so the log-scan test occasionally fails — making demos
  realistic.
- If `status != "active"`, `ping`/`ssh`/`snmp` return failures — so an inactive
  device produces error results, just like reality.

The key design idea: `MockDeviceClient` exposes the **same method surface**
(`ping`, `ssh_exec`, `snmp_get`, `radius_check`) that a real client would. The
runner doesn't know or care it's a mock. That's **programming to an interface** —
you can swap the implementation without touching the caller.

**Why deterministic randomness is not a contradiction.** A pseudo-random
generator like `random.Random` produces a sequence that *looks* random but is
entirely determined by its starting **seed**. Seed it with the same number and
you get the same sequence every time. `_seed_for(hostname)` exploits this: it
hashes the hostname to a big stable number and seeds the generator with it, so a
device named `core-sw-01` always yields the same "random" ping latencies and
occasional failures, run after run, machine after machine. Different hostnames
seed differently, so the *fleet* looks varied — but each *individual* device is
reproducible. This is exactly what you want for a demo and for debugging: if a
test fails, it fails the *same way* next time so you can investigate, instead of a
flaky "works on the second try" mystery. True randomness would make the demo
unpredictable and tests non-repeatable; seeded randomness gives you variety
*and* repeatability at once.

**"Programming to an interface" is the seam that makes mocking possible.** The
runner calls `client.ping()`, `client.ssh_exec(cmd)`, and so on, never asking
"are you real or fake?" Because both `MockDeviceClient` and the real SSH client
expose the *same method names with the same shapes*, either can be dropped in and
the runner is none the wiser. This is the **dependency inversion** idea: the
high-level policy (the test runner) depends on an *abstract* notion of "a device
client," not on a concrete implementation. The single `_get_client` function is
the one place that decides which concrete client to hand back — flip it to read
`DEVICE_EXECUTION_MODE` and the entire app talks to real hardware with zero
changes anywhere else. The same seam is what lets the *tests* run without any
network at all. One well-placed interface buys you demos, tests, and a real-mode
upgrade path simultaneously.

### 16.2 `integrations/ssh_client.py` and `snmp_client.py`

These are the **real-mode placeholders**. `ssh_client.run_command(...)` uses
`paramiko` to actually SSH in and run a command (returning an `SSHResult`).
`snmp_client.snmp_get(...)` is a stub that returns "not implemented in MVP."
They exist to show the *seam* where real device communication would plug in
(`DEVICE_EXECUTION_MODE=real`), without requiring real gear for the demo. In
`runner.py`, `_get_client` currently always returns the mock, with a comment
noting where you'd branch to real clients with secrets. **MVP** = Minimum Viable
Product: build the smallest thing that demonstrates the idea, leave clean hooks
for the rest.

---

## 17. Backend, part 12: the seed script

`backend/app/seed.py`. **Seeding** means loading initial/demo data so the app
isn't empty on first run.

```python
def main():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            log.info("seed_skipped_existing_data"); return
        # create admin/engineer/viewer users (password "password123")
        # create 8 devices across vendors/types/statuses
        # create 3 test suites with their test cases
        db.commit()
    finally:
        db.close()
```

The most important property is the first check: **idempotency**. *Idempotent*
means "running it multiple times has the same effect as running it once." The
seed only inserts data if there are no users yet. That's vital because Docker
Compose runs the seed *every time the backend starts* — without the guard, you'd
get duplicate data on every restart. Idempotency is a recurring requirement for
setup/migration/seed scripts.

The seed also encodes the **demo narrative**: it creates a Cisco VLAN suite that
checks for VLAN 1718 and `aaa new-model` (which the mock client is rigged to
return), so a fresh install has a satisfying, mostly-passing demo out of the box.

**Why seeding and migrations are different things (a common confusion).** People
new to backends often blur *migrations* (§18) and *seeding*, but they answer
different questions. A **migration** changes the *shape* of the database — it
creates or alters tables, columns, indexes, constraints. **Seeding** inserts
*data* into tables that already exist. Migrations are about structure; seeds are
about contents. They also have different lifecycles: migrations are an
append-only, versioned history you never edit after release (because they've run
on other databases), whereas a seed is just demo/initial data you can freely
change. In production you'd typically run all migrations, then optionally seed a
*minimal* set of required rows (e.g. a first admin account); the rich demo data
here is a portfolio convenience, not something you'd ship to real customers.

**Why the guard checks users specifically.** The idempotency check counts `User`
rows, not devices or suites. That's a deliberate, simple choice: users are
created *first* in the seed, so "are there any users?" is a reliable proxy for
"has this database already been seeded?" If the script had crashed halfway last
time it could in theory leave a partial seed, but because the whole seed runs
inside one transaction that only `commit()`s at the very end (§3.3 atomicity),
either *all* the seed data is committed or *none* is — there's no half-seeded
state for the guard to misread. This is the same all-or-nothing transaction
property that protects the suite-plus-cases creation in §11.3, reused here.

**Why the demo password is hard-coded — and why that's fine *here*.** The seed
creates users with the password `"password123"`, hashed with bcrypt before
storage exactly like a real registration (§7) — the database never holds the
plain text. Hard-coding a known password is acceptable *only* because this is a
local demo/portfolio app with mock data and no real users. In a real deployment
you would never seed a known password into a system anyone can reach; you'd
either prompt for an initial admin password, generate a random one and print it
once, or require a password reset on first login. Being able to articulate "this
shortcut is fine in *this* context but would be a vulnerability in production" is
exactly the security judgment the project is meant to demonstrate.

**Why seed at startup at all (vs. a manual step).** Running the seed automatically
when the backend container starts means a brand-new clone of the repo comes up
*already populated* — you can `docker compose up` and immediately log in and click
around. Because the seed is idempotent, doing this on *every* start is safe: the
first start populates, and every subsequent start sees existing users and exits in
milliseconds. The cost of that convenience is essentially zero (one `COUNT` query
per startup), which is why automatic, idempotent seeding is a common pattern for
demo and development environments.

---

## 18. Backend, part 13: database migrations (Alembic)

`backend/app/db/migrations/` + `alembic.ini`. This solves a problem you might
not have thought about yet: **how does the database schema change over time?**

Your models define the *desired* table shapes. But a running production database
already has tables full of data. You can't just `DROP` and recreate them — you'd
lose everything. **Migrations** are versioned scripts that *evolve* the schema
incrementally (add a column, create a table, add an index) while preserving data.

### 18.1 `migrations/env.py`

The configuration Alembic runs. Key lines:

```python
from app.core.config import settings
from app.db.base import Base
from app import models  # noqa: F401  ensure models are imported

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

- It pulls the DB URL from your *app settings* (single source of truth — no
  duplicated connection string).
- `import app.models` forces all model classes to load so they register
  themselves on `Base.metadata`. `target_metadata = Base.metadata` is what lets
  Alembic *autogenerate* migrations by comparing your models to the live DB.
- It supports **offline mode** (emit SQL text) and **online mode** (connect and
  apply) — standard Alembic boilerplate.

### 18.2 `migrations/versions/0001_initial.py`

The first migration. It has:

```python
revision = "0001"
down_revision = None     # this is the first one; nothing comes before it

def upgrade() -> None:    # apply the change
    op.create_table("users", ...)
    op.create_table("devices", ...)
    # ... all tables, enums, indexes
def downgrade() -> None:  # reverse the change
    ...
```

Every migration has a unique `revision` id and a `down_revision` pointing to the
previous one, forming a **linked list of schema versions**. `upgrade()` moves
forward; `downgrade()` rolls back. Alembic stores the current revision in a
special table in your DB, so it knows which migrations still need to run. The
command `alembic upgrade head` means "apply every migration up to the latest"
— that's exactly what the Docker `backend` service runs on startup, before
seeding.

**The linked list of revisions, and why it's a chain.** Each migration names its
parent via `down_revision`, so the set of migrations forms an ordered chain:
`0001 → 0002 → 0003 → ...`, with the newest called `head`. Alembic keeps a tiny
table named `alembic_version` *inside your database* that records which revision
the database is currently at. When you run `alembic upgrade head`, Alembic reads
that marker, sees (say) the DB is at `0002`, and runs the `upgrade()` of every
revision after it in order until it reaches `head`. This is what makes
deployments safe and repeatable: a brand-new database runs every migration from
the start, while an existing production database runs only the *new* ones, and
nobody has to remember which changes have been applied — the chain plus the
version marker track it automatically. `downgrade()` exists for the reverse
journey: if a deploy goes wrong, `alembic downgrade -1` runs the current
revision's `downgrade()` to undo it, stepping back one link in the chain.

**Autogenerate, and why you still review what it writes.** Because `env.py` wired
`target_metadata = Base.metadata`, Alembic can *compare* your current models to
the live database schema and **autogenerate** a migration capturing the
difference — `alembic revision --autogenerate -m "add notes column"` will detect a
new column on a model and write the `op.add_column(...)` call for you. This is a
huge time-saver, but it is a *draft*, not gospel: autogenerate reliably catches
new tables and columns, but it can miss or mis-guess things like column renames
(which it may see as a drop-plus-add, destroying data) or subtle type changes. So
the professional workflow is: let Alembic generate the migration, then *read it*
and fix anything dangerous before committing. The migration file, once reviewed,
becomes the authoritative, version-controlled record of exactly how the schema
evolved.

Notice the enums (`user_role`, `device_vendor`, etc.) are created explicitly —
in PostgreSQL, enums are real database types that must be defined. The migration
is the authoritative DDL (**Data Definition Language**: the `CREATE TABLE`-type
SQL).

> **Why not just `Base.metadata.create_all()`?** That works for a fresh DB (and
> the tests use it for speed), but it can't *evolve* an existing populated DB.
> Migrations are the professional answer for anything that goes to production.

---

## 19. Backend, part 14: the tests

`backend/app/tests/`. Automated tests prove the code works and keep it working
as you change it. This project uses **pytest**.

### 19.1 `tests/conftest.py` — the test setup

`conftest.py` is a special pytest file holding shared **fixtures** (reusable
setup pieces). The top of the file is doing something clever:

```python
_db_file = os.path.join(tempfile.gettempdir(), "nto_test.sqlite")
... remove old file ...
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["SYNC_JOBS"] = "1"
os.environ["JWT_SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from app.main import app
```

- It sets environment variables **before importing the app**, because `settings`
  reads them at import time. Order matters.
- Tests use **SQLite** (a tiny file-based database) instead of PostgreSQL — no
  server to run, fast, disposable. This works because SQLAlchemy abstracts the
  database; the same model code runs on either. (A tradeoff: SQLite isn't
  identical to Postgres, so CI also runs against real Postgres.)
- `SYNC_JOBS=1` makes jobs run **inline** (recall §15.1) — no Redis/worker
  needed, and tests are deterministic.

The fixtures:

```python
@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine); yield

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: ... db_session ...
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()
```

- `_reset_db` is `autouse=True`, so *before every test* it drops and recreates
  all tables — each test starts from a **clean, isolated** database. Test
  isolation is essential: tests must not depend on each other's leftover data.
- The `client` fixture builds a `TestClient` (an in-process fake HTTP client
  from FastAPI/httpx) and uses **`dependency_overrides`** to swap the real
  `get_db` for the test session. This is dependency injection paying off: you
  inject a test DB without changing any app code.
- `auth_headers(...)` is a helper that registers a user and returns the
  `Authorization` header — so tests can easily make authenticated requests.

**What a fixture is, and what `yield` does inside one.** A pytest **fixture** is a
function that prepares something a test needs and hands it over. When a test
function declares a parameter named `client`, pytest notices there's a fixture
called `client`, runs it, and passes its result in — the same dependency-injection
idea as FastAPI's `Depends`, applied to tests. The `yield` is the clever part: a
fixture that `yield`s is split into "setup before the yield" and "teardown after
the yield." Pytest runs the setup, freezes at the `yield` to run your test with
the yielded value, and then — *after* the test finishes — resumes the fixture to
run the teardown. So the `client` fixture sets up the dependency override, yields
the test client, and afterward clears the override; `_reset_db` recreates the
tables, yields, and the next test gets a clean slate. It's the exact same
generator pattern as `get_db` in §8.2 — setup, yield, guaranteed cleanup.

**`autouse=True` and the discipline of isolation.** Most fixtures run only when a
test asks for them by name. Marking `_reset_db` with `autouse=True` makes it run
automatically before *every single test*, asked for or not — which is exactly
right for "reset the database to empty." The principle it enforces is **test
isolation**: each test must run as if it were the only test in the world,
starting from a known clean state and leaving nothing behind. Without isolation,
tests develop hidden dependencies — test B passes only because test A happened to
create a user first — and then reordering or running one test alone mysteriously
breaks things. Drop-and-recreate before each test guarantees that can never
happen: no test can see another's data, so a passing test is genuinely passing on
its own merits.

**`dependency_overrides` is the whole reason DI was worth it.** Recall §12 made a
fuss about declaring dependencies instead of hardcoding them. Here is the payoff,
concretely: `app.dependency_overrides[get_db] = lambda: db_session` tells FastAPI
"whenever any endpoint asks for `get_db`, give it *this* test session instead."
Every route in the entire app instantly uses the SQLite test database, with zero
changes to any route code. You could not do this if routes called `get_db()`
directly; it works precisely *because* the dependency is a declared seam the
framework controls. The override is set in the fixture's setup and cleared in its
teardown, so it never leaks into other tests.

### 19.2 The test files

- `test_auth.py` — registration, login, JWT-protected routes, role enforcement.
- `test_devices.py` — device CRUD and that non-admins can't create devices.
- `test_test_suites.py` — suite + case creation.
- `test_jobs.py` — the **end-to-end** test (the most valuable one):

```python
def test_run_job_end_to_end(client):
    h = auth_headers(client)
    device_id, suite_id = _setup(client, h)            # create a device + a 3-case suite
    r = client.post("/api/jobs", json={"device_id": device_id, "test_suite_id": suite_id}, headers=h)
    assert r.status_code == 201
    job_id = r.json()["id"]
    # Because SYNC_JOBS=1, the job already ran by now.
    assert client.get(f"/api/jobs/{job_id}", headers=h).json()["status"] in ("passed", "partial", "failed")
    assert len(client.get(f"/api/jobs/{job_id}/results", headers=h).json()) == 3
    body = client.get(f"/api/reports/jobs/{job_id}.json", headers=h).json()
    assert body["passed"] + body["failed"] + body["errored"] <= 3
```

This single test exercises the *entire* stack: auth → create device → create
suite → enqueue job → run it (synchronously) → fetch results → fetch a report.
This is an **integration test** — it tests the pieces working *together*, not in
isolation. It's the test that gives you confidence the whole feature works.

**Unit tests versus integration tests, and why you want both.** A **unit test**
checks one small piece in isolation — "does `list_devices` apply the search filter
correctly?" — and when it fails it points a sharp finger at exactly what broke.
An **integration test** like `test_run_job_end_to_end` checks that many pieces
*cooperate* — auth, routing, the service layer, the queue seam, the runner, the
result writing, the report builder — all firing in sequence through real HTTP
calls. Integration tests catch a whole category of bugs unit tests can't: the
mismatches *between* components, like a route passing arguments in the wrong order
or a schema that doesn't match what the service returns. The trade-off is that
when one fails, the cause could be anywhere along the chain, so it's a coarser
signal. The healthy mix is many fast, precise unit tests plus a few
high-confidence integration tests over the critical flows — here, the job
lifecycle, which is the feature the whole app exists to deliver. The fact that
this end-to-end test can run at all — with no Redis, no worker, no Postgres, in
milliseconds — is the combined payoff of every seam built earlier: `SYNC_JOBS`,
`dependency_overrides`, and the SQLite swap.

> **Testing philosophy here:** isolate the DB per test, make async synchronous,
> use a real HTTP client against the real app, and cover both *units* (one
> endpoint) and the *integration* (the whole job flow).

---

## 20. Frontend, part 1: how a React app boots

Now the `frontend/`. First, the mental model of **React**: you describe your UI
as a tree of **components** (functions that return markup), and React renders
them. When data (**state**) changes, React re-runs the affected components and
efficiently updates the screen. You write *what the UI should look like for a
given state*, and React handles the *how*.

The markup-in-JS syntax is **JSX/TSX**: `return <div className="card">{count}</div>`.
It looks like HTML but it's TypeScript; `{ }` embeds real expressions.

**Declarative versus imperative — the core mental shift.** The old way of building
web UIs (raw JavaScript or jQuery) was **imperative**: you manually found
elements and mutated them step by step — "grab the counter span, set its text to
5; if the user is an admin, find the menu and add a logout button." Every state
change meant writing the exact DOM-surgery steps to get from the old screen to
the new one, and keeping all those mutations consistent was where bugs bred.
React is **declarative**: you write a function that, given the current state,
returns *what the whole UI should look like* — `count is 5`, `admins see a logout
button` — and you never write the transition steps at all. When the state
changes, you don't edit the screen; you just describe the *new* desired screen,
and React figures out the minimal changes to make it so. This is the single
biggest idea in React: **UI as a function of state**. Your job is to keep the
state correct and describe how state maps to markup; React's job is the tedious,
error-prone DOM updating.

**The virtual DOM and reconciliation, demystified.** Touching the real browser
DOM is comparatively slow, and naively re-rendering the entire page on every
keystroke would be sluggish. React's solution is the **virtual DOM**: a
lightweight in-memory JavaScript representation of what the UI should look like.
When state changes, React re-runs your component functions to build a *new*
virtual tree, then **reconciles** — it diffs the new virtual tree against the
previous one to compute the *smallest set of real DOM operations* that would make
the actual page match. If only one number changed, only that one text node gets
updated; the rest of the page is untouched. This is why you can afford to write
components that "re-render everything" on each state change — React makes it cheap
by only applying the diff. You get the simplicity of "just describe the whole UI
again" with the performance of "only change what actually changed." (This is also
why lists need stable `key` props: keys let the diffing algorithm match old items
to new ones instead of rebuilding the whole list.)

### 20.1 `index.html` + `main.tsx` — the entry point

A Vite app has one `index.html` with an empty `<div id="root"></div>`. The whole
app gets injected there by `main.tsx`:

```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

This is the app's setup, and the **nesting order is meaningful** — each wrapper
is a **Provider** that makes some capability available to everything inside it:

- `QueryClientProvider` — enables TanStack Query (server data fetching/caching)
  everywhere. The `queryClient` is configured with `retry: 1` and
  `refetchOnWindowFocus: false`.
- `BrowserRouter` — enables URL-based routing.
- `AuthProvider` — provides login state (the current user) to all components.
- `<App />` — your actual app (the route table).

This **Provider pattern** is how React shares global concerns without passing
them through every component manually ("prop drilling"). They wrap from
outermost (most global) to innermost.

`main.tsx` also imports `./styles/global.css` — the single stylesheet.

**Prop drilling, and why providers exist.** Data in React normally flows *down*
from parent to child through **props** (function arguments). That's clean for one
or two levels, but consider the logged-in user: the nav bar needs it, the
dashboard needs it, a button buried five components deep needs it. Passing `user`
as a prop through every intermediate component — most of which don't use it
themselves, they just forward it — is **prop drilling**, and it's tedious and
fragile. A **Provider** (built on React Context) solves this by putting a value
"in the air" for an entire subtree: any descendant, however deep, can reach up and
grab it directly via a hook, with no intermediate component needing to know it
exists. That's why `AuthProvider` wraps the whole app — so any page can call
`useAuth()` and get the current user without a chain of props. The cost is that
providers are best reserved for *genuinely global* concerns (auth, theme, the
query client); over-using context for everything makes data flow harder to trace.

**The nesting order encodes dependencies.** The wrappers go outermost
(most global) to innermost, and the order isn't arbitrary — an inner provider can
use anything an outer one provides. `AuthProvider` sits *inside* `BrowserRouter`
because the auth logic may need to trigger navigation (redirect to `/login`), and
it sits *inside* `QueryClientProvider` because logging in involves data fetching.
`App` is innermost because it depends on *all* of them. Reading the nesting top to
bottom is reading the app's capability stack: "everything has query caching,
then routing, then auth, then here's the app."

---

## 21. Frontend, part 2: routing & auth

### 21.1 `App.tsx` — the route table

```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
    <Route index element={<Navigate to="/dashboard" replace />} />
    <Route path="/dashboard" element={<DashboardPage />} />
    <Route path="/devices" element={<DevicesPage />} />
    <Route path="/devices/new" element={<DeviceFormPage />} />
    <Route path="/devices/:id" element={<DeviceDetailPage />} />
    ...
    <Route path="/jobs/:id" element={<JobDetailPage />} />
  </Route>
  <Route path="*" element={<Navigate to="/dashboard" replace />} />
</Routes>
```

This is **client-side routing**: instead of the server returning a new HTML page
per URL, the browser stays on one page and React swaps which component shows
based on the URL. `/login` shows `LoginPage`; `/devices/42` shows
`DeviceDetailPage`.

**What "client-side routing" actually means, mechanically.** In a traditional
website, clicking a link makes the browser throw away the current page and fetch
a brand-new HTML document from the server for the new URL — a full reload, a white
flash, all JavaScript state lost. A **single-page application** (SPA) loads *once*
and then never does a full reload; React Router intercepts link clicks, uses the
browser's History API to *change the URL bar without a network request*, and then
re-renders to show the component mapped to the new path. The result feels instant
because nothing is re-downloaded — only the component tree swaps. The `<Routes>`
block is essentially a big switch statement: "look at the current URL, find the
matching `<Route>`, render its element." One subtlety this buys *and* costs: deep
links work (you can bookmark `/devices/42` and it renders the right page), but the
server must be configured to return the same `index.html` for *any* path, since
the real routing happens in JavaScript after load — otherwise refreshing on
`/devices/42` would 404 on a server that expects a real file there.

The clever structure: `/login` and `/register` are public. *Everything else* is
nested inside a parent route whose element is
`<ProtectedRoute><Layout /></ProtectedRoute>`. That means **every** inner page is
automatically (a) gated behind login and (b) wrapped in the shared `Layout`
(nav bar etc.). `:id` is a **URL parameter** (e.g. `/devices/42` → `id = "42"`).
`path="*"` is the catch-all for unknown URLs → redirect to dashboard.

### 21.2 `auth/AuthContext.tsx` — global login state

A **React Context** is a way to share a value with a whole subtree without
prop-drilling. `AuthContext` holds: the current `user`, a `loading` flag, and
`login`/`register`/`logout` functions.

```tsx
useEffect(() => {
  const token = localStorage.getItem("auth_token");
  if (!token) { setLoading(false); return; }
  authApi.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
}, []);
```

`useEffect(..., [])` runs **once when the app mounts**. On startup it checks
`localStorage` (browser persistent storage) for a saved token; if present, it
calls `GET /api/auth/me` to verify it and load the user. This is what keeps you
logged in across page refreshes. `login` calls the API, stores the returned
token, and sets the user in state; `logout` clears both.

`useAuth()` is a **custom hook** that any component calls to read `user` or
trigger `login`/`logout`. It throws if used outside the provider — a guardrail
against misuse.

**Hooks, state, and why a component "re-runs."** A React component function runs
every time it needs to render. That raises a puzzle: if the function runs from
scratch each time, how does it *remember* anything between renders — like the
current user, or a counter? The answer is **hooks**. `useState` gives a component
a piece of memory that survives re-renders: `const [user, setUser] = useState(null)`
hands back the current value and a setter, and calling `setUser(...)` does two
things — it stores the new value *and* tells React "this component's state
changed, please re-render it." That's the loop that drives the whole UI: event
happens → call a setter → React re-runs the component → it returns new markup
reflecting the new state → React reconciles it onto the screen. State changes are
the *only* sanctioned way to update what's displayed; you never poke the DOM
yourself.

**`useEffect` and the dependency array, precisely.** Rendering is supposed to be
pure — take state, return markup, no side effects. But real apps must *do* things:
fetch data, read `localStorage`, set timers. `useEffect` is the sanctioned escape
hatch for those **side effects**, and its second argument — the **dependency
array** — controls *when* it runs. `[]` (empty) means "run once, right after the
component first mounts, and never again" — perfect for one-time startup work like
checking for a saved token. `[jobId]` would mean "run on mount *and* every time
`jobId` changes." Omitting the array entirely means "run after *every* render,"
which is usually a bug (and a classic cause of infinite fetch loops). Getting the
dependency array right — listing exactly the values the effect reads — is one of
the trickier parts of React, and the source of many "why is this fetching over
and over" puzzles.

**A custom hook is just a function that uses other hooks.** `useAuth()` isn't
magic; it's a plain function that internally calls React's `useContext` to read
the `AuthContext` value and hands it back. Wrapping that in a named
`useAuth()` does two nice things: it gives every component a clean,
self-documenting way to get auth (`const { user, login } = useAuth()`), and it's
the natural place for the guardrail — if the context is missing (because someone
rendered a component outside `AuthProvider`), `useAuth` throws a clear error
instead of silently handing back `undefined` and causing a confusing crash later.
Custom hooks are how you package and reuse stateful logic across components.

### 21.3 `components/ProtectedRoute.tsx`

```tsx
const { user, loading } = useAuth();
if (loading) return <div>Loading…</div>;
if (!user) return <Navigate to="/login" replace />;
return <>{children}</>;
```

Simple but important: while auth is still being checked, show "Loading…"; if
there's no user, redirect to login; otherwise render the protected content. This
is the frontend half of authentication (the backend enforces it for real; this
just improves UX so users don't see broken protected pages).

---

## 22. Frontend, part 3: the API client & data fetching

### 22.1 `api/client.ts` — the single fetch wrapper

Every backend call goes through one function, `apiFetch`:

```ts
export async function apiFetch<T>(path, options = {}): Promise<T> {
  const headers = { "Content-Type": "application/json", ...options.headers };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = body.detail?.detail || body.detail || res.statusText;
    const code = body.detail?.code;
    if (res.status === 401) setToken(null);
    throw new ApiError(String(detail), res.status, code);
  }
  return body as T;
}
```

Why centralize this? **DRY and consistency.** Every request automatically:

- Gets the base URL prepended (configurable via `VITE_API_BASE_URL`).
- Attaches the JWT from `localStorage` (this is the frontend half of §7.2 — the
  token the backend's `get_current_user` will verify).
- Sends/parses JSON.
- Handles `204 No Content` (empty body).
- On error, extracts the backend's `{detail, code}` shape (see §6.3 — the
  frontend *depends on* that consistent error contract) and throws a typed
  `ApiError`.
- On `401`, clears the stored token (it's expired/invalid → effectively logs you
  out).

`<T>` is a **generic type parameter**: `apiFetch<Page<Device>>(...)` tells
TypeScript what shape to expect back, giving you autocomplete and type safety on
the result.

**Promises and `async`/`await`, since the whole client rests on them.** A network
request takes time, and JavaScript is single-threaded — it cannot freeze and wait
or the entire page would lock up. So `fetch` returns a **Promise**: an object
representing "a value that isn't here yet but will be." The `async`/`await`
syntax lets you write code that *reads* sequentially while *behaving*
non-blockingly: `const res = await fetch(...)` means "pause this function until
the response arrives, but let the rest of the app keep running meanwhile, then
resume here with the result." Marking a function `async` makes it return a
Promise automatically, which is why callers of `apiFetch` also `await` it. This
is the same cooperative-concurrency idea as the backend's event loop (§3.5),
living in the browser: one thread juggling many in-flight operations by parking
the ones that are waiting. Without it, every API call would freeze the UI until
the server answered.

**One wrapper means one place to change cross-cutting behavior.** Because *every*
request funnels through `apiFetch`, any policy that should apply to all calls is
written exactly once. Want to add a request-id header for tracing? Retry on
network blips? Redirect to login on any `401`? It's a one-line change here, not a
hunt-and-edit across forty call sites. This is the frontend mirror of the
backend's service layer: a single choke point where shared concerns live. The
`401 → clear token` handling is a good example — token expiry is detected in one
spot and turns into a clean logout everywhere, rather than each page
reinventing the check.

### 22.2 The per-resource API modules

`api/devices.ts`, `api/jobs.ts`, `api/auth.ts`, etc., each export an object of
small functions that call `apiFetch` with the right path/method, plus the
**TypeScript interfaces** describing the data (e.g. `interface Job { id: number;
status: JobStatus; ... }`). For example, `jobsApi`:

```ts
export const jobsApi = {
  list: (params) => apiFetch<Page<Job>>(`/api/jobs?${query}`),
  get: (id) => apiFetch<Job>(`/api/jobs/${id}`),
  create: (device_id, test_suite_id) => apiFetch<Job>("/api/jobs", { method: "POST", body: JSON.stringify({device_id, test_suite_id}) }),
  results: (id) => apiFetch<TestResult[]>(`/api/jobs/${id}/results`),
  cancel: (id) => apiFetch<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),
};
```

These TypeScript interfaces **mirror the backend's Pydantic schemas**. That
mirroring is the contract: backend and frontend agree on the JSON shape. (If they
drift, TypeScript catches it at build time — which is why CI runs `npm run
build`.)

### 22.3 TanStack Query — the polling magic

Components don't call `jobsApi` directly in a raw way; they use **`useQuery`**,
which wraps a fetch with caching, loading/error states, and re-fetching. The
star feature is in `JobDetailPage.tsx`:

```tsx
const ACTIVE = new Set(["queued", "running"]);

const job = useQuery({
  queryKey: ["job", jobId],
  queryFn: () => jobsApi.get(jobId),
  refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 1500 : false),
});
```

- `queryKey: ["job", jobId]` — a cache key. Query caches results by key, so
  navigating away and back is instant.
- `queryFn` — how to fetch.
- **`refetchInterval`** — *this is the polling*. It returns `1500` (re-fetch
  every 1.5 seconds) **while** the job status is `queued`/`running`, and `false`
  (stop polling) once it reaches a terminal status. This is the frontend side of
  the async story (§2): the backend runs the job in the background, and the UI
  keeps asking "done yet?" until it is — then automatically stops. The user sees
  the status flip from "queued" → "running" → "passed" without refreshing.

`q.state.data` is the latest job object. The results query polls on the same
condition. This declarative, self-stopping polling is exactly why TanStack Query
was chosen over hand-rolled `setInterval` code.

**What TanStack Query does that raw `fetch` doesn't.** You *could* fetch in a
`useEffect` and store the result in `useState`, but you'd quickly re-implement a
pile of fiddly concerns: tracking loading and error states, caching so revisiting
a page doesn't re-fetch from scratch, de-duplicating identical requests,
refetching stale data, and cleaning up timers. **`useQuery`** packages all of
that. You give it a `queryKey` (a cache identity) and a `queryFn` (how to fetch),
and it hands back `{ data, isLoading, isError }` while managing the cache behind
the scenes. Because the cache is keyed, two components asking for
`["job", 42]` share one fetch and one cached result, and navigating away and back
shows the cached data instantly while quietly refetching for freshness. It turns
data-fetching from imperative plumbing into a declarative "here's what I want and
how to get it."

**Why `refetchInterval` as a function is the elegant part.** Hand-rolled polling
with `setInterval` forces you to manually start the timer when a job begins and
— the part everyone forgets — *clear it* when the job finishes or the component
unmounts, or you leak timers that hammer the server forever. Here, polling is
expressed **declaratively** as a function of the data: "if the job's status is
`queued` or `running`, refetch in 1500ms; otherwise return `false` to stop."
TanStack Query evaluates this after every fetch, so the polling *automatically
stops itself* the instant the job reaches a terminal state — no manual cleanup, no
leaked intervals. This is the front-end completion of the asynchronous story: the
backend does the work off to the side (§15), and the UI politely asks "done yet?"
every 1.5 seconds until the answer is yes, then goes quiet. The user watches the
status badge flip `queued → running → passed` in near real time without ever
touching the refresh button.

### 22.4 Keeping the cache fresh after a write (`invalidateQueries`)

Caching reads is wonderful until you *change* something — then the cache is stale
and the screen shows old data. This project handles that with TanStack Query's
**`invalidateQueries`**. Look at the real "run a job" handler on
`DeviceDetailPage`:

```tsx
const qc = useQueryClient();

const runJob = async () => {
  if (!suiteId) return;
  const job = await jobsApi.create(deviceId, Number(suiteId));
  qc.invalidateQueries({ queryKey: ["jobs-for-device", deviceId] });
  navigate(`/jobs/${job.id}`);
};
```

The flow is: perform the write (`jobsApi.create` POSTs a new job), then tell the
query cache that anything stored under the key `["jobs-for-device", deviceId]` is
now **stale**. `invalidateQueries` doesn't delete the data or block — it marks
those cached entries as out of date so TanStack Query refetches them the next time
they're observed (here, when you return to the device page, its "recent jobs" list
re-fetches and shows the job you just created). `TestSuiteDetailPage` does the same
thing after editing a suite, invalidating `["suite", sid]` so the edited suite
reloads.

**Why invalidation instead of manually updating the cache.** You *could* hand-edit
the cached array to splice in the new job, which is faster (no refetch) but risky:
your client-side guess about the new state can drift from what the server actually
stored (the server assigns the id, timestamps, default fields, and may apply rules
you didn't replicate). Invalidating and refetching trades a tiny bit of extra
network for *guaranteed* correctness — the screen always reflects the real
server state, which is the single source of truth (§3.3). For an app where
correctness matters more than shaving a request, "write, then invalidate, then let
it refetch" is the simple, robust default. (The fancier alternative, *optimistic
updates*, edits the cache immediately and rolls back on error — more responsive but
more code and more ways to be subtly wrong; this project sensibly skips it.)

**Why the query key structure matters here.** Notice the keys are *structured*
arrays like `["jobs-for-device", deviceId]`, not bare strings. That structure is
what makes targeted invalidation possible: invalidating `["jobs-for-device", 42]`
refreshes device 42's job list *without* disturbing device 99's cached list or the
unrelated `["suites"]` cache. Designing query keys to mirror your data's identity
(resource name + id) is what lets you invalidate exactly the right slice after a
write and nothing more — the same precision the cache uses to *share* a fetch
between components asking for the identical key.

---

## 23. Frontend, part 4: pages & components

### 23.1 Components (reusable pieces) in `components/`

- **`Layout.tsx`** — the shell around every authenticated page: the nav
  sidebar/header, links, the logout button, and an `<Outlet />` where the
  current page renders. Rendered once; the inner page swaps as you navigate.
- **`ProtectedRoute.tsx`** — covered in §21.3.
- **`StatusBadge.tsx`** — takes a `status` string and renders a colored pill
  (green for passed, red for failed, etc.). A tiny **presentational component**:
  pure input → output, no logic. Reused on jobs, results, devices.
- **`LogViewer.tsx`** — renders the job's log text in a monospaced, scrollable
  block.
- **`TestResultTable.tsx`** — renders the array of test results as a table
  (name, status badge, expected vs. actual, duration). Given `results`, it draws
  rows.

This is **component decomposition**: build small, focused, reusable pieces, then
compose them into pages. `StatusBadge` is used in many places; writing it once
keeps the UI consistent.

**Presentational versus container components.** A useful way to categorize the
pieces: `StatusBadge`, `LogViewer`, and `TestResultTable` are **presentational**
— they take data as props and render markup, with no knowledge of where the data
came from. They're pure, trivially reusable, and easy to reason about because
given the same props they always draw the same thing. Pages like `JobDetailPage`
are **container** components — they do the fetching (`useQuery`), hold the state,
and then *hand data down* to presentational children. This split is a recurring
front-end design principle: keep the components that *get* data separate from the
components that *show* data. A `StatusBadge` that fetched its own status would be
useless anywhere else; one that just takes `status="passed"` and renders a green
pill works on the jobs list, the job detail, the results table, and the device
page alike. Writing it once and reusing it everywhere is also what guarantees a
passed job looks identical no matter where it appears.

### 23.2 Pages in `pages/`

Each page is a component mapped to a route:

- **`LoginPage` / `RegisterPage`** — forms that call `useAuth().login/register`,
  then navigate to the dashboard.
- **`DashboardPage`** — fetches `/api/dashboard/summary` with `useQuery` and
  shows metric cards (device count, pass rate, recent jobs).
- **`DevicesPage`** — lists devices with search/pagination; links to detail and
  "new device."
- **`DeviceFormPage`** — one form reused for both *create* (`/devices/new`) and
  *edit* (`/devices/:id/edit`); it checks for an `id` param to decide which.
- **`DeviceDetailPage`** — shows one device; offers "Run a test suite" (which
  POSTs a job and navigates to the job page).
- **`TestSuitesPage` / `TestSuiteDetailPage` / `TestSuiteFormPage`** — list,
  view (with nested test cases), and create suites.
- **`JobsPage`** — paginated job history with status badges.
- **`JobDetailPage`** — the polling page (§22.3): live status, results table,
  logs, and the **download buttons**.

The download logic in `JobDetailPage` is worth one note:

```tsx
const downloadCsv = () => {
  const token = localStorage.getItem("auth_token");
  fetch(`${API_BASE}/api/reports/jobs/${jobId}.csv`, { headers: { Authorization: `Bearer ${token}` } })
    .then(r => r.text())
    .then(text => {
      const blob = new Blob([text], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `job-${jobId}.csv`; a.click();
      URL.revokeObjectURL(url);
    });
};
```

Because the CSV endpoint needs the auth header, you can't just point a plain
link at it — you `fetch` it (with the token), wrap the text in a `Blob` (an
in-memory file), make a temporary object URL, and programmatically "click" a
hidden download link. A common browser technique for **authenticated file
downloads**.

---

## 24. Infrastructure: Docker, Compose, CI

### 24.1 Why Docker

"It works on my machine" is the classic failure. **Docker** packages an app
*and its entire environment* (OS libraries, Python/Node version, dependencies)
into an **image**; a running instance of an image is a **container**. The
container runs the same everywhere — your laptop, a teammate's, CI, production.

Each `Dockerfile` (one in `backend/`, one in `frontend/`) is the recipe: start
from a base image (e.g. `python:3.12-slim`), copy in the code, install
dependencies, set the start command.

**Container versus virtual machine — the distinction that makes Docker fast.** A
**virtual machine** virtualizes *hardware*: it runs a complete second operating
system (its own kernel, boot process, the works) on top of yours, which is heavy
— gigabytes of disk, a minute to boot. A **container** virtualizes only the
*process*: it shares the host's kernel but gets its own isolated view of the
filesystem, network, and process list. That's why containers are measured in
megabytes and start in milliseconds — there's no second OS to boot, just an
isolated process with its own bundled libraries. The isolation is enough that the
app *thinks* it has its own machine (its own `/app`, its own installed packages)
while actually being a lightweight process on yours. This is what makes
"identical environment everywhere" cheap enough to use for every service.

**Image versus container, and why layers matter.** An **image** is a frozen,
read-only template — the recipe's output, a snapshot of a filesystem with your
code and dependencies baked in. A **container** is a running, writable instance of
an image; you can start many containers from one image (which is exactly how the
`backend` and `worker` services share a single image). Images are built in
**layers**, one per Dockerfile instruction, and Docker *caches* each layer. This
is why a well-written Dockerfile copies the dependency manifest and installs
dependencies *before* copying the application code: dependencies change rarely, so
their (slow) layer stays cached across builds, and only the fast "copy my code"
layer rebuilds when you edit a source file. Order your Dockerfile from
least-frequently-changing to most, and your builds stay fast.

### 24.2 `docker-compose.yml` — running the whole system

Compose defines and connects all five services so one command
(`docker compose up`) launches everything:

- **`postgres`** — the database, using the official `postgres:16-alpine` image,
  with a **named volume** `pgdata` so data **persists** across restarts, and a
  **healthcheck** (`pg_isready`) so other services can wait until it's actually
  ready.
- **`redis`** — `redis:7-alpine`, the queue broker, also with a healthcheck.
- **`backend`** — built from `./backend`. Its start command is the key sequence:
  ```
  alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
  i.e. **migrate the DB, seed it, then start the API.** `depends_on` with
  `condition: service_healthy` means it waits for Postgres and Redis to be ready
  first. Its `DATABASE_URL`/`REDIS_URL` point at the `postgres`/`redis` services
  by name (Compose provides DNS between containers).
- **`worker`** — built from the *same* backend image but with a different
  command: `python -m app.workers.worker`. **Same code, different entry point** —
  the worker and API share everything but run different processes. This is why
  the worker can call the same services/models.
- **`frontend`** — runs the Vite dev server on port 5173, with
  `VITE_API_BASE_URL` pointing at the backend.

The `volumes: - ./backend:/app` **bind mounts** your source into the container so
code changes hot-reload during development without rebuilding the image.

Notice how Compose is essentially §2's architecture diagram written as
configuration. Reading this file *is* understanding the system topology.

**Three Compose concepts worth naming explicitly.** First, **service discovery by
name**: inside the Compose network, each service is reachable by its service name
as a hostname — the backend connects to the database at `postgres:5432`, not an IP
address, because Compose runs a little DNS that resolves `postgres` to whichever
container is currently running that service. This is why `DATABASE_URL` can be
written once and never change as containers come and go. Second, **named volumes
for persistence**: containers are *ephemeral* — delete one and everything written
inside it vanishes. That's fine for a stateless API but catastrophic for a
database, so `pgdata` is a **volume**, a storage area that lives *outside* any
container's lifecycle, so your data survives `docker compose down` and restarts.
Third, **healthchecks and `depends_on`**: starting the backend before Postgres is
accepting connections would crash it, so `depends_on: condition:
service_healthy` makes the backend *wait* until Postgres's `pg_isready`
healthcheck passes. Startup order in a multi-service system is a real problem, and
healthchecks are how you solve it declaratively instead of with brittle
"sleep 10 and hope" hacks.

### 24.3 CI with GitHub Actions

`.github/workflows/ci.yml` runs automatically on every push/PR. It:

1. Spins up Postgres + Redis **service containers**.
2. Installs backend deps, runs `alembic upgrade head` (proving migrations
   apply), runs `pytest` (proving the backend works) — against *real* Postgres,
   not SQLite, catching DB-specific issues.
3. Installs frontend deps and runs `npm run build` (which type-checks the whole
   TypeScript tree).

**CI (Continuous Integration)** means every change is automatically verified
before it's merged. If a test breaks or types don't compile, you find out in
minutes, not in production. This is a safety net that lets teams move fast
without breaking things.

### 24.4 The cold-start boot sequence, step by step

It's worth tracing exactly what happens, in order, when you run
`docker compose up` on a fresh machine — because the ordering is deliberate and
several earlier concepts (healthchecks, migrations, idempotent seeding, service
DNS) all come together here.

1. **Compose builds/pulls images.** It pulls `postgres:16-alpine` and
   `redis:7-alpine`, and builds the `backend` and `frontend` images from their
   Dockerfiles (running through the cached layers — §24.1). One backend image is
   built and reused for *both* the `backend` and `worker` services.
2. **The network and volumes come up.** Compose creates a private virtual network
   (with the name-based DNS) and the `pgdata` named volume if it doesn't already
   exist.
3. **Postgres and Redis start first.** They have no `depends_on`, so they boot
   immediately. Compose begins running their **healthchecks** (`pg_isready`,
   a Redis ping) on a loop, marking each service "healthy" only once it actually
   answers — not merely once the process started.
4. **The backend waits, then runs its start command.** Because the backend
   declares `depends_on: condition: service_healthy` for both, Compose holds it
   back until Postgres *and* Redis report healthy. Then the backend container's
   command runs its three-part sequence in order:
   - `alembic upgrade head` — applies every migration to bring the (initially
     empty) database schema up to the latest revision. On a fresh volume this
     creates all the tables; on an existing volume it applies only new migrations.
   - `python -m app.seed` — runs the **idempotent** seed (§17). First boot: no
     users exist, so it populates demo data. Every later boot: users exist, so it
     exits in milliseconds. This is why automatic seeding on every start is safe.
   - `uvicorn app.main:app ...` — finally starts the actual web server, which
     opens the socket on port 8000 and begins accepting requests.
5. **The worker starts in parallel.** It shares the backend's `depends_on`, so it
   also waits for healthy Postgres/Redis, then runs `python -m app.workers.worker`
   — the RQ worker loop that blocks waiting for jobs on the Redis queue. Note it
   does *not* run migrations or seed; that's the backend's job, and the worker
   simply assumes the schema is ready (which the dependency ordering guarantees in
   practice).
6. **The frontend starts.** The Vite dev server comes up on port 5173, configured
   via `VITE_API_BASE_URL` to send its API calls to the backend.
7. **Steady state.** You now have five healthy containers: browser → frontend →
   backend → (Postgres + Redis) and worker → (Redis + Postgres). The system is the
   §2 diagram, alive.

The single most important thing to notice is that the ordering problem — "don't
start X until Y is truly ready" — is solved *declaratively* by healthchecks plus
`depends_on`, and the "schema must exist before the app uses it" problem is solved
by putting `alembic upgrade head` first in the start command. Neither relies on
guessing how long something takes. That's the difference between a robust startup
and a flaky "works on my machine" one.

> **A subtle race to be aware of.** Because the worker doesn't itself wait for the
> backend to finish migrating, a worker *could* in theory start before the backend
> has run `alembic upgrade head`. In this project it's harmless because the worker
> blocks idle on an empty queue until the backend (which also enqueues) is up and
> jobs exist, by which time migrations have long since run. In a stricter
> production setup you'd run migrations as a dedicated one-shot step that *both*
> the backend and worker depend on, so the schema is guaranteed ready before
> either starts. Recognizing this is the kind of ordering nuance that separates a
> demo from a production deployment.

---

## 25. Five end-to-end walkthroughs

Tracing real flows ties every layer together. Follow the data. If you can narrate
each of these from memory — naming the page, the API module, the route, the
dependency, the service, and the SQL — you understand the system.

### 25.1 Logging in

```mermaid
sequenceDiagram
    participant B as Browser (LoginPage)
    participant API as FastAPI
    participant DB as Postgres
    B->>API: POST /api/auth/login {email, password}
    API->>API: schema validates LoginRequest
    API->>DB: SELECT user WHERE email=...
    API->>API: verify_password(plain, hashed) [bcrypt]
    API->>API: create_access_token(user.id, role)
    API-->>B: 200 {access_token, user}
    B->>B: setToken(token) in localStorage; setUser
```

1. `LoginPage` calls `useAuth().login(email, password)` → `authApi.login` →
   `apiFetch("POST /api/auth/login")`.
2. FastAPI parses the body into `LoginRequest` (validating it's a real email).
3. `auth.login` route → `auth_service.authenticate` loads the user by email and
   `verify_password`s the bcrypt hash. Wrong creds → `UnauthorizedError` (401).
4. `issue_token` builds a JWT with the user id + role.
5. The route returns `TokenResponse`. The frontend stores the token and sets the
   user. Now every future `apiFetch` carries `Authorization: Bearer <token>`.

### 25.2 Listing devices (an authenticated, paginated read)

1. `DevicesPage` `useQuery` → `devicesApi.list({limit, offset, search})` →
   `apiFetch("GET /api/devices?limit=20&offset=0&search=core")`. The token is
   attached automatically.
2. `get_current_user` dependency decodes the token, loads the user (401 if bad).
   Any role may list.
3. The route reads/validates the query params (`limit` bounded 1–100), calls
   `device_service.list_devices`.
4. The service builds a filtered, ordered, paginated `SELECT` plus a `COUNT`,
   returns `(items, total)`.
5. The route wraps them in `Page[DeviceOut]`; FastAPI serializes to JSON.
6. TanStack Query caches the result; the page renders a table.

### 25.3 Running a test suite (the full async story)

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as FastAPI
    participant DB as Postgres
    participant R as Redis
    participant W as Worker
    B->>API: POST /api/jobs {device_id, test_suite_id}
    API->>API: require_engineer_or_admin
    API->>DB: validate device & suite exist; INSERT job (queued)
    API->>R: enqueue run_job(job_id)
    API-->>B: 201 {job: queued}
    B->>API: GET /api/jobs/{id} (poll every 1.5s)
    R->>W: deliver run_job(job_id)
    W->>DB: status=running, started_at
    loop each enabled case (by order_index)
        W->>W: _run_case via MockDeviceClient
        W->>DB: INSERT test_result
    end
    W->>DB: status=passed/failed/partial/error, summary, logs, duration
    B->>API: GET /api/jobs/{id} → now "passed"
    B->>B: stop polling, show results + logs
```

1. **Trigger:** `DeviceDetailPage` POSTs to `/api/jobs`. `require_engineer_or_admin`
   gates it (viewers can't). `job_service.create_job` validates the device/suite
   and inserts a `queued` job. The route calls `enqueue_job(job.id)` (push to
   Redis) and returns `201` *immediately*.
2. **Poll:** The browser navigates to `JobDetailPage`, whose `useQuery` polls
   `GET /api/jobs/{id}` every 1.5s while status is `queued`/`running`.
3. **Execute:** The separate `worker` process pulls `run_job(job_id)` off the
   queue. `tasks.run_job` opens a session, skips canceled jobs, and calls
   `runner.execute_job`, which marks the job `running`, runs each enabled case in
   order against the `MockDeviceClient`, writes a `TestResult` per case, and
   computes the final status/summary/logs.
4. **Finish:** Next poll returns `passed`/`partial`/`failed`; the page stops
   polling and shows the results table, logs, and download buttons. Downloads hit
   `/api/reports/jobs/{id}.json|.csv`.

That single flow uses *every* concept in this document: auth, RBAC, schemas,
services, the DB, the queue, the worker, the mock integration, polling, and
reporting.

### 25.4 Creating a device (an authorized write)

This flow is short but exercises the *write* path and authorization, which the
read flows don't.

```mermaid
sequenceDiagram
    participant B as Browser (DeviceFormPage)
    participant API as FastAPI
    participant DB as Postgres
    B->>API: POST /api/devices {hostname, management_ip, vendor, ...}
    API->>API: parse + validate body into DeviceCreate (422 if bad)
    API->>API: require_admin (403 if not admin)
    API->>DB: INSERT device; commit; refresh
    API-->>B: 201 DeviceOut
    B->>B: navigate to the new device's detail page
```

1. **Form submit:** `DeviceFormPage` collects the fields and calls
   `devicesApi.create(payload)` → `apiFetch("POST /api/devices", { body })`. The
   token rides along automatically.
2. **Validate:** FastAPI parses the JSON body into a `DeviceCreate` schema. An
   empty hostname or a non-enum vendor is rejected with `422` *before* the route
   body runs — the boundary validation from §10 in action.
3. **Authorize:** the `require_admin` dependency runs the auth chain (§12). A
   logged-in viewer or engineer gets `403`; only an admin proceeds. Notice the
   distinction from listing devices, which any role can do — *reading* is open to
   all authenticated users, *writing* is admin-only, and the only difference is
   which dependency the route declares.
4. **Persist:** `device_service.create_device` spreads the validated schema into
   a `Device(**payload.model_dump())`, then `add → commit → refresh` so the
   returned object has its DB-assigned `id` and timestamps (§11.1).
5. **Respond + redirect:** the route returns `DeviceOut` with `status_code=201`,
   and the frontend navigates to the new device's detail page. TanStack Query's
   cache for the device list is now stale, which is why the list refetches when
   you return to it.

The whole point of walking this is to see that a *write* differs from a *read* in
exactly two ways — it validates a request body and it requires a stronger role —
and both are expressed declaratively in the route signature.

### 25.5 Canceling a running job (a state-machine guard and a race)

```mermaid
sequenceDiagram
    participant B as Browser (JobDetailPage)
    participant API as FastAPI
    participant DB as Postgres
    participant W as Worker
    B->>API: POST /api/jobs/{id}/cancel
    API->>API: require_engineer_or_admin
    API->>DB: load job; if queued/running -> status=canceled; commit
    API-->>B: 200 Job (canceled)
    Note over W: when the worker later picks up the job...
    W->>DB: load job; status == canceled? -> skip, do nothing
```

1. **Request:** the user clicks "Cancel" on `JobDetailPage`; `jobsApi.cancel(id)`
   POSTs to `/api/jobs/{id}/cancel`, gated by `require_engineer_or_admin`.
2. **Guarded transition:** `job_service.cancel_job` loads the job and flips it to
   `canceled` *only if* it's still `queued` or `running` (§11.4). If the job
   already finished, it does nothing and returns the job unchanged — the
   idempotent, state-machine-respecting behavior. You can't drag a job out of a
   terminal state.
3. **The race, resolved:** there are two actors here — the API marking the job
   canceled, and the worker that may be about to run it. The producer sets
   *intent* (`status=canceled`); the consumer *honors* it. When the worker pulls
   the job off the queue, the very first thing `tasks.run_job` does (after opening
   its session) is re-check the status and `return` immediately if it's canceled
   (§15.3). So a job canceled while sitting in the queue is simply skipped, never
   run. This is the producer/consumer cancellation pattern: you can't reach into
   another process and stop it mid-flight, so instead you record the decision in
   the shared database and let the other side check it at the right moment.
4. **UI:** the cancel response flips the status badge to `canceled`, and because
   `canceled` is terminal, `refetchInterval` returns `false` and the page stops
   polling.

This flow is worth internalizing because "signal intent through shared state, act
on it at a safe checkpoint" is how cancellation, feature flags, and many
distributed coordination problems are solved when you can't directly interrupt
another process.

---

## 26. How to build this whole thing from scratch

Here's the order I'd build it in, and *why* that order. Building back-to-front
(data → logic → API → UI) means each layer rests on a tested foundation.

1. **Scaffold + config.** Create the repo, `backend/` with a virtualenv,
   `requirements.txt`, and `app/core/config.py` (settings from env). Decide your
   secrets come from the environment from day one.
2. **Database foundation.** Add `db/base.py` (Base + TimestampMixin) and
   `db/session.py` (engine, SessionLocal, `get_db`). Pick Postgres; use SQLite
   for tests.
3. **Models.** Write the ORM classes in dependency order: `User`, `Device`,
   `TestSuite`+`TestCase` (with the relationship), `Job`, `TestResult`. Decide
   enums, indexes, foreign keys, and CASCADE vs SET NULL deliberately.
4. **Migrations.** Set up Alembic (`env.py` pointing at `settings` + `Base.metadata`)
   and generate the initial migration. Now your schema is reproducible.
5. **Security.** `core/security.py`: bcrypt hashing + JWT create/decode. This
   unblocks auth.
6. **Schemas.** For each resource, write `Base`/`Create`/`Update`/`Out` Pydantic
   models, plus the generic `Page[T]`. This defines your API contract.
7. **Services.** Implement the business logic per resource (CRUD, listing with
   pagination/search, auth, dashboard aggregates, reports). Keep them
   HTTP-agnostic. Add the typed errors in `core/errors.py`.
8. **Dependencies.** `api/deps.py`: `get_current_user`, `require_roles`. Wire
   auth/RBAC as injectable dependencies.
9. **Routes.** Thin endpoints per resource that validate input, enforce auth,
   call services, and return schemas. Mount them in `main.py` with CORS.
10. **Workers.** Add `queue.py` (enqueue + `SYNC_JOBS` seam), `worker.py` (the
    RQ process), `tasks.py` (safe entry), and `runner.py` (execute a suite). Add
    the `MockDeviceClient`. Now jobs run asynchronously.
11. **Seed.** Idempotent demo data so the app isn't empty.
12. **Tests.** `conftest.py` (SQLite + `SYNC_JOBS=1` + per-test DB reset +
    client fixture), then unit tests per resource and the end-to-end job test.
13. **Frontend.** Vite + React + TS. Build `api/client.ts` first (the fetch
    wrapper), then per-resource API modules + interfaces, then `AuthContext`,
    routing with `ProtectedRoute`, the shared `Layout`, reusable components, and
    finally the pages. Use TanStack Query for fetching, and `refetchInterval` for
    job polling.
14. **Infra.** `Dockerfile`s, `docker-compose.yml` (5 services, healthchecks,
    volumes), and a GitHub Actions CI workflow (Postgres+Redis services,
    migrate+pytest, frontend build).

If you can write this list from memory and explain *why* each step depends on the
ones before it, you understand the architecture.

**A recipe for adding one new resource end to end.** Building the whole app is one
thing; the more common real-world task is *adding a feature* to an existing
codebase. Because this project is consistently layered, adding a brand-new
resource is a predictable, almost mechanical walk through the same files every
time. Suppose you wanted to add a first-class `Tag` resource (replacing the
comma-string simplification). You'd touch these files, in this order, and the list
*is* the architecture in miniature:

1. **Model** (`models/tag.py`) — define the `Tag` ORM class (and, for a real
   many-to-many, a `device_tags` association table). Decide the columns, the
   unique constraint on the tag name, indexes, and the relationship to `Device`.
2. **Migration** (`alembic revision --autogenerate`) — generate and *review* the
   migration that creates the new table(s), then apply it. The schema now matches
   the model.
3. **Schemas** (`schemas/tag.py`) — write `TagCreate`, `TagUpdate`, and `TagOut`,
   plus reuse the generic `Page[TagOut]` for listing. This defines the JSON
   contract.
4. **Service** (`services/tag_service.py`) — implement the business logic: create
   (rejecting duplicate names), list with pagination/search, update, delete. Keep
   it HTTP-agnostic and add any new typed errors to `core/errors.py`.
5. **Routes** (`api/routes/tags.py`) — thin endpoints that validate input, declare
   the right auth dependency (e.g. `require_admin` for writes), call the service,
   and return the schemas. Register the router in `main.py`.
6. **Tests** (`tests/test_tags.py`) — unit-test the service and route behavior
   (create, duplicate rejection, list, auth enforcement) using the existing
   `client` and DB fixtures.
7. **Frontend API module** (`api/tags.ts`) — small typed functions wrapping
   `apiFetch` for each endpoint, plus a `Tag` interface.
8. **Frontend pages/components** — a list page and a form, using `useQuery` to
   read and `invalidateQueries` to refresh after writes, wired into the router and
   nav.

Notice this is the *same dependency order* as building the whole app, just scoped
to one resource — model before schema before service before route before UI. If
you internalize this recipe, you can extend the system confidently, and you can
also *read* any existing resource (devices, jobs, suites) by following the same
chain of files. That predictability — knowing exactly which files a feature lives
in before you even open them — is the practical reward of a disciplined layered
architecture.

**Why back-to-front, and why this is the order that minimizes rework.** The
guiding principle is that you build on *settled* ground: each step should depend
only on things already built and tested, never on things you haven't written yet.
Start at the foundation (data) because everything ultimately manipulates data, and
work outward toward the user. Config comes first because literally everything
reads settings — the database URL, the JWT secret, the CORS origins — so it's the
one thing with no dependencies of its own. The database layer and models come next
because they define the *shape of your domain*; you can't write a service that
lists devices before a `Device` exists. Migrations follow models because a
migration is a snapshot of the models. Security (hashing/JWT) is a small, isolated
utility with no dependencies, and it *unblocks* auth, so it slots in before the
services that need it. Schemas before services because services return data shaped
by schemas. Services before routes because routes are thin wrappers that *call*
services — build the engine before the steering wheel. Dependencies (auth wiring)
before routes because routes declare them. Workers after services because the
runner reuses the same models and session machinery. Tests after the backend is
functional so you have something to test (though in practice you'd write tests
alongside each layer). And the frontend comes last because it consumes a
*finished, stable* API — building UI against a moving API target wastes effort.
Infra wraps it all once the pieces exist to containerize.

**The deeper lesson about dependency order.** Notice that this build order is
exactly a **topological sort** of the dependency graph: A must come before B
whenever B depends on A. That's not a coincidence — it's the same reasoning the
database uses when you create tables (you can't add a foreign key to a table that
doesn't exist yet), the same reasoning Alembic uses to order migrations, and the
same reasoning Docker Compose uses with `depends_on`. Whenever you face "in what
order should I do these interdependent things," the answer is almost always
"draw the dependency arrows, then do them in an order where every arrow points
backward to something already done." Internalizing that single idea makes you
better at sequencing not just code, but projects, deployments, and debugging.

---

## 27. Glossary

Each term gets a short definition plus where it shows up in this project, so you
can look things up without leaving the document.

- **ACID** — the four guarantees a relational database gives transactions:
  **A**tomicity (all-or-nothing), **C**onsistency (constraints always hold),
  **I**solation (concurrent transactions don't corrupt each other), **D**urability
  (committed data survives a crash). Postgres provides these; it's why a database
  beats storing data in flat files.
- **ASGI** — Asynchronous Server Gateway Interface, the standard contract between
  an async Python web app (FastAPI) and the server that runs it (uvicorn). Because
  both speak ASGI, you can swap servers without changing app code.
- **Alembic revision** — one migration file, identified by a hash and linked to
  its parent revision, forming an ordered chain. `upgrade head` applies every
  revision from the current point to the newest.
- **back_populates** — the SQLAlchemy keyword that links the two sides of a
  relationship (`TestSuite.test_cases` ↔ `TestCase.test_suite`) so updating one in
  memory keeps the other consistent.
- **Aggregate query** — SQL that returns a computed value (`COUNT`, `SUM`, `AVG`)
  instead of rows. The dashboard uses these to count devices and jobs in the
  database rather than loading rows into Python and counting.
- **Base64 / Base64URL** — a way to represent arbitrary bytes as plain text using
  a 64-character alphabet. It's *encoding, not encryption* — anyone can decode it.
  A JWT's header and payload are Base64URL-encoded, which is why you must never put
  secrets in a token's payload.
- **Bearer token** — an auth scheme where possessing the token is enough to use
  it ("the bearer"). Requests carry `Authorization: Bearer <jwt>`; the server
  trusts any caller presenting a valid token, which is why tokens must be kept
  secret and expire quickly.
- **B-tree** — the balanced, sorted tree structure most database indexes use. It
  keeps data ordered so a lookup takes O(log n) steps instead of scanning every
  row. The "shape" behind why an index makes searches fast.
- **Atomicity** — the property that a group of database changes either all commit
  or all roll back. `create_suite` relies on it so a suite and its cases are
  created together or not at all.
- **Bind mount / volume** — Docker storage mechanisms. A bind mount maps a host
  folder into a container (used to hot-reload source code in dev); a named volume
  is container-independent storage (used so Postgres data survives restarts).
- **bcrypt** — a deliberately slow, salted password-hashing algorithm with a
  tunable cost factor. Slowness is a feature: it makes brute-forcing stolen hashes
  impractical. Used in `core/security.py`.
- **Claims** — the facts encoded inside a JWT's payload (e.g. `sub` = subject/user
  id, `exp` = expiry, plus a custom `role`). The server reads claims to learn who
  you are without a database lookup.
- **Closure** — a function that "remembers" variables from the scope where it was
  created. `require_roles` returns an inner function that closes over the allowed
  `roles`, which is how one factory produces many configured role-checkers.
- **Connection pool** — a set of pre-opened database connections kept ready and
  reused across requests, so you pay the expensive connect-and-authenticate cost
  once at startup instead of on every query. SQLAlchemy's engine manages it.
- **CORS** — Cross-Origin Resource Sharing, the browser mechanism that lets a
  server opt in to being called by JavaScript from a different origin. Without the
  backend's `CORSMiddleware` allowlisting the frontend's origin, the browser would
  block the requests.
- **CRUD** — Create, Read, Update, Delete: the four basic operations on a
  resource, mapped to POST/GET/PATCH/DELETE. `device_service` is the canonical
  example.
- **Cascade delete-orphan** — the SQLAlchemy relationship option that deletes a
  child when its parent is deleted *or* when it's removed from the parent's
  collection. Used so test cases never outlive their suite.
- **Cursor / keyset pagination** — paging by "give me rows *after* this key"
  instead of `OFFSET n`. It stays fast at any depth because it uses the index
  directly; the offset approach slows down on deep pages. Listed as a future
  improvement here.
- **DDL / DML** — the two halves of SQL. **DDL** (Data Definition Language)
  defines *structure*: `CREATE`/`ALTER`/`DROP TABLE` (what Alembic migrations
  generate). **DML** (Data Manipulation Language) works with *data*:
  `INSERT`/`SELECT`/`UPDATE`/`DELETE` (what the ORM generates).
- **Denormalization** — deliberately duplicating data to preserve history or speed
  reads, accepting some redundancy. `TestResult.test_case_name` copies the case
  name so the historical record stays accurate even if the case is later renamed.
- **DNS (in Compose)** — the name-resolution service Docker Compose runs so
  containers reach each other by *service name* (`postgres`, `redis`) instead of
  by IP. It's why connection URLs use those hostnames and never break on restart.
- **Docker image / layer** — an **image** is a read-only template (your code +
  dependencies + OS bits) from which containers are created. It's built in stacked
  **layers**, each cached, which is why ordering a Dockerfile least-changing first
  makes rebuilds fast.
- **Dependency Injection (DI)** — the pattern where a function declares what it
  needs and the framework supplies it (`Depends(...)`), rather than the function
  creating it. Enables testability (override the DB) and clean lifecycle handling.
- **Dependency (FastAPI)** — a function whose result FastAPI computes and injects
  into a route via `Depends`. `get_db`, `get_current_user`, and `require_roles` are
  the dependencies used here.
- **Mock** — a stand-in implementation used in place of a real one, exposing the
  same interface. `MockDeviceClient` mocks real network hardware so the app runs
  with no devices (§16).
- **DTO (Data Transfer Object)** — an object whose job is to cross a boundary (the
  API), distinct from the storage object. The Pydantic `*Out` schemas are DTOs;
  the SQLAlchemy models are the storage objects.
- **Eager loading / N+1** — N+1 is the performance bug where fetching N parents and
  touching a relationship fires one query per parent (N+1 total). Eager loading
  (`selectinload`) fetches all the children in one extra query instead.
- **Enum** — a type with a fixed set of named values (e.g. `JobStatus`,
  `UserRole`). Makes illegal states unrepresentable and is enforced by both the DB
  and Pydantic.
- **Endpoint** — one URL+method the API responds to (e.g. `GET /api/devices`),
  implemented by a route function. The set of all endpoints is the API surface.
- **Fixture (pytest)** — a reusable setup/teardown helper a test declares as a
  parameter. The `client` and DB-reset fixtures give every test a clean app and
  database (§19).
- **Event loop** — the mechanism (in uvicorn/ASGI) that lets one thread juggle
  thousands of connections by never blocking: while one request waits on I/O, the
  loop progresses others and returns when the wait is done. The "fast" in FastAPI.
- **FIFO** — First In, First Out: the ordering a queue gives — messages are
  processed in the order they arrived, like a checkout line. Redis-backed RQ
  processes jobs FIFO.
- **Flush vs. commit** — `flush` sends pending SQL to the database (so it assigns
  ids and runs constraints) *within* the current transaction, still reversible;
  `commit` makes it permanent. `create_suite` flushes to get the suite's id, then
  commits suite + cases together.
- **Foreign key** — a column that must point at an existing row's primary key in
  another table, enforcing referential integrity. `TestCase.test_suite_id` is one.
- **Generic** — a reusable type parameterized by another type, written once and
  specialized many times. `Page[T]` becomes `Page[DeviceOut]`, `Page[JobOut]`,
  etc., all sharing one pagination shape.
- **Hook (React)** — a function starting with `use` that lets a component tap into
  React features: `useState` (local state), `useEffect` (side effects),
  `useQuery`/`useContext` (data and shared values). Hooks must be called at the top
  level of a component, unconditionally.
- **GIL (Global Interpreter Lock)** — a CPython lock that prevents threads from
  running Python bytecode truly in parallel. It's part of why this project scales
  heavy work with *separate worker processes* rather than threads.
- **Healthcheck** — a command Compose runs periodically to test whether a service
  is actually ready (not just started). `depends_on: service_healthy` uses it to
  start the backend only after Postgres accepts connections.
- **HMAC** — a keyed hash that mixes a message with a secret key. A JWT's signature
  is an HMAC-SHA256 of its header+payload; only the server (which holds the key)
  can produce a valid one, so tampering is detectable.
- **Idempotent** — an operation that has the same effect run once or many times.
  The seed script (guarded by a "users exist?" check) and `cancel_job` are both
  idempotent.
- **Index** — an auxiliary B-tree structure that makes lookups on a column fast
  (logarithmic instead of a full scan), at the cost of disk and slightly slower
  writes. Applied to `hostname`, `management_ip`, and foreign keys.
- **Integration (code)** — code that talks to an external system (network devices
  here), isolated in its own folder so the rest of the app doesn't depend on the
  details of how that communication works.
- **JWT (JSON Web Token)** — a signed, self-contained, expiring token carrying
  claims (user id, role). The server verifies its signature with a secret instead
  of looking up a session, making auth stateless.
- **JSX / TSX** — the syntax extension that lets you write HTML-like markup inside
  JavaScript/TypeScript (`return <div>{name}</div>`). The build step compiles it to
  plain function calls that build the virtual DOM. `.tsx` is JSX in a TypeScript
  file.
- **Least privilege** — the security principle of granting every actor the minimum
  permissions they need. New users default to the weakest role (`viewer`) for this
  reason.
- **localhost / 127.0.0.1** — the special address meaning "this same machine." In
  development the browser, backend, and database all run on localhost at different
  *ports*.
- **Middleware** — code that wraps every request/response like layers of an onion,
  used for cross-cutting concerns. `CORSMiddleware` is the example here.
- **Migration** — a versioned, ordered script (Alembic) that evolves the database
  schema while preserving existing data, unlike `create_all` which only builds
  fresh tables.
- **Monorepo** — a single repository holding multiple related projects; here the
  backend and frontend live side by side, sharing one git history and one
  `docker-compose.yml`.
- **Mixin** — a small class contributing shared fields/behavior via inheritance.
  `TimestampMixin` adds `created_at`/`updated_at` to every model without copy-paste.
- **Monotonic clock** — a clock that only moves forward at a steady rate, used to
  measure durations safely (`time.monotonic()`), as opposed to the wall clock
  which can jump.
- **MVCC (Multi-Version Concurrency Control)** — Postgres's technique of keeping
  multiple row versions so readers see a consistent snapshot without waiting for
  writers. It's how heavy reads and writes happen at once without blocking.
- **MVP** — Minimum Viable Product: the smallest version that demonstrates the
  idea, with clean seams for the rest (e.g. the mock device client with a hook for
  real execution).
- **Normalization** — structuring tables so each fact lives in exactly one place
  (a job stores a `device_id`, not a copy of the hostname), preventing update
  anomalies. This project is mostly normalized, with two *deliberate* exceptions
  (comma `tags`, denormalized `test_case_name`).
- **ORM (Object-Relational Mapper)** — a library mapping database tables to
  classes and rows to objects (SQLAlchemy), so you write Python instead of raw SQL
  and get parameterized, injection-safe queries.
- **OpenAPI** — a machine-readable description of an HTTP API. FastAPI generates
  one automatically from your type hints, which powers the interactive `/docs`
  page.
- **Pagination** — returning data in pages via `limit`/`offset` instead of all
  rows at once, with a separate count query for totals. Every list endpoint uses
  the `Page[T]` envelope.
- **Primary key** — the column (almost always `id`) that uniquely identifies each
  row and serves as its permanent handle. Foreign keys point at primary keys.
- **Process vs. thread** — a **process** is a running program with its own private
  memory (the backend and worker are separate processes); a **thread** is one
  sequence of execution inside a process. Separate processes can't share memory, so
  they coordinate through Redis and Postgres.
- **Parameterized query** — a query where user input is sent as a bound parameter,
  never concatenated into the SQL string, which is what makes the ORM immune to
  SQL injection.
- **Polling** — the client repeatedly asking the server for updates. The job page
  polls `GET /api/jobs/{id}` every 1.5s until the job reaches a terminal status.
- **Prop drilling** — passing a value down through many intermediate components
  that don't use it, just to reach a deep child. React Context exists to avoid it.
- **Pseudo-random / seed** — a generator that produces a sequence determined
  entirely by a starting **seed**; same seed, same sequence. The mock client seeds
  from the hostname so each device's fake results are reproducible (§16).
- **Principle of least privilege** — grant every actor the minimum access it
  needs. New users default to `viewer`, and roles are widened only deliberately.
- **Origin** — the scheme + host + port of a web page (e.g. `http://localhost:5173`).
  The browser's same-origin policy blocks cross-origin requests unless the server
  opts in via CORS.
- **Payload** — the meaningful data carried by a message: a request/response body,
  or the claims section of a JWT.
- **Provider / Context** — React's mechanism to share a value with an entire
  component subtree without prop drilling. `AuthProvider` shares the current user;
  `useAuth` reads it.
- **Preflight (OPTIONS)** — an automatic `OPTIONS` request the browser sends before
  certain cross-origin calls to ask the server's permission. The CORS middleware
  answers it; a failed preflight is a common cause of "CORS error."
- **Referential integrity** — the database guarantee that a foreign key always
  points at a real existing row, so you can't, say, create a test case for a suite
  that doesn't exist. Enforced by foreign-key constraints.
- **Queue / broker / worker** — the async job pattern: a producer enqueues work, a
  broker (Redis) holds it, and a consumer (the worker process) runs it. Decouples
  accepting work from doing it.
- **RBAC (Role-Based Access Control)** — authorization based on a user's role
  (admin/engineer/viewer), implemented here as dependency factories (`require_roles`)
  declared right in route signatures.
- **Route** — the function bound to an endpoint that parses input, checks auth,
  calls a service, and returns a schema. Routes are the only layer that knows HTTP
  exists.
- **Render (React)** — the process of a component producing its virtual-DOM output
  from current props and state. A state change triggers a re-render, which
  reconciliation turns into minimal real-DOM updates.
- **Rainbow table** — a giant precomputed table mapping hashes back to passwords,
  used to crack unsalted hashes instantly. Per-user **salts** defeat it, which is
  why bcrypt salts every password.
- **Reconciliation** — React's diffing of the new virtual DOM against the old to
  compute the minimal real DOM updates. It's why re-rendering is cheap.
- **refetchInterval** — a TanStack Query option that re-runs a fetch on a timer.
  Given as a *function of the data*, it returns `1500` while a job is in progress
  and `false` once terminal, so polling stops itself.
- **REST** — an API style organized around resources (nouns) acted on by HTTP
  verbs, using status codes to convey outcomes. The whole `/api/...` surface
  follows it.
- **Resource** — a named thing the API exposes (a device, a job, a suite), acted on
  through the standard verbs. REST is organized around resources.
- **Status code** — the three-digit number in an HTTP response conveying the
  outcome: 2xx success, 4xx client error, 5xx server error. Choosing the right one
  is part of good API design.
- **Schema (Pydantic)** — the API/JSON shape of data, separate from the database
  *model*. Validates inputs at the boundary and controls outputs (never leaking
  `hashed_password`).
- **selectinload** — the SQLAlchemy eager-loading strategy that fetches a
  relationship's children for *all* parents in one follow-up `SELECT ... IN (...)`,
  curing the N+1 problem. Used for a suite's test cases.
- **Surrogate key** — a primary key with no business meaning (an auto-incrementing
  `id`) chosen precisely *because* it never needs to change, unlike a natural key
  such as an email.
- **Salt** — a unique random value mixed into each password before hashing and
  stored with the hash, so identical passwords get different hashes and rainbow
  tables are useless. bcrypt embeds it in its output.
- **Seeding** — loading initial/demo data so the app isn't empty on first run,
  done idempotently in `app/seed.py`.
- **Serialization / deserialization** — turning an in-memory object into a
  transmittable format (JSON text) and back. Pydantic serializes responses and
  deserializes/validates requests on the backend; `JSON.stringify`/`parse` do it
  on the frontend.
- **Separation of concerns / layered architecture** — splitting the system into
  layers each with one responsibility (routes → services → models), so changes
  stay local and pieces stay testable and reusable.
- **Service container (CI)** — a throwaway Postgres/Redis spun up just for a CI run
  so tests execute against real infrastructure.
- **SPA (Single-Page Application)** — a web app that loads one HTML page and then
  swaps content via JavaScript as you navigate, instead of fetching a new page per
  click. This frontend is an SPA, which is why the server serves `index.html` for
  any path.
- **SQL injection** — an attack where malicious input is interpreted as SQL
  commands. Parameterized ORM queries make the app immune; you'd only reintroduce
  it by building SQL with string concatenation/f-strings.
- **State machine** — an object that moves through defined states via allowed
  transitions. `Job.status` is one, with terminal states that can't transition
  further.
- **Stateless** — keeping no per-client memory between requests. HTTP is
  stateless, which is why every request re-proves identity via its JWT; the
  backend processes are stateless too (all durable state lives in Postgres).
- **Transaction / session** — a unit of database work that commits or rolls back
  as a whole. SQLAlchemy's `Session` is the unit-of-work tracking your changes
  until `commit`.
- **Token expiry (`exp`)** — the timestamp claim after which a JWT is rejected.
  Short expiries (60 minutes here) limit the damage of a stolen or stale token,
  partly offsetting JWT's lack of easy revocation.
- **Truthiness** — Python's rule that `None`, `0`, `""`, `[]`, and `{}` count as
  false in a boolean test, so `if not results:` means "if results is empty."
- **TanStack Query** — the frontend data-fetching library that caches server data
  by key, handles loading/error states, dedupes requests, and supports interval
  polling. It replaces hand-rolled `useState`+`useEffect` fetching.
- **TCP / IP** — the layered transport beneath HTTP. **IP** addresses and routes
  packets between machines; **TCP** adds reliability and ordering and introduces
  *ports*. An address+port (`127.0.0.1:8000`) identifies one program's connection.
- **Type variable** — the placeholder (`T`) in a generic, filled in at the point
  of use to produce a concrete type like `Page[DeviceOut]`.
- **uvicorn** — the ASGI server that actually runs the FastAPI app: it owns the
  socket, speaks HTTP, and drives the event loop. FastAPI defines *what* responds;
  uvicorn is the process that *listens*.
- **Virtual DOM** — React's in-memory picture of the desired UI. On a state change
  React builds a new one, diffs it (reconciliation), and applies only the minimal
  real DOM changes — cheap re-renders from declarative code.
- **yield / generator** — a function containing `yield` is a generator that runs
  up to the `yield`, hands back a value, and resumes later. `get_db` uses it to
  create a session, yield it to the endpoint, and guarantee cleanup afterward.
- **Unit of work** — the pattern (embodied by the session) of accumulating object
  changes in memory and flushing them to the database together, rather than
  writing each change immediately.
- **Vite** — the frontend build tool and dev server. It serves modules instantly
  during development (no slow bundling) and produces an optimized bundle for
  production. `VITE_`-prefixed env vars are exposed to the browser code.
- **WebSocket** — a persistent two-way connection between browser and server,
  letting the server *push* updates instead of being polled. Not used here (the job
  page polls), but the obvious upgrade from polling and listed as future work.
- **WSGI vs. ASGI** — WSGI is the older synchronous Python web-server interface
  (one request per worker at a time); ASGI is its asynchronous successor that
  supports concurrency and WebSockets. FastAPI is ASGI, which is why it can handle
  many connections on one thread.
- **12-factor app** — a set of conventions for building portable, scalable apps;
  the one most visible here is "store config in the environment," which is why
  settings come from env vars rather than hard-coded values.

---

## 28. Interview-style questions & answers

Use these to test yourself. Try to answer before reading.

**Q: Why use a background worker instead of running tests in the request?**
A: Test runs can be slow. Doing them in the HTTP request would block the response
and tie up the web server. Enqueuing to Redis and processing in a separate worker
keeps the API responsive, lets the UI poll for progress, and lets you scale
workers independently.

**Q: What's the difference between a model and a schema here?**
A: Models (SQLAlchemy) define the *database* shape; schemas (Pydantic) define the
*API/JSON* shape. They're separate so you can validate inputs and control outputs
(e.g. never returning `hashed_password`) without coupling storage to the API.

**Q: How does authentication work, and why JWT?**
A: Login verifies a bcrypt-hashed password and returns a signed JWT containing
the user id, role, and expiry. The browser stores it and sends it on each
request; the server verifies the signature (no DB session lookup needed). JWT is
stateless and simple; the tradeoff is you can't easily revoke a token before it
expires, so expiries are short.

**Q: 401 vs 403?**
A: 401 = not authenticated (missing/invalid token). 403 = authenticated but not
authorized (wrong role).

**Q: How is RBAC implemented?**
A: As dependency factories (`require_roles`) using closures. A route declares
`Depends(require_admin)`; the dependency loads the current user from the token and
rejects non-matching roles with 403 before the endpoint runs.

**Q: How do you avoid the N+1 query problem?**
A: Use eager loading (`selectinload(TestSuite.test_cases)`) so related rows come
back in one extra query instead of one per parent.

**Q: How are migrations different from `create_all()`?**
A: `create_all()` builds tables fresh but can't evolve a populated DB. Alembic
migrations are versioned, ordered scripts (`upgrade`/`downgrade`) that change the
schema while preserving data — required for production.

**Q: Why does the seed check for existing users first?**
A: Idempotency. The seed runs on every container start; the guard prevents
duplicate data.

**Q: How do tests run jobs without Redis?**
A: `enqueue_job` checks `SYNC_JOBS=1` and runs the job inline in-process, so the
end-to-end test is deterministic and needs no worker/Redis.

**Q: Why store `test_case_name` on `test_result` when there's already a
`test_case_id`?**
A: Historical accuracy — a case can be renamed/deleted later, but the result
should still reflect what ran at the time.

**Q: How does the UI know when a job finishes?**
A: TanStack Query's `refetchInterval` polls `GET /api/jobs/{id}` every 1.5s while
status is queued/running, and stops automatically on a terminal status.

**Q: Why are the worker and API the same Docker image with different commands?**
A: They share all the same code (models, services, settings). Only the entry
point differs: the API runs uvicorn; the worker runs the RQ worker loop. One
image, two roles — less to build and maintain.

**Q: How would you add real device execution?**
A: Implement the real SSH/SNMP clients (paramiko/pysnmp) behind the same method
interface as `MockDeviceClient`, source credentials from a secrets manager, and
branch in `runner._get_client` based on `DEVICE_EXECUTION_MODE`. Nothing else
needs to change because the runner programs to the interface.

#### More questions: data & the database

**Q: Why bcrypt and not SHA-256 for passwords?**
A: SHA-256 is designed to be *fast*, which is exactly wrong for passwords — an
attacker with a stolen hash table can try billions of guesses per second. bcrypt
is deliberately *slow* and has a tunable **cost factor**, so you can dial it to
take ~100ms per hash. It also salts automatically, defeating precomputed rainbow
tables. Fast hashes (SHA, MD5) are for integrity checks; slow salted hashes
(bcrypt, scrypt, argon2) are for passwords.

**Q: What is a salt and why does it matter?**
A: A salt is a unique random value mixed into each password before hashing, stored
alongside the hash. It means two users with the same password get *different*
hashes, so an attacker can't tell duplicates apart and can't precompute a single
rainbow table that cracks everyone. bcrypt embeds the salt directly in its output
string.

**Q: Is the app vulnerable to SQL injection?**
A: No, because all queries go through SQLAlchemy, which uses **parameterized
queries** — user input is sent to the database as bound *parameters*, never
concatenated into the SQL string. The classic injection (`'; DROP TABLE users;--`)
is treated as a literal string value, not executable SQL. You'd only reintroduce
the risk by hand-building raw SQL with f-strings, which this app never does.

**Q: What's an index and what's the tradeoff?**
A: An index is an auxiliary data structure (usually a B-tree) that lets the
database find rows by a column's value without scanning the whole table — turning
a linear search into a logarithmic one. The tradeoff: indexes take disk space and
must be updated on every insert/update, so they slightly slow writes to speed up
reads. You index columns you frequently filter or sort by (here, `hostname`,
`management_ip`, foreign keys), not every column.

**Q: What does a database transaction give you?**
A: The ACID guarantees — most importantly **atomicity** (all changes in the
transaction commit together or none do) and **isolation** (concurrent
transactions don't see each other's half-finished work). The `create_suite`
flush-then-commit is the canonical example: the suite and all its cases are one
atomic unit, so you never get a suite with only half its cases.

**Q: Why use a connection pool?**
A: Opening a database connection involves a TCP handshake plus authentication —
tens of milliseconds, far more than a typical query. A pool keeps a set of
connections open and hands them out per request, so you pay that cost once at
startup instead of on every request. `SessionLocal` draws from SQLAlchemy's pool.

**Q: Explain the difference between `ondelete="CASCADE"` and `SET NULL`.**
A: Both decide what happens to child rows when a parent is deleted. CASCADE
deletes the children too (used for test cases when a suite is deleted — orphan
cases are meaningless). SET NULL keeps the children but nulls the foreign key
(used for a job's `triggered_by_user_id` when a user is deleted — you want to keep
the audit history of the run even though the user is gone). The choice encodes
whether the child can outlive its parent.

**Q: Why store results denormalized with `test_case_name` and `metadata_json`?**
A: A `TestResult` is a historical record of what happened at run time. If you only
stored `test_case_id` and later renamed or deleted the case, the historical result
would change meaning or break. Copying the name (and severity/type into
`metadata_json`) freezes the result as an accurate snapshot — like a bank
statement that doesn't change when you later rename your account.

**Q: When would the comma-separated `tags` design break down?**
A: As soon as you need to efficiently query "all devices with tag X" — that
requires a `LIKE '%x%'` scan that can't use an index and has false-positive
hazards (`prod` matches `production`). At that point you'd migrate to a proper
many-to-many design with a `tags` table and a `device_tags` join table.

#### More questions: API & backend design

**Q: What is dependency injection and why is it worth it here?**
A: Instead of an endpoint creating what it needs (a DB session, the current user),
it *declares* them as parameters and FastAPI supplies them via `Depends`. The
payoff is testability — tests use `app.dependency_overrides` to swap the real DB
for SQLite with zero changes to route code — plus automatic lifecycle management
(the `get_db` generator's cleanup runs after the response).

**Q: Why is `get_db` a generator with `yield` instead of returning a session?**
A: The `yield` splits it into setup (create session) and teardown (close session
in `finally`). FastAPI runs it up to the yield, injects the session, lets the
endpoint run, then resumes it to clean up *after* the response is sent. This
guarantees the connection is always returned to the pool, even if the endpoint
raises.

**Q: What does `response_model` do beyond documentation?**
A: At runtime FastAPI filters the returned object through that schema, dropping any
field not declared on it. So it both documents the response shape *and* enforces
it — a safety net that prevents accidentally leaking a sensitive field even if a
service starts returning one.

**Q: Why validate at the boundary with Pydantic instead of inside handlers?**
A: Because once validation happens at the edge, every layer inside can *trust* its
inputs — no defensive `if not hostname` checks scattered through the code. Invalid
requests are rejected with a precise `422` before your handler ever runs. It
centralizes correctness at one place: the boundary.

**Q: What's the difference between authentication and authorization?**
A: Authentication answers "who are you?" (verified by the JWT in
`get_current_user`). Authorization answers "are you allowed to do this?" (checked
by `require_roles`). They're separate steps and map to 401 vs 403 respectively.

**Q: Why pass only `job.id` to the queue instead of the whole job object?**
A: The database is the single source of truth. Passing the id keeps the message
tiny and avoids serializing a complex ORM object. The worker re-loads the job
fresh, guaranteeing it works with current state rather than a stale snapshot.

**Q: What makes `cancel_job` idempotent and why does that matter?**
A: It only acts if the job is still queued/running; on an already-finished job it
quietly does nothing. So calling it once or five times has the same effect, which
is robust against retries (double-clicks, network resends) — the real world
retries, and safe-to-repeat operations survive that.

**Q: Why does the worker create its own database session?**
A: Sessions aren't shareable across processes. The web request's session was
closed when its response was sent, long before the worker picks up the job. So
`run_job` opens a fresh `SessionLocal()` scoped to that one job, with a
`try/finally` to guarantee cleanup.

**Q: Why catch a broad `except Exception` in `run_job` when that's usually a smell?**
A: Because it's the outermost edge of an autonomous background task. A single bad
job must never crash the worker or vanish silently — the broad catch converts any
crash into a recorded `error` status with the message saved, and the worker
survives to process the next job. At a system boundary, catching broadly is
exactly right.

**Q: Why `time.monotonic()` for durations instead of `datetime.now()`?**
A: The wall clock can jump (NTP corrections, DST, manual changes); if it jumps
backward mid-test you'd compute a negative duration. `time.monotonic()` only ever
moves forward, so the difference between two readings is a reliable elapsed time.
Rule: wall clock for *when*, monotonic for *how long*.

**Q: Why commit each test result individually instead of batching?**
A: So the polling frontend sees progress in near real time — each result becomes
visible the moment it's written, letting the UI show "3 of 10 passed so far"
instead of a long silence then a sudden dump. The extra commits are worth the
live visibility.

#### More questions: frontend

**Q: What is the virtual DOM and why does React use it?**
A: It's an in-memory representation of the desired UI. On a state change React
builds a new virtual tree, diffs it against the old one (reconciliation), and
applies only the minimal real DOM changes. This lets you write components that
"re-render everything" while paying only for what actually changed, since real DOM
mutations are slow.

**Q: What problem does React Context / the Provider pattern solve?**
A: Prop drilling — passing a value like the current user through many intermediate
components that don't use it, just to reach a deep child. A Provider puts the value
"in the air" for an entire subtree so any descendant can grab it directly via a
hook (`useAuth`), no forwarding needed.

**Q: What does the `useEffect` dependency array control?**
A: When the effect re-runs. `[]` means once on mount; `[x]` means on mount and
whenever `x` changes; omitting it means after every render (usually a bug). It's
how you tie side effects (fetching, timers, reading localStorage) to specific
state.

**Q: How does the job page stop polling automatically?**
A: `refetchInterval` is a function of the data: it returns `1500` while status is
queued/running and `false` once terminal. TanStack Query re-evaluates it after
each fetch, so polling stops itself the instant the job finishes — no manual
`clearInterval`, no leaked timers.

**Q: Why funnel every API call through one `apiFetch` wrapper?**
A: DRY and consistency. Every request automatically gets the base URL, the auth
header, JSON handling, the typed error contract, and `401 → logout`. Any
cross-cutting change is a one-line edit instead of touching forty call sites.

**Q: How does the app stay logged in across refreshes?**
A: The JWT is stored in `localStorage`. On startup an `useEffect([])` reads it and
calls `GET /api/auth/me` to verify and load the user. If valid, you're logged in;
if not, the token is cleared.

**Q: Why is client-side routing a single-page app, and what does it require of the server?**
A: React Router changes the URL via the History API without a full page reload and
swaps the rendered component — feels instant. The catch: the server must return the
same `index.html` for any path, since routing happens in JS after load; otherwise
refreshing a deep link like `/devices/42` would 404.

#### More questions: infrastructure & testing

**Q: Container vs virtual machine?**
A: A VM virtualizes hardware and runs a whole second OS (heavy, slow to boot). A
container virtualizes just the process — shares the host kernel but gets isolated
filesystem/network — so it's megabytes and starts in milliseconds. That lightness
is why we can run five containers casually.

**Q: Why order a Dockerfile to install dependencies before copying code?**
A: Docker caches each layer. Dependencies change rarely, so putting them first
keeps that slow layer cached; editing a source file only rebuilds the fast
"copy code" layer. Order least-changing to most-changing for fast builds.

**Q: How do containers find each other in Compose?**
A: By service name. Compose runs a DNS so `postgres` resolves to the database
container — that's why `DATABASE_URL` uses the hostname `postgres` and never needs
to change as containers restart.

**Q: Why a named volume for Postgres?**
A: Containers are ephemeral — delete one and its internal data is gone. A named
volume (`pgdata`) lives outside any container's lifecycle, so the database
survives restarts and `docker compose down`.

**Q: What do healthchecks and `depends_on` solve?**
A: Startup ordering. Starting the backend before Postgres accepts connections
crashes it. `depends_on: condition: service_healthy` makes the backend wait for
Postgres's healthcheck to pass — declarative ordering instead of a brittle
`sleep`.

**Q: Why does CI run against real Postgres when tests use SQLite?**
A: SQLite is fast and disposable for local/unit tests, but it isn't identical to
Postgres (enum handling, types, constraints). CI spins up real Postgres to catch
DB-specific issues the SQLite tests would miss, and verifies migrations actually
apply.

**Q: What is a test "seam" and which ones does this project use?**
A: A seam is a deliberate point where you can substitute a hard-to-test dependency
with a deterministic one. This app has three: `SYNC_JOBS=1` (run jobs inline
instead of via Redis/worker), `dependency_overrides` (swap the DB), and the
SQLite-for-Postgres swap. Together they make a full end-to-end test run in
milliseconds with no external services.

**Q: Why is `autouse=True` on the DB-reset fixture important?**
A: It runs before every test automatically, dropping and recreating tables so each
test starts clean and isolated. Without isolation, tests develop hidden
dependencies on each other's leftover data, and reordering or running one alone
breaks mysteriously.

**Q: Unit test vs integration test — why have both?**
A: Unit tests check one piece in isolation and point sharply at what broke.
Integration tests (like the end-to-end job test) check that many pieces cooperate
and catch mismatches *between* components that units can't. You want many fast
units plus a few high-confidence integration tests over critical flows.

#### More questions: architecture & tradeoffs

**Q: What is the layered architecture and why follow it?**
A: Routes (HTTP) → services (business logic) → models (data). Each layer has one
job and talks only to its neighbors. It keeps routes thin, makes logic reusable
(both a route and the worker call the same services) and testable, and means a
change in one layer doesn't ripple through the others.

**Q: What's the producer/broker/consumer pattern here?**
A: The route is the producer (creates a job, drops its id on Redis), Redis is the
broker (holds the to-do list so the two sides needn't run simultaneously), and the
worker is the consumer (pulls ids and runs them). It decouples accepting work from
doing work, which is what makes the API responsive and the workers scalable.

**Q: How would you scale the system if jobs piled up?**
A: Run more worker containers. They all pull from the same Redis queue, so N
workers process N jobs concurrently with no code change — that's the whole point of
decoupling via a queue.

**Q: What's a state machine and where does this app use one?**
A: An object that moves through a fixed set of states via defined transitions. The
`Job.status` is one: `queued → running → {passed, failed, partial, error,
canceled}`. The terminal states can't transition further, which is why cancel
guards on non-terminal states and the runner derives a final status from the
result tallies.

**Q: Why separate `failed` from `error` in results?**
A: `failed` means the test ran and the device gave the wrong answer (a real
finding). `error` means the test couldn't run at all (couldn't connect). They're
operationally different — one is a config problem on the device, the other an
infrastructure problem — so conflating them would hide that distinction.

**Q: Where are the OWASP-style risks handled?**
A: Injection (parameterized ORM queries), broken auth (bcrypt + signed JWT +
constant-time hash compare), sensitive data exposure (schemas omit
`hashed_password`), broken access control (RBAC via dependencies), and security
misconfiguration (secrets from env, CORS allowlist). The `JWT_SECRET_KEY`
defaulting to a placeholder is the one flag to fix before production.

**Q: If you had one more week, what would you improve first?**
A: Real device execution behind the existing client interface, token refresh /
revocation (the JWT's main weakness), keyset pagination if data grows, and
structured rate limiting on auth endpoints. The architecture already has clean
seams for each, which is the point of designing it this way.

#### Senior-level deep cuts (tradeoffs & alternatives)

These probe *why this tool over that one* and the limits of the current design —
the questions that separate "I used the framework" from "I understood the
choice."

**Q: Why FastAPI over Flask or Django?**
A: Flask is minimal and unopinionated but gives you no built-in validation,
serialization, async, or docs — you'd bolt those on yourself. Django is a
batteries-included monolith (its own ORM, admin, templates) optimized for
server-rendered sites, heavier than needed for a JSON API with a separate React
frontend. FastAPI hits the sweet spot for this project: type-hint-driven
validation, automatic OpenAPI docs, native async on ASGI, and it stays a *library
you compose* rather than a framework that dictates your whole structure. The
tradeoff is it's younger with a smaller ecosystem than Django.

**Q: Why RQ for the queue instead of Celery?**
A: Celery is the heavyweight standard — more features (scheduling, complex
routing, many brokers) but more configuration and conceptual overhead. RQ
(Redis Queue) is deliberately simple: a job is just a Python function call pushed
onto Redis, and a worker is one command. For an MVP that only needs "run this
function in the background," RQ's simplicity is the right call; you'd reach for
Celery if you needed cron-like scheduling, complex workflows, or multiple broker
backends. The architecture's `SYNC_JOBS` seam means swapping queues later barely
touches the rest of the code.

**Q: Why Pydantic for validation instead of hand-written checks?**
A: Hand-rolled validation is repetitive, easy to get inconsistent, and scatters
rules across handlers. Pydantic lets you declare the valid shape *once* as a typed
class and get parsing, coercion, clear error messages, and serialization for free
— and FastAPI wires it to every endpoint automatically. You centralize correctness
at the boundary instead of sprinkling `if not x: raise` everywhere.

**Q: Why environment variables for configuration (the 12-factor idea)?**
A: Config that varies between environments (database URL, secret key, CORS
origins) must live *outside* the code, so the exact same built artifact runs in
dev, CI, and prod with only the environment changing — and so secrets never get
committed to git. Reading config from the environment into a typed `Settings`
object (validated by Pydantic, cached with `lru_cache`) is the standard
"12-factor app" approach, and it's why the same image can be the API or the worker
just by changing env + command.

**Q: Why structured (JSON) logging instead of plain `print`?**
A: `print` produces unstructured text that's painful to search or aggregate.
Structured logging emits each event as key–value data (JSON), so a log
aggregator can filter by `job_id`, `level`, or `event` and build dashboards. It
also encourages logging *events with context* (`job_failed job_id=42 reason=...`)
rather than ad-hoc strings, which is far more useful when debugging a running
system you can't attach a debugger to.

**Q: What happens if a JWT expires while the user is mid-session?**
A: The next request carries the now-expired token; `get_current_user` fails to
verify it and returns `401`. The frontend's `apiFetch` wrapper treats any `401` as
"session over," clears the stored token, and redirects to login. So expiry is
handled gracefully and centrally — the user simply gets bounced to log in again.
The lack of a refresh-token flow (so they must fully re-login) is the known
tradeoff of this MVP's stateless-JWT choice.

**Q: Why `limit`/`offset` pagination, and when would it break down?**
A: Offset pagination is the simplest to implement and reason about (`LIMIT 20
OFFSET 40` = "page 3"), perfect for a UI with page numbers and modest data. It
degrades on very large tables (the database must still scan and discard the
skipped rows, so deep pages get slow) and can skip/duplicate rows if data changes
between page loads. The fix at scale is **keyset (cursor) pagination** — "give me
the next 20 *after* id X" — which uses the index directly and stays fast at any
depth. The README lists this as a deliberate future improvement.

**Q: Could you run multiple backend instances? What breaks?**
A: Yes — the backend is stateless (all durable state is in Postgres, sessions are
stateless JWTs), so you can run N copies behind a load balancer and any one can
serve any request. Nothing in the app holds per-user memory between requests.
What you'd need to add for real scale is shared infrastructure config and possibly
rate-limiting/coordination in Redis, but the *application* design already supports
horizontal scaling, which is a direct payoff of the stateless choices.

**Q: How would you test the worker/runner logic directly?**
A: Because `runner.execute_job` is plain Python that takes a session and a job and
uses the injectable device client, you can test it without Redis or a real worker:
seed a job in the test DB, call `execute_job` directly, and assert the resulting
`TestResult` rows and final status. The `SYNC_JOBS` seam does this end-to-end
through the API, but the runner can also be unit-tested in isolation because it was
written HTTP- and queue-agnostic — another payoff of the layering.

**Q: Why does the dashboard compute aggregates in SQL instead of in Python?**
A: Pushing `COUNT`/`SUM`/`AVG` into the database means the work happens where the
data lives, using indexes, and only a handful of numbers cross the wire — versus
loading thousands of rows into Python just to count them. It's faster, uses far
less memory, and scales with the data. The rule: compute next to the data, return
only the answer.

**Q: What's the single biggest risk in this codebase for production?**
A: The `JWT_SECRET_KEY` defaulting to a placeholder. If that default shipped, an
attacker who knows it could forge tokens for any user/role and bypass auth
entirely. It must be overridden with a strong secret from the environment before
any real deployment. Everything else (mock devices, hard-coded demo password,
SQLite-in-tests) is a contained, intentional demo simplification; the secret-key
default is the one that would be a genuine vulnerability if ignored.

#### A few more, across the gaps

**Q: What is the `Page[T]` envelope and why return `total` separately from the
items?**
A: `Page[T]` is a generic schema wrapping a list of items plus pagination metadata
(`total`, `limit`, `offset`). `total` is returned separately because the items
array only holds the *current page* — the frontend needs the overall count to draw
"page 3 of 12" and to know whether a "next" button should exist. Computing it
takes a second `COUNT` query alongside the `LIMIT`/`OFFSET` query (§11.2).

**Q: Why TypeScript on the frontend instead of plain JavaScript?**
A: TypeScript adds static types to JavaScript, caught at build time. It means the
shapes returned by the API (a `Device`, a `Job`) are typed end to end, so a typo
like `device.hostnam` or passing a number where a string is expected is a compile
error, not a runtime surprise in the browser. The `npm run build` step type-checks
the whole tree, which is also why CI runs it (§24.3).

**Q: What does `ProtectedRoute` do?**
A: It's a wrapper component that checks the auth state before rendering a page: if
there's no logged-in user it redirects to `/login`, otherwise it renders the child
route. It's how the frontend enforces "you must be logged in to see this,"
mirroring the backend's `get_current_user` dependency — though the *real* security
is server-side; the frontend guard is just UX so unauthenticated users don't see
broken pages.

**Q: Why store timestamps as timezone-aware UTC?**
A: A timestamp without a timezone is ambiguous — "3:00" where? Storing everything
in UTC (`DateTime(timezone=True)`) gives one unambiguous, monotonic reference that
every server and client agrees on; you convert to the viewer's local time only at
display. It also makes ordering by `created_at` correct regardless of where the
writing server is.

**Q: What's the difference between `default` and `server_default` on a column?**
A: `default` is applied by SQLAlchemy in Python before sending the INSERT;
`server_default` tells the *database* to fill the value. The timestamps use
`server_default=func.now()` so the authoritative database clock stamps every row,
which is more reliable than trusting each app server's clock (§8.1).

**Q: Why is there a shared `StatusBadge` component?**
A: Job and result statuses appear on many screens, each needing the same
color-coded pill. A single `StatusBadge` component takes a status and renders the
right style, so the mapping from status to color lives in exactly one place — change
it once and every screen updates. It's the component-level version of DRY (§23).

**Q: How does the app decide a job's final status from its results?**
A: The runner tallies the per-case `TestResult` statuses and derives the job
status: all passed → `passed`; all failed/errored → `failed`; a mix → `partial`;
a crash before/while running → `error`; and `canceled` if it was canceled. This is
the job's state machine reaching a terminal state based on what actually happened,
not a value the client supplies.

**Q: Why does listing devices allow any role but creating one requires admin?**
A: Reading is low-risk and useful to everyone (viewers audit, engineers work), so
list/get endpoints only require authentication. Writing changes shared state, so
those endpoints additionally require a stronger role via a different dependency
(`require_admin`). The only code difference is which dependency the route declares
— authorization is expressed declaratively in the signature (§12, §25.4).

**Q: What stops a viewer from just calling the API directly to create a device?**
A: Nothing about the *frontend* enforces permissions — the frontend guards are
only UX. The real enforcement is the backend dependency (`require_admin`) that runs
on every request regardless of who calls it (browser, `curl`, a script). A viewer's
token decodes to `role=viewer`, the dependency sees that and returns `403`. Always
enforce authorization on the server; never trust the client.

**Q: Why are services kept free of any HTTP or FastAPI imports?**
A: So business logic stays reusable and testable. The same `job_service` functions
are called by the API routes *and* by the worker, neither of which should require
the other's context. Keeping HTTP concerns in the route layer means you can call a
service from a script, a test, or a background task without spinning up a web
request (§3.7).

#### Debugging: symptom → likely cause

Understanding a system means knowing how it *fails*. For each symptom below, the
reasoning traces straight back to a concept in this document — which is exactly
how you'd diagnose it for real.

**Symptom: the browser shows a CORS error in the console, requests never reach
the backend.** Cause: the backend's `CORSMiddleware` allowlist doesn't include the
frontend's origin (§14). The browser blocks the response *before* your JS sees it.
Fix: add the frontend origin to the allowed origins config. Tell-tale sign: the
request shows up in the network tab as failed/blocked, and the *backend* logs show
no error (because the request was blocked client-side, or the preflight `OPTIONS`
was rejected).

**Symptom: every request returns `401`, even right after logging in.** Cause:
the token isn't being attached or isn't valid. Check that `apiFetch` reads the
token from `localStorage` and sets `Authorization: Bearer ...` (§22), and that the
`JWT_SECRET_KEY` used to *verify* matches the one used to *sign* — if the backend
restarted with a different secret, all previously issued tokens become invalid.

**Symptom: a job is stuck in `queued` forever.** Cause: nothing is consuming the
queue — the `worker` process isn't running (§15), or it can't reach Redis. The
backend happily enqueues, but with no consumer the job never advances. Check the
worker container is up and its `REDIS_URL` points at the right service. (In tests
this never happens because `SYNC_JOBS=1` runs the job inline.)

**Symptom: the list endpoint is slow and the database CPU spikes when opening a
suite with many cases.** Cause: an N+1 query — a relationship is being lazily
loaded inside a loop (§11.3). Fix: eager-load with `selectinload` so the children
come back in one query instead of one per parent.

**Symptom: `alembic upgrade head` fails or the app says a column doesn't exist.**
Cause: the models and the database schema are out of sync — you changed a model
but didn't generate/apply a migration (§18). Fix: autogenerate a migration,
*review it*, and apply it. On a fresh volume, make sure migrations ran before the
app tried to query.

**Symptom: duplicate demo data after restarts.** Cause: the seed's idempotency
guard isn't working — it should skip when users already exist (§17). If you see
duplicates, the guard check was removed or the data is being inserted before the
check.

**Symptom: a `422 Unprocessable Entity` on a request you think is fine.** Cause:
the request body failed Pydantic validation at the boundary (§10) — a missing
required field, a wrong type, an invalid enum value (e.g. a vendor not in the
allowed set), or a malformed email. The response body lists exactly which field
failed and why; read it.

**Symptom: durations come out as zero or negative.** Cause: timing with the wall
clock (`datetime.now()`) instead of `time.monotonic()` (§15) — a clock adjustment
jumped backward mid-run. Fix: measure elapsed time with the monotonic clock.

**Symptom: a deep-linked frontend URL (e.g. `/devices/42`) 404s on refresh but
works when navigated to in-app.** Cause: the server isn't configured to return
`index.html` for unknown paths (§21). In-app navigation is handled by React Router
in JS, but a hard refresh asks the *server* for that path, which doesn't exist as
a file. Fix: configure the static server to serve `index.html` for any unmatched
route.

**Symptom: `sensitive` data like `hashed_password` appears in an API response.**
Cause: the route returned the ORM model directly or used a schema that includes
the field, instead of an `*Out` schema that omits it (§10). Fix: ensure the
`response_model` is the safe output schema; FastAPI will then filter the field out.

The pattern across all of these: a symptom at the surface points to a specific
layer, and knowing the layers (§3.7) lets you jump straight to the cause instead of
guessing. That's the practical payoff of understanding the architecture.

#### Frequently confused pairs (say the difference out loud)

Interviewers love asking you to distinguish two similar-sounding things. If you
can crisply state the difference for each pair below, you've understood the
concept, not just the word.

**Authentication vs. authorization.** Authentication is *who are you* (proving
identity by logging in, verified by the JWT). Authorization is *what may you do*
(permissions, checked by your role). You authenticate once, then every request is
authorized. They map to `401` and `403` respectively.

**Model vs. schema.** A model (SQLAlchemy) is the *database* shape — a table. A
schema (Pydantic) is the *API/JSON* shape — what crosses the wire. They're kept
separate so storage and API can evolve independently, and so a model field like
`hashed_password` never appears in a response schema.

**`flush` vs. `commit`.** `flush` pushes pending SQL to the database *inside* the
current transaction (so ids get assigned and constraints run) but is still
reversible; `commit` makes everything permanent and ends the transaction. You
flush when you need a generated id mid-transaction, then commit once at the end.

**`401` vs. `403`.** `401 Unauthorized` actually means *un-authentic-ated* —
you're not logged in (missing/invalid token). `403 Forbidden` means you *are*
logged in but lack permission for this action. The names are historically
backwards; remember 401 = "who are you?", 403 = "you can't do that."

**`PUT` vs. `PATCH`.** `PUT` replaces a resource *entirely* (you send the whole
object); `PATCH` updates it *partially* (you send only changed fields). This app
uses `PATCH` for edits, which is why its `*Update` schemas make every field
optional and the service uses `exclude_unset` to touch only what was sent.

**Process vs. thread.** A process has its own private memory (the backend and the
worker are separate processes); a thread runs inside a process and shares its
memory. Separate processes can't call each other's functions, which is exactly
why the backend and worker coordinate through Redis and Postgres rather than
directly.

**Synchronous vs. asynchronous.** Synchronous means "wait here until it finishes";
asynchronous means "start it and move on, get notified later." The whole job
system exists to turn a slow *synchronous* operation (running a suite) into an
*asynchronous* one so the API can respond instantly.

**Concurrency vs. parallelism.** Concurrency is *dealing with* many things at once
by interleaving them (one event-loop thread juggling many requests); parallelism
is *doing* many things at the same instant on multiple cores (multiple worker
processes running jobs simultaneously). This project uses both, in different
places.

**Library vs. framework.** With a library, *you* call *it* (you call
`passlib.hash`). With a framework, *it* calls *you* (FastAPI calls your route
functions when requests arrive). The inversion of control — "don't call us, we'll
call you" — is the defining trait of a framework.

**Encoding vs. encryption vs. hashing.** Encoding (Base64) makes data
transport-safe and is trivially reversible — no secrecy. Encryption scrambles data
so only a key-holder can read it — reversible *with the key*. Hashing is a one-way
fingerprint — *not* reversible by design. A JWT's body is encoded (readable),
its signature uses keyed hashing (HMAC), and passwords are hashed (bcrypt).

**`null` vs. `undefined` vs. `None`.** In the JSON/TypeScript world `null` is an
explicit "no value" and `undefined` is "not set." In Python both collapse to
`None`. The API boundary translates between them — an omitted optional field
arrives as `None` in Python, and a `None` going out becomes `null` in JSON.

**`GET` vs. `POST` (semantically).** `GET` reads and must be *safe* (never changes
data) and idempotent; `POST` creates/submits and is *not* idempotent (POST twice =
two things). This is why "run a job" is a `POST` (it creates a job) while "view a
job" is a `GET`.

**Optimistic vs. pessimistic (concurrency).** Not used heavily here, but worth
knowing: pessimistic locking blocks others while you work; optimistic assumes no
conflict and checks at write time. Postgres's MVCC leans optimistic — readers
never block writers.

**Eager vs. lazy loading.** Lazy loading fetches a relationship only when you touch
it (causing the N+1 problem in a loop); eager loading (`selectinload`) fetches all
related rows up front in one extra query. The fix for N+1 is switching lazy to
eager.

**Unit vs. integration test.** A unit test checks one piece in isolation and
pinpoints failures; an integration test checks several pieces cooperating and
catches mismatches *between* them. You want many fast unit tests plus a few
high-value integration tests over critical flows (the end-to-end job test).

#### A concrete study plan

Reading once isn't enough; here's how to convert this document into durable
understanding.

1. **First pass — concepts (§1–§4).** Read the foundational sections and, for each
   bolded term, close the doc and explain it aloud in one sentence. If you can't,
   reread just that paragraph. Don't move on until the vocabulary feels natural.
2. **Second pass — trace one flow (§25).** Pick "running a test suite" and follow
   it across every file: the page, the API module, the route, the dependency, the
   service, the model, the queue, the worker, the SQL. Draw the arrows yourself on
   paper. The goal is to feel the layers handing off to each other.
3. **Third pass — rebuild one slice.** From a blank file, write the devices CRUD
   end to end (model → schema → service → route) without looking. Then diff
   against the real code and study every difference. This is where passive reading
   becomes active skill.
4. **Fourth pass — defend the decisions.** Go through §28 and the "frequently
   confused pairs" and answer each *before* reading the answer. For any you miss,
   trace back to the section that explains it. An interviewer's follow-up is almost
   always "why?", so practice the *why*, not just the *what*.
5. **Ongoing — break and fix.** Run the app, then deliberately break something
   (rename a schema field, drop an index, remove a dependency) and predict what
   fails before you observe it. Predicting failure is the truest test of a mental
   model.

---

### Final advice

Don't try to memorize this. Instead, **trace flows**. Pick a feature (say,
"cancel a job") and follow it: which page button, which `api/*.ts` function,
which route, which dependency, which service, which model, what SQL. Do that for
five features and the whole system will click. Then try to *rebuild* one slice
(e.g. devices CRUD) from a blank file without looking — that's when you'll know
you truly understand it.

One last framing to carry with you: almost every decision in this codebase is an
answer to a *constraint*, not an arbitrary preference. Background jobs exist
because requests must stay fast. Schemas are separate from models because the API
and the database must evolve independently. Bcrypt is slow on purpose because
attackers are fast. The queue carries only an id because the database is the
single source of truth. When you can recite the *constraint* behind each piece,
you're no longer memorizing a tutorial — you're thinking like the engineer who
built it, which is exactly the level of understanding that lets you answer any
question about this repo and rebuild it from scratch. That was the whole goal.
Good luck.
