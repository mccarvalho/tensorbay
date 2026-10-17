"""GPU Asset Inventory models (product plan section 11 / EPIC 05).

Models the physical hierarchy Region -> Datacenter -> Cluster -> Rack ->
Server -> GpuAsset. Each GPU asset keeps operational_status and
commercial_status as SEPARATE fields, as required by the plan: a GPU may be
OFFLINE operationally while still ALLOCATED commercially, and the capacity
ledger depends on reading both independently.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class OperationalStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"
    DECOMMISSIONED = "DECOMMISSIONED"


class CommercialStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"


class Region(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_regions"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    datacenters: Mapped[list["Datacenter"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )


class Datacenter(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_datacenters"

    region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_regions.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    region: Mapped["Region"] = relationship(back_populates="datacenters")
    clusters: Mapped[list["Cluster"]] = relationship(
        back_populates="datacenter", cascade="all, delete-orphan"
    )


class Cluster(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_clusters"

    datacenter_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inventory_datacenters.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    datacenter: Mapped["Datacenter"] = relationship(back_populates="clusters")
    racks: Mapped[list["Rack"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class Rack(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_racks"

    cluster_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_clusters.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    cluster: Mapped["Cluster"] = relationship(back_populates="racks")
    servers: Mapped[list["Server"]] = relationship(
        back_populates="rack", cascade="all, delete-orphan"
    )


class Server(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_servers"

    rack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_racks.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    rack: Mapped["Rack"] = relationship(back_populates="servers")
    gpus: Mapped[list["GpuAsset"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class GpuAsset(Base, UUIDMixin, AuditMixin):
    __tablename__ = "inventory_gpu_assets"

    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_servers.id"), nullable=False, index=True
    )
    gpu_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    memory_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acquisition_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    acquisition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warranty: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Operational and commercial status are independent dimensions.
    operational_status: Mapped[OperationalStatus] = mapped_column(
        SAEnum(OperationalStatus, name="gpu_operational_status"),
        nullable=False,
        default=OperationalStatus.ONLINE,
        index=True,
    )
    commercial_status: Mapped[CommercialStatus] = mapped_column(
        SAEnum(CommercialStatus, name="gpu_commercial_status"),
        nullable=False,
        default=CommercialStatus.AVAILABLE,
        index=True,
    )

    server: Mapped["Server"] = relationship(back_populates="gpus")
