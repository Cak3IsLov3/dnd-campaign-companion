from django.db import models


class CachedSRDEntry(models.Model):
    """A cached response from the D&D 5e SRD API.

    `index` is empty for list endpoints (e.g. all monsters) and holds the
    resource index (e.g. "goblin") for detail responses.
    """

    endpoint = models.CharField(max_length=60)
    index = models.CharField(max_length=120, blank=True, default="")
    data = models.JSONField()
    fetched_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["endpoint", "index"], name="unique_srd_entry")
        ]
        verbose_name = "cached SRD entry"
        verbose_name_plural = "cached SRD entries"

    def __str__(self):
        return f"{self.endpoint}/{self.index}"
