# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging
import math

from earthkit.data.core.fieldlist import Field
from earthkit.data.indexing.fieldlist import NewFieldWrapper
from earthkit.data.utils.array import array_namespace

LOG = logging.getLogger(__name__)


class ArrayField(Field):
    r"""Represent a field consisting of an array and metadata object.

    Parameters
    ----------
    array: array
        Array storing the values of the field
    metadata: :class:`Metadata`
        Metadata object describing the field metadata.
    """

    def __init__(self, array, metadata):
        if isinstance(array, list):
            import numpy as np

            array = np.array(array)

        if isinstance(metadata, dict):
            from earthkit.data.utils.metadata.dict import UserMetadata

            metadata = UserMetadata(metadata, values=array)

        # TODO: this solution is questionable due to performance reasons
        if metadata is not None:
            metadata = metadata._hide_internal_keys()

        self.__metadata = metadata
        self._array = array

    def _values(self, dtype=None):
        """Native array type"""
        if dtype is None:
            return self._array
        else:
            return array_namespace(self._array).astype(self._array, dtype, copy=False)

    def __repr__(self):
        return self.__class__.__name__ + "(%s,%s,%s,%s,%s,%s)" % (
            self._metadata.get("shortName", None),
            self._metadata.get("levelist", None),
            self._metadata.get("date", None),
            self._metadata.get("time", None),
            self._metadata.get("step", None),
            self._metadata.get("number", None),
        )

    def write(self, f, **kwargs):
        r"""Write the field to a file object.

        Parameters
        ----------
        f: file object
            The target file object.
        **kwargs: dict, optional
            Other keyword arguments passed to :meth:`data.writers.grib.GribWriter.write`.
        """
        from earthkit.data.writers import write

        write(f, self, values=self.to_numpy(flatten=True), **kwargs)

    @property
    def _metadata(self):
        return self.__metadata

    @property
    def handle(self):
        return self._metadata._handle

    def __getstate__(self) -> dict:
        ret = {}
        ret["_array"] = self._array
        ret["_metadata"] = self._metadata
        return ret

    def __setstate__(self, state: dict):
        self._array = state.pop("_array")
        self.__metadata = state.pop("_metadata")

    def copy(self, **kwargs):
        return NewArrayField(self, **kwargs)


class NewArrayField(NewFieldWrapper, ArrayField):
    def __init__(self, field, **kwargs):
        NewFieldWrapper.__init__(self, field, **kwargs)
        ArrayField.__init__(self, field._array, None)


def from_array(array, metadata):
    def _shape_match(shape1, shape2):
        if shape1 == shape2:
            return True
        if len(shape1) == 1 and shape1[0] == math.prod(shape2):
            return True
        return False

    if not isinstance(metadata, list):
        metadata = [metadata]

    # array_ns = get_backend(self._array).array_ns
    if isinstance(array, list):
        if len(array) == 0:
            raise ValueError("array must not be empty")

    if not isinstance(array, list):
        array_ns = array_namespace(array)
        if array_ns is None:
            raise ValueError(f"array type {type(array)} is not supported")
        elif array.shape[0] != len(metadata):
            # we have a single array and a single metadata
            if len(metadata) == 1 and _shape_match(array.shape, metadata[0].geography.shape()):
                array = array_ns.stack([array])
            else:
                raise ValueError(
                    (
                        f"first array dimension={array.shape[0]} differs "
                        f"from number of metadata objects={len(metadata)}"
                    )
                )
    else:
        if len(array) != len(metadata):
            raise ValueError(
                (f"array len=({len(array)}) differs " f"from number of metadata objects=({len(metadata)})")
            )

    fields = []
    for i, a in enumerate(array):
        if len(metadata) == 1:
            fields.append(ArrayField(a, metadata[0]))
        else:
            fields.append(ArrayField(a, metadata[i]))

    from earthkit.data.indexing.fieldlist import SimpleFieldList

    return SimpleFieldList(fields)
