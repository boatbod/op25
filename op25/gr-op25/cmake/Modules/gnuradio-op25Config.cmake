find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_OP25 gnuradio-op25)

FIND_PATH(
    GR_OP25_INCLUDE_DIRS
    NAMES gnuradio/op25/api.h
    HINTS $ENV{OP25_DIR}/include
        ${PC_OP25_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_OP25_LIBRARIES
    NAMES gnuradio-op25
    HINTS $ENV{OP25_DIR}/lib
        ${PC_OP25_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-op25Target.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_OP25 DEFAULT_MSG GR_OP25_LIBRARIES GR_OP25_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_OP25_LIBRARIES GR_OP25_INCLUDE_DIRS)
