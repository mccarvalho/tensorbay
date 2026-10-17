"""FastAPI router for the GPU Asset Inventory module (prefix /inventory).

Reads require Permission.INVENTORY_READ, writes Permission.INVENTORY_WRITE.
Every write records an audit entry using the current user's subject as actor.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.inventory import schemas
from neocloud.domains.inventory.models import (
    Cluster,
    CommercialStatus,
    Datacenter,
    GpuAsset,
    OperationalStatus,
    Rack,
    Region,
    Server,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.INVENTORY_READ))]
WriteUser = Annotated[CurrentUser, Depends(require_permission(Permission.INVENTORY_WRITE))]
Session = Annotated[AsyncSession, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


async def _get_or_404(session: AsyncSession, model, entity_id: str):
    obj = await session.get(model, entity_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} {entity_id} not found",
        )
    return obj


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------
@router.get("/regions", response_model=list[schemas.RegionRead])
async def list_regions(
    session: Session, _user: ReadUser, limit: Limit = 100, offset: Offset = 0
):
    result = await session.execute(select(Region).limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/regions/{region_id}", response_model=schemas.RegionRead)
async def get_region(region_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, Region, region_id)


@router.post("/regions", response_model=schemas.RegionRead, status_code=status.HTTP_201_CREATED)
async def create_region(payload: schemas.RegionCreate, session: Session, user: WriteUser):
    obj = Region(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.region",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/regions/{region_id}", response_model=schemas.RegionRead)
async def update_region(
    region_id: str, payload: schemas.RegionUpdate, session: Session, user: WriteUser
):
    obj = await _get_or_404(session, Region, region_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.region",
        entity_id=obj.id,
        actor=user.subject,
        new_value=changes,
    )
    await session.refresh(obj)
    return obj


@router.delete("/regions/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(region_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, Region, region_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.region",
        entity_id=region_id,
        actor=user.subject,
    )


# ---------------------------------------------------------------------------
# Datacenters
# ---------------------------------------------------------------------------
@router.get("/datacenters", response_model=list[schemas.DatacenterRead])
async def list_datacenters(
    session: Session,
    _user: ReadUser,
    region_id: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(Datacenter)
    if region_id is not None:
        stmt = stmt.where(Datacenter.region_id == region_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/datacenters/{datacenter_id}", response_model=schemas.DatacenterRead)
async def get_datacenter(datacenter_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, Datacenter, datacenter_id)


@router.post(
    "/datacenters",
    response_model=schemas.DatacenterRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_datacenter(
    payload: schemas.DatacenterCreate, session: Session, user: WriteUser
):
    obj = Datacenter(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.datacenter",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/datacenters/{datacenter_id}", response_model=schemas.DatacenterRead)
async def update_datacenter(
    datacenter_id: str,
    payload: schemas.DatacenterUpdate,
    session: Session,
    user: WriteUser,
):
    obj = await _get_or_404(session, Datacenter, datacenter_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.datacenter",
        entity_id=obj.id,
        actor=user.subject,
        new_value=changes,
    )
    await session.refresh(obj)
    return obj


@router.delete("/datacenters/{datacenter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datacenter(datacenter_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, Datacenter, datacenter_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.datacenter",
        entity_id=datacenter_id,
        actor=user.subject,
    )


# ---------------------------------------------------------------------------
# Clusters
# ---------------------------------------------------------------------------
@router.get("/clusters", response_model=list[schemas.ClusterRead])
async def list_clusters(
    session: Session,
    _user: ReadUser,
    datacenter_id: str | None = None,
    gpu_model: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(Cluster)
    if datacenter_id is not None:
        stmt = stmt.where(Cluster.datacenter_id == datacenter_id)
    if gpu_model is not None:
        stmt = stmt.where(Cluster.gpu_model == gpu_model)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/clusters/{cluster_id}", response_model=schemas.ClusterRead)
async def get_cluster(cluster_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, Cluster, cluster_id)


@router.post(
    "/clusters", response_model=schemas.ClusterRead, status_code=status.HTTP_201_CREATED
)
async def create_cluster(payload: schemas.ClusterCreate, session: Session, user: WriteUser):
    obj = Cluster(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.cluster",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/clusters/{cluster_id}", response_model=schemas.ClusterRead)
async def update_cluster(
    cluster_id: str, payload: schemas.ClusterUpdate, session: Session, user: WriteUser
):
    obj = await _get_or_404(session, Cluster, cluster_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.cluster",
        entity_id=obj.id,
        actor=user.subject,
        new_value=changes,
    )
    await session.refresh(obj)
    return obj


@router.delete("/clusters/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(cluster_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, Cluster, cluster_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.cluster",
        entity_id=cluster_id,
        actor=user.subject,
    )


# ---------------------------------------------------------------------------
# Racks
# ---------------------------------------------------------------------------
@router.get("/racks", response_model=list[schemas.RackRead])
async def list_racks(
    session: Session,
    _user: ReadUser,
    cluster_id: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(Rack)
    if cluster_id is not None:
        stmt = stmt.where(Rack.cluster_id == cluster_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/racks/{rack_id}", response_model=schemas.RackRead)
async def get_rack(rack_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, Rack, rack_id)


@router.post("/racks", response_model=schemas.RackRead, status_code=status.HTTP_201_CREATED)
async def create_rack(payload: schemas.RackCreate, session: Session, user: WriteUser):
    obj = Rack(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.rack",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/racks/{rack_id}", response_model=schemas.RackRead)
async def update_rack(
    rack_id: str, payload: schemas.RackUpdate, session: Session, user: WriteUser
):
    obj = await _get_or_404(session, Rack, rack_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.rack",
        entity_id=obj.id,
        actor=user.subject,
        new_value=changes,
    )
    await session.refresh(obj)
    return obj


@router.delete("/racks/{rack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rack(rack_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, Rack, rack_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.rack",
        entity_id=rack_id,
        actor=user.subject,
    )


# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------
@router.get("/servers", response_model=list[schemas.ServerRead])
async def list_servers(
    session: Session,
    _user: ReadUser,
    rack_id: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(Server)
    if rack_id is not None:
        stmt = stmt.where(Server.rack_id == rack_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/servers/{server_id}", response_model=schemas.ServerRead)
async def get_server(server_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, Server, server_id)


@router.post("/servers", response_model=schemas.ServerRead, status_code=status.HTTP_201_CREATED)
async def create_server(payload: schemas.ServerCreate, session: Session, user: WriteUser):
    obj = Server(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.server",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/servers/{server_id}", response_model=schemas.ServerRead)
async def update_server(
    server_id: str, payload: schemas.ServerUpdate, session: Session, user: WriteUser
):
    obj = await _get_or_404(session, Server, server_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.server",
        entity_id=obj.id,
        actor=user.subject,
        new_value=changes,
    )
    await session.refresh(obj)
    return obj


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, Server, server_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.server",
        entity_id=server_id,
        actor=user.subject,
    )


# ---------------------------------------------------------------------------
# GPU assets
# ---------------------------------------------------------------------------
@router.get("/gpus", response_model=list[schemas.GpuAssetRead])
async def list_gpus(
    session: Session,
    _user: ReadUser,
    server_id: str | None = None,
    gpu_model: str | None = None,
    operational_status: OperationalStatus | None = None,
    commercial_status: CommercialStatus | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(GpuAsset)
    if server_id is not None:
        stmt = stmt.where(GpuAsset.server_id == server_id)
    if gpu_model is not None:
        stmt = stmt.where(GpuAsset.model == gpu_model)
    if operational_status is not None:
        stmt = stmt.where(GpuAsset.operational_status == operational_status)
    if commercial_status is not None:
        stmt = stmt.where(GpuAsset.commercial_status == commercial_status)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/gpus/{gpu_asset_id}", response_model=schemas.GpuAssetRead)
async def get_gpu(gpu_asset_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, GpuAsset, gpu_asset_id)


@router.post("/gpus", response_model=schemas.GpuAssetRead, status_code=status.HTTP_201_CREATED)
async def create_gpu(payload: schemas.GpuAssetCreate, session: Session, user: WriteUser):
    obj = GpuAsset(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="inventory.gpu_asset",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/gpus/{gpu_asset_id}", response_model=schemas.GpuAssetRead)
async def update_gpu(
    gpu_asset_id: str, payload: schemas.GpuAssetUpdate, session: Session, user: WriteUser
):
    obj = await _get_or_404(session, GpuAsset, gpu_asset_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="inventory.gpu_asset",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/gpus/{gpu_asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gpu(gpu_asset_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, GpuAsset, gpu_asset_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="inventory.gpu_asset",
        entity_id=gpu_asset_id,
        actor=user.subject,
    )
