find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_OP25_REPEATER gnuradio-op25_repeater)

FIND_PATH(
    GR_OP25_REPEATER_INCLUDE_DIRS
    NAMES gnuradio/op25_repeater/api.h
    HINTS $ENV{OP25_REPEATER_DIR}/include
        ${PC_OP25_REPEATER_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_OP25_REPEATER_LIBRARIES
    NAMES gnuradio-op25_repeater
    HINTS $ENV{OP25_REPEATER_DIR}/lib
        ${PC_OP25_REPEATER_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-op25_repeaterTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_OP25_REPEATER DEFAULT_MSG GR_OP25_REPEATER_LIBRARIES GR_OP25_REPEATER_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_OP25_REPEATER_LIBRARIES GR_OP25_REPEATER_INCLUDE_DIRS)
