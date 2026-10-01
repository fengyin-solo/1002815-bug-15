"""灌溉作业业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "irrigation"
REQUIRED_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式"]
# 表格导入与登记都要完整保留的业务字段，顺序即导出列顺序；
# 之前只留 REQUIRED_FIELDS，用水量/灌溉设备等列进库就丢，导出自然整列缺失。
IMPORT_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式", "用水量", "灌溉时段", "灌溉设备", "作业人员"]
STATUS_ORDER = ["待灌溉", "灌溉中", "已完成", "已暂停"]
ACTION_RULES = {"安排灌溉": "灌溉中", "开始灌溉": "已完成", "暂停灌溉": "已暂停"}
NEGATIVE_ACTIONS: list[str] = []


def _clean(value: Any) -> Any:
    """空白单元格统一成 None，其余原样保留；空着的用水量绝不落成 0。"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _merge_into(entry: dict[str, Any], values: dict[str, Any]) -> None:
    """同编号合并：新值非空才覆盖，已读到的字段不许被空值或占位顶掉。"""
    for field in IMPORT_FIELDS:
        incoming = values.get(field)
        if incoming is not None:
            entry[field] = incoming


class IrrigationService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        area: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("灌溉编号", ""))]
        if area:
            rows = [row for row in rows if area in str(row.get("灌溉区域", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_by_code(self, code: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("灌溉编号") or "").strip() == code:
                return row
        return None

    def _new_entry(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["status"] = STATUS_ORDER[0]
        entry["灌溉状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记一条灌溉任务；同一灌溉编号已存在时合并进原记录，不再生成第二份。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        cleaned = {field: _clean(values.get(field)) for field in IMPORT_FIELDS}
        existing = self._find_by_code(str(cleaned["灌溉编号"]))
        if existing is not None:
            _merge_into(existing, cleaned)
            return existing, [], False
        entry = self._new_entry()
        entry.update(cleaned)
        store.rows(MODULE).append(entry)
        return entry, [], True

    def import_entries(
        self,
        columns: list[str],
        rows: list[list[Any]],
        offset: int = 0,
    ) -> tuple[dict[str, Any] | None, str]:
        """表格导入：按列名对齐字段，按灌溉编号合并同批数据。

        - 列对不上：整批拒绝，一行都不写；
        - 整行为空：退回该行并在结果里标注行号（含已续传偏移，行号与原始表格一致）；
        - 同一灌溉编号重复导入只生效一次，断点续传重发已读行不会产生重复记录。
        """
        headers = [str(column or "").strip() for column in columns]
        missing_cols = [field for field in IMPORT_FIELDS if field not in headers]
        extra_cols = [header for header in headers if header and header not in IMPORT_FIELDS]
        if missing_cols or extra_cols:
            parts = []
            if missing_cols:
                parts.append(f"缺少列：{'、'.join(missing_cols)}")
            if extra_cols:
                parts.append(f"无法识别的列：{'、'.join(extra_cols)}")
            return None, f"表格列与灌溉作业字段对不上（{'；'.join(parts)}），整批已拒绝"

        offset = max(int(offset or 0), 0)
        batch: dict[str, dict[str, Any]] = {}
        rejected: list[dict[str, Any]] = []
        for index, raw in enumerate(rows):
            row_no = offset + index + 1
            cells = [_clean(cell) for cell in list(raw)[: len(headers)]]
            cells += [None] * (len(headers) - len(cells))
            values = dict(zip(headers, cells))
            if all(value is None for value in values.values()):
                rejected.append({"row": row_no, "reason": "整行为空，已退回"})
                continue
            code = values.get("灌溉编号")
            if code is None:
                rejected.append({"row": row_no, "reason": "缺少灌溉编号，无法按编号合并入库"})
                continue
            key = str(code)
            if key not in batch:
                batch[key] = {field: None for field in IMPORT_FIELDS}
            _merge_into(batch[key], values)

        created = 0
        updated = 0
        table = store.rows(MODULE)
        for key, values in batch.items():
            existing = self._find_by_code(key)
            if existing is not None:
                _merge_into(existing, values)
                updated += 1
            else:
                entry = self._new_entry()
                entry.update(values)
                table.append(entry)
                created += 1

        summary = {
            "created": created,
            "updated": updated,
            "rejected": rejected,
            "processed": len(rows),
            "next_row": offset + len(rows) + 1,
        }
        message = f"导入完成：新增 {created} 条，按灌溉编号合并更新 {updated} 条"
        if rejected:
            message += f"，退回 {len(rejected)} 行（行号见明细）"
        return summary, message

    def export_entries(
        self,
        *,
        keyword: str | None = None,
        area: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """导出当前筛选条件下的清单：列固定齐全，灌溉设备、用水量、作业人员一并带上。"""
        rows, total = self.list_entries(keyword=keyword, area=area, status=status, page=1, size=10000)
        items = []
        for row in rows:
            item = {field: row.get(field) for field in IMPORT_FIELDS}
            item["灌溉状态"] = row.get("status")
            items.append(item)
        return items, total

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"灌溉任务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于灌溉作业可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["灌溉状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"灌溉任务已{action}"
