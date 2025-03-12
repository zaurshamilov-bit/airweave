"""Weaviate native destination implementation."""

from airweave.platform.decorators import destination
from airweave.platform.destinations.weaviate import WeaviateDestination


@destination("Weaviate Native", "weaviate_native")
class WeaviateNativeDestination(WeaviateDestination):
    """Weaviate native destination implementation."""
