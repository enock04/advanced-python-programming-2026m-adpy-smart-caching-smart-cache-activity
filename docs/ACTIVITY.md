# Smart Cache Layer — Guided Activity

**Course:** Advanced Python Programming | ALU BSE  
**Topic:** Caching  
**Duration:** ~30 minutes  
**File to work in:** `blog/views.py`

---

## Overview

You have been given a working Django REST API for a blog platform with 500 posts
and 3 users. The API works — but it hits the database on **every single request**.

Your job is to add a smart cache layer, level by level, until the API is fast,
correct, and secure.

---

## Setup

```bash
# 1. Clone the repo and enter the directory
git clone <repo-url>
cd smart-cache-activity

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations and seed the database
python manage.py migrate
python manage.py seed

# 5. Start the server
python manage.py runserver
```

You should see output confirming 500 posts and 3 users created:
```
✅ Created user: alice / password123
✅ Created user: bob / password123
✅ Created user: carol / password123
✅ Created 500 posts
```

---

## The Endpoints

| Method | URL | What it does | Auth required? |
|--------|-----|--------------|----------------|
| GET | `/api/posts/` | All published posts | No |
| GET | `/api/posts/<id>/` | Single published post | No |
| POST | `/api/posts/` | Create a new post | Yes |
| GET | `/api/posts/my-drafts/` | Your own drafts only | Yes |
| GET | `/api/posts/broken-drafts/` | Buggy draft view | Yes |

---

## Level 1 — Feel the Pain (5 min)

Before writing any cache code, run the timing script to record your baseline:

```bash
# Make sure the server is running in another terminal first
python timing.py
```

**Record your results here:**

| Endpoint | First Request | Average |
|----------|--------------|---------|
| All Posts | 30.7ms | 18.4ms |
| Single Post | 5.2ms | *(crashed on repeat requests — see note)* |

> **Note:** With the original code, the *first* call to `/api/posts/<id>/` succeeds
> (cache miss → DB query → 5.2ms), but every request after that returns
> **HTTP 500**. That's because on a cache *hit* the code falls through to code that
> references a `post` variable that was only ever assigned inside the cache-miss
> branch — so on a hit, Python raises `UnboundLocalError`. This is the same class
> of "looks-cached but isn't handled correctly" bug you'll be asked to reason
> about again in `BrokenDraftsView` (Level 3), just manifesting as a crash
> instead of a data leak. It had to be fixed before real timing numbers for this
> endpoint were possible — see the Final Check table below.

You'll run this again after each level to see how much you've improved.

---

## Level 2 — Cache the Public Data (15 min)

Open `blog/views.py` and find the `PostListView` and `PostDetailView` classes.

Follow the TODO comments to implement **cache-aside** for both endpoints.

**The pattern you are implementing:**
```
Request comes in
    ↓
Check cache → HIT?  → Return cached data immediately (fast ⚡)
    ↓ MISS
Query database
    ↓
Store result in cache
    ↓
Return data to user
```

**Tools available:**
```python
from django.core.cache import cache

cache.get("your-key")                      # returns None if not found
cache.set("your-key", data, timeout=300)   # stores data for 300 seconds
```

**When you're done**, run `python timing.py` again and compare.

> **Discussion:** What cache key did you choose for the list endpoint?
> Compare with a classmate — did you choose the same key? Why or why not?

_Answer:_ `"posts:list:published"`: a namespaced key (`resource:action:filter`).
Every visitor sees the exact same published-post list, so one shared key can
serve everyone and still be correct; there's no per-user data in this
response. The namespacing (`posts:` prefix, `:list` vs `:detail`) matters so
this key can't collide with `posts:detail:<id>` or another app's cache keys
in the same cache backend. (For the stretch goal below, the key becomes
query-aware: `posts:list:published:<querystring>`.)

---

## Level 3 — Protect Personal Data (15 min)

Now find the `MyDraftsView` class and implement caching for the `/my-drafts/` endpoint.

**This one is different.** The drafts belong to a specific user — you must ensure
that **User A can never see User B's drafts**, even through the cache.

### Step 1 — Implement the cache

Follow the TODO in `MyDraftsView.get()`. Think carefully about your cache key.

### Step 2 — Find the bug

Look at `BrokenDraftsView` at the bottom of `views.py`.

**Do NOT fix the code.** Instead, answer these questions below:

---

**Bug Report**

> What is the bug in `BrokenDraftsView`?

_Answer:_ The cache key is the hardcoded literal string `"my-drafts"`,
identical for every user. It never includes `request.user.id`, so all
authenticated users read from and write to the exact same cache slot.

---

> Walk through this exact scenario — what happens step by step?
> 1. Alice logs in and calls `/api/posts/broken-drafts/`
> 2. Bob logs in and calls `/api/posts/broken-drafts/`

_Answer:_
1. Alice calls the endpoint → `cache.get("my-drafts")` misses → her drafts are
   queried from the DB, serialized, and stored under `"my-drafts"` for 120s →
   Alice correctly receives her own drafts.
2. Bob calls the same endpoint (within that 120s window) → `cache.get("my-drafts")`
   **hits**, because it's the same key Alice just filled, and Bob is handed
   Alice's serialized drafts directly, without the view ever touching the
   database or checking whose data it actually is.

We verified this with an isolated test (`APIClient`, `force_authenticate`):
after Alice populates `"my-drafts"`, Bob's response titles are byte-for-byte
identical to Alice's, confirmed cross-user leak, not a hypothetical.

---

> What is the real-world impact of this bug if it shipped to production?

_Answer:_ Any logged-in user can view another user's private, unpublished drafts for up to 120 seconds after that user last loaded their own drafts. This is an access-control/IDOR-style data leak, but the flaw sits in the caching layer rather than in the permission check itself, which works correctly. On a blog platform, this could expose unreleased articles, embargoed announcements, or personal notes. It's also completely silent, there's no error and no log entry, and nothing distinguishes a leaked response from a normal one, so the issue could persist in production for a long time before it's ever noticed.
---

> What is the one-line fix?

_Answer:_ Scope the key to the requesting user, exactly like
`MyDraftsView` does:
`cache_key = f"my-drafts:{request.user.id}"` (and use `cache_key` in place of
`"my-drafts"` in both the `cache.get()` and `cache.set()` calls).

---

## Level 4 — Invalidation (10 min)

You've now cached the post list. But there's a problem.

**Scenario:**
1. User requests `GET /api/posts/` — gets cached response (100 posts)
2. User creates a new post via `POST /api/posts/`
3. User requests `GET /api/posts/` again — **still sees 100 posts, not 101**

The cache doesn't know the data changed.

### Your task

Find the `post()` method in `PostListView` and add the one line of code
that fixes this problem after a new post is saved.

```python
cache.delete("your-key-here")   # removes the stale entry
```

**Test it:**
1. Call `GET /api/posts/` and note the count
2. Call `POST /api/posts/` to create a new post
3. Call `GET /api/posts/` again — the new post should appear

> **Discussion:** What's the difference between `cache.delete()` and
> updating the cache with the new data directly? When would you choose each?

_Answer:_ `cache.delete()` just removes the stale entry, the *next* GET gets
a cache miss, re-queries the DB, and repopulates the cache (classic
cache-aside; simple, and the write path stays decoupled from how the read
path shapes its response). Updating the cache directly ("write-through")
means the write path immediately puts a fresh, correctly-serialized value
back under the same key, so there's never a miss at all, but now the write
path has to reconstruct exactly what the read path would have produced
(same queryset, same serializer), which is more code and can drift out of
sync if one side changes and the other doesn't. I used `delete()` here
because it's simpler and the list endpoint's cache-miss cost is small; I'd
reach for write-through only for a very hot key where even one cache-miss
per write is too costly.

---

## Stretch Goal — Query-Aware Cache Key

If you finish early, look at this scenario:

```
GET /api/posts/?status=published    # all published posts
GET /api/posts/?status=published&page=2   # page 2 only
```

If you used a single key like `"posts:all"` for both, they'd overwrite each other.

**Challenge:** Modify your `PostListView.get()` so that the cache key
accounts for any query parameters in the request.

```python
# Hint — something like this:
params = request.query_params.urlencode()   # turns params into a string
cache_key = f"posts:list:{params}"
```

**Done.** `PostListView.get()` now builds
`cache_key = f"posts:list:published:{params}"` when there are query params,
falling back to the plain `"posts:list:published"` key when there are none
(so the Level 4 `cache.delete("posts:list:published")` still hits the common
no-params case). One caveat worth naming: that single `delete()` only clears
the no-params entry — a differently-parameterized entry like
`?page=2` would keep serving stale data until its own TTL expires. A more
complete fix would track and delete all variant keys (or use a short TTL and
accept brief staleness), but that's beyond this activity's scope.

---

## Final Check — Run the Timer One More Time

```bash
python timing.py
```

**Record your final results:**

| Endpoint | Before (DB hit every time) | After (cache hit) | Improvement |
|----------|-----------------|-----------------|-------------|
| All Posts | 18.6ms | 5.1ms | ~73% faster |
| Single Post | 2.1ms | 2.0ms | ~1% faster (see note) |

> **Note:** measured with cache cleared before each "before" request and a
> warm cache for each "after" request, 5 runs averaged per cell (isolates the
> cache effect from network/process noise better than 3 raw `timing.py` runs
> on a machine this fast). The list endpoint improves a lot because avoiding
> the DB hit also avoids re-serializing ~400 rows every time. The single-post
> endpoint barely moves, a SQLite lookup by primary key on 500 rows is
> already close to free locally, so there's very little DB cost left for the
> cache to remove. **Lesson:** caching helps most when the *uncached* work is
> expensive; for a cheap indexed lookup, caching mainly avoids
> re-serialization, not the query itself, and the win will look much bigger
> in production against a real network-attached database under load.

---

## Reflection Questions

Answer these before the debrief:

1. Why did you use a **shared** key for `/api/posts/` but a **user-specific** key for `/my-drafts/`?

   _Answer:_ `/api/posts/` returns the same data to everyone, it's public,
   so one cache entry can correctly serve every visitor and the hit rate is
   maximized. `/my-drafts/` returns different, private data *per user*; a
   shared key would mean whoever populates the cache first "leaks" their
   drafts to everyone else who hits it next (exactly the bug in
   `BrokenDraftsView`). Including `request.user.id` in the key gives each
   user their own isolated cache slot.

2. What would happen if you set `timeout=None` on the post list cache?

   _Answer:_ The entry would never expire on its own, it lives in the cache
   backend forever (until evicted for memory pressure or the process
   restarts, since `LocMemCache` is per-process) and only changes when
   something explicitly calls `cache.delete()` or overwrites it. That's fine
   as long as *every* write path that changes published posts also
   invalidates the cache, but if any other path forgets to (an admin edit,
   a bulk import, a future endpoint), the cache would serve stale data
   indefinitely with no self-healing, which is worse than a short TTL where
   staleness is at least bounded in time.

3. In what situation would caching `/my-drafts/` actually cause a bug even with the correct user-specific key?
   *(Hint: think about what happens when a user saves a new draft)*

   _Answer:_ The key correctly isolates users from *each other*, but nothing
   invalidates a user's own `my-drafts:<id>` entry when *that same user*
   creates, edits, or deletes a draft. If Alice saves a new draft and then
   immediately calls `/my-drafts/`, she can be served her own stale cached
   list (missing the new draft, or still showing one she just deleted) for
   up to 120 seconds, a correctness bug, not a security one, but still a
   real "why isn't my draft showing up" bug report. Fixing it needs the same
   idea as Level 4: `cache.delete(f"my-drafts:{request.user.id}")` after any
   write to that user's drafts.

---

## Key Concepts Checklist

By the end of this activity you should be able to:

- [x] Explain what cache-aside (lazy loading) means in your own words
- [x] Design a cache key that is shared, user-specific, or query-aware as needed
- [x] Explain why authentication must happen **before** the cache lookup
- [x] Implement cache invalidation when underlying data changes
- [x] Identify a cache key bug and explain its security impact

**Cache-aside, in my own words:** on a read, check the cache first; if it's a
miss, fall through to the real source of truth (the DB), build the response,
and store it in the cache before returning — so the *next* read for the same
key is a hit. The cache is populated lazily, on demand, rather than being
pre-warmed ahead of time.

**Why auth must run before the cache lookup:** `permission_classes` /
`get_permissions()` run before `.get()`/`.post()` even starts, so an
unauthenticated or wrong-user request never reaches the cache logic at all
for `MyDraftsView`. If the cache were checked *before* auth, a cached
response built for one user could be returned to a request that hasn't even
proven who it is yet — the cache would bypass the permission check entirely
instead of sitting behind it.

---

*Built for ALU BSE — Advanced Python Programming*
