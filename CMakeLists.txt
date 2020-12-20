########################################################################
# Project setup
########################################################################
cmake_minimum_required(VERSION 2.6)
project(gr-op25 CXX C)
enable_testing()

#select the release build type by default to get optimization flags
if(NOT CMAKE_BUILD_TYPE)
   set(CMAKE_BUILD_TYPE "Release")
   message(STATUS "Build type not specified: defaulting to release.")
endif(NOT CMAKE_BUILD_TYPE)
set(CMAKE_BUILD_TYPE ${CMAKE_BUILD_TYPE} CACHE STRING "")

########################################################################
# Compiler specific setup
########################################################################
if(CMAKE_COMPILER_IS_GNUCXX AND NOT WIN32)
    #http://gcc.gnu.org/wiki/Visibility
    add_definitions(-fvisibility=hidden)
endif()

########################################################################
# Find boost
########################################################################
if(UNIX AND EXISTS "/usr/lib64")
    list(APPEND BOOST_LIBRARYDIR "/usr/lib64") #fedora 64-bit fix
endif(UNIX AND EXISTS "/usr/lib64")
set(Boost_ADDITIONAL_VERSIONS
    "1.35.0" "1.35" "1.36.0" "1.36" "1.37.0" "1.37" "1.38.0" "1.38" "1.39.0" "1.39"
    "1.40.0" "1.40" "1.41.0" "1.41" "1.42.0" "1.42" "1.43.0" "1.43" "1.44.0" "1.44"
    "1.45.0" "1.45" "1.46.0" "1.46" "1.47.0" "1.47" "1.48.0" "1.48" "1.49.0" "1.49"
    "1.50.0" "1.50" "1.51.0" "1.51" "1.52.0" "1.52" "1.53.0" "1.53" "1.54.0" "1.54"
    "1.55.0" "1.55" "1.56.0" "1.56" "1.57.0" "1.57" "1.58.0" "1.58" "1.59.0" "1.59"
    "1.60.0" "1.60" "1.61.0" "1.61" "1.62.0" "1.62" "1.63.0" "1.63" "1.64.0" "1.64"
    "1.65.0" "1.65" "1.66.0" "1.66" "1.67.0" "1.67" "1.68.0" "1.68" "1.69.0" "1.69"
)
find_package(Boost "1.35" COMPONENTS filesystem system)

if(NOT Boost_FOUND)
    message(FATAL_ERROR "Boost required to compile op25")
endif()

########################################################################
# Find gnuradio build dependencies
########################################################################
list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake/Modules)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
find_package(CppUnit)
if(NOT CPPUNIT_FOUND)
    message(FATAL_ERROR "CppUnit required to compile op25")
endif()
set(GR_REQUIRED_COMPONENTS RUNTIME BLOCKS FILTER PMT)
find_package(GnuradioRuntime)
find_package(Gnuradio REQUIRED)
MESSAGE(STATUS "GnuRadio version ${Gnuradio_VERSION}")
if ("${Gnuradio_VERSION}" VERSION_LESS "2.7.0")
    MESSAGE(FATAL_ERROR "OP25 Required Gnuradio minimum version 2.7.0")
elseif ("${Gnuradio_VERSION}" VERSION_LESS "3.8.0")
    set(OP25_PYTHON_VER 2)
else()
    set(OP25_PYTHON_VER 3) 
endif()
MESSAGE(STATUS "Configuring for Python ${OP25_PYTHON_VER}")

execute_process(COMMAND python${OP25_PYTHON_VER} -c "
import os
import sys
from distutils import sysconfig
pfx = '/usr/local'
m1 = os.path.join('lib', 'python' + sys.version[:3], 'dist-packages')
m2 = sysconfig.get_python_lib(plat_specific=True, prefix='')
f1 = os.path.join(pfx, m1)
f2 = os.path.join(pfx, m2)
ok2 = f2 in sys.path
if ok2:
	print(m2)
else:
	print(m1)
" OUTPUT_VARIABLE OP25_PYTHON_DIR OUTPUT_STRIP_TRAILING_WHITESPACE
)
MESSAGE(STATUS "OP25_PYTHON_DIR has been set to \"${OP25_PYTHON_DIR}\".")

add_subdirectory(op25/gr-op25)
add_subdirectory(op25/gr-op25_repeater)

########################################################################
# Create uninstall target
########################################################################
configure_file(
    ${CMAKE_SOURCE_DIR}/cmake/cmake_uninstall.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/cmake_uninstall.cmake
@ONLY)

add_custom_target(uninstall
    ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/cmake_uninstall.cmake
)
