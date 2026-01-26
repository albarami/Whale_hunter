# IMPLEMENTATION RULES

## ⚠️ Non-Negotiable Rules for AI-Assisted Development

**This document governs all code changes to the V3.1 Whale Hunter system.**  
**Violations are not "mistakes" — they are system failures.**

---

### 1. Docs Are Source of Truth

> **"If code conflicts with docs, docs win."**

- `POLICY.md`, `GATES.md`, `DATA_DICTIONARY.md` are **authoritative**
- Code must conform to specifications, not the other way around
- Never modify docs to match broken code
- **If unclear, ASK — don't assume**

---

### 2. Fail-Closed: Missing Data → BLOCK

> **"The default state is BLOCKED, not ALLOWED."**

- Never assume data is valid
- Never skip validation because "it's probably fine"
- If **any** required field is missing, null, or stale → **BLOCK the trade**
- Empty response from API → BLOCK
- Timeout → BLOCK
- Parse error → BLOCK

---

### 3. Assassin Gate: 95% Accuracy, 50 Samples

> **"Assassin disabled unless Simulator blocker accuracy ≥95% with ≥50 samples."**

- This is a **hard gate**, not a suggestion
- ❌ No "just enable it for testing"
- ❌ No "we'll fix the accuracy later"
- ❌ No "it's close enough at 94%"
- The **95% threshold is non-negotiable**

---

### 4. No Placeholders in Production Paths

> **"Incomplete code in critical paths = system failure."**

- ❌ No `# TODO: implement later` in safety functions
- ❌ No `pass` statements in veto gates
- ❌ No mock data in production code
- ❌ No hardcoded test values that bypass checks
- ❌ No `if DEBUG: skip_validation()`

---

### 5. Every Change Requires Tests + Verification

> **"No 'I'll add tests later.'"**

- All changes must include corresponding tests
- Changes to `POLICY.md` rules require test updates
- Run `pytest` and verification **before committing**
- Failed tests = no merge, no exceptions

---

### 6. Additional Non-Negotiables

#### Never Weaken Safety Gates
- ❌ Never reduce a veto threshold "for convenience"
- ❌ Never convert a hard BLOCK to a soft warning
- ❌ Never add "override" parameters to safety checks

#### Never Increase Risk Without Approval
- ❌ Never increase position limits without explicit approval
- ❌ Never raise capital phase without gate verification
- ❌ Never skip the First 50 Trades rules

#### Never Disable Kill Switches
- ❌ Never disable kill switches, even temporarily
- ❌ Never add "maintenance mode" that bypasses safety
- ❌ Never comment out kill switch checks

#### Never Skip Simulation
- ❌ Never skip simulation "just this once"
- ❌ Never bypass honeypot detection
- ❌ Never assume a token is safe

#### Log Everything
- Silence is suspicious
- Every decision must be logged with reasoning
- Every veto must include the specific reason
- Missing logs = audit failure

---

## Quick Reference

| Rule | Violation Example | Correct Behavior |
|------|-------------------|------------------|
| Docs win | Changing POLICY.md to match buggy code | Fix the code |
| Fail-closed | `if data is None: continue` | `if data is None: BLOCK` |
| 95% gate | Enabling Assassin at 90% accuracy | Wait for 95% |
| No placeholders | `def check_honeypot(): pass` | Full implementation |
| Tests required | "Tests coming in next PR" | Tests in same PR |

---

**Last updated:** 2026-01-25  
**Applies to:** All human and AI contributors
