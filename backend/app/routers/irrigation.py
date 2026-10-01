"""灌溉作业接口：维护灌溉任务，覆盖表格导入、筛选导出、班次对账与状态流转。"""
from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.irrigation import LIST_FIELDS, IrrigationService

router = APIRouter(prefix="/api/irrigation", tags=["灌溉作业"])

service = IrrigationService()

STATUSES = ["待灌溉", "灌溉中", "已完成", "已暂停"]


class ImportPayload(BaseModel):
    """灌溉表格导入入参：content 为表格文本（CSV，含表头行）。"""

    content: str
    sheet: str = Field(default="", description="批次编号；同批重复导入只生效一次")
    token: str = Field(default="", description="断点续传令牌，首次可不传")
    resume_from: int = Field(default=1, ge=1, description="从第几数据行续传")


def _query_rows(
    keyword: str | None,
    area: str | None,
    method: str | None,
    status: str | None,
    *,
    size: int = 10000,
) -> list[dict[str, Any]]:
    items, _ = service.list_entries(
        keyword=keyword, area=area, method=method, status=status, page=1, size=size
    )
    return items


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按灌溉编号检索"),
    area: str | None = Query(default=None, description="按灌溉区域检索"),
    method: str | None = Query(default=None, description="按灌溉方式检索"),
    status: str | None = Query(default=None, description="待灌溉、灌溉中、已完成、已暂停"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按灌溉编号、区域、方式与状态过滤灌溉作业列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, area=area, method=method, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/import")
def import_entries(payload: ImportPayload) -> dict[str, Any]:
    """导入灌溉表格：同编号合并、空行退回、断行续传、同批去重。"""
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="表格内容为空，整批未导入")
    return service.import_sheet(
        content=payload.content,
        sheet=payload.sheet,
        token=payload.token,
        resume_from=payload.resume_from,
    )


# 注意：/export 与 /reconcile 必须声明在 /{entry_id} 之前，否则会被当成 entry_id 解析
@router.get("/export")
def export_entries(
    keyword: str | None = None,
    area: str | None = None,
    method: str | None = None,
    status: str | None = None,
    format: str = Query(default="csv", description="csv 或 json"),
):
    """按当前选择的灌溉区域（及其他筛选）导出；灌溉设备、用水量、作业人员整列都带上。"""
    items = _query_rows(keyword, area, method, status)
    if format == "json":
        return {"module": "irrigation", "total": len(items), "fields": LIST_FIELDS, "items": items}

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LIST_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({field: item.get(field, "") for field in LIST_FIELDS})
    buffer.seek(0)
    filename = "irrigation_export.csv"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/reconcile")
def reconcile(area: str | None = None) -> dict[str, Any]:
    """班次对账：水量按当前明细实时汇总，空着的用水量单列，不当成 0。"""
    return service.reconcile(area=area)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条灌溉任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"灌溉任务 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条灌溉任务，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="灌溉任务已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条灌溉任务执行安排灌溉、开始灌溉、暂停灌溉；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
