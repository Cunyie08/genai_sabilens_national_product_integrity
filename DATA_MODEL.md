# SabiLens Data Model & Relationships

## 🗺️ Entity Relationship Diagram (Simplified)

```
users (1) ──────── (N) scans
     │
     ├──────────── (N) reports  
     ├──────────── (N) sessions
     ├──────────── (N) notifications
     └──────────── (N) otp_verifications

scans (1) ────── (1) scan_analyses
      │
      └────────── (N) reports

companies (1) ────────── (N) products
       │
       ├──────────────── (N) company_api_keys
       ├──────────────── (N) company_settings
       ├──────────────── (N) subscription_plans
       ├──────────────── (N) webhook_logs
       └──────────────── (N) alerts

products (1) ────────── (N) product_embeddings
       │
       ├────────────── (N) product_barcodes
       └────────────── (N) scans

reports (1) ────────── (N) report_evidence
    │
    ├─────────────── (1) alerts
    └─────────────── (1) cases

cases (1) ────────────── (N) enforcement_actions
   │
   └────────────────── (1) reports

alerts ────── companies, users, nafdac_officers

hotspots (geographical) ── cluster of scans/reports
```

---

## 📋 Table Schemas

### users
```
id (UUID) [PK]
email (String) [UNIQUE]
phone (String) [UNIQUE]
password_hash (String)
first_name (String)
last_name (String)
role (Enum: consumer|company_admin|nafdac_officer|nafdac_admin)
status (Enum: pending|active|suspended|deleted)
phone_verified (Boolean)
email_verified (Boolean)
last_login (DateTime)
created_at (DateTime)
updated_at (DateTime)
deleted_at (DateTime) [SOFT DELETE]
```

### sessions
```
id (UUID) [PK]
user_id (UUID) [FK → users]
refresh_token (String)
expires_at (DateTime)
created_at (DateTime)
```

### otp_verifications
```
id (UUID) [PK]
user_id (UUID) [FK → users] [NULLABLE]
phone (String)
email (String) [NULLABLE]
otp_code (String)
purpose (String: registration|email_verification|password_reset|phone_change)
verified_at (DateTime) [NULLABLE]
expires_at (DateTime)
created_at (DateTime)
```

### scans
```
id (UUID) [PK]
user_id (UUID) [FK → users]
product_id (UUID) [FK → products] [NULLABLE]
image_url (String)
barcode (String) [NULLABLE]
latitude (Float) [NULLABLE]
longitude (Float) [NULLABLE]
location_text (String)
status (Enum: pending|analyzing|authentic|caution|counterfeit)
created_at (DateTime)
updated_at (DateTime)
```

### scan_analyses
```
id (UUID) [PK]
scan_id (UUID) [FK → scans] [UNIQUE]
confidence_score (Float: 0.0-1.0)
visual_analysis (JSON)
ocr_analysis (JSON)
regulatory_check (JSON)
fusion_result (JSON)
risk_level (Enum: low|medium|high|critical)
recommendation (Text)
created_at (DateTime)
```

### products
```
id (UUID) [PK]
category_id (UUID) [FK → product_categories] [NULLABLE]
company_id (UUID) [FK → companies] [NULLABLE]
nafdac_number (String) [UNIQUE] [NULLABLE]
name (String)
manufacturer (String)
description (Text)
is_approved (Boolean)
created_at (DateTime)
updated_at (DateTime)
```

### product_embeddings
```
id (UUID) [PK]
product_id (UUID) [FK → products]
embedding_type (Enum: visual|ocr|regulatory|fusion|multi_modal)
embedding_vector (VECTOR[1536]) [pgvector extension]
confidence (Float)
created_at (DateTime)
```

### product_barcodes
```
id (UUID) [PK]
product_id (UUID) [FK → products]
barcode_value (String) [UNIQUE]
barcode_type (Enum: ean13|ean8|code128|qr)
is_primary (Boolean)
created_at (DateTime)
```

### reports
```
id (UUID) [PK]
user_id (UUID) [FK → users]
scan_id (UUID) [FK → scans] [NULLABLE]
description (Text)
status (Enum: open|investigating|resolved|closed)
severity (Enum: low|medium|high|critical)
created_at (DateTime)
updated_at (DateTime)
```

### report_evidence
```
id (UUID) [PK]
report_id (UUID) [FK → reports]
evidence_type (String: photo|video|document|audio|receipt)
file_url (String)
description (Text)
created_at (DateTime)
```

### companies
```
id (UUID) [PK]
name (String)
registration_number (String) [UNIQUE]
email (String)
phone (String)
address (Text)
city (String)
state (String)
status (Enum: pending|verified|suspended)
subscription_tier (String)
created_at (DateTime)
updated_at (DateTime)
```

### company_api_keys
```
id (UUID) [PK]
company_id (UUID) [FK → companies]
key_name (String)
api_key (String) [UNIQUE]
last_used_at (DateTime) [NULLABLE]
created_at (DateTime)
expires_at (DateTime) [NULLABLE]
```

### alerts
```
id (UUID) [PK]
report_id (UUID) [FK → reports] [NULLABLE]
company_id (UUID) [FK → companies] [NULLABLE]
alert_type (Enum: counterfeit_detected|suspicious_activity|enforcement_action)
severity (Enum: critical|high|medium|low)
title (String)
message (Text)
alert_data (JSON)
is_read (Boolean)
is_acknowledged (Boolean)
acknowledged_by (UUID) [FK → users] [NULLABLE]
acknowledged_at (DateTime) [NULLABLE]
created_at (DateTime)
```

### cases
```
id (UUID) [PK]
report_id (UUID) [FK → reports]
case_number (String) [UNIQUE]
status (Enum: open|investigating|pending_approval|closed)
severity (Enum: low|medium|high|critical)
description (Text)
assigned_officer_id (UUID) [FK → users] [NULLABLE]
resolution (Text) [NULLABLE]
opened_at (DateTime)
closed_at (DateTime) [NULLABLE]
created_at (DateTime)
```

### enforcement_actions
```
id (UUID) [PK]
case_id (UUID) [FK → cases]
action_type (Enum: raid|seizure|warning_notice|fine|product_recall)
location (String)
quantity_seized (Integer) [NULLABLE]
value_seized (Decimal) [NULLABLE]
description (Text)
officer_id (UUID) [FK → users]
created_at (DateTime)
```

### hotspots
```
id (UUID) [PK]
location (POINT) [PostGIS geometry]
latitude (Float)
longitude (Float)
city (String)
state (String)
counterfeit_count (Integer)
total_scans (Integer)
risk_score (Float: 0.0-1.0)
updated_at (DateTime)
```

### vendor_locations
```
id (UUID) [PK]
location (POINT) [PostGIS geometry]
latitude (Float)
longitude (Float)
vendor_name (String)
product_id (UUID) [FK → products] [NULLABLE]
reports_count (Integer)
last_flagged (DateTime) [NULLABLE]
created_at (DateTime)
```

### notifications
```
id (UUID) [PK]
user_id (UUID) [FK → users]
notification_type (Enum: scan_result|report_update|alert|system|achievement)
title (String)
message (Text)
related_id (UUID) [NULLABLE] - FK to scan/report/case
is_read (Boolean)
channel (Enum: push|email|sms|in_app)
created_at (DateTime)
```

### audit_logs
```
id (UUID) [PK]
user_id (UUID) [FK → users] [NULLABLE]
action (String) - What was done
resource_type (String) - What was affected
resource_id (UUID)
changes (JSON) - Before/after values
ip_address (String)
user_agent (String)
created_at (DateTime)
```

---

## 🔗 Key Relationships

### User → Scans (1:N)
A consumer can submit multiple scans for product verification.

### Scan → ScanAnalysis (1:1)
A scan has exactly one analysis record with AI predictions.

### User → Reports (1:N)
A consumer can file multiple counterfeit reports.

### Report → ReportEvidence (1:N)
A report can have multiple pieces of evidence (photos, videos, documents).

### Report → Case (1:1)
A report triggers a NAFDAC investigation case.

### Case → EnforcementActions (1:N)
A case results in multiple enforcement actions (raid, seizure, notices).

### Product → ProductEmbeddings (1:N)
A product has multiple AI embeddings (visual, OCR, regulatory, fusion).

### Company → CompanyAPIKeys (1:N)
A company can have multiple API keys for different integrations.

### Alert → Company|User (N:M)
Alerts are broadcast to companies and NAFDAC officers.

---

## 🔍 Query Patterns

### Find Scans by User
```sql
SELECT s.* FROM scans s
WHERE s.user_id = $1
ORDER BY s.created_at DESC
LIMIT 20 OFFSET 0;
```

### Find Counterfeit Rate for Product
```sql
SELECT 
  p.id, p.name,
  COUNT(s.id) total_scans,
  SUM(CASE WHEN sa.risk_level = 'high' THEN 1 ELSE 0 END) counterfeit_count,
  ROUND(SUM(CASE WHEN sa.risk_level = 'high' THEN 1 ELSE 0 END)::numeric / COUNT(s.id) * 100, 2) counterfeit_rate
FROM products p
LEFT JOIN scans s ON p.id = s.product_id
LEFT JOIN scan_analyses sa ON s.id = sa.scan_id
GROUP BY p.id, p.name
ORDER BY counterfeit_rate DESC;
```

### Find Hotspots (Geographic Clustering)
```sql
SELECT 
  ST_AsText(ST_ClusterCentroid(ST_Collect(location))) as hotspot,
  COUNT(*) as incident_count,
  COUNT(DISTINCT product_id) as unique_products
FROM scans
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY ST_ClusterDBSCAN(location, 5000, 5)  -- 5km radius, min 5 incidents
HAVING COUNT(*) >= 5;
```

### Get Recent Alerts for Company
```sql
SELECT a.* FROM alerts a
WHERE a.company_id = $1
AND a.created_at > NOW() - INTERVAL '7 days'
ORDER BY a.severity DESC, a.created_at DESC;
```

### Find Open Cases by Region
```sql
SELECT 
  s.state, s.city,
  COUNT(DISTINCT c.id) as open_cases,
  COUNT(DISTINCT r.id) as reports,
  SUM(ea.value_seized) as total_value_seized
FROM cases c
JOIN reports r ON c.report_id = r.id
JOIN scans s ON r.scan_id = s.id
LEFT JOIN enforcement_actions ea ON c.id = ea.case_id
WHERE c.status = 'open'
GROUP BY s.state, s.city
ORDER BY open_cases DESC;
```

---

## 🔐 Access Control Matrix

```
Resource          | Consumer | Company Admin | NAFDAC Officer | NAFDAC Admin
─────────────────────────────────────────────────────────────────────────
User Profile      | R (own)  | R (own)      | R (own)        | R (all)
Scan History      | R (own)  | R (company) | R (all)         | R (all)
Submit Scan       | CU       | R (company)  | R (all)         | R (all)
Create Report     | C        | C            | C               | C
View Cases        | —        | —             | R (assigned)    | R (all)
Create Case       | —        | —             | —               | C
Record Enforcement| —        | —             | CU               | CU
View Dashboard    | R (own)  | R (company)  | R (regional)    | R (national)
Export Data       | —        | —             | —               | C
```

Legend: C=Create, R=Read, U=Update, D=Delete, (—)=No access

---

## 📊 Indexing Strategy

```sql
-- Performance indexes
CREATE INDEX idx_scans_user_id ON scans(user_id);
CREATE INDEX idx_scans_created_at ON scans(created_at DESC);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_reports_user_id ON reports(user_id);
CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_alerts_company_id ON alerts(company_id);
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_products_nafdac_number ON products(nafdac_number);
CREATE INDEX idx_hotspots_location ON hotspots USING GIST(location);
```

---

**Last Updated**: March 1, 2026
**Version**: 1.0
