# S4-01b — HTTP Contract/Security Gates Wiring Report
Generated: 2026-02-20T14:38:44.3560650-03:00

## Objective
Wire the pending HTTP gates in QA report and make CI fail if they are missing in --mode ci.

## Repo snapshot
- HEAD: 6a12426eac610da300ce6ccac613ec8b466bf836

## FastAPI app entrypoints

```text
backend\app\main.py:8:app = FastAPI(
```

## Chat endpoint (/api/v1/chat/message) implementation

```text
backend\tests\api\test_chat.py:48:    response = client.post("/api/v1/chat/message", json={"message": "Validate invoice INV-999"})
backend\tests\api\test_chat.py:74:    response = client.post("/api/v1/chat/message", json={
backend\tests\api\test_chat.py:88:    response = client.post("/api/v1/chat/message", json={"message": long_msg})
backend\tests\api\test_chat.py:92:    response = client.post("/api/v1/chat/message", json={"message": ""})
```

## Jobs endpoints + tenant scoping (anti-IDOR)

```text
backend/tests\test_auth.py:9:from app.models.auth import Tenant, User
backend/tests\test_auth.py:19:@pytest.fixture(scope="module")
backend/tests\test_auth.py:59:def test_tenant(session):
backend/tests\test_auth.py:62:    slug = f"test-tenant-{uuid.uuid4()}"
backend/tests\test_auth.py:63:    tenant = Tenant(name="Test Tenant", slug=slug)
backend/tests\test_auth.py:64:    session.add(tenant)
backend/tests\test_auth.py:66:    session.refresh(tenant)
backend/tests\test_auth.py:67:    return tenant
backend/tests\test_auth.py:71:def test_user(session, test_tenant):
backend/tests\test_auth.py:78:        tenant_id=test_tenant.id,
backend/tests\test_auth.py:89:def test_login_success(client, test_user, test_tenant):
backend/tests\test_auth.py:95:            "tenant_slug": test_tenant.slug
backend/tests\test_auth.py:104:def test_login_wrong_password(client, test_user, test_tenant):
backend/tests\test_auth.py:110:            "tenant_slug": test_tenant.slug
backend/tests\test_auth.py:117:def test_login_inactive_user(client, session, test_user, test_tenant):
backend/tests\test_auth.py:127:            "tenant_slug": test_tenant.slug
backend/tests\test_auth.py:134:def test_login_wrong_tenant(client, test_user):
backend/tests\test_auth.py:140:            "tenant_slug": "non-existent-tenant"
backend/tests\api\test_chat.py:17:    tenant_id=uuid4(),
backend/tests\api\test_chat.py:44:            JobEvidence(type="job", job_id=expected_job_id, href=f"/jobs/{expected_job_id}", label="Validation Job")
backend/tests\api\test_chat.py:61:    assert call_kwargs["tenant_id"] == mock_user.tenant_id
backend/app\crews\executor.py:9:from app.tools.postgres_tool import get_tenant_slug, job_create, job_status_update
backend/app\crews\executor.py:19:    async def trigger_task_a(self, *, tenant_id: UUID, user_id: UUID, message: str) -> UUID:
backend/app\crews\executor.py:33:        tenant_id_str = str(tenant_id)
backend/app\crews\executor.py:34:        tenant_slug = get_tenant_slug(tenant_id_str)
backend/app\crews\executor.py:39:            tenant_id=tenant_id_str,
backend/app\crews\executor.py:52:                    "tenant_id": tenant_id_str,
backend/app\crews\executor.py:53:                    "tenant_slug": tenant_slug,
backend/app\crews\executor.py:68:    async def get_job_status(self, *, tenant_id: UUID, user_id: UUID, job_id: UUID) -> str:
backend/app\models\chat.py:13:    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
backend/app\models\auth.py:17:class Tenant(Base):
backend/app\models\auth.py:18:    __tablename__ = "tenants"
backend/app\models\auth.py:51:    tenant_id = Column(
backend/app\models\auth.py:53:        ForeignKey("tenants.id", ondelete="CASCADE"),
backend/app\models\auth.py:71:    __table_args__ = (UniqueConstraint("tenant_id", "email", name="users_tenant_id_email_key"),)
backend/app\schemas\auth.py:12:    tenant_id: str
backend/app\schemas\auth.py:21:    tenant_slug: str = "default"
backend/app\schemas\auth.py:29:    tenant_id: UUID
backend/app\alembic\versions\2026_02_16_0001_baseline.py:25:    # 1. Tenants
backend/app\alembic\versions\2026_02_16_0001_baseline.py:26:    op.create_table('tenants',
backend/app\alembic\versions\2026_02_16_0001_baseline.py:40:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:48:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:50:        sa.UniqueConstraint('tenant_id', 'email', name='users_tenant_id_email_key')
backend/app\alembic\versions\2026_02_16_0001_baseline.py:52:    op.create_index('idx_users_tenant', 'users', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:57:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:66:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:68:        sa.UniqueConstraint('tenant_id', 'cnpj')
backend/app\alembic\versions\2026_02_16_0001_baseline.py:70:    op.create_index('idx_companies_tenant', 'companies', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:75:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:84:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:86:        sa.UniqueConstraint('tenant_id', 'rule_code', 'valid_from')
backend/app\alembic\versions\2026_02_16_0001_baseline.py:88:    op.create_index('idx_tax_rules_tenant', 'tax_rules', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:89:    op.create_index('idx_tax_rules_type', 'tax_rules', ['tenant_id', 'tax_type'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:94:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:102:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:104:        sa.UniqueConstraint('tenant_id', 'code')
backend/app\alembic\versions\2026_02_16_0001_baseline.py:106:    op.create_index('idx_ncm_codes_tenant', 'ncm_codes', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:111:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:125:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:127:        sa.UniqueConstraint('tenant_id', 'company_id', 'invoice_number')
backend/app\alembic\versions\2026_02_16_0001_baseline.py:129:    op.create_index('idx_invoices_company', 'invoices', ['tenant_id', 'company_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:130:    op.create_index('idx_invoices_tenant', 'invoices', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:135:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:151:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:155:    op.create_index('idx_invoice_items_tenant', 'invoice_items', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:160:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:171:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:174:    op.create_index('idx_tax_credits_company', 'tax_credits', ['tenant_id', 'company_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:175:    op.create_index('idx_tax_credits_tenant', 'tax_credits', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:180:        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:187:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0001_baseline.py:192:    op.create_index('idx_audit_log_tenant', 'audit_log', ['tenant_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:195:    # Default Tenant
backend/app\alembic\versions\2026_02_16_0001_baseline.py:196:    op.execute("INSERT INTO tenants (name, slug) VALUES ('Default Tenant', 'default') ON CONFLICT (slug) DO NOTHING")
backend/app\alembic\versions\2026_02_16_0001_baseline.py:200:        INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:202:        FROM tenants t WHERE t.slug = 'default'
backend/app\alembic\versions\2026_02_16_0001_baseline.py:206:        INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
backend/app\alembic\versions\2026_02_16_0001_baseline.py:208:        FROM tenants t WHERE t.slug = 'default'
backend/app\alembic\versions\2026_02_16_0001_baseline.py:222:    op.drop_table('tenants')
backend/app\routers\audit.py:24:    # tenant_slug: str = "default"  <-- REMOVED
backend/app\routers\audit.py:30:    tenant_id: str
backend/app\routers\audit.py:39:    # tenant_slug: str = "default" <-- REMOVED
backend/app\routers\audit.py:66:    tenant_id = str(current_user.tenant_id)
backend/app\routers\audit.py:70:            INSERT INTO audit_log (id, tenant_id, user_id, action,
backend/app\routers\audit.py:72:            VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), CAST(:user_id AS uuid), :action,
backend/app\routers\audit.py:77:            "tenant_id": tenant_id,
backend/app\routers\audit.py:89:        tenant_id=tenant_id,
backend/app\routers\audit.py:105:    tenant_id = str(current_user.tenant_id)
backend/app\routers\audit.py:107:    filters = ["al.tenant_id = CAST(:tid AS uuid)"]
backend/app\routers\audit.py:108:    bind: dict[str, Any] = {"tid": tenant_id, "limit": params.limit}
backend/app\routers\audit.py:120:            SELECT al.id, al.tenant_id, al.action, al.entity_type,
backend/app\routers\audit.py:135:            tenant_id=str(r.tenant_id),
backend/app\routers\chat.py:35:      - tenant_id MUST come from JWT/current_user, never from payload
backend/app\routers\chat.py:36:      - mismatch tenant/user for conversation_id MUST return 404
backend/app\routers\chat.py:40:    tenant_id = cast(UUID, current_user.tenant_id)
backend/app\routers\chat.py:41:    if tenant_id is None:
backend/app\routers\chat.py:44:            detail="Invalid authentication context (missing tenant).",
backend/app\routers\chat.py:48:        tenant_id=tenant_id,
backend/app\routers\auth.py:7:from app.models.auth import Tenant, User
backend/app\routers\auth.py:16:    # 1. Resolve Tenant
backend/app\routers\auth.py:17:    stmt_tenant = select(Tenant).where(Tenant.slug == login_data.tenant_slug)
backend/app\routers\auth.py:18:    tenant = db.execute(stmt_tenant).scalar_one_or_none()
backend/app\routers\auth.py:21:    if not tenant or not cast(bool, tenant.is_active):
backend/app\routers\auth.py:28:    # 2. Resolve User within Tenant
backend/app\routers\auth.py:29:    # Use Tenant.id (class attr) for query, which is correct
backend/app\routers\auth.py:32:        User.tenant_id == tenant.id
backend/app\routers\auth.py:64:            "tenant_id": str(tenant.id),
backend/app\routers\jobs.py:16:router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
backend/app\routers\jobs.py:29:    # tenant_slug removed - derived from auth
backend/app\routers\jobs.py:43:    tenant_id: str
backend/app\routers\jobs.py:58:    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
backend/app\routers\jobs.py:67:    UNIQUE (tenant_id, idempotency_key)
backend/app\routers\jobs.py:69:CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
backend/app\routers\jobs.py:70:CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status);
backend/app\routers\jobs.py:82:        tenant_id=str(r.tenant_id),
backend/app\routers\jobs.py:103:    exists for this tenant, the existing job is returned (safe retry).
backend/app\routers\jobs.py:106:    tenant_id = str(current_user.tenant_id)
backend/app\routers\jobs.py:113:                WHERE tenant_id = :tid AND idempotency_key = :key
backend/app\routers\jobs.py:115:            {"tid": tenant_id, "key": req.idempotency_key},
backend/app\routers\jobs.py:124:            INSERT INTO jobs (id, tenant_id, job_type, status,
backend/app\routers\jobs.py:130:            "tid": tenant_id,
backend/app\routers\jobs.py:139:        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:140:        {"id": job_id, "tid": tenant_id},
backend/app\routers\jobs.py:153:    tenant_id = str(current_user.tenant_id)
backend/app\routers\jobs.py:155:        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:156:        {"id": job_id, "tid": tenant_id},
backend/app\routers\jobs.py:178:    tenant_id = str(current_user.tenant_id)
backend/app\routers\jobs.py:179:    params: dict[str, Any] = {"id": job_id, "tid": tenant_id, "status": req.status.value}
backend/app\routers\jobs.py:189:    db.execute(text(f"UPDATE jobs SET {set_clause} WHERE id = :id AND tenant_id = :tid"), params)
backend/app\routers\jobs.py:193:        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:194:        {"id": job_id, "tid": tenant_id},
backend/app\routers\jobs.py:208:    """List jobs for the authenticated user's tenant, optionally filtered by status."""
backend/app\routers\jobs.py:210:    tenant_id = str(current_user.tenant_id)
backend/app\routers\jobs.py:212:    filters = ["j.tenant_id = :tid"]
backend/app\routers\jobs.py:213:    params: dict[str, Any] = {"tid": tenant_id, "limit": limit}
backend/app\routers\jobs.py:243:    tenant_id = str(current_user.tenant_id)
backend/app\routers\jobs.py:245:        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:246:        {"id": job_id, "tid": tenant_id},
backend/app\routers\jobs.py:256:        text("UPDATE jobs SET status = 'QUEUED', error_message = NULL, updated_at = now() WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:257:        {"id": job_id, "tid": tenant_id},
backend/app\routers\jobs.py:262:        text("SELECT * FROM jobs WHERE id = :id AND tenant_id = :tid"),
backend/app\routers\jobs.py:263:        {"id": job_id, "tid": tenant_id},
backend/app\services\chat_service.py:49:        tenant_id: UUID,
backend/app\services\chat_service.py:64:                    Conversation.tenant_id == tenant_id
backend/app\services\chat_service.py:77:                tenant_id=tenant_id,
backend/app\services\chat_service.py:95:        # TODO: Audit chat_message_received (tenant_id, user_id, conversation_id, intent)
backend/app\services\chat_service.py:104:                    tenant_id=tenant_id,
backend/app\services\chat_service.py:113:                    href=f"/jobs/{job_id}",
backend/app\alembic\versions\2026_02_16_0002_chat_history.py:24:        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
backend/app\alembic\versions\2026_02_16_0002_chat_history.py:30:        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
backend/app\alembic\versions\2026_02_16_0002_chat_history.py:33:    op.create_index(op.f('idx_conversations_tenant_user'), 'conversations', ['tenant_id', 'user_id'], unique=False)
backend/app\alembic\versions\2026_02_16_0002_chat_history.py:53:    op.drop_index(op.f('idx_conversations_tenant_user'), table_name='conversations')
backend/app\tasks\task_c_simulation.py:20:    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
backend/app\tasks\task_c_simulation.py:27:CREATE INDEX IF NOT EXISTS idx_simulations_tenant ON simulations(tenant_id);
backend/app\tasks\task_c_simulation.py:45:    tenant_id: str,
backend/app\tasks\task_c_simulation.py:46:    tenant_slug: str,
backend/app\tasks\task_c_simulation.py:72:    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
backend/app\tasks\task_c_simulation.py:134:                INSERT INTO simulations (id, tenant_id, name, base_scenario, scenarios, result)
backend/app\tasks\task_c_simulation.py:140:                "tid": tenant_id,
backend/app\tasks\task_c_simulation.py:153:        tenant_id=tenant_id,
backend/app\tasks\task_c_simulation.py:163:    logger.info("Task C [%s] simulation=%s scenarios=%d", tenant_slug, sim_id, len(scenarios))
backend/app\tasks\task_b_report.py:19:    tenant_id: str,
backend/app\tasks\task_b_report.py:20:    tenant_slug: str,
backend/app\tasks\task_b_report.py:37:    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref_date)
backend/app\tasks\task_b_report.py:116:    s3_key = f"reports/{tenant_slug}/{reference_period}/compliance_{now_str}.md"
backend/app\tasks\task_b_report.py:121:        metadata={"tenant": tenant_slug, "period": reference_period},
backend/app\tasks\task_b_report.py:128:        tenant_id=tenant_id,
backend/app\tasks\task_b_report.py:130:        entity_id=f"{tenant_slug}/{reference_period}",
backend/app\tasks\task_b_report.py:138:        tenant_id=tenant_id,
backend/app\tasks\task_b_report.py:141:        entity_id=f"{tenant_slug}/{reference_period}",
backend/app\tasks\task_b_report.py:158:    logger.info("Task B [%s] report=%s status=%s", tenant_slug, s3_key, result["status"])
backend/app\tasks\task_e_hubspot.py:43:    tenant_id: str,
backend/app\tasks\task_e_hubspot.py:44:    tenant_slug: str,
backend/app\tasks\task_e_hubspot.py:63:    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
backend/app\tasks\task_e_hubspot.py:78:            "tribultz_tenant": tenant_slug,
backend/app\tasks\task_e_hubspot.py:83:    deal_name = f"Tribultz – {company_name} ({tenant_slug})"
backend/app\tasks\task_e_hubspot.py:114:        tenant_id=tenant_id,
backend/app\tasks\task_e_hubspot.py:133:    logger.info("Task E [%s] score=%d hubspot=%s", tenant_slug, score, settings.HUBSPOT_ENABLED)
backend/app\tasks\task_d_reconciliation.py:25:    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
backend/app\tasks\task_d_reconciliation.py:33:CREATE INDEX IF NOT EXISTS idx_recon_tenant ON reconciliation_runs(tenant_id);
backend/app\tasks\task_d_reconciliation.py:51:    tenant_id: str,
backend/app\tasks\task_d_reconciliation.py:52:    tenant_slug: str,
backend/app\tasks\task_d_reconciliation.py:169:                    (id, tenant_id, total_records, matched, exceptions, details)
backend/app\tasks\task_d_reconciliation.py:175:                "tid": tenant_id,
backend/app\tasks\task_d_reconciliation.py:188:    s3_key = f"reconciliation/{tenant_slug}/{now_str}_exceptions.json"
backend/app\tasks\task_d_reconciliation.py:193:        tenant_id=tenant_id,
backend/app\tasks\task_d_reconciliation.py:211:    logger.info("Task D [%s] run=%s matched=%d exceptions=%d", tenant_slug, run_id, matched, len(exceptions))
backend/app\tasks\task_a_validate.py:18:    tenant_id: str,
backend/app\tasks\task_a_validate.py:19:    tenant_slug: str,
backend/app\tasks\task_a_validate.py:47:        rules = get_tax_rules(tenant_id, list(all_codes), ref_date)
backend/app\tasks\task_a_validate.py:105:            tenant_id=tenant_id,
backend/app\tasks\task_a_validate.py:117:        logger.info("Task A [%s] invoice=%s status=%s", tenant_slug, invoice_number, status)
backend/app\routers\tasks.py:24:def _get_tenant_slug(db: Session, tenant_id: str) -> str:
backend/app\routers\tasks.py:26:        text("SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)"),
backend/app\routers\tasks.py:27:        {"id": tenant_id}
backend/app\routers\tasks.py:30:        raise HTTPException(404, f"Tenant {tenant_id} not found")
backend/app\routers\tasks.py:60:    tenant_id = str(current_user.tenant_id)
backend/app\routers\tasks.py:61:    tenant_slug = _get_tenant_slug(db, tenant_id)
backend/app\routers\tasks.py:66:            tenant_id=tenant_id,
backend/app\routers\tasks.py:67:            tenant_slug=tenant_slug,
backend/app\routers\tasks.py:76:        tenant_id=tenant_id,
backend/app\routers\tasks.py:77:        tenant_slug=tenant_slug,
backend/app\routers\tasks.py:114:    tenant_id = str(current_user.tenant_id)
backend/app\routers\tasks.py:115:    tenant_slug = _get_tenant_slug(db, tenant_id)
backend/app\routers\tasks.py:120:            tenant_id=tenant_id,
backend/app\routers\tasks.py:121:            tenant_slug=tenant_slug,
backend/app\routers\tasks.py:129:        tenant_id=tenant_id,
backend/app\routers\tasks.py:130:        tenant_slug=tenant_slug,
backend/app\routers\tasks.py:161:    tenant_id = str(current_user.tenant_id)
backend/app\routers\tasks.py:162:    tenant_slug = _get_tenant_slug(db, tenant_id)
backend/app\routers\tasks.py:167:            tenant_id=tenant_id,
backend/app\routers\tasks.py:168:            tenant_slug=tenant_slug,
backend/app\routers\tasks.py:176:        tenant_id=tenant_id,
backend/app\routers\tasks.py:177:        tenant_slug=tenant_slug,
backend/app\routers\tasks.py:206:    tenant_id = str(current_user.tenant_id)
backend/app\routers\tasks.py:207:    tenant_slug = _get_tenant_slug(db, tenant_id)
backend/app\routers\tasks.py:212:            tenant_id=tenant_id,
backend/app\routers\tasks.py:213:            tenant_slug=tenant_slug,
backend/app\routers\tasks.py:220:        tenant_id=tenant_id,
backend/app\routers\tasks.py:221:        tenant_slug=tenant_slug,
backend/app\routers\tasks.py:247:    tenant_id = str(current_user.tenant_id)
backend/app\routers\tasks.py:248:    tenant_slug = _get_tenant_slug(db, tenant_id)
backend/app\routers\tasks.py:252:            tenant_id=tenant_id,
backend/app\routers\tasks.py:253:            tenant_slug=tenant_slug,
backend/app\routers\tasks.py:263:        tenant_id=tenant_id,
backend/app\routers\tasks.py:264:        tenant_slug=tenant_slug,
backend/app\routers\validate.py:65:    tenant_id: str,
backend/app\routers\validate.py:75:            WHERE tr.tenant_id = CAST(:tenant_id AS uuid)
backend/app\routers\validate.py:84:            "tenant_id": tenant_id,
backend/app\routers\validate.py:94:            detail=f"Rule '{rule_code}' ({tax_type}) not found for tenant "
backend/app\routers\validate.py:95:                   f"'{tenant_id}' on {ref_date}",
backend/app\routers\validate.py:115:    tenant_id = str(current_user.tenant_id)
backend/app\routers\validate.py:119:            db, tenant_id, item.cbs_rule_code, "CBS", req.issue_date,
backend/app\routers\validate.py:122:            db, tenant_id, item.ibs_rule_code, "IBS", req.issue_date,
backend/app\routers\validation.py:27:    # tenant_slug: str = Field(..., min_length=1, max_length=100) -- REMOVED
backend/app\routers\validation.py:105:    tenant_id = str(current_user.tenant_id)
backend/app\routers\validation.py:111:            WHERE tr.tenant_id = CAST(:tenant_id AS uuid)
backend/app\routers\validation.py:119:            "tenant_id": tenant_id,
backend/app\routers\validation.py:128:            detail=f"No {req.tax_type.value} rule found for tenant '{tenant_id}' "
backend/app\routers\validation.py:164:    """Return all active tax rules for a tenant, optionally filtered."""
backend/app\routers\validation.py:166:    tenant_id = str(current_user.tenant_id)
backend/app\routers\validation.py:167:    params: dict = {"tenant_id": tenant_id, "ref_date": ref}
backend/app\routers\validation.py:179:            WHERE tr.tenant_id = CAST(:tenant_id AS uuid)
backend/app\tools\postgres_tool.py:21:    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
backend/app\tools\postgres_tool.py:30:    UNIQUE (tenant_id, idempotency_key)
backend/app\tools\postgres_tool.py:32:CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
backend/app\tools\postgres_tool.py:33:CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status);
backend/app\tools\postgres_tool.py:44:    tenant_id: str,
backend/app\tools\postgres_tool.py:69:                    (id, tenant_id, user_id, action, entity_type, entity_id, payload)
backend/app\tools\postgres_tool.py:77:                "tid": tenant_id,
backend/app\tools\postgres_tool.py:94:    tenant_id: str,
backend/app\tools\postgres_tool.py:99:    Return active tax rules for the given tenant and rule_codes.
backend/app\tools\postgres_tool.py:106:        params: dict[str, Any] = {"tid": tenant_id, "ref": ref}
backend/app\tools\postgres_tool.py:115:                WHERE tenant_id = CAST(:tid AS uuid)
backend/app\tools\postgres_tool.py:141:    tenant_id: str,
backend/app\tools\postgres_tool.py:160:        tenant_id=tenant_id,
backend/app\tools\postgres_tool.py:169:def get_tenant_slug(tenant_id: str) -> str:
backend/app\tools\postgres_tool.py:170:    """Resolve tenant slug from tenant UUID string."""
backend/app\tools\postgres_tool.py:174:            text("SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)"),
backend/app\tools\postgres_tool.py:175:            {"id": tenant_id},
backend/app\tools\postgres_tool.py:178:            raise ValueError(f"Tenant not found for id={tenant_id}")
backend/app\tools\postgres_tool.py:187:    tenant_id: str,
backend/app\tools\postgres_tool.py:199:                INSERT INTO jobs (id, tenant_id, job_type, status, idempotency_key, payload)
backend/app\tools\postgres_tool.py:202:                    CAST(:tenant_id AS uuid),
backend/app\tools\postgres_tool.py:212:                "tenant_id": tenant_id,
backend/app\tools\validation_tool.py:57:    tenant_id: str,
backend/app\tools\validation_tool.py:66:    rules = get_tax_rules(tenant_id, rule_codes, ref)
backend/app\tools\validation_tool.py:82:    tenant_id: str,
backend/app\tools\validation_tool.py:103:    rules = get_tax_rules(tenant_id, list(all_codes), ref)
```

## Auth login + rate limiting (429)

```text
backend\tests\test_auth.py:91:        "/api/v1/auth/login",
backend\tests\test_auth.py:106:        "/api/v1/auth/login",
backend\tests\test_auth.py:123:        "/api/v1/auth/login",
backend\tests\test_auth.py:136:        "/api/v1/auth/login",
backend\app\api\deps.py:15:oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
backend\app\services\chat_service.py:14:from app.services.rate_limit import RateLimiter
backend\app\services\chat_service.py:43:        self.rate_limiter = RateLimiter() # Can inject singleton
backend\app\services\chat_service.py:56:        self.rate_limiter.check_or_raise(str(user_id))
backend\app\services\rate_limit.py:12:class RateLimiter:
backend\app\services\rate_limit.py:28:                logger.info(f"RateLimiter connected to Redis: {settings.REDIS_URL}")
backend\app\services\rate_limit.py:30:                logger.warning(f"RateLimiter failed to connect to Redis: {e}. Fallback to in-memory.")
backend\app\services\rate_limit.py:35:        Check limit for key (usually user_id). Raises 429 if exceeded.
backend\app\services\rate_limit.py:58:                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
backend\app\services\rate_limit.py:62:            logger.error(f"Redis error in RateLimiter: {e}")
backend\app\services\rate_limit.py:81:                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
```

## Message length validation (422 > 4000)

```text
backend\requirements.txt:3:pydantic[email]==2.10.4
backend\requirements.txt:4:pydantic-settings==2.7.1
backend\app\config.py:3:from pydantic_settings import BaseSettings
backend\tests\api\test_chat.py:86:def test_chat_payload_validation_max_length():
backend\app\routers\audit.py:7:from pydantic import BaseModel, Field
backend\app\api\deps.py:36:        # Validate structure with Pydantic
backend\app\api\deps.py:42:        # Pydantic validation error or other issuer
backend\app\routers\chat.py:4:from pydantic import BaseModel, Field, UUID4
backend\app\routers\chat.py:18:    message: str = Field(..., min_length=1, max_length=4000)
backend\app\routers\validation.py:7:from pydantic import BaseModel, Field, field_validator
backend\app\routers\validation.py:27:    # tenant_slug: str = Field(..., min_length=1, max_length=100) -- REMOVED
backend\app\routers\validation.py:29:    ncm_code: Optional[str] = Field(None, max_length=10)
backend\app\routers\validation.py:50:    cnpj: str = Field(..., min_length=14, max_length=18)
backend\app\routers\validate.py:7:from pydantic import BaseModel, Field
backend\app\tools\erp_connector_tool.py:11:from pydantic import BaseModel, Field
backend\app\routers\tasks.py:7:from pydantic import BaseModel
backend\app\schemas\auth.py:2:from pydantic import BaseModel, EmailStr
backend\app\routers\jobs.py:8:from pydantic import BaseModel, Field
backend\app\schemas\chat.py:1:from pydantic import BaseModel, ConfigDict
```

## Existing test fixtures (TestClient/db/tenant/user)

```text
backend/tests\test_smoke.py:12:from fastapi.testclient import TestClient
backend/tests\test_smoke.py:16:client = TestClient(app)
backend/tests\test_auth.py:3:from fastapi.testclient import TestClient
backend/tests\test_auth.py:19:@pytest.fixture(scope="module")
backend/tests\test_auth.py:30:@pytest.fixture(name="session")
backend/tests\test_auth.py:31:def session_fixture(db_engine):
backend/tests\test_auth.py:48:@pytest.fixture(name="client")
backend/tests\test_auth.py:49:def client_fixture(session):
backend/tests\test_auth.py:54:    yield TestClient(app)
backend/tests\test_auth.py:58:@pytest.fixture
backend/tests\test_auth.py:70:@pytest.fixture
backend/tests\api\test_chat.py:3:from fastapi.testclient import TestClient
backend/tests\api\test_chat.py:11:client = TestClient(app)
backend/tests\api\test_chat.py:25:@pytest.fixture
```
