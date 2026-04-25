"""
Celery tasks for the admin report pipeline.

generate_report(report_id: str):
  Full pipeline — data fetch → heatmap PNG → trend chart PNG → OpenAI narrative
  → Jinja2 HTML → weasyprint PDF → GCS upload → AdminReport row update.

refresh_enforcement_cases():
  Recalculates risk scores for open EnforcementCase rows every 6 hours.

daily_analytics_aggregation():
  Populates analytics_daily and analytics_regions at 1 AM Lagos time.
"""
from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — required in Celery workers

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from celery import shared_task
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from weasyprint import HTML as WeasyHTML

from backend.config import settings
from backend.core.celery_app import celery_app

logger = logging.getLogger("admin.tasks")

TEMPLATE_DIR = Path(__file__).parent / "templates"
GEOJSON_PATH = Path(__file__).parent / "assets" / "nigeria_states.geojson"
GEOJSON_STATE_COL = "NAME_1"

RISK_COLORS = {
    "critical": "#dc2626",
    "high":     "#f97316",
    "medium":   "#eab308",
    "low":      "#22c55e",
    "none":     "#e5e7eb",
}

_nigeria_gdf = None  # module-level GeoDataFrame cache


# -----------------------------------------------------------------------
# Synchronous DB session for Celery tasks (asyncpg → psycopg2)
# -----------------------------------------------------------------------

def _get_sync_session() -> Session:
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    engine = create_engine(sync_url, pool_pre_ping=True)
    return Session(engine)


# -----------------------------------------------------------------------
# Heatmap PNG
# -----------------------------------------------------------------------

def _load_nigeria_gdf():
    global _nigeria_gdf
    if _nigeria_gdf is None:
        import geopandas as gpd
        _nigeria_gdf = gpd.read_file(GEOJSON_PATH)
    return _nigeria_gdf


def generate_heatmap_png(heatmap_points: list[dict]) -> bytes:
    """Returns PNG bytes of a Nigeria choropleth map coloured by risk_level."""
    gdf = _load_nigeria_gdf().copy()

    if heatmap_points:
        df = pd.DataFrame(heatmap_points)
        gdf["_state_norm"] = gdf[GEOJSON_STATE_COL].str.strip().str.title()
        df["_state_norm"] = df["state"].str.strip().str.title()
        merged = gdf.merge(
            df[["_state_norm", "risk_level", "fake_count", "total_scans"]],
            on="_state_norm",
            how="left",
        )
    else:
        merged = gdf.copy()
        merged["risk_level"] = None
        merged["fake_count"] = 0
        merged["total_scans"] = 0

    merged["risk_level"] = merged["risk_level"].fillna("none")
    merged["color"] = merged["risk_level"].map(RISK_COLORS)

    fig, ax = plt.subplots(1, 1, figsize=(14, 12))
    merged.plot(ax=ax, color=merged["color"].tolist(), edgecolor="#ffffff", linewidth=0.6)

    legend_handles = [
        mpatches.Patch(facecolor=color, label=level.capitalize())
        for level, color in RISK_COLORS.items()
    ]
    ax.legend(handles=legend_handles, loc="lower left", title="Risk Level",
              fontsize=9, title_fontsize=10)
    ax.set_title("SabiLens — Counterfeit Risk Heatmap (Nigeria)",
                 fontsize=15, fontweight="bold", pad=12)
    ax.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# -----------------------------------------------------------------------
# Trend chart PNG
# -----------------------------------------------------------------------

def generate_trend_chart_png(trend_points: list[dict]) -> bytes:
    """Line chart: date vs authentic / suspicious / fake counts."""
    if not trend_points:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.text(0.5, 0.5, "No trend data available",
                ha="center", va="center", transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    df = pd.DataFrame(trend_points)
    df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period")

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df["period"], df["authentic_count"], label="Authentic", color="#22c55e", linewidth=2)
    ax.plot(df["period"], df["suspicious_count"], label="Suspicious", color="#eab308", linewidth=2)
    ax.plot(df["period"], df["fake_count"], label="Fake", color="#dc2626", linewidth=2)
    ax.fill_between(df["period"], df["fake_count"], alpha=0.15, color="#dc2626")
    ax.set_title("Scan Verdict Trend", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Scan Count")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# -----------------------------------------------------------------------
# OpenAI narrative
# -----------------------------------------------------------------------

OPENAI_SYSTEM_PROMPT = (
    "You are a senior product integrity analyst for SabiLens, "
    "a Nigerian anti-counterfeit intelligence platform. "
    "Your output must be valid JSON only — no markdown, no prose outside the JSON structure."
)

REPORT_SCHEMA = {
    "title": "string — descriptive report title",
    "executive_summary": "string — 3-5 sentence overview of findings",
    "key_findings": ["string — one finding per item, maximum 8 items"],
    "risk_assessment": {
        "overall_level": "critical | high | medium | low",
        "rationale": "string — 2-3 sentences explaining the risk rating",
    },
    "hotspot_analysis": [
        {
            "location": "state or state/LGA",
            "risk_level": "critical | high | medium | low",
            "fake_count": "integer",
            "fake_pct": "float",
            "observation": "string",
        }
    ],
    "product_breakdown": [
        {
            "product_name": "string",
            "nafdac_number": "string or null",
            "fake_pct": "float",
            "recommendation": "string",
        }
    ],
    "recommendations": ["string — actionable, specific, maximum 6 items"],
    "generated_at": "ISO 8601 timestamp string",
}


def call_openai_for_report(data_payload: dict, report_type: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    user_message = (
        f"Generate a '{report_type}' intelligence report for SabiLens.\n\n"
        f"Input data:\n{json.dumps(data_payload, indent=2, default=str)}\n\n"
        f"Return a JSON object matching exactly this schema:\n"
        f"{json.dumps(REPORT_SCHEMA, indent=2)}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=4096,
    )
    return json.loads(response.choices[0].message.content)


# -----------------------------------------------------------------------
# Data fetching (sync — runs inside Celery task)
# -----------------------------------------------------------------------

def _fetch_report_data(session: Session, report_id: str) -> dict:
    """Fetch AdminReport row + all aggregated scan data needed for the report."""
    row = session.execute(
        text("SELECT * FROM admin_reports WHERE id = :id"),
        {"id": report_id},
    ).mappings().one()
    report_meta = dict(row)

    company_id = report_meta.get("company_id")
    filter_state = report_meta.get("filter_state")
    filter_lga = report_meta.get("filter_lga")
    filter_date_from = report_meta.get("filter_date_from")
    filter_date_to = report_meta.get("filter_date_to")

    conditions = ["scan_location_state IS NOT NULL"]
    params: dict = {}
    if company_id:
        conditions.append("company_id = :company_id")
        params["company_id"] = str(company_id)
    if filter_state:
        conditions.append("scan_location_state = :state")
        params["state"] = filter_state
    if filter_lga:
        conditions.append("scan_location_lga = :lga")
        params["lga"] = filter_lga
    if filter_date_from:
        conditions.append("created_at >= :date_from")
        params["date_from"] = filter_date_from
    if filter_date_to:
        conditions.append("created_at <= :date_to")
        params["date_to"] = filter_date_to

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    overview_sql = f"""
        SELECT
            COUNT(*)                                                   AS total_scans,
            SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)          AS fake_count,
            SUM(CASE WHEN status = 'suspicious' THEN 1 ELSE 0 END)    AS suspicious_count,
            SUM(CASE WHEN status = 'authentic' THEN 1 ELSE 0 END)     AS authentic_count,
            ROUND(AVG(confidence_score)::numeric, 2)                   AS avg_confidence,
            COUNT(DISTINCT product_id)                                 AS total_products_scanned
        FROM scans
        {where}
    """
    ov = dict(session.execute(text(overview_sql), params).mappings().one())
    total = ov["total_scans"] or 1
    ov["fake_rate_pct"] = round((ov["fake_count"] or 0) / total * 100, 2)

    heatmap_sql = f"""
        SELECT
            scan_location_state              AS state,
            scan_location_lga                AS lga,
            market_name,
            COUNT(*)                         AS total_scans,
            SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)      AS fake_count,
            SUM(CASE WHEN status = 'suspicious' THEN 1 ELSE 0 END) AS suspicious_count,
            AVG(latitude)                    AS center_latitude,
            AVG(longitude)                   AS center_longitude
        FROM scans
        {where}
        GROUP BY scan_location_state, scan_location_lga, market_name
        ORDER BY fake_count DESC
        LIMIT 200
    """
    heatmap_rows = session.execute(text(heatmap_sql), params).mappings().all()
    heatmap_points = []
    for r in heatmap_rows:
        t = r["total_scans"] or 1
        f = r["fake_count"] or 0
        fp = round(f / t * 100, 2)
        rl = "critical" if fp > 30 else "high" if fp > 15 else "medium" if fp > 5 else "low"
        heatmap_points.append({
            "state": r["state"],
            "lga": r["lga"],
            "market_name": r["market_name"],
            "total_scans": r["total_scans"],
            "fake_count": f,
            "suspicious_count": r["suspicious_count"] or 0,
            "fake_pct": fp,
            "risk_level": rl,
            "center_latitude": float(r["center_latitude"]) if r["center_latitude"] else None,
            "center_longitude": float(r["center_longitude"]) if r["center_longitude"] else None,
        })

    # Product query: build scan-table WHERE with explicit alias
    prod_conditions = []
    prod_params: dict = {}
    if company_id:
        prod_conditions.append("s.company_id = :company_id")
        prod_params["company_id"] = str(company_id)
    if filter_date_from:
        prod_conditions.append("s.created_at >= :date_from")
        prod_params["date_from"] = filter_date_from
    if filter_date_to:
        prod_conditions.append("s.created_at <= :date_to")
        prod_params["date_to"] = filter_date_to
    prod_where = ("WHERE " + " AND ".join(prod_conditions)) if prod_conditions else ""

    product_sql = f"""
        SELECT
            p.name                           AS product_name,
            p.nafdac_number,
            COUNT(s.id)                      AS total_scans,
            SUM(CASE WHEN s.status = 'fake' THEN 1 ELSE 0 END) AS fake_count
        FROM scans s
        JOIN products p ON s.product_id = p.id
        {prod_where}
        GROUP BY p.id, p.name, p.nafdac_number
        ORDER BY fake_count DESC
        LIMIT 20
    """
    product_rows = session.execute(text(product_sql), prod_params).mappings().all()
    product_breakdown = [
        {
            "product_name": r["product_name"],
            "nafdac_number": r["nafdac_number"],
            "total_scans": r["total_scans"],
            "fake_count": r["fake_count"] or 0,
            "fake_pct": round((r["fake_count"] or 0) / max(r["total_scans"] or 1, 1) * 100, 2),
        }
        for r in product_rows
    ]

    trend_sql = f"""
        SELECT
            DATE_TRUNC('day', created_at)::date                      AS period,
            SUM(CASE WHEN status = 'authentic' THEN 1 ELSE 0 END)   AS authentic_count,
            SUM(CASE WHEN status = 'suspicious' THEN 1 ELSE 0 END)  AS suspicious_count,
            SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)        AS fake_count,
            COUNT(*)                                                  AS total_scans
        FROM scans
        {where}
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 30
    """
    trend_rows = session.execute(text(trend_sql), params).mappings().all()
    trend_points = [
        {
            "period": str(r["period"]),
            "authentic_count": r["authentic_count"] or 0,
            "suspicious_count": r["suspicious_count"] or 0,
            "fake_count": r["fake_count"] or 0,
            "total_scans": r["total_scans"] or 0,
        }
        for r in reversed(list(trend_rows))
    ]

    company_name = None
    if company_id:
        cn_row = session.execute(
            text("SELECT name FROM companies WHERE id = :id"),
            {"id": str(company_id)},
        ).fetchone()
        if cn_row:
            company_name = cn_row[0]

    return {
        "report_meta": report_meta,
        "overview": ov,
        "heatmap_points": heatmap_points,
        "product_breakdown": product_breakdown,
        "trend_points": trend_points,
        "company_name": company_name,
    }


# -----------------------------------------------------------------------
# Main report generation task
# -----------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="backend.admin.tasks.generate_report",
    max_retries=2,
    default_retry_delay=60,
)
def generate_report(self, report_id: str) -> None:
    """
    Full pipeline:
      1. Mark status=processing
      2. Fetch aggregated data
      3. Generate heatmap PNG
      4. Generate trend chart PNG
      5. Call OpenAI GPT-4o for narrative JSON
      6. Render Jinja2 HTML template
      7. Convert HTML → PDF via weasyprint
      8. Upload PDF to GCS sabilens-report-prod
      9. Mark status=ready; store gcs_key, report_json, generated_at
    On exception: mark status=failed, store error_message, retry up to 2 times.
    """
    session = _get_sync_session()
    try:
        session.execute(
            text("UPDATE admin_reports SET status='processing', updated_at=NOW() WHERE id=:id"),
            {"id": report_id},
        )
        session.commit()

        data = _fetch_report_data(session, report_id)
        report_meta = data["report_meta"]

        heatmap_bytes = generate_heatmap_png(data["heatmap_points"])
        heatmap_b64 = base64.b64encode(heatmap_bytes).decode()

        trend_bytes = generate_trend_chart_png(data["trend_points"])
        trend_b64 = base64.b64encode(trend_bytes).decode()

        ai_payload = {
            "report_type": report_meta["report_type"],
            "period": {
                "from": str(report_meta.get("filter_date_from") or "all-time"),
                "to": str(report_meta.get("filter_date_to") or "present"),
            },
            "overview": data["overview"],
            "heatmap_points": data["heatmap_points"][:20],
            "product_breakdown": data["product_breakdown"],
            "trend": data["trend_points"],
            "company_name": data["company_name"],
        }
        report_json = call_openai_for_report(ai_payload, report_meta["report_type"])

        jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        template = jinja_env.get_template("report.html")
        html_str = template.render(
            report_json=report_json,
            overview=data["overview"],
            company_name=data["company_name"],
            report_type=report_meta["report_type"],
            filter_date_from=report_meta.get("filter_date_from"),
            filter_date_to=report_meta.get("filter_date_to"),
            heatmap_b64=heatmap_b64,
            trend_b64=trend_b64,
        )

        pdf_bytes = WeasyHTML(string=html_str).write_pdf()

        from google.cloud import storage as gcs_storage
        company_id = str(report_meta.get("company_id") or "global")
        gcs_key = f"reports/{company_id}/{report_id}.pdf"
        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(settings.GCS_REPORTS_BUCKET)
        blob = bucket.blob(gcs_key)
        blob.upload_from_string(pdf_bytes, content_type="application/pdf")
        logger.info("PDF uploaded to GCS: %s", gcs_key)

        session.execute(
            text("""
                UPDATE admin_reports
                SET status      = 'ready',
                    gcs_key     = :gcs_key,
                    report_json = :report_json,
                    generated_at = NOW(),
                    updated_at   = NOW()
                WHERE id = :id
            """),
            {
                "id": report_id,
                "gcs_key": gcs_key,
                "report_json": json.dumps(report_json),
            },
        )
        session.commit()
        logger.info("Report %s marked ready.", report_id)

    except Exception as exc:
        session.execute(
            text("""
                UPDATE admin_reports
                SET status        = 'failed',
                    error_message = :err,
                    updated_at    = NOW()
                WHERE id = :id
            """),
            {"id": report_id, "err": str(exc)[:2000]},
        )
        session.commit()
        logger.exception("Report %s failed: %s", report_id, exc)
        raise self.retry(exc=exc)
    finally:
        session.close()


# -----------------------------------------------------------------------
# Scheduled tasks
# -----------------------------------------------------------------------

@celery_app.task(name="backend.admin.tasks.refresh_enforcement_cases")
def refresh_enforcement_cases() -> None:
    """
    Runs every 6 hours (see beat_schedule in celery_app.py).
    Recalculates risk_score for open cases and promotes new clusters.

    Risk score formula:
      base = fake_scan_count / max(total_scan_count, 1)
      suspicious_bonus = (suspicious_scan_count / max(total_scan_count, 1)) * 0.3
      volume_bonus = min(total_scan_count / 100, 0.2)
      risk_score = min(sum, 1.0)
    """
    session = _get_sync_session()
    try:
        session.execute(text("""
            UPDATE enforcement_cases
            SET risk_score = LEAST(
                (fake_scan_count::float / GREATEST(total_scan_count, 1))
                + (suspicious_scan_count::float / GREATEST(total_scan_count, 1)) * 0.3
                + LEAST(total_scan_count::float / 100, 0.2),
                1.0
            ),
            updated_at = NOW()
            WHERE status = 'open'
        """))

        session.execute(text("""
            INSERT INTO enforcement_cases
                (cluster_key, product_id, company_id, scan_location_state,
                 scan_location_lga, market_name, center_latitude, center_longitude,
                 fake_scan_count, suspicious_scan_count, total_scan_count,
                 risk_score, status)
            SELECT
                MD5(CONCAT(
                    s.scan_location_state, '|',
                    COALESCE(s.scan_location_lga, ''), '|',
                    COALESCE(s.product_id::text, '')
                )) AS cluster_key,
                s.product_id,
                s.company_id,
                s.scan_location_state,
                s.scan_location_lga,
                s.market_name,
                AVG(s.latitude)   AS center_latitude,
                AVG(s.longitude)  AS center_longitude,
                SUM(CASE WHEN s.status = 'fake' THEN 1 ELSE 0 END)       AS fake_scan_count,
                SUM(CASE WHEN s.status = 'suspicious' THEN 1 ELSE 0 END)  AS suspicious_scan_count,
                COUNT(*)                                                    AS total_scan_count,
                LEAST(
                    (SUM(CASE WHEN s.status = 'fake' THEN 1 ELSE 0 END)::float / COUNT(*))
                    + (SUM(CASE WHEN s.status = 'suspicious' THEN 1 ELSE 0 END)::float / COUNT(*)) * 0.3
                    + LEAST(COUNT(*)::float / 100, 0.2),
                    1.0
                ) AS risk_score,
                'open' AS status
            FROM scans s
            WHERE s.created_at >= NOW() - INTERVAL '7 days'
              AND s.scan_location_state IS NOT NULL
            GROUP BY s.scan_location_state, s.scan_location_lga, s.market_name,
                     s.product_id, s.company_id
            HAVING SUM(CASE WHEN s.status = 'fake' THEN 1 ELSE 0 END) >= 3
            ON CONFLICT (cluster_key) DO UPDATE
              SET fake_scan_count       = EXCLUDED.fake_scan_count,
                  suspicious_scan_count = EXCLUDED.suspicious_scan_count,
                  total_scan_count      = EXCLUDED.total_scan_count,
                  risk_score            = EXCLUDED.risk_score,
                  updated_at            = NOW()
        """))
        session.commit()
        logger.info("refresh_enforcement_cases: done.")
    except Exception as exc:
        session.rollback()
        logger.exception("refresh_enforcement_cases failed: %s", exc)
    finally:
        session.close()


@celery_app.task(name="backend.admin.tasks.daily_analytics_aggregation")
def daily_analytics_aggregation() -> None:
    """
    Runs at 1 AM Lagos time daily (see beat_schedule in celery_app.py).
    Upserts yesterday's data into analytics_daily and analytics_regions.
    """
    session = _get_sync_session()
    try:
        session.execute(text("""
            INSERT INTO analytics_daily
                (date, total_scans, authentic_scans, suspicious_scans,
                 counterfeit_scans, total_reports, unique_users, unique_companies)
            SELECT
                (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1             AS date,
                COUNT(*)                                                   AS total_scans,
                SUM(CASE WHEN status = 'authentic' THEN 1 ELSE 0 END)     AS authentic_scans,
                SUM(CASE WHEN status = 'suspicious' THEN 1 ELSE 0 END)    AS suspicious_scans,
                SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)          AS counterfeit_scans,
                (SELECT COUNT(*) FROM reports
                 WHERE reported_at::date =
                       (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1)     AS total_reports,
                COUNT(DISTINCT user_id)                                    AS unique_users,
                COUNT(DISTINCT company_id)                                 AS unique_companies
            FROM scans
            WHERE created_at::date =
                  (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1
            ON CONFLICT (date) DO UPDATE
              SET total_scans      = EXCLUDED.total_scans,
                  authentic_scans  = EXCLUDED.authentic_scans,
                  suspicious_scans = EXCLUDED.suspicious_scans,
                  counterfeit_scans = EXCLUDED.counterfeit_scans,
                  total_reports    = EXCLUDED.total_reports,
                  unique_users     = EXCLUDED.unique_users,
                  unique_companies = EXCLUDED.unique_companies
        """))

        session.execute(text("""
            INSERT INTO analytics_regions
                (state, period, period_start, period_end, scan_count,
                 counterfeit_count, risk_score)
            SELECT
                scan_location_state                                        AS state,
                'daily'                                                    AS period,
                (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1             AS period_start,
                (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1             AS period_end,
                COUNT(*)                                                   AS scan_count,
                SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)          AS counterfeit_count,
                ROUND(
                    SUM(CASE WHEN status = 'fake' THEN 1 ELSE 0 END)::numeric
                    / GREATEST(COUNT(*), 1) * 100, 2
                )                                                          AS risk_score
            FROM scans
            WHERE created_at::date =
                  (NOW() AT TIME ZONE 'Africa/Lagos')::date - 1
              AND scan_location_state IS NOT NULL
            GROUP BY scan_location_state
            ON CONFLICT DO NOTHING
        """))

        session.commit()
        logger.info("daily_analytics_aggregation: done.")
    except Exception as exc:
        session.rollback()
        logger.exception("daily_analytics_aggregation failed: %s", exc)
    finally:
        session.close()
