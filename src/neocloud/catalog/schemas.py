"""Catalog domain schemas."""
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import List, Optional
import uuid
from datetime import datetime

from .models import GPUGeneration, GPUMemoryType, ProductStatus, PricingModel


class GPUProductResponse(BaseModel):
    """GPU product response schema."""
    id: uuid.UUID
    sku: str
    name: str
    description: Optional[str]
    gpu_model: str
    gpu_generation: GPUGeneration
    manufacturer: str
    memory_size_gb: int
    memory_type: GPUMemoryType
    status: ProductStatus
    base_price_per_hour: Optional[Decimal] = Field(None, description="Base hourly price")
    created_at: datetime
    
    class Config:
        from_attributes = True


class ServiceOfferingResponse(BaseModel):
    """Service offering response schema."""
    id: uuid.UUID
    offering_code: str
    name: str
    description: Optional[str]
    gpu_product_sku: str
    gpu_count: int
    vcpu_count: int
    memory_gb: int
    pricing_model: PricingModel
    base_price_per_hour: Decimal
    status: ProductStatus
    available_regions: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True