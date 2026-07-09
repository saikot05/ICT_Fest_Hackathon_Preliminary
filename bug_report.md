# CoWork API: Comprehensive Bug Report

This document outlines the bugs identified and fixed in the CoWork API implementation to strictly adhere to the Hackathon Business Rules and API contract. Our team resolved these bugs through combined efforts, addressing severe concurrency issues, multi-tenancy leaks, logical validation errors, and refund miscalculations.

## Booking Flow & Refund Engine Fixes

### 1. Strict Future Start-Time Check (`app/routers/bookings.py`)
- **Bug**: The `create_booking` endpoint allowed a grace period for bookings, violating Rule 2.
- **Fix**: Removed the grace period and enforced a strict `start <= now` check, guaranteeing that booking start times must be strictly in the future.

### 2. Booking Duration Validation (`app/routers/bookings.py`)
- **Bug**: Bookings could be created with invalid durations or negative time slots.
- **Fix**: Added validation to throw `INVALID_BOOKING_WINDOW` if `end <= start` or if the booking duration is less than 1 hour (violating Rule 2).

### 3. Back-to-Back Booking Overlap (`app/routers/bookings.py`)
- **Bug**: The `_has_conflict` function incorrectly rejected back-to-back bookings by using inclusive `<=` and `>=` operators.
- **Fix**: Changed the overlap operators to strictly less than (`<`), satisfying Rule 3 which explicitly allows back-to-back bookings.

### 4. Booking Pagination & Ordering (`app/routers/bookings.py`)
- **Bug**: `list_bookings` failed to properly paginate and sort results (Rule 11).
- **Fix**: Implemented sorting by `start_time` (ascending), then `id` (ascending). Replaced the hardcoded limit of 10 with a dynamic `limit` parameter, and fixed the offset calculation to `(page - 1) * limit`.

### 5. Booking Visibility for Members (`app/routers/bookings.py`)
- **Bug**: Members could potentially read bookings belonging to other members, violating Rule 10.
- **Fix**: Updated `get_booking` to explicitly check `user.role == "admin" or booking.user_id == user.id`. Non-compliant access now strictly returns `404 BOOKING_NOT_FOUND`.

### 6. Booking Start Time Overwrite (`app/routers/bookings.py`)
- **Bug**: A logical bug inside `get_booking` mistakenly overwrote the booking's `start_time` with its `created_at` timestamp.
- **Fix**: Removed the offending line that overwrote the start time.

### 7. Refund Notice Period Tiers (`app/routers/bookings.py`)
- **Bug**: The refund tier boundaries (Rule 6) were incorrectly mapped (e.g., failing to provide 100% refund for exactly 48 hours notice, and providing 50% instead of 0% for <24 hours).
- **Fix**: Corrected the boundary check to `>= 48 hours` for 100% refund, and updated the `< 24 hours` else block to return 0% refund.

### 8. Refund Cent Rounding (`app/services/refunds.py` & `app/routers/bookings.py`)
- **Bug**: 50% refunds were using standard floating-point division, causing half-cents to truncate instead of round up.
- **Fix**: Replaced division with integer arithmetic `(price_cents * refund_percent + 50) // 100` to guarantee half-cents are correctly rounded up.

### 9. Cache Invalidation (`app/routers/bookings.py`)
- **Bug**: Creating and cancelling bookings did not properly invalidate the cache, leading to stale reports.
- **Fix**: Added `cache.invalidate_report(org_id)` on booking creation, and `cache.invalidate_availability(...)` on cancellation to ensure data freshness.

---

## Concurrency, Multi-Tenancy & Data Consistency Fixes

### 10. Server Liveness & Deadlocks (`app/services/notifications.py`)
- **Bug**: A critical server hang vulnerability existed due to nested thread locks (`_email_lock` and `_audit_lock`) inside `notify_created` and `notify_cancelled`. 
- **Fix**: Un-nested the locks. They are now acquired and released sequentially, guaranteeing server liveness under concurrent loads (Rule 16).

### 11. Thread-Safe Rate Limiting (`app/services/ratelimit.py`)
- **Bug**: A race condition allowed users to bypass the 20-request/60-second limit (Rule 5).
- **Fix**: Wrapped the rate limit timestamp tracking and cleanup logic inside a `threading.Lock()` to ensure strict enforcement during concurrent bursts.

### 12. Unique Reference Code Generation (`app/services/reference.py`)
- **Bug**: Concurrent requests could generate duplicate booking reference IDs, violating Rule 7.
- **Fix**: Synchronized the sequential ID counter with a global thread lock, guaranteeing perfectly unique reference codes.

### 13. Data Accuracy & Live Statistics (`app/services/stats.py` & `app/routers/rooms.py`)
- **Bug**: Room statistics were relying on desynced in-memory state, leading to inconsistent counts (Rule 14).
- **Fix**: Restructured `stats.get` to query the SQLite database directly using SQLAlchemy's `func.count` and `func.sum`. Used `coalesce` to handle `None` sums, ensuring accurate integer returns.

### 14. Admin Export Isolation (`app/routers/admin.py`)
- **Bug**: `GET /admin/export` failed to enforce strict multi-tenancy, allowing cross-tenant data access.
- **Fix**: Added validation to check if the requested `room_id` strictly belongs to the authenticated admin's `org_id`, raising `404 ROOM_NOT_FOUND` on violations.

### 15. Report Datetime Boundary Inclusivity (`app/routers/admin.py`)
- **Bug**: The `GET /admin/usage-report` logic failed to include bookings for the entirety of the `to` date.
- **Fix**: Corrected the logic to parse `from` and `to` query parameters into timezone-aware UTC datetime objects. Extended the upper boundary filter to `parsed_to_date + timedelta(days=1)`.

---

## Architecture & Database Level Fixes

### 16. Database Transaction Isolation (`app/database.py`)
- **Bug**: SQLite's default transaction isolation allowed read-modify-write races, meaning overlapping double-bookings could bypass the conflict checker under load.
- **Fix**: Configured SQLite with `PRAGMA journal_mode=WAL` and adjusted transaction boundaries to prevent concurrent write races.

### 17. SQLAlchemy Type Constraints & Warnings
- **Bug**: Static type mismatches occurred when passing SQLAlchemy `InstrumentedAttribute` properties into functions expecting strictly `int` types. Using `int()` caused further type-checker errors.
- **Fix**: Replaced runtime `int()` conversions with `typing.cast(int, ...)` across `admin.py`, `bookings.py`, and `refunds.py` to correctly satisfy static analysis while preserving execution speed.

### 18. Authentication & Multi-Tenancy Flaws (`app/routers/auth.py` & `app/models.py`)
- **Bug**: Access tokens didn't strictly expire at 900 seconds; Refresh tokens lacked single-use revocation; Usernames were required to be globally unique instead of organization-scoped.
- **Fix**: 
  - Adjusted JWT generation for exact 900-second access lifespans.
  - Implemented single-use refresh token revocation (JTI checking).
  - Scoped the unique constraint for usernames down to `org_id`.
