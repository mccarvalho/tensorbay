import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class OperationalStatus(str, enum.Enum):
    PROVISIONING = "PROVISIONING"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"
    DECOMMISSIONED = "DECOMMISSIONED"


class CommercialStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"
    MAINTENANCE_HOLD = "MAINTENANCE_HOLD"


class NetworkFabric(str, enum.Enum):
    INFINIBAND = "INFINIBAND"
    ETHERNET = "ETHERNET"
    NVLINK = "NVLINK"


class Orchestrator(str, enum.Enum):
    KUBERNETES = "KUBERNETES"
    SLURM = "SLURM"
    BARE_METAL = "BARE_METAL"


class Region(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    datacenters: Mapped[list["Datacenter"]] = relationship(back_populates="region", lazy="selectin")


class Datacenter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "datacenters"

    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(50), default="owned")
    total_power_kw: Mapped[int | None] = mapped_column(Integer)
    total_rack_units: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(default=True)

    region: Mapped["Region"] = relationship(back_populates="datacenters")
    clusters: Mapped[list["Cluster"]] = relationship(back_populates="datacenter", lazy="selectin")


class Cluster(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "clusters"

    datacenter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datacenters.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(50), nullable=False)
    total_gpus: Mapped[int] = mapped_column(Integer, default=0)
    network_fabric: Mapped[NetworkFabric] = mapped_column(Enum(NetworkFabric), default=NetworkFabric.INFINIBAND)
    orchestrator: Mapped[Orchestrator] = mapped_column(Enum(Orchestrator), default=Orchestrator.KUBERNETES)
    is_active: Mapped[bool] = mapped_column(default=True)

    datacenter: Mapped["Datacenter"] = relationship(back_populates="clusters")
    racks: Mapped[list["Rack"]] = relationship(back_populates="cluster", lazy="selectin")


class Rack(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "racks"

    cluster_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clusters.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, default=42)
    used_units: Mapped[int] = mapped_column(Integer, default=0)
    power_capacity_kw: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)

    cluster: Mapped["Cluster"] = relationship(back_populates="racks")
    servers: Mapped[list["Server"]] = relationship(back_populates="rack", lazy="selectin")


class Server(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "servers"

    rack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("racks.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, default=8)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_tb: Mapped[int] = mapped_column(Integer, default=0)
    operational_status: Mapped[OperationalStatus] = mapped_column(
        Enum(OperationalStatus), default=OperationalStatus.PROVISIONING
    )
    os_image: Mapped[str | None] = mapped_column(String(255))
    ip_management: Mapped[str | None] = mapped_column(String(50))
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_cost: Mapped[float | None] = mapped_column(Float)
    supplier: Mapped[str | None] = mapped_column(String(255))
    warranty_months: Mapped[int | None] = mapped_column(Integer)

    rack: Mapped["Rack"] = relationship(back_populates="servers")
    gpus: Mapped[list["GPU"]] = relationship(back_populates="server", lazy="selectin")


class GPU(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "gpus"

    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id"), nullable=False)
    gpu_id_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), default="NVIDIA")
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    memory_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slot_position: Mapped[int] = mapped_column(Integer, nullable=False)
    operational_status: Mapped[OperationalStatus] = mapped_column(
        Enum(OperationalStatus), default=OperationalStatus.PROVISIONING
    )
    commercial_status: Mapped[CommercialStatus] = mapped_column(
        Enum(CommercialStatus), default=CommercialStatus.AVAILABLE
    )
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_cost: Mapped[float | None] = mapped_column(Float)
    supplier: Mapped[str | None] = mapped_column(String(255))
    warranty_months: Mapped[int | None] = mapped_column(Integer)
    power_draw_watts: Mapped[float | None] = mapped_column(Float)
    last_health_check: Mapped[datetime | None] = mapped_column()
    health_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    server: Mapped["Server"] = relationship(back_populates="gpus")
