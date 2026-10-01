"""灌溉作业接口：维护灌溉任务，覆盖安排灌溉、开始灌溉、暂停灌溉等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, ImportPayload, ImportResult, PageResult
from app.services.irrigation import IrrigationService

router = APIRouter(prefix="/api/irrigation", tags=["灌溉作业"])

service = IrrigationService()

LIST_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式", "用水量", "灌溉时段", "灌溉设备", "作业人员", "灌溉状态"]
STATUSES = ["待灌溉", "灌溉中", "已完成", "已暂停"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按灌溉编号检索"),
    area: str | None = Query(default=None, description="按灌溉区域过滤"),
    status: str | None = Query(default=None, description="待灌溉、灌溉中、已完成、已暂停"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按灌溉编号、灌溉区域与状态过滤灌溉作业列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, area=area, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/export、/import 必须写在 /{entry_id} 之前，否则会被当成 entry_id 抢走，
# 导出直接 422，这也是之前导出内容对不上的根源之一。
@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按灌溉编号检索"),
    area: str | None = Query(default=None, description="按当前选中的灌溉区域导出"),
    status: str | None = Query(default=None, description="按灌溉状态过滤"),
) -> dict[str, Any]:
    """导出灌溉作业清单：跟随当前筛选条件，灌溉设备、用水量、作业人员等列齐全。"""
    items, total = service.export_entries(keyword=keyword, area=area, status=status)
    return {"module": "irrigation", "total": total, "items": items}


@router.post("/import", response_model=ImportResult)
def import_entries(payload: ImportPayload) -> ImportResult:
    """表格导入：列对不上整批拒绝；空行退回并标注行号；同批同编号合并，重复导入只生效一次。"""
    summary, message = service.import_entries(payload.columns, payload.rows, payload.offset)
    if summary is None:
        return ImportResult(ok=False, message=message)
    return ImportResult(
        ok=True,
        message=message,
        created=int(summary["created"]),
        updated=int(summary["updated"]),
        rejected=summary["rejected"],
        next_row=int(summary["next_row"]),
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条灌溉任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"灌溉任务 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条灌溉任务，缺字段时说明原因而不是静默丢弃；同一灌溉编号只保留一份。"""
    entry, missing, created = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if not created:
        return ActionResult(ok=True, message="同一灌溉编号已存在，已合并到原记录，不重复生成", entry=entry)
    return ActionResult(ok=True, message="灌溉任务已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条灌溉任务执行安排灌溉、开始灌溉、暂停灌溉；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
