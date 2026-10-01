"""灌溉作业业务规则：状态流转、表格导入合并、导出筛选与班次对账口径。"""
from __future__ import annotations

import csv
import io
import re
import uuid
from typing import Any

from app.store import store

MODULE = "irrigation"
LIST_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式", "用水量", "灌溉时段", "灌溉设备", "作业人员", "灌溉状态"]
REQUIRED_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式"]
# 表格表头：前七个字段必须有列，灌溉状态列可缺（默认待灌溉）
SHEET_FIELDS = ["灌溉编号", "灌溉区域", "灌溉方式", "用水量", "灌溉时段", "灌溉设备", "作业人员", "灌溉状态"]
SHEET_REQUIRED_HEADERS = SHEET_FIELDS[:-1]
STATUS_ORDER = ["待灌溉", "灌溉中", "已完成", "已暂停"]
ACTION_RULES = {"安排灌溉": "灌溉中", "开始灌溉": "已完成", "暂停灌溉": "已暂停"}
NEGATIVE_ACTIONS = []

# 合并同批数据时需要把多人/多设备拼起来的字段
JOIN_FIELDS = ["灌溉设备", "作业人员"]
SPLIT_RE = re.compile(r"[、,，;；/\s]+")


def _clean(value: Any) -> str:
    """表格单元格统一转成去空白的字符串；空单元格仍是空串，不会被当成 0。"""
    if value is None:
        return ""
    return str(value).strip()


def _parse_water(value: str) -> tuple[float | None, str | None]:
    """用水量只在填了且能转成非负数字时参与求和；空着就返回 None，绝不补零。"""
    text = _clean(value)
    if not text:
        return None, None
    try:
        number = float(text)
    except ValueError:
        return None, f"用水量「{text}」不是数字，未计入对账水量"
    if number < 0:
        return None, f"用水量「{text}」为负数，未计入对账水量"
    return number, None


def _water_key(number: float) -> str:
    """水量在存储/求和时的稳定键，避免 12.0 与 12、浮点尾差被当成两份。"""
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _split_multi(value: str) -> list[str]:
    return [part for part in SPLIT_RE.split(_clean(value)) if part]


class _BatchState:
    """一次导入的合并暂存区：同一批次编号多行先在这里合并，落库时再 upsert。"""

    def __init__(self, token: str, sheet: str):
        self.token = token
        self.sheet = sheet
        self.groups: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.committed_through = 0  # 已成功落库的数据行序号（续传时跳过这些行）
        self.water_seen: dict[str, set[str]] = {}  # 每个编号已计入的水量，去重重复行
        self.created = 0
        self.updated = 0
        self.merged = 0
        self.warnings: list[dict[str, Any]] = []


class IrrigationService:
    def __init__(self) -> None:
        self._batches: dict[str, _BatchState] = {}
        # 已成功导入的批次编号 -> 首次导入结果摘要，重复导入直接返回首次结果
        self._imported_sheets: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ 列表/详情
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        area: str | None = None,
        method: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("灌溉编号", ""))]
        if area:
            rows = [row for row in rows if area in str(row.get("灌溉区域", ""))]
        if method:
            rows = [row for row in rows if method in str(row.get("灌溉方式", ""))]
        if status:
            rows = [row for row in rows if _display_status(row) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._public_row(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._public_row(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not _clean(values.get(field, ""))]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in LIST_FIELDS:
            text = _clean(values.get(field, ""))
            if text:
                entry[field] = text
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._public_row(entry), []

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
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        # 灌溉状态是列表页/导出实际展示的字段，状态流转后必须一起更新，
        # 否则刷新后又回到旧值。
        entry["灌溉状态"] = target
        return self._public_row(entry), f"灌溉任务已{action}"

    # ------------------------------------------------------------------ 表格导入
    def import_sheet(
        self,
        *,
        content: str,
        sheet: str = "",
        token: str = "",
        resume_from: int = 1,
    ) -> dict[str, Any]:
        """导入灌溉表格。

        - 按表头取列，列顺序换了也不会错位；表头对不上整批拒绝。
        - 同一灌溉编号的多行合并成一条，用水量相加、设备/人员并集拼接。
        - 空着的整行退回，并给出数据行序号。
        - 读到截断/缺列的行就停在那一行，已读字段不写半成品，可续传。
        - 同一批编号重复导入只生效一次。
        """
        sheet = _clean(sheet)
        if sheet and sheet in self._imported_sheets:
            return dict(self._imported_sheets[sheet], repeated=True)

        # 去掉 Excel 导出的 UTF-8 BOM，否则第一列表头会带不可见字符导致整批拒绝
        if content.startswith("﻿"):
            content = content.lstrip("﻿")

        state = self._batches.get(token) if token else None
        if state is None or state.sheet != sheet:
            token = token or uuid.uuid4().hex
            state = _BatchState(token, sheet)
            self._batches[token] = state

        reader = csv.reader(io.StringIO(content))
        records = list(reader)
        if not records:
            return self._reject("表格内容为空，整批未导入", state)

        header_cells = [_clean(cell) for cell in records[0]]
        header_error = self._check_headers(header_cells)
        if header_error:
            # 列对不上整批拒绝：一次都不落库
            self._batches.pop(token, None)
            return {"ok": False, "stage": "header", "message": header_error, "errors": [
                {"row": 1, "reason": header_error},
            ]}
        # 按表头定位列索引，顺序再乱也不会把灌溉方式对到时段上
        index = {name: header_cells.index(name) for name in SHEET_FIELDS if name in header_cells}

        skipped: list[dict[str, Any]] = []
        broken_row: int | None = None
        data_row_no = 0
        for raw in records[1:]:
            data_row_no += 1
            # 续传：之前已经落过库的行直接跳过
            if data_row_no < resume_from:
                continue
            if not any(_clean(cell) for cell in raw):
                # 整行空白也要退回，并告诉用户是第几行，不静默吞掉
                skipped.append({"row": data_row_no, "reason": "整行为空，已退回"})
                continue
            if len(raw) > len(header_cells):
                # 列比表头多，多半是错位行，整行退回而不是截掉后面的单元格
                skipped.append({"row": data_row_no, "reason": "列数多于表头，疑似错位，整行退回"})
                continue
            if len(raw) < len(header_cells):
                # 后面的数据取不到了：停在断掉的这一行，已读字段不保留占位
                broken_row = data_row_no
                break
            values = {name: _clean(raw[pos]) if pos < len(raw) else "" for name, pos in index.items()}
            if not values.get("灌溉编号"):
                skipped.append({"row": data_row_no, "reason": "灌溉编号为空，整行退回"})
                continue
            missing = [field for field in REQUIRED_FIELDS if not values.get(field)]
            if missing:
                skipped.append({
                    "row": data_row_no,
                    "reason": f"必填字段为空（{'、'.join(missing)}），整行退回",
                })
                continue
            water, water_warning = _parse_water(values.get("用水量", ""))
            if water_warning:
                state.warnings.append({"row": data_row_no, "灌溉编号": values["灌溉编号"], "reason": water_warning})
            self._merge_row(state, values, water, data_row_no)

        if broken_row is not None:
            self._commit(state, through=broken_row - 1)
            return {
                "ok": False,
                "stage": "data",
                "token": token,
                "sheet": sheet,
                "message": f"第 {broken_row} 行数据不完整（疑似读取中断），已保留前 {broken_row - 1} 行，请从第 {broken_row} 行续传",
                "resume_from": broken_row,
                **self._summary(state),
                "skipped": skipped,
            }

        self._commit(state, through=data_row_no)
        result = {
            "ok": True,
            "stage": "done",
            "token": token,
            "sheet": sheet,
            "message": self._build_message(state, skipped),
            **self._summary(state),
            "skipped": skipped,
        }
        if sheet:
            # 同一批编号再次导入时直接返回首次结果，不再落第二份
            self._imported_sheets[sheet] = dict(result)
        return result

    def _check_headers(self, headers: list[str]) -> str | None:
        if not any(headers):
            return "表头为空，无法识别列，整批拒绝"
        missing = [name for name in SHEET_REQUIRED_HEADERS if name not in headers]
        unknown = [name for name in headers if name and name not in SHEET_FIELDS]
        duplicates = {name for name in headers if name and headers.count(name) > 1}
        problems: list[str] = []
        if missing:
            problems.append(f"缺少列：{'、'.join(missing)}")
        if unknown:
            problems.append(f"存在无法识别的列：{'、'.join(unknown)}")
        if duplicates:
            problems.append(f"表头重复：{'、'.join(sorted(duplicates))}")
        if problems:
            return "列对不上（" + "；".join(problems) + "），整批拒绝"
        return None

    def _merge_row(
        self,
        state: _BatchState,
        values: dict[str, str],
        water: float | None,
        data_row_no: int,
    ) -> None:
        code = values["灌溉编号"]
        group = state.groups.get(code)
        if group is None:
            group = {"fields": {}, "waters": [], "committed": False, "dirty": False}
            state.groups[code] = group
            state.order.append(code)
            state.water_seen[code] = set()
        if group["committed"]:
            # 续传时给已落库的编号补数据：标记脏，落库阶段要按合并后的全量重写
            group["dirty"] = True
        fields = group["fields"]
        for field in SHEET_REQUIRED_HEADERS + ["灌溉状态"]:
            text = values.get(field, "")
            if not text or field == "用水量":
                continue
            if field in JOIN_FIELDS:
                merged: list[str] = _split_multi(fields.get(field, ""))
                for part in _split_multi(text):
                    if part not in merged:
                        merged.append(part)
                fields[field] = "、".join(merged)
            else:
                # 后读的非空值覆盖先读的（含灌溉区域、灌溉方式、灌溉时段、灌溉状态）
                fields[field] = text
        if water is not None:
            key = _water_key(water)
            if key not in state.water_seen[code]:
                state.water_seen[code].add(key)
                group["waters"].append(water)

    def _commit(self, state: _BatchState, *, through: int) -> None:
        """把序号 <= through 的合并组按灌溉编号 upsert 落库。"""
        rows = store.rows(MODULE)
        by_code = {str(row.get("灌溉编号", "")): row for row in rows}
        for code in state.order:
            group = state.groups[code]
            if through < 1:
                return
            # 已落库且续传期间没有新数据的组直接跳过
            if group["committed"] and not group["dirty"]:
                continue
            fields = group["fields"]
            waters: list[float] = group["waters"]
            water_text = _water_key(sum(waters)) if waters else ""
            existing = by_code.get(code)
            if existing is None:
                entry: dict[str, Any] = {
                    "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
                    "灌溉编号": code,
                    "status": STATUS_ORDER[0],
                    "pending": True,
                    "abnormal": False,
                }
                entry.update(fields)
                if water_text:
                    entry["用水量"] = water_text
                status_text = entry.get("灌溉状态", "")
                if status_text in STATUS_ORDER:
                    entry["status"] = status_text
                    entry["pending"] = status_text != STATUS_ORDER[-1]
                else:
                    entry["灌溉状态"] = STATUS_ORDER[0]
                rows.append(entry)
                by_code[code] = entry
                state.created += 1
            else:
                for field, value in fields.items():
                    if field == "灌溉状态":
                        continue
                    existing[field] = value
                if water_text:
                    existing["用水量"] = water_text
                else:
                    existing.pop("用水量", None)
                status_text = fields.get("灌溉状态", "")
                if status_text in STATUS_ORDER:
                    existing["status"] = status_text
                    existing["灌溉状态"] = status_text
                    existing["pending"] = status_text != STATUS_ORDER[-1]
                state.updated += 1
            group["committed"] = True
            group["dirty"] = False
        state.committed_through = through

    def _summary(self, state: _BatchState) -> dict[str, Any]:
        return {
            "created": state.created,
            "updated": state.updated,
            "merged": len(state.order),
            "warnings": list(state.warnings),
        }

    def _build_message(self, state: _BatchState, skipped: list[dict[str, Any]]) -> str:
        parts = [f"按灌溉编号合并 {len(state.order)} 条", f"新增 {state.created} 条", f"更新 {state.updated} 条"]
        if skipped:
            parts.append(f"退回 {len(skipped)} 行")
        if state.warnings:
            parts.append(f"{len(state.warnings)} 条水量提示")
        return "，".join(parts)

    def _reject(self, message: str, state: _BatchState) -> dict[str, Any]:
        self._batches.pop(state.token, None)
        return {"ok": False, "stage": "data", "message": message, "errors": []}

    # ------------------------------------------------------------------ 班次对账
    def reconcile(self, *, area: str | None = None) -> dict[str, Any]:
        """班次对账：水量始终按明细现算，明细改了对账结果跟着变。

        空着的用水量不计入合计，也不被当成 0，单独列入 unmeasured。
        """
        rows = store.rows(MODULE)
        if area:
            rows = [row for row in rows if area in str(row.get("灌溉区域", ""))]
        total = 0.0
        measured: list[dict[str, Any]] = []
        unmeasured: list[dict[str, Any]] = []
        for row in rows:
            code = str(row.get("灌溉编号", ""))
            raw = _clean(row.get("用水量", ""))
            water, warning = _parse_water(raw)
            item = {
                "id": row.get("id"),
                "灌溉编号": code,
                "灌溉区域": row.get("灌溉区域", ""),
                "作业人员": row.get("作业人员", ""),
            }
            if water is None:
                unmeasured.append({**item, "reason": warning or "用水量未填报"})
            else:
                total += water
                measured.append({**item, "用水量": _water_key(water)})
        total = round(total, 2)
        by_area: dict[str, float] = {}
        for item in measured:
            name = str(item["灌溉区域"] or "未填区域")
            by_area[name] = round(by_area.get(name, 0.0) + float(item["用水量"]), 2)
        return {
            "area": area or "",
            "total_water": _water_key(total),
            "measured_count": len(measured),
            "unmeasured_count": len(unmeasured),
            "by_area": [{"灌溉区域": name, "用水量": _water_key(value)} for name, value in sorted(by_area.items())],
            "measured": measured,
            "unmeasured": unmeasured,
        }

    # ------------------------------------------------------------------ 出参规整
    def _public_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情统一出参：保证整行字段齐全，缺列不再让整条记录在页面上消失。"""
        public = {"id": row.get("id")}
        for field in LIST_FIELDS:
            value = row.get(field)
            public[field] = "" if value is None else value
        public["灌溉状态"] = _display_status(row)
        public["status"] = public["灌溉状态"]
        public["pending"] = bool(row.get("pending", row.get("status") != STATUS_ORDER[-1]))
        public["abnormal"] = bool(row.get("abnormal"))
        return public


def _display_status(row: dict[str, Any]) -> str:
    """灌溉状态以中文列为准；老数据该列为占位文本时回退到 status 字段。"""
    text = _clean(row.get("灌溉状态", ""))
    if text in STATUS_ORDER:
        return text
    status = _clean(row.get("status", ""))
    return status if status in STATUS_ORDER else STATUS_ORDER[0]
