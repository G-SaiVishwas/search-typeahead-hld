"""Generate the Project Report PDF for the HLD101 Search Typeahead assignment.

Produces docs/Project_Report.pdf with the five required sections:
  1. Architecture diagram / explanation
  2. Dataset source and loading instructions
  3. API documentation
  4. Design choices and trade-offs
  5. Performance report
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "Project_Report.pdf"

# ---- palette -------------------------------------------------------------
INK = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#475569")
MUTED = colors.HexColor("#64748b")
BLUE = colors.HexColor("#2563eb")
LIGHT = colors.HexColor("#eff6ff")
BORDER = colors.HexColor("#e2e8f0")
GREEN = colors.HexColor("#047857")
CARD = colors.HexColor("#f8fafc")

# ---- styles --------------------------------------------------------------
styles = getSampleStyleSheet()


def style(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


H1 = style("H1", fontName="Helvetica-Bold", fontSize=17, textColor=INK,
           spaceBefore=14, spaceAfter=8, leading=21)
H2 = style("H2", fontName="Helvetica-Bold", fontSize=12.5, textColor=BLUE,
           spaceBefore=10, spaceAfter=5, leading=16)
BODY = style("BODY", fontName="Helvetica", fontSize=9.7, textColor=SLATE,
             leading=14.5, spaceAfter=6, alignment=TA_LEFT)
BODY_INK = style("BODYINK", parent=BODY, textColor=INK)
SMALL = style("SMALL", fontName="Helvetica", fontSize=8.3, textColor=MUTED,
              leading=11.5)
CODE = style("CODE", fontName="Courier", fontSize=8.2, textColor=INK,
             leading=11.5, backColor=CARD, borderColor=BORDER, borderWidth=0.5,
             borderPadding=6, spaceAfter=6)
BULLET = style("BULLET", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=3)


def bullets(items):
    return [Paragraph(f"\u2022 {t}", BULLET) for t in items]


# ---- architecture diagram (vector) --------------------------------------
def architecture_drawing() -> Drawing:
    W, H = 16.8 * cm, 8.6 * cm
    d = Drawing(W, H)

    def box(x, y, w, h, label, sub=None, fill=colors.white, stroke=BORDER,
            txt=INK, bold=True):
        d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=stroke,
                   strokeWidth=1))
        fn = "Helvetica-Bold" if bold else "Helvetica"
        if sub:
            d.add(String(x + w / 2, y + h / 2 + 3, label, fontName=fn,
                         fontSize=8.4, fillColor=txt, textAnchor="middle"))
            d.add(String(x + w / 2, y + h / 2 - 7, sub, fontName="Helvetica",
                         fontSize=6.6, fillColor=MUTED, textAnchor="middle"))
        else:
            d.add(String(x + w / 2, y + h / 2 - 3, label, fontName=fn,
                         fontSize=8.4, fillColor=txt, textAnchor="middle"))
        return (x, y, w, h)

    def arrow(x1, y1, x2, y2, label=None, color=SLATE, dashed=False):
        ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.1)
        if dashed:
            ln.strokeDashArray = [3, 2]
        d.add(ln)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        sz = 5
        d.add(Polygon([
            x2, y2,
            x2 - sz * math.cos(ang - 0.5), y2 - sz * math.sin(ang - 0.5),
            x2 - sz * math.cos(ang + 0.5), y2 - sz * math.sin(ang + 0.5),
        ], fillColor=color, strokeColor=color))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            d.add(String(mx, my + 3, label, fontName="Helvetica", fontSize=6.2,
                         fillColor=MUTED, textAnchor="middle"))

    # columns (x), rows (y)
    box(0.2 * cm, 6.5 * cm, 3.4 * cm, 1.4 * cm, "React UI",
        "debounced 150ms", fill=LIGHT, stroke=BLUE)
    box(6.2 * cm, 6.5 * cm, 4.0 * cm, 1.4 * cm, "FastAPI Service",
        "suggest / search / debug", fill=colors.white, stroke=BLUE)
    box(12.0 * cm, 6.5 * cm, 4.6 * cm, 1.4 * cm, "Cache Ring",
        "redis-0 / 1 / 2  -  150 vnodes", fill=LIGHT, stroke=BLUE)

    box(6.2 * cm, 3.9 * cm, 4.0 * cm, 1.4 * cm, "Top-K Trie",
        "in-memory, O(prefix)", fill=CARD)
    box(12.0 * cm, 3.9 * cm, 4.6 * cm, 1.4 * cm, "Write Buffer",
        "batch flush 500 / 2s", fill=CARD)
    box(6.2 * cm, 1.4 * cm, 4.0 * cm, 1.4 * cm, "SQLite",
        "durable query counts", fill=CARD)

    # arrows
    arrow(3.6 * cm, 7.2 * cm, 6.2 * cm, 7.2 * cm, "GET / POST")
    arrow(10.2 * cm, 7.2 * cm, 12.0 * cm, 7.2 * cm, "shard", color=BLUE)
    arrow(8.2 * cm, 6.5 * cm, 8.2 * cm, 5.3 * cm, "miss")
    arrow(8.2 * cm, 3.9 * cm, 8.2 * cm, 2.8 * cm, "build", dashed=True)
    arrow(10.2 * cm, 6.7 * cm, 12.0 * cm, 5.5 * cm, "enqueue")
    arrow(12.6 * cm, 3.9 * cm, 9.2 * cm, 2.7 * cm, "flush")
    arrow(15.6 * cm, 5.3 * cm, 15.6 * cm, 6.5 * cm, "invalidate", color=GREEN,
          dashed=True)
    return d


# ---- page chrome ---------------------------------------------------------
def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(2 * cm, A4[1] - 1.1 * cm, "Search Typeahead System")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.1 * cm,
                           "HLD101 Project Report")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, A4[1] - 1.3 * cm, A4[0] - 2 * cm, A4[1] - 1.3 * cm)
    canvas.line(2 * cm, 1.3 * cm, A4[0] - 2 * cm, 1.3 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 0.9 * cm, f"Page {doc.page}")
    canvas.restoreState()


CELL = style("CELL", fontName="Helvetica", fontSize=8.5, textColor=SLATE,
             leading=11)
CELL_H = style("CELLH", fontName="Helvetica-Bold", fontSize=8.5,
               textColor=colors.white, leading=11)


def tbl(data, col_widths, header=True):
    wrapped = []
    for r, row in enumerate(data):
        st = CELL_H if (header and r == 0) else CELL
        wrapped.append([
            c if not isinstance(c, str) else Paragraph(c.replace("&", "&amp;"), st)
            for c in row
        ])
    data = wrapped
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), SLATE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(cmds))
    return t


def build():
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.7 * cm, bottomMargin=1.6 * cm,
        title="HLD101 Search Typeahead - Project Report",
        author="G-SaiVishwas",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=header_footer)])

    e = []

    # ---- title block ----
    e.append(Spacer(1, 18))
    e.append(Paragraph("Search Typeahead System",
                       style("title", fontName="Helvetica-Bold", fontSize=26,
                             textColor=INK, leading=30)))
    e.append(Paragraph("HLD101 Assignment &mdash; Project Report",
                       style("sub", fontName="Helvetica", fontSize=12,
                             textColor=BLUE, spaceAfter=10)))
    e.append(Paragraph(
        "A prefix typeahead system with an in-memory top-K trie, a distributed "
        "Redis cache sharded by consistent hashing, recency-aware trending, and "
        "batched search-count writes, served through a FastAPI backend and a "
        "React UI.", BODY))
    e.append(Spacer(1, 6))
    meta = tbl([
        ["Repository", "github.com/G-SaiVishwas/search-typeahead-hld"],
        ["Stack", "FastAPI + SQLite + Redis x3 + React (Vite)"],
        ["Dataset", "AOL User Session Collection (500k), Kaggle"],
        ["Scale", "1,244,453 seed queries / 2,969,752 raw events"],
    ], [3.6 * cm, 11 * cm], header=False)
    e.append(meta)
    e.append(Spacer(1, 10))

    # ---- 1. architecture ----
    e.append(Paragraph("1. Architecture", H1))
    e.append(Paragraph(
        "The system is read-optimized and write-buffered. Reads are served from a "
        "Redis cache, then an in-memory trie, then SQLite. Writes are accepted "
        "instantly and applied to SQLite in aggregated batches.", BODY))
    e.append(Spacer(1, 4))
    e.append(architecture_drawing())
    e.append(Paragraph(
        "Figure 1 &mdash; Request flow across UI, API, cache ring, trie, buffer, and store.",
        style("cap", parent=SMALL, alignment=TA_CENTER, spaceAfter=8)))

    e.append(Paragraph("Read path (GET /suggest)", H2))
    e.extend(bullets([
        "Normalize the prefix (trim, lowercase, collapse whitespace).",
        "Hash the key <font face='Courier'>suggest:{mode}:{prefix}</font> onto the ring and route to the owning Redis node.",
        "Cache hit &rarr; return cached top-K JSON immediately.",
        "Cache miss &rarr; walk the trie for the precomputed top-K (O(prefix length), no sort), populate the cache with a TTL, and return. Long-tail prefixes fall back to an indexed SQLite prefix scan.",
    ]))
    e.append(Paragraph("Write path (POST /search)", H2))
    e.extend(bullets([
        "The event is appended to an in-memory buffer and the API returns <font face='Courier'>{\"message\":\"Searched\"}</font> without blocking.",
        "A background thread flushes every 500 events or 2 seconds, aggregating duplicates into per-query deltas.",
        "One SQLite transaction applies all deltas; trie counts are updated in place and affected prefix keys are invalidated in Redis.",
    ]))

    e.append(Paragraph("2. Dataset Source &amp; Loading", H1))
    e.append(Paragraph(
        "<b>Source:</b> AOL User Session Collection (500k) &mdash; real anonymized web "
        "search logs from March&ndash;May 2006, published on Kaggle: "
        "<font color='#2563eb'>kaggle.com/datasets/dineshydv/aol-user-session-collection-500k</font>.",
        BODY))
    e.append(Paragraph("Two derived CSV files are used:", BODY))
    e.append(tbl([
        ["File", "Rows", "Columns", "Role"],
        ["typeahed_dataset.csv", "1,244,453",
         "Query, Global/Weekly/Daily Count, Trending Score", "Seed counts"],
        ["raw_queries.csv", "2,969,752", "Query, QueryTime",
         "Replay events / recency"],
    ], [3.5 * cm, 2.0 * cm, 5.6 * cm, 3.3 * cm]))
    e.append(Spacer(1, 4))
    e.append(Paragraph(
        "The verified trending formula in the seed file is "
        "<font face='Courier'>0.6&middot;Global + 0.3&middot;Weekly + 0.1&middot;Daily</font>. "
        "Drive mirrors of the derived files are linked in the README.", BODY))
    e.append(Paragraph("Loading instructions", H2))
    e.append(Paragraph(
        "Place both CSVs in <font face='Courier'>data/</font>, then start the stack. "
        "Ingestion runs automatically on first launch; the trie is built from SQLite "
        "at backend startup.", BODY))
    e.append(Paragraph(
        "git clone &amp; cd search-typeahead-hld<br/>"
        "git lfs install   # raw_queries.csv is tracked via Git LFS (&gt;100MB)<br/>"
        "./start.sh        # Redis (Docker or local) + ingest + backend + frontend<br/>"
        "# or manually:<br/>"
        "python backend/scripts/ingest.py   # bulk-load typeahed_dataset.csv &rarr; SQLite",
        CODE))
    e.append(Paragraph(
        "Ingestion bulk-inserts in 50k-row transactions (~1.24M rows in ~36s) and "
        "creates <font face='Courier'>data/typeahead.db</font>.", SMALL))

    # ---- 3. API ----
    e.append(Paragraph("3. API Documentation", H1))
    e.append(tbl([
        ["Endpoint", "Purpose"],
        ["GET /suggest?q=&limit=&mode=", "Top-K prefix suggestions (basic|trending)"],
        ["POST /search", "Submit a search; buffered count update"],
        ["GET /cache/debug?prefix=", "Node ownership, ring hash/position, hit/miss"],
        ["GET /trending?limit=&mode=", "Global trending (basic|trending)"],
        ["GET /trending/compare?prefix=", "Side-by-side basic vs trending ranking"],
        ["POST /cache/demo/rebalance", "Consistent-hashing remap demonstration"],
        ["POST /batch/flush", "Force-flush the write buffer (demo/test)"],
        ["GET /metrics", "Latency p50/p95/p99, hit rate, write reduction"],
        ["GET /health", "Trie size, DB rows, per-node Redis status"],
    ], [5.6 * cm, 9.0 * cm]))
    e.append(Paragraph("Example: GET /suggest?q=goog&amp;limit=3", H2))
    e.append(Paragraph(
        "{<br/>"
        "&nbsp;&nbsp;\"prefix\": \"goog\", \"mode\": \"basic\",<br/>"
        "&nbsp;&nbsp;\"cache\": {\"node\": \"redis-2\", \"hit\": true},<br/>"
        "&nbsp;&nbsp;\"suggestions\": [<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;{\"query\": \"google\", \"count\": 32948, \"score\": 20646.5},<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;{\"query\": \"google.com\", \"count\": 8323, \"score\": 5268.7}<br/>"
        "&nbsp;&nbsp;]<br/>}", CODE))
    e.append(Paragraph("Example: GET /cache/debug?prefix=goog", H2))
    e.append(Paragraph(
        "{ \"enabled\": true, \"assigned_node\": \"redis-2\", \"hit\": true,<br/>"
        "&nbsp;&nbsp;\"ring_position\": 57, \"total_vnodes\": 450,<br/>"
        "&nbsp;&nbsp;\"nodes\": [\"redis-0\", \"redis-1\", \"redis-2\"] }", CODE))
    e.append(Paragraph(
        "Input edge cases: empty/missing <font face='Courier'>q</font> returns an empty "
        "list with HTTP 200; matching is case-insensitive; no-match prefixes return an "
        "empty list; empty <font face='Courier'>POST /search</font> is rejected with 422.",
        SMALL))

    # ---- 4. design choices ----
    e.append(Paragraph("4. Design Choices &amp; Trade-offs", H1))
    e.append(tbl([
        ["Decision", "Why", "Trade-off"],
        ["Trie with precomputed top-K",
         "O(prefix) lookup, no query-time sort",
         "~ a few hundred MB; rebuilt at startup"],
        ["Load global_count >= 10 into trie",
         "Fast startup (~42k hot queries)",
         "Long tail served via SQLite fallback"],
        ["SQLite primary store",
         "Zero-setup, single file, durable",
         "Not horizontally scalable"],
        ["3 standalone Redis + own ring",
         "Consistent hashing is explicit/debuggable",
         "Manual ring vs Redis Cluster"],
        ["Batch writes (500 / 2s)",
         "Collapse bursts; ~1000:1 read:write",
         "Crash before flush loses buffer"],
        ["Dual ranking modes",
         "Basic (count) + recency-aware score",
         "Two code paths to maintain"],
    ], [4.4 * cm, 5.3 * cm, 4.9 * cm]))
    e.append(Spacer(1, 4))
    e.append(Paragraph("Failure mode &amp; mitigations", H2))
    e.append(Paragraph(
        "Buffered events live in memory until flush, so a crash before flush loses "
        "pending counts. Mitigations: an append-only WAL, a durable queue (Redis "
        "Streams / Kafka), or a shorter flush interval &mdash; trading durability "
        "against write throughput. The cache degrades gracefully: if Redis is down, "
        "the API still serves from the trie and SQLite.", BODY))

    # ---- 5. performance ----
    e.append(Paragraph("5. Performance Report", H1))
    e.append(Paragraph(
        "Measured locally (Apple Silicon) with all three Redis nodes running. "
        "Workload: 27 representative prefixes requested cold once then 20&times; warm "
        "(567 suggest requests), followed by a 5,000-event search replay.", BODY))
    e.append(tbl([
        ["Metric", "Result"],
        ["/suggest server-side p50", "0.321 ms"],
        ["/suggest server-side p95", "0.644 ms"],
        ["/suggest server-side p99", "0.869 ms"],
        ["Cache hit rate (warm)", "95.8% (569 hits / 25 misses)"],
        ["Search events replayed", "5,000"],
        ["SQLite write transactions", "5"],
        ["Write reduction ratio", "0.999 (99.9% fewer writes)"],
        ["Automated smoke tests", "21 / 21 pass"],
    ], [7.0 * cm, 7.6 * cm]))
    e.append(Spacer(1, 4))
    e.append(Paragraph("Consistent hashing distribution", H2))
    e.append(Paragraph(
        "27 prefix keys mapped across the 3-node ring: redis-0 = 9, redis-1 = 10, "
        "redis-2 = 8. Adding a 4th node via "
        "<font face='Courier'>/cache/demo/rebalance</font> remapped 25% of sample keys "
        "&mdash; matching the ~1/N expectation for consistent hashing (N = 4).", BODY))
    e.append(Paragraph("Interpretation", H2))
    e.extend(bullets([
        "Server-side p99 stays under 1 ms because the trie returns precomputed top-K with no sorting at query time.",
        "After warmup ~96% of suggest requests are served from Redis without touching the trie or DB.",
        "5,000 search events collapsed into 5 DB transactions, confirming the batch-write design.",
    ]))
    e.append(Spacer(1, 6))
    e.append(Paragraph(
        "Reproduce: <font face='Courier'>./start.sh</font> then "
        "<font face='Courier'>python backend/scripts/smoke_test.py</font> and "
        "<font face='Courier'>python backend/scripts/replay.py --limit 5000</font>; "
        "read <font face='Courier'>GET /metrics</font>.", SMALL))

    doc.build(e)
    print(f"Wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    build()
