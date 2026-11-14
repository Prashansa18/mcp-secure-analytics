import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from server import analytics

mcp = FastMCP(
    "Secure-Retail-Analytics",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8001)),
    streamable_http_path="/mcp",
    stateless_http=True,   # no session state: works behind Render/ChatGPT/Claude proxies
    json_response=True,
    # Public hostname is on onrender.com, so Host-header allow-listing is turned off.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "mcp-secure-analytics"})


@mcp.custom_route("/", methods=["GET"])
async def root(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "mcp_endpoint": "/mcp"})


@mcp.tool()
def get_dataset_info() -> dict:
    """Describe the retail supply-chain sales dataset: columns, types, date range,
    categorical values and derived columns (Year, Quarter, Month, Ship Days).
    Call this first to learn valid column names."""
    return analytics.dataset_info()


@mcp.tool()
def preview_rows(n: int = 5, filters: Optional[dict] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Return up to 50 sample rows (PII masked).
    filters: {"Region": "West"} or {"Category": ["Furniture", "Technology"]}.
    date_from / date_to: YYYY-MM-DD, applied to Order Date."""
    return analytics.preview(n, filters, date_from, date_to)


@mcp.tool()
def get_kpis(filters: Optional[dict] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Headline KPIs: orders, customers, total sales, total profit, profit margin %,
    average discount %, average ship days, return rate %. Supports the same filters as preview_rows."""
    return analytics.kpis(filters, date_from, date_to)


@mcp.tool()
def aggregate_data(group_by: list[str], metrics: Optional[list[str]] = None,
                   filters: Optional[dict] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   sort_by: Optional[str] = None, ascending: bool = False,
                   limit: int = 20) -> dict:
    """Group-by analysis. group_by examples: ["Region"], ["Category","Sub-Category"], ["Month"], ["Year","Segment"].
    metrics are "Column:agg" strings, agg in sum|mean|count|min|max|median|nunique,
    e.g. ["Sales:sum","Profit:sum","Order ID:nunique"]. Default is Sales:sum and Profit:sum.
    sort_by is a result column such as "Sales (sum)". Use for top-N, trends and comparisons."""
    return analytics.aggregate(group_by, metrics, filters, date_from, date_to, sort_by, ascending, limit)
