"""Weaviate native destination implementation."""

from app.platform.decorators import destination
from app.platform.destinations.weaviate import WeaviateDestination


@destination("Weaviate Native", "weaviate_native")
class WeaviateNativeDestination(WeaviateDestination):
    """Weaviate native destination implementation."""
