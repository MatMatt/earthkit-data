import earthkit.data

from earthkit.data.testing import earthkit_file


def test_geotiff_reader():
    s = earthkit.data.from_source(
        "file",
        earthkit_file("tests/data/test_geotiff.tiff"),
    )
    print(s)
    assert isinstance(s._reader, earthkit.data.readers.geotiff.GeotiffReader)


if __name__ == "__main__":
    from earthkit.data.testing import main

    main(__file__)
