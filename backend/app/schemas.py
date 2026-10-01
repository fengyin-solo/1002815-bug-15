"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ImportPayload(BaseModel):
    """表格导入：columns 为表头，rows 为数据行，offset 为断点续传时已入库的数据行数。"""

    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    offset: int = Field(default=0, ge=0)


class RejectedRow(BaseModel):
    """被退回的表格行：行号对应原始表格的数据行号（含续传偏移）。"""

    row: int
    reason: str


class ImportResult(BaseModel):
    ok: bool
    message: str
    created: int = 0
    updated: int = 0
    rejected: list[RejectedRow] = Field(default_factory=list)
    next_row: int = 1



class PlotEntry(BaseModel):
    """绿地明细结构。"""

    field_0: str | None = None  # 绿地编号
    field_1: str | None = None  # 绿地名称
    field_2: str | None = None  # 所属区域
    field_3: str | None = None  # 绿地类型
    field_4: str | None = None  # 面积
    field_5: str | None = None  # 植被群落
    field_6: str | None = None  # 管养等级
    field_7: str | None = None  # 绿地状态

class TreeEntry(BaseModel):
    """乔木明细结构。"""

    field_0: str | None = None  # 树木编号
    field_1: str | None = None  # 树种名称
    field_2: str | None = None  # 胸径
    field_3: str | None = None  # 冠幅
    field_4: str | None = None  # 树龄
    field_5: str | None = None  # 定植日期
    field_6: str | None = None  # 管护人员
    field_7: str | None = None  # 树木状态

class ShrubEntry(BaseModel):
    """灌木明细结构。"""

    field_0: str | None = None  # 灌木编号
    field_1: str | None = None  # 品种名称
    field_2: str | None = None  # 栽植面积
    field_3: str | None = None  # 修剪周期
    field_4: str | None = None  # 高度范围
    field_5: str | None = None  # 花开季节
    field_6: str | None = None  # 管护人员
    field_7: str | None = None  # 灌木状态

class LawnEntry(BaseModel):
    """草坪明细结构。"""

    field_0: str | None = None  # 草坪编号
    field_1: str | None = None  # 草种类型
    field_2: str | None = None  # 草坪面积
    field_3: str | None = None  # 修剪频率
    field_4: str | None = None  # 灌溉方式
    field_5: str | None = None  # 返青情况
    field_6: str | None = None  # 斑秃面积
    field_7: str | None = None  # 草坪状态

class FlowerEntry(BaseModel):
    """花卉造景明细结构。"""

    field_0: str | None = None  # 造景编号
    field_1: str | None = None  # 造景主题
    field_2: str | None = None  # 花卉品种
    field_3: str | None = None  # 景观面积
    field_4: str | None = None  # 花期起止
    field_5: str | None = None  # 换花周期
    field_6: str | None = None  # 养护人员
    field_7: str | None = None  # 造景状态

class PestEntry(BaseModel):
    """防治记录明细结构。"""

    field_0: str | None = None  # 防治编号
    field_1: str | None = None  # 受害植物
    field_2: str | None = None  # 病虫种类
    field_3: str | None = None  # 危害等级
    field_4: str | None = None  # 发生面积
    field_5: str | None = None  # 防治药剂
    field_6: str | None = None  # 防治日期
    field_7: str | None = None  # 防治状态

class IrrigationEntry(BaseModel):
    """灌溉任务明细结构。"""

    field_0: str | None = None  # 灌溉编号
    field_1: str | None = None  # 灌溉区域
    field_2: str | None = None  # 灌溉方式
    field_3: str | None = None  # 用水量
    field_4: str | None = None  # 灌溉时段
    field_5: str | None = None  # 灌溉设备
    field_6: str | None = None  # 作业人员
    field_7: str | None = None  # 灌溉状态

class FertilizeEntry(BaseModel):
    """施肥记录明细结构。"""

    field_0: str | None = None  # 施肥编号
    field_1: str | None = None  # 施肥区域
    field_2: str | None = None  # 肥料类型
    field_3: str | None = None  # 施肥量
    field_4: str | None = None  # 施肥方式
    field_5: str | None = None  # 施肥日期
    field_6: str | None = None  # 作业人员
    field_7: str | None = None  # 施肥状态

class PruneEntry(BaseModel):
    """修剪任务明细结构。"""

    field_0: str | None = None  # 修剪编号
    field_1: str | None = None  # 修剪对象
    field_2: str | None = None  # 修剪类型
    field_3: str | None = None  # 修剪量
    field_4: str | None = None  # 造型要求
    field_5: str | None = None  # 作业日期
    field_6: str | None = None  # 操作人员
    field_7: str | None = None  # 修剪状态

class PatrolEntry(BaseModel):
    """巡查记录明细结构。"""

    field_0: str | None = None  # 巡查编号
    field_1: str | None = None  # 巡查区域
    field_2: str | None = None  # 巡查日期
    field_3: str | None = None  # 巡查人员
    field_4: str | None = None  # 巡查路线
    field_5: str | None = None  # 发现问题
    field_6: str | None = None  # 处置措施
    field_7: str | None = None  # 巡查状态

class WeedEntry(BaseModel):
    """除草任务明细结构。"""

    field_0: str | None = None  # 除草编号
    field_1: str | None = None  # 除草区域
    field_2: str | None = None  # 杂草种类
    field_3: str | None = None  # 覆盖程度
    field_4: str | None = None  # 除草方式
    field_5: str | None = None  # 作业日期
    field_6: str | None = None  # 作业人员
    field_7: str | None = None  # 除草状态

class SupportEntry(BaseModel):
    """支撑设施明细结构。"""

    field_0: str | None = None  # 支撑编号
    field_1: str | None = None  # 所属树木
    field_2: str | None = None  # 支撑方式
    field_3: str | None = None  # 支撑材料
    field_4: str | None = None  # 安装日期
    field_5: str | None = None  # 检查日期
    field_6: str | None = None  # 稳固情况
    field_7: str | None = None  # 支撑状态

class TransplantEntry(BaseModel):
    """移植记录明细结构。"""

    field_0: str | None = None  # 移植编号
    field_1: str | None = None  # 移植树种
    field_2: str | None = None  # 移植数量
    field_3: str | None = None  # 移出位置
    field_4: str | None = None  # 移入位置
    field_5: str | None = None  # 移植日期
    field_6: str | None = None  # 成活率
    field_7: str | None = None  # 移植状态

class FacilityEntry(BaseModel):
    """园建设施明细结构。"""

    field_0: str | None = None  # 设施编号
    field_1: str | None = None  # 设施名称
    field_2: str | None = None  # 设施类型
    field_3: str | None = None  # 所在绿地
    field_4: str | None = None  # 安装日期
    field_5: str | None = None  # 上次检修
    field_6: str | None = None  # 损坏描述
    field_7: str | None = None  # 设施状态

class EquipmentEntry(BaseModel):
    """园林机械明细结构。"""

    field_0: str | None = None  # 机械编号
    field_1: str | None = None  # 机械名称
    field_2: str | None = None  # 规格型号
    field_3: str | None = None  # 购置日期
    field_4: str | None = None  # 上次保养
    field_5: str | None = None  # 下次保养日
    field_6: str | None = None  # 操作人员
    field_7: str | None = None  # 机械状态

class SeedlingEntry(BaseModel):
    """苗圃明细结构。"""

    field_0: str | None = None  # 苗圃编号
    field_1: str | None = None  # 苗圃名称
    field_2: str | None = None  # 苗圃面积
    field_3: str | None = None  # 培育品种
    field_4: str | None = None  # 出圃周期
    field_5: str | None = None  # 在圃数量
    field_6: str | None = None  # 管护人员
    field_7: str | None = None  # 苗圃状态

class WaterbodyEntry(BaseModel):
    """水体明细结构。"""

    field_0: str | None = None  # 水体编号
    field_1: str | None = None  # 水体类型
    field_2: str | None = None  # 水体面积
    field_3: str | None = None  # 水质等级
    field_4: str | None = None  # 富营养化
    field_5: str | None = None  # 换水周期
    field_6: str | None = None  # 管护人员
    field_7: str | None = None  # 水体状态

class CodeEntry(BaseModel):
    """名木古树明细结构。"""

    field_0: str | None = None  # 古树编号
    field_1: str | None = None  # 树种
    field_2: str | None = None  # 树龄
    field_3: str | None = None  # 保护等级
    field_4: str | None = None  # 保护范围
    field_5: str | None = None  # 生长状况
    field_6: str | None = None  # 复壮记录
    field_7: str | None = None  # 古树状态

class ComplaintEntry(BaseModel):
    """热线记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 来电人
    field_2: str | None = None  # 来电内容
    field_3: str | None = None  # 问题位置
    field_4: str | None = None  # 问题类型
    field_5: str | None = None  # 转办部门
    field_6: str | None = None  # 处理结果
    field_7: str | None = None  # 记录状态

class SeasonplanEntry(BaseModel):
    """养护方案明细结构。"""

    field_0: str | None = None  # 方案编号
    field_1: str | None = None  # 方案季度
    field_2: str | None = None  # 覆盖绿地
    field_3: str | None = None  # 方案内容
    field_4: str | None = None  # 预算金额
    field_5: str | None = None  # 编制人
    field_6: str | None = None  # 审批人
    field_7: str | None = None  # 方案状态
