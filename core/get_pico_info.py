import ctypes
from ctypes import ArgumentError
from picosdk.psospa import psospa as ps
from picosdk.PicoDeviceEnums import picoEnum as enums
from picosdk.functions import assert_pico_ok
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP


def pico_info() -> tuple[list[str], list[str]]:
    chandle = ctypes.c_int16()
    status = {}
    err = []

    def __check_health(status: hex, stop: bool = False) -> str | None:
        try:
            assert_pico_ok(status)
        except PicoSDKCtypesError:
            ps.psospaCloseUnit(chandle)
            return f'{PICO_STATUS_LOOKUP[status]}'
        return None

    resolution = enums.PICO_DEVICE_RESOLUTION["PICO_DR_8BIT"]
    status["openUnit"] = ps.psospaOpenUnit(ctypes.byref(chandle), None, resolution, None)
    err.append(__check_health(status["openUnit"]))

    SIZE = ctypes.c_short(20)
    info = [(ctypes.c_char * SIZE.value)() for _ in range(3)]
    stringLength = ctypes.c_int16(SIZE.value)
    requiredSize = ctypes.c_int16(SIZE.value)
    query = ps.PICO_INFO["PICO_VARIANT_INFO"]
    try:
        status["getInfo"] = ps.psospaGetUnitInfo(
            chandle,
            ctypes.byref(info[0]),
            # None,
            stringLength,
            ctypes.byref(requiredSize),
            query
        )
        err.append(__check_health(status["getInfo"]))
    except ArgumentError as error:
        err.append(str(error))

    # print(f'{requiredSize=}')
    status["closeUnit"] = ps.psospaCloseUnit(chandle)
    err.append(__check_health(status["closeUnit"]))

    return err, info
