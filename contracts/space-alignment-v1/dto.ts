/** DRAFT_PENDING_OWNER_RULING. No mounted endpoint or approved action/state names. */
export type CandidateStatus = 'DRAFT_PENDING_OWNER_RULING';
export type ProposedAction = 'read_metadata'|'read_content'|'create_kb'|'attach_kb'|'detach_kb'|'manage_members'|'transfer_owner'|'freeze_archive';
export type ProposedDeliverableState = 'draft'|'generating'|'ready'|'published'|'withdrawn';
export interface Space {tenant_id:string;space_id:string;kind:'enterprise'|'team'|'personal';owner_id:string;lifecycle:'active'|'frozen'|'archived';policy_generation:number;sharing_enabled:false;offboarding_enabled:false;}
export interface Freshness {asserted_at:number;valid_until:number;policy_generation:number;}
export interface Tombstone {reason:'source_revoked'|'expired'|'unavailable';observed_generation:number;}
export type AssetEnvelope = {tenant_id:string;asset_id:string} & (
 {kind:'uploaded_document';payload:{document_id:string;version_id:string}} |
 {kind:'agent_deliverable';payload:{deliverable_id:string;state:ProposedDeliverableState}} |
 {kind:'enterprise_materialized_ref';payload:{projection_id:string;scope_applied:string[];masked_fields:('title'|'excerpt'|'source_uri')[];trace_refs:string[];freshness:Freshness;publication_state:'complete'|'partial';cursor:string|null;tombstone:Tombstone|null}});
export type FavoriteHydrated = {target_type:'kb'|'asset';target_id:string} & ({state:'available';display_name:string;policy_generation:number}|{state:'unavailable'});
export interface ToolBoundary {kind:'data_capability';capability_id:string;mediated:true;credentials_exposed:false;}
export interface HydrateRequest {tenant_id:string;subject_id:string;targets:{tenant_id:string;target_type:'kb'|'asset';target_id:string}[];}
