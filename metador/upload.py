"""
Handle the upload per HTTP / tus
"""

from typing import Final

#: API route to handle tusd events
TUSD_HOOK_ROUTE: Final[str] = "/tusd-events"

# TODO: reject uploads to invalid uuid,
# on upload completion import into dataset and compute checksum as background job?
