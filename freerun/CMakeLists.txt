cmake_minimum_required(VERSION 3.25)

project(AltairFreerun VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

# CommonLibSSE-NG and the SKSE Menu Framework header are read from the faith-runner checkout (not modified; built
# into this project's own build folder).
set(FR_SKYRIM "C:/Users/myste/Downloads/faith-runner/faith-runner/skyrim" CACHE PATH "faith-runner skyrim folder")
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ENABLE_SKYRIM_VR OFF CACHE BOOL "" FORCE)
set(SKSE_SUPPORT_XBYAK ON CACHE BOOL "" FORCE)
add_subdirectory("${FR_SKYRIM}/extern/CommonLibSSE-NG" CommonLibSSE EXCLUDE_FROM_ALL)
if(NOT COMMAND add_commonlibsse_plugin)
	include("${FR_SKYRIM}/extern/CommonLibSSE-NG/cmake/CommonLibSSE.cmake")
endif()

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp src/*.h)
add_commonlibsse_plugin(
	AltairFreerun
	NAME "AltairFreerun"
	AUTHOR "Altair AC1 Skyrim"
	USE_ADDRESS_LIBRARY
	SOURCES ${SOURCES}
)
target_include_directories(AltairFreerun PRIVATE src "${FR_SKYRIM}/extern/SKSEMenuFramework")
target_precompile_headers(AltairFreerun PRIVATE src/PCH.h)
target_compile_definitions(AltairFreerun PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
if(MSVC)
	target_compile_options(AltairFreerun PRIVATE /W4 /permissive- /Zc:preprocessor /utf-8 /MP /wd4200)
	target_link_options(AltairFreerun PRIVATE /DEBUG:FULL)
endif()

if(ALTAIR_DEPLOY_DIR)
	add_custom_command(TARGET AltairFreerun POST_BUILD
		COMMAND ${CMAKE_COMMAND} -E make_directory "${ALTAIR_DEPLOY_DIR}/SKSE/Plugins"
		COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:AltairFreerun>" "${ALTAIR_DEPLOY_DIR}/SKSE/Plugins/"
		VERBATIM)
endif()
