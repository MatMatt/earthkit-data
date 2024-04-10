# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging

import numpy as np

from earthkit.data.core.fieldlist import Field
from earthkit.data.core.geography import Geography
from earthkit.data.core.metadata import RawMetadata
from earthkit.data.utils.bbox import BoundingBox
from earthkit.data.utils.dates import to_datetime
from earthkit.data.utils.projections import Projection

from .coords import TimeSlice

LOG = logging.getLogger(__name__)

GEOGRAPHIC_COORDS = {
    "x": ["x", "projection_x_coordinate", "lon", "longitude"],
    "y": ["y", "projection_y_coordinate", "lat", "latitude"],
}


class DataSet:
    def __init__(self, ds):
        self._ds = ds
        self._bbox = {}
        self._cache = {}

    @property
    def data_vars(self):
        return self._ds.data_vars

    def __getitem__(self, key):
        if key not in self._cache:
            self._cache[key] = self._ds[key]
        return self._cache[key]

    def bbox(self, variable):
        data_array = self[variable]
        dims = data_array.dims

        lat = dims[-2]
        lon = dims[-1]

        if (lat, lon) not in self._bbox:
            dims = data_array.dims

            latitude = data_array[lat]
            longitude = data_array[lon]

            self._bbox[(lat, lon)] = (
                np.amax(latitude.data),
                np.amin(longitude.data),
                np.amin(latitude.data),
                np.amax(longitude.data),
            )

        return self._bbox[(lat, lon)]


class XArrayFieldGeography(Geography):
    def __init__(self, metadata, da, ds, variable):
        self.metadata = metadata
        self._da = da
        self._ds = ds
        self.north, self.west, self.south, self.east = self._ds.bbox(variable)

    def latitudes(self, dtype=None):
        return self.x(dtype=dtype)

    def longitudes(self, dtype=None):
        return self.y(dtype=dtype)

    def _get_xy(self, axis, flatten=False, dtype=None):
        if axis not in ("x", "y"):
            raise ValueError(f"Invalid axis={axis}")

        points = dict()
        for ax in ("x", "y"):
            for coord in self._da.coords:
                if self._da.coords[coord].attrs.get("axis", "").lower() == ax:
                    break
            else:
                candidates = GEOGRAPHIC_COORDS.get(ax, [])
                for coord in candidates:
                    if coord in self._da.coords:
                        break
                else:
                    raise ValueError(f"No coordinate found with axis '{ax}'")
            points[ax] = self._da.coords[coord]
        points["x"], points["y"] = np.meshgrid(points["x"], points["y"])
        if flatten:
            points[axis] = points[axis].flatten()
        if dtype is not None:
            return points[axis].astype(dtype)
        else:
            return points[axis]

    def x(self, dtype=None):
        return self._get_xy("x", flatten=True, dtype=dtype)

    def y(self, dtype=None):
        return self._get_xy("y", flatten=True, dtype=dtype)

    def shape(self):
        return self._da.shape[-2:]

    def _unique_grid_id(self):
        return self.shape

    def projection(self):
        return Projection.from_cf_grid_mapping(**self._grid_mapping().attrs)

    def bounding_box(self):
        return BoundingBox(
            north=self.north, south=self.south, east=self.east, west=self.west
        )

    def _grid_mapping(self):
        if "grid_mapping" in self._da.attrs:
            grid_mapping = self._ds[self._da.attrs["grid_mapping"]]
        else:
            raise AttributeError(
                "no CF-compliant 'grid_mapping' detected in netCDF attributes"
            )
        return grid_mapping

    def gridspec(self):
        raise NotImplementedError("gridspec is not implemented for netcdf/xarray")


class XArrayMetadata(RawMetadata):
    LS_KEYS = ["variable", "level", "time", "units"]

    def __init__(self, field):
        if not isinstance(field, XArrayField):
            raise TypeError(
                f"XArrayMetadata: expected field type XArrayField, got {type(field)}"
            )
        self._field = field
        self._geo = None

        d = dict(self._field._da.attrs)
        d["variable"] = self._field.variable
        for s in self._field.slices:
            if isinstance(s, TimeSlice):
                d[s.name] = to_datetime(s.value)
            else:
                d[s.name] = s.value
        super().__init__(d)

    def override(self, *args, **kwargs):
        return None

    @property
    def geography(self):
        if self._geo is None:
            self._geo = XArrayFieldGeography(
                self, self._field._da, self._field._ds, self._field.variable
            )
        return self._geo

    def _base_datetime(self):
        return self._valid_datetime()

    def _valid_datetime(self):
        return to_datetime(self._field.time)


class XArrayField(Field):
    def __init__(self, ds, variable, slices, non_dim_coords, array_backend):
        super().__init__(array_backend)
        self._ds = ds
        self._da = ds[variable]

        # self.north, self.west, self.south, self.east = ds.bbox(variable)

        self.variable = variable
        self.slices = slices
        self.non_dim_coords = non_dim_coords
        # self.name = self.variable

        # print(f"ds={ds}")
        # print(f"da={data_array}")
        # print(f"non_dim_coords={non_dim_coords}")

        self.title = getattr(
            self._da,
            "long_name",
            getattr(self._da, "standard_name", self.variable),
        )

        self.time = non_dim_coords.get("valid_time", non_dim_coords.get("time"))

        # print('====', non_dim_coords)

        # print(f"time={self.time}")

        for s in self.slices:
            if isinstance(s, TimeSlice):
                self.time = s.value

            if s.is_info:
                self.title += " (" + s.name + "=" + str(s.value) + ")"

        # print(f"-> time={self.time}")

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.variable},"
            + ",".join([f"{s.name}={s.value}" for s in self.slices])
            + ")"
        )

    def _make_metadata(self):
        return XArrayMetadata(self)

    def to_xarray(self):
        dims = self._da.dims
        v = {}
        for s in self.slices:
            if s.is_dimension:
                if s.name in dims:
                    v[s.name] = s.index
        return self._da.isel(**v)

    def to_pandas(self):
        return self.to_xarray().to_pandas()

    def _to_numpy(self):
        return self.to_xarray().to_numpy()

    def _values(self, dtype=None):
        if dtype is None:
            return self._to_numpy()
        else:
            return self._to_numpy().astype(dtype, copy=False)


class NetCDFMetadata(XArrayMetadata):
    pass


class NetCDFField(XArrayField):
    def _make_metadata(self):
        return NetCDFMetadata(self)
