import logging
import struct

from earthkit.data.readers import Reader

LOG = logging.getLogger(__name__)


class GeotiffReader(Reader):
    def __init__(self, source, path):
        super().__init__(source, path)

    def __repr__(self):
        return f"GeotiffReader ({self.path})"

    def to_pandas(self, **kwargs):
        raise NotImplementedError("method to_pandas() not implemented")

    def to_xarray(self, **kwargs):
        raise NotImplementedError("method to_xarray() not implemented")


def is_tiff(data):
    try:
        # Check if there are at least 8 bytes for TIFF header
        if len(data) < 8:
            return False  # Not enough data to be a valid TIFF file

        # Read endianness (first 2 byte)
        endian_indicator = data[:2]
        if endian_indicator == b"II":
            endian = "<"  # Little-endian
        elif endian_indicator == b"MM":
            endian = ">"  # Big-endian
        else:
            return False  # It is not a valid TIFF file

        # Check the magic number (byte 2-4)
        magic_number = struct.unpack(endian + "H", data[2:4])[0]
        if magic_number != 42:
            return False  # It is not a valid TIFF file

        # Validations checked, it is a valid TIFF file
        return True

    except Exception as e:
        LOG.exception(f"An error has occurred in is_tiff_from_bytes, {e}")
        return False


def reader(source, path, *, magic=None, deeper_check=False, **kwargs):
    """
    'is_tiff' function checks only if a file is a valid tiff,
    but it doesn't check if there are geographic information
    """
    if is_tiff(magic):
        return GeotiffReader(source, path)
