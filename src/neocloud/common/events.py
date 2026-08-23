"""Domain event publishing via AWS EventBridge."""
import json
from datetime import datetime, timezone
from typing import Any

import boto3

from neocloud.common.config import settings


class EventPublisher:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client("events", region_name=settings.aws_region)
        return self._client

    async def publish(
        self,
        source: str,
        detail_type: str,
        detail: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        """Publish a domain event to EventBridge."""
        entry = {
            "Source": f"neocloud.{source}",
            "DetailType": detail_type,
            "Detail": json.dumps(
                {
                    **detail,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                }
            ),
            "EventBusName": settings.aws_eventbridge_bus,
        }

        # In development, just log the event
        if settings.app_env == "development":
            import structlog
            logger = structlog.get_logger()
            logger.info("domain_event", source=source, detail_type=detail_type, detail=detail)
            return

        self.client.put_events(Entries=[entry])


event_publisher = EventPublisher()
