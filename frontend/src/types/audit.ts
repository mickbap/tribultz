export interface AuditLogItem {
    id: string;
    tenant_id: string;
    entity?: string | null;
    entity_id?: string | null;
    action: string;
    payload: unknown;
    created_at?: string | null;
    checksum?: string | null;
}

export interface AuditSearchResponse {
    items: AuditLogItem[];
    total?: number;
}
