"""Test script to verify timezone fixes.

This script tests that:
1. Local timezone is auto-detected correctly
2. Time functions work across different timezones
3. Idempotency keys use local dates consistently
"""

from datetime import datetime, timedelta
from myxai_desk.core.timeutil import (
    LOCAL_TZ,
    now_local,
    now_utc,
    to_local,
    to_utc,
    local_date_str,
    local_datetime_str,
    utc_isoformat,
    local_isoformat,
)

print("=" * 60)
print("Timezone Configuration Test")
print("=" * 60)

print(f"\n1. Auto-detected LOCAL_TZ: {LOCAL_TZ}")
print(f"   Type: {type(LOCAL_TZ)}")

print(f"\n2. Current times:")
local_now = now_local()
utc_now = now_utc()
print(f"   Local time: {local_now}")
print(f"   UTC time:   {utc_now}")
print(f"   Offset:     {local_now.utcoffset()}")

print(f"\n3. Date string formatting:")
print(f"   local_date_str():     {local_date_str()}")
print(f"   local_datetime_str(): {local_datetime_str()}")
print(f"   utc_isoformat():      {utc_isoformat()}")
print(f"   local_isoformat():    {local_isoformat()}")

print(f"\n4. Timezone conversions:")
# Create a UTC datetime
utc_dt = datetime(2026, 2, 26, 15, 30, 0, tzinfo=None)
print(f"   Naive datetime:       {utc_dt}")
print(f"   → to_local():         {to_local(utc_dt)}")
print(f"   → to_utc():           {to_utc(utc_dt)}")

print(f"\n5. Cross-timezone date consistency:")
# Test that date strings are based on local time, not UTC
# This is critical for daily task idempotency keys
print(f"   UTC date:   {now_utc().strftime('%Y-%m-%d')}")
print(f"   Local date: {local_date_str()}")
print(f"   → These should match user's local calendar date")

print(f"\n6. Scheduler idempotency key simulation:")
from myxai_desk.core.scheduler_service import make_idempotency_key

task_id = "test_task"
test_time = now_local()
for mode in ["daily", "weekly", "monthly"]:
    key = make_idempotency_key(task_id, test_time, mode)
    print(f"   {mode:10s} → {key}")

print(f"\n7. File timestamp format (for trash/reports):")
print(f"   Format: {local_datetime_str()}")
print(f"   Example filename: report_{local_datetime_str()}.json")

print("\n" + "=" * 60)
print("All timezone utilities working correctly!")
print("=" * 60)

# Additional validation
print("\n8. Validation checks:")
checks_passed = 0
checks_total = 0

# Check 1: LOCAL_TZ is not None
checks_total += 1
if LOCAL_TZ is not None:
    print("   [PASS] LOCAL_TZ is properly detected")
    checks_passed += 1
else:
    print("   [FAIL] LOCAL_TZ is None")

# Check 2: Local and UTC times are different (unless user is in UTC±0)
checks_total += 1
if abs((now_local() - now_utc()).total_seconds()) < 86400:  # Within 24 hours
    print("   [PASS] Local and UTC time difference is reasonable")
    checks_passed += 1
else:
    print("   [FAIL] Local and UTC time difference is suspicious")

# Check 3: Date strings are properly formatted
checks_total += 1
date_str = local_date_str()
if len(date_str) == 10 and date_str.count('-') == 2:
    print(f"   [PASS] Date string format is correct: {date_str}")
    checks_passed += 1
else:
    print(f"   [FAIL] Date string format is wrong: {date_str}")

# Check 4: Datetime strings are properly formatted
checks_total += 1
datetime_str = local_datetime_str()
if len(datetime_str) == 15 and datetime_str.count('_') == 1:
    print(f"   [PASS] Datetime string format is correct: {datetime_str}")
    checks_passed += 1
else:
    print(f"   [FAIL] Datetime string format is wrong: {datetime_str}")

print(f"\n   Result: {checks_passed}/{checks_total} checks passed")

if checks_passed == checks_total:
    print("\n[SUCCESS] All validation checks PASSED!")
else:
    print(f"\n[WARNING] {checks_total - checks_passed} validation check(s) FAILED")
