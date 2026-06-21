from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# -----------------------------
# user
# -----------------------------
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_curator: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("0")
    )
    global_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("1")
    )
    must_change_password: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("0")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('department','global')",
            name="user_account_type_check",
        ),
        CheckConstraint(
            "department IN ('Комплектация','Закупки','Сопровождение')",
            name="user_department_check",
        ),
        CheckConstraint(
            "global_role IN ('Админ','Руководитель')",
            name="user_global_role_check",
        ),
    )


# -----------------------------
# parent_request
# -----------------------------
class ParentRequest(Base):
    __tablename__ = "parent_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    mtr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    srok: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zagruzka: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("date('now')")
    )
    sostavitel: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    dept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'awaiting'")
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting','cancelled')",
            name="parent_request_status_check",
        ),
        Index("ix_parent_status", "status"),
    )


# -----------------------------
# requested_position
# -----------------------------
class RequestedPosition(Base):
    __tablename__ = "requested_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("parent_request.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gost_tu: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_reqpos_parent", "parent_id"),)

    parent: Mapped["ParentRequest"] = relationship("ParentRequest")


# -----------------------------
# tender
# -----------------------------
class Tender(Base):
    __tablename__ = "tender"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    num: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("parent_request.id"), nullable=False
    )

    __table_args__ = (Index("ix_tender_parent", "parent_id"),)

    parent: Mapped["ParentRequest"] = relationship("ParentRequest")
    procedures: Mapped[list["Procedure"]] = relationship(
        "Procedure", back_populates="tender"
    )


# -----------------------------
# procedure
# -----------------------------
class Procedure(Base):
    __tablename__ = "procedure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proc: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tender.id"), nullable=False
    )
    supplier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fio_zakupshchik: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fio_dogovornik: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mtr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pub_start: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pub_end: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_sum: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    block: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'zakupka'")
    )
    block_entered_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_zakup: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_postavki: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_sdelki: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    srok_dd: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fakt_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )

    __table_args__ = (
        CheckConstraint(
            "block IN ('zakupka','soprovozhdenie')",
            name="procedure_block_check",
        ),
        CheckConstraint(
            "status_postavki IN "
            "('Новая','В производстве','В поставке','Частично поставлено',"
            "'Поставлено','Отменена')",
            name="procedure_status_postavki_check",
        ),
        Index("ix_proc_tender", "tender_id"),
        Index("ix_proc_block", "block"),
        Index("ix_proc_supplier", "supplier"),
    )

    tender: Mapped["Tender"] = relationship("Tender", back_populates="procedures")


# -----------------------------
# delivery
# -----------------------------
class Delivery(Base):
    __tablename__ = "delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    procedure_id: Mapped[int] = mapped_column(
        ForeignKey("procedure.id", ondelete="CASCADE"), nullable=False
    )
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'transit'")
    )
    date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_ttn: Mapped[int] = mapped_column(
        Integer, nullable=True, server_default=sql_text("0")
    )
    doc_m15: Mapped[int] = mapped_column(
        Integer, nullable=True, server_default=sql_text("0")
    )
    doc_upd: Mapped[int] = mapped_column(
        Integer, nullable=True, server_default=sql_text("0")
    )
    doc_sert: Mapped[int] = mapped_column(
        Integer, nullable=True, server_default=sql_text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('transit','done')",
            name="delivery_status_check",
        ),
        Index("ix_delivery_proc", "procedure_id"),
    )


# -----------------------------
# procedure_position
# -----------------------------
class ProcedurePosition(Base):
    __tablename__ = "procedure_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    procedure_id: Mapped[int] = mapped_column(
        ForeignKey("procedure.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("requested_position.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gost_tu: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("delivery.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_procpos_proc", "procedure_id"),
        Index("ix_procpos_delivery", "delivery_id"),
        Index("ix_procpos_source", "source_id"),
    )


# -----------------------------
# upd_payment
# -----------------------------
class UpdPayment(Base):
    __tablename__ = "upd_payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upd: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("delivery.id"), nullable=True
    )
    ext_source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ext_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zrds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    srok: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pay_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'await'")
    )
    pay_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )

    __table_args__ = (
        CheckConstraint(
            "origin IN ('delivery','manual','external')",
            name="upd_payment_origin_check",
        ),
        CheckConstraint(
            "pay_status IN ('await','paid')",
            name="upd_payment_pay_status_check",
        ),
        Index("ix_upd_delivery", "delivery_id"),
        Index("ix_upd_paystatus", "pay_status"),
    )


# -----------------------------
# upd_position
# -----------------------------
class UpdPosition(Base):
    __tablename__ = "upd_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upd_payment_id: Mapped[int] = mapped_column(
        ForeignKey("upd_payment.id", ondelete="CASCADE"), nullable=False
    )
    n: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_updpos_upd", "upd_payment_id"),)


# -----------------------------
# comment
# -----------------------------
class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )

    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('parent','tender','procedure')",
            name="comment_target_kind_check",
        ),
        Index("ix_comment_target", "target_kind", "target_id"),
    )


# -----------------------------
# audit_log
# -----------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_kind: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("datetime('now')")
    )

    __table_args__ = (Index("ix_audit_entity", "entity_kind", "entity_id"),)


# -----------------------------
# dict
# -----------------------------
class Dict(Base):
    __tablename__ = "dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default=sql_text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('status_zakup','status_sdelki')",
            name="dict_kind_check",
        ),
        UniqueConstraint("kind", "value", name="dict_kind_value_unique"),
    )
