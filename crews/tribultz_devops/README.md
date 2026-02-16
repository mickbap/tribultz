# Tribultz DevOps & Engineering Crew

This crew automates critical DevOps and Engineering tasks to ensure the stability, security, and scalability of the Tribultz backend.

## Agents
- **Senior Security Engineer**: Enforces tenant isolation and API security.
- **QA Automation Engineer**: Verification and testing.
- **DevOps Engineer**: Infrastructure and migrations.

## Tasks
1.  **Enforce Tenant Scoping**: Scans code to ensure no `tenant_slug` usage in authenticated routes.
2.  **Tenant Isolation Tests**: Runs integration tests to verify data isolation.
3.  **Alembic Baseline**: Ensures database schema migrations are up to date.
4.  **Console Smoke Test**: Verifies frontend build and API integration.

## Usage

Run the crew:
```bash
python main.py
```

Safe Dry Run (simulated):
```bash
python main.py --dry-run
```
