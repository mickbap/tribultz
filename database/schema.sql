-- ============================================================
-- Tribultz – Multi-Tenant DDL
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- 1. Tenants
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200)  NOT NULL,
    slug        VARCHAR(100)  NOT NULL UNIQUE,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 2. Users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email       VARCHAR(255)  NOT NULL,
    full_name   VARCHAR(200)  NOT NULL,
    password_hash TEXT         NOT NULL,
    role        VARCHAR(50)   NOT NULL DEFAULT 'user',
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

-- ------------------------------------------------------------
-- 3. Companies (contribuintes)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cnpj        VARCHAR(18)   NOT NULL,
    legal_name  VARCHAR(300)  NOT NULL,
    trade_name  VARCHAR(300),
    state_code  CHAR(2),
    city_code   VARCHAR(10),
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cnpj)
);

CREATE INDEX IF NOT EXISTS idx_companies_tenant ON companies(tenant_id);

-- ------------------------------------------------------------
-- 4. Tax Rules (alíquotas / regras tributárias)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tax_rules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_code   VARCHAR(50)   NOT NULL,
    description VARCHAR(500),
    tax_type    VARCHAR(20)   NOT NULL,            -- CBS, IBS, IS
    rate        NUMERIC(10,4) NOT NULL DEFAULT 0,
    valid_from  DATE          NOT NULL,
    valid_to    DATE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, rule_code, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_tax_rules_tenant ON tax_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tax_rules_type   ON tax_rules(tenant_id, tax_type);

-- ------------------------------------------------------------
-- 5. NCM Codes (Nomenclatura Comum do Mercosul)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ncm_codes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        VARCHAR(10)   NOT NULL,
    description VARCHAR(500),
    cbs_rate    NUMERIC(10,4),
    ibs_rate    NUMERIC(10,4),
    is_exempt   BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_ncm_codes_tenant ON ncm_codes(tenant_id);

-- ------------------------------------------------------------
-- 6. Invoices (notas fiscais / documentos)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id    UUID          NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    invoice_number VARCHAR(60)  NOT NULL,
    invoice_type  VARCHAR(30)   NOT NULL DEFAULT 'NF-e',
    status        VARCHAR(30)   NOT NULL DEFAULT 'draft',
    issue_date    DATE          NOT NULL DEFAULT CURRENT_DATE,
    total_amount  NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_cbs     NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_ibs     NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_is      NUMERIC(18,2) NOT NULL DEFAULT 0,
    notes         TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, company_id, invoice_number)
);

CREATE INDEX IF NOT EXISTS idx_invoices_tenant  ON invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(tenant_id, company_id);

-- ------------------------------------------------------------
-- 7. Invoice Items (itens da nota)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoice_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id    UUID          NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    ncm_code      VARCHAR(10),
    description   VARCHAR(500)  NOT NULL,
    quantity      NUMERIC(14,4) NOT NULL DEFAULT 1,
    unit_price    NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_price   NUMERIC(18,2) NOT NULL DEFAULT 0,
    cbs_rate      NUMERIC(10,4) NOT NULL DEFAULT 0,
    cbs_amount    NUMERIC(18,2) NOT NULL DEFAULT 0,
    ibs_rate      NUMERIC(10,4) NOT NULL DEFAULT 0,
    ibs_amount    NUMERIC(18,2) NOT NULL DEFAULT 0,
    is_rate       NUMERIC(10,4) NOT NULL DEFAULT 0,
    is_amount     NUMERIC(18,2) NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_tenant  ON invoice_items(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);

-- ------------------------------------------------------------
-- 8. Credits (créditos tributários)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tax_credits (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id    UUID          NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    tax_type      VARCHAR(20)   NOT NULL,
    credit_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    reference_period VARCHAR(7) NOT NULL,          -- YYYY-MM
    origin_invoice_id UUID      REFERENCES invoices(id),
    status        VARCHAR(30)   NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tax_credits_tenant  ON tax_credits(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tax_credits_company ON tax_credits(tenant_id, company_id);

-- ------------------------------------------------------------
-- 9. Audit Log
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID          REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100)  NOT NULL,
    entity_type VARCHAR(100),
    entity_id   UUID,
    payload     JSONB,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Default tenant
INSERT INTO tenants (name, slug) VALUES ('Default Tenant', 'default')
ON CONFLICT (slug) DO NOTHING;

-- Standard CBS rate 2026
INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
SELECT t.id, 'STD_CBS', 'Aliquota padrão CBS 2026', 'CBS', 0.0925, '2026-01-01'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;

-- Standard IBS rate 2026
INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
SELECT t.id, 'STD_IBS', 'Aliquota padrão IBS 2026', 'IBS', 0.1200, '2026-01-01'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;
