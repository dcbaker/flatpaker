# SPDX-License-Identifier: MIT
# Copyright © 2026 Dylan Baker

"""Pydantic Models for the the flatpak-manifest format
"""

from __future__ import annotations

import typing
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

if typing.TYPE_CHECKING:
    from typing import TypeAlias

    from typing_extensions import Self


# Workaround for pydantic not disginguishing that inputs to `__init__` are
# fundementally different than `model_validate`, i.e., that if I expect
# to have a field called `my-field`, then it must be serialized that way, but
# python class members cannot have that name, they must be `my_field`.
# Additionally, this requires that any calls to `.model_dump*` must have
# `by_alias=True` and any calls to `.model_validate*` be called with
# `validate_by_name=False`.
#
# I haven't attempted to sublcass BaseModel because it's too much work for
# my use.
#
# See: https://github.com/pydantic/pydantic/issues/11857
_CONFIG = ConfigDict(validate_by_alias=True, validate_by_name=True)


def _is_none(v: None | object) -> bool:
    """Helper for Field(exclude_if=...)

    :param v: The object in question
    :return: True if the object is None, otherwise False
    """
    return v is None


class BuildOptions(BaseModel):
    """Model of the flatpak-manifest Build Options."""

    model_config = _CONFIG

    cflags: list[str] | None = Field(default=None, exclude_if=_is_none)
    cflags_override: list[str] | None = Field(default=None, alias='cflags-override', exclude_if=_is_none)
    cppflags: list[str] | None = Field(default=None, exclude_if=_is_none)
    cppflags_override: list[str] | None = Field(default=None, alias='cppflags-override', exclude_if=_is_none)
    cxxflags: list[str] | None = Field(default=None, exclude_if=_is_none)
    cxxflags_override: list[str] | None = Field(default=None, alias='cxxflags-override', exclude_if=_is_none)
    ldflags: list[str] | None = Field(default=None, exclude_if=_is_none)
    ldflags_override: list[str] | None = Field(default=None, alias='ldflags-override', exclude_if=_is_none)
    prefix: str | None = Field(default=None, exclude_if=_is_none)
    libdir: str | None = Field(default=None, exclude_if=_is_none)
    append_path: str | None = Field(default=None, alias='append-path', exclude_if=_is_none)
    prepend_path: str | None = Field(default=None, alias='prepend-path', exclude_if=_is_none)
    append_ld_library_path: str | None = Field(default=None, alias='append-ld-library-path', exclude_if=_is_none)
    prepend_ld_library_path: str | None = Field(default=None, alias='prepend-ld-library-path', exclude_if=_is_none)
    env: dict[str, str] | None = Field(default=None, exclude_if=_is_none)
    secret_env: list[str] | None = Field(default=None, alias='secret-env', exclude_if=_is_none)
    make_args: list[str] | None = Field(default=None, alias='make-args', exclude_if=_is_none)
    make_install_args: list[str] | None = Field(default=None, alias='make-install-args', exclude_if=_is_none)
    strip: bool | None = Field(default=None, exclude_if=_is_none)
    no_debuginfo: bool | None = Field(default=None, alias='no-debuginfo', exclude_if=_is_none)
    no_debuginfo_compression: bool | None = Field(default=None, alias='no-debuginfo-compression', exclude_if=_is_none)
    arch: dict[str, BuildOptions] | None = Field(default=None, exclude_if=_is_none)


class _SourceBase(BaseModel):

    model_config = _CONFIG

    only_arches: list[str] | None = Field(default=None, alias='only-arches', exclude_if=_is_none)
    skip_arches: list[str] | None = Field(default=None, alias='skip-arches', exclude_if=_is_none)
    dest: str | None = Field(default=None, exclude_if=_is_none)


class _SourceWithUrlOrPathMixin(BaseModel):

    path: str | None = Field(default=None, exclude_if=_is_none)
    url: str | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode='before')
    @classmethod
    def __validate_path_or_url(cls, value: object) -> object:  # pylint: disable=W0238
        if isinstance(value, dict):
            url = value.get('url')
            path = value.get('path')

            if not url and not path:
                raise ValueError(
                    'A source of type "archive" must have either the "path" or "url" set')
            if url and path:
                raise ValueError(
                    'A source of type "archive" must have only one of the "path" or "url" fields set')

        return value


_ARCHIVE_TYPES: TypeAlias = typing.Literal[
    'rpm', 'tar', 'tar-gzip', 'tar-compress', 'tar-bzip2', 'tar-lzip',
    'tar-lzma', 'tar-lzop', 'tar-xz', 'tar-zst', 'zip', '7z']


class SourceArchive(_SourceBase, _SourceWithUrlOrPathMixin):
    """Model of an Archive type source."""

    type: typing.Literal['archive'] = Field('archive', init=False)
    mirror_urls: list[str] | None = Field(default=None, alias='mirror-urls', exclude_if=_is_none)
    referer: str | None = Field(default=None, exclude_if=_is_none)
    disable_http_decompression: bool | None = Field(default=None, alias='disable-http-decompression', exclude_if=_is_none)
    git_init: bool | None = Field(default=None, alias='git-init', exclude_if=_is_none)
    archive_type: _ARCHIVE_TYPES | None = Field(default=None, alias='archive-type', exclude_if=_is_none)
    # md5 is intentionally excluded
    # sha1 is intentionally excluded
    sha256: str | None = Field(default=None)
    sha512: str | None = Field(default=None)
    strip_components: int | None = Field(default=None, alias='strip-components', exclude_if=_is_none)
    dest_filename: str | None = Field(default=None, alias='dest-filename', exclude_if=_is_none)


class SourceGit(_SourceBase, _SourceWithUrlOrPathMixin):
    """Model of a Git type source"""

    type: typing.Literal['git'] = Field('git', init=False)
    branch: str | None = Field(default=None, exclude_if=_is_none)
    tag: str | None = Field(default=None, exclude_if=_is_none)
    commit: str | None = Field(default=None, exclude_if=_is_none)
    disable_fsckobjects: bool | None = Field(default=None, alias='disable-fsckobjects', exclude_if=_is_none)
    disable_shallow_clone: bool | None = Field(default=None, alias='disable-shallow-clone', exclude_if=_is_none)
    disable_submodules: bool | None = Field(default=None, alias='disable-submodules', exclude_if=_is_none)
    disable_lfs: bool | None = Field(default=None, alias='disable-lfs', exclude_if=_is_none)


class SourceBzr(_SourceBase):
    """Model of a BZR type source"""

    type: typing.Literal['bzr'] = Field('bzr', init=False)
    url: str
    revision: str | None = Field(default=None, exclude_if=_is_none)


class SourceSvn(_SourceBase):
    """Model of a SVN type source"""

    type: typing.Literal['svn'] = Field('svn', init=False)
    url: str
    revision: str | None = Field(default=None, exclude_if=_is_none)


class SourceDir(_SourceBase):
    """Model of a Directory type source"""

    type: typing.Literal['dir'] = Field('dir', init=False)
    path: str
    skip: list[str] | None = Field(default=None, exclude_if=_is_none)


class SourceFile(_SourceBase, _SourceWithUrlOrPathMixin):
    """Model of a File type source"""

    type: typing.Literal['file'] = Field('file', init=False)
    mirror_urls: list[str] | None = Field(default=None, alias='mirror-urls', exclude_if=_is_none)
    referer: str | None = Field(default=None, exclude_if=_is_none)
    disable_http_decompression: bool | None = Field(default=None, alias='disable-http-decompression', exclude_if=_is_none)
    # md5 is intentionally excluded
    # sha1 is intentionally excluded
    sha256: str | None = Field(default=None)
    sha512: str | None = Field(default=None)
    dest_filename: str | None = Field(default=None, alias='dest-filename', exclude_if=_is_none)


class SourceScript(_SourceBase):
    """Model of a script type source"""

    type: typing.Literal['script'] = Field('script', init=False)
    commands: list[str]
    dest_filename: str | None = Field(default=None, alias='dest-filename', exclude_if=_is_none)


class SourceInline(_SourceBase):
    """Model of a inline type source"""

    type: typing.Literal['inline'] = Field('inline', init=False)
    dest_filename: str | None = Field(default=None, alias='dest-filename', exclude_if=_is_none)
    contents: str
    base64: bool | None = Field(default=None, exclude_if=_is_none)


class SourceShell(_SourceBase):
    """Model of a shell type source"""

    type: typing.Literal['shell'] = Field('shell', init=False)
    commands: list[str]


class SourcePatch(_SourceBase):
    """Model of a patch type source"""

    type: typing.Literal['patch'] = Field('patch', init=False)
    path: str | None = Field(default=None, exclude_if=_is_none)
    paths: list[str] | None = Field(default=None, exclude_if=_is_none)
    strip_components: int | None = Field(default=None, alias='strip-components', exclude_if=_is_none)
    use_git: bool | None = Field(default=None, alias='use-git', exclude_if=_is_none)
    use_git_am: bool | None = Field(default=None, alias='use-git-am', exclude_if=_is_none)
    options: list[str] | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode='before')
    @classmethod
    def __validate_path_or_paths(cls, value: object) -> object:  # pylint: disable=W0238
        if isinstance(value, dict):
            path = value.get('path')
            paths = value.get('paths')

            if not paths and not path:
                raise ValueError(
                    'A source of type "patch" must have either the "path" or "paths" set')
            if paths and path:
                raise ValueError(
                    'A source of type "patch" must have only one of the "path" or "paths" fields set')

        return value


class SourceExtraData(_SourceBase):
    """Model of an extra-data type source"""

    type: typing.Literal['extra-data'] = Field('extra-data', init=False)
    filename: str
    url: str | None = Field(default=None, exclude_if=_is_none)
    sha256: str | None = Field(default=None, exclude_if=_is_none)
    size: int | None = Field(default=None, exclude_if=_is_none)
    installed_size: int | None = Field(default=None, alias='installed-zie', exclude_if=_is_none)


# This is a good place to use Union instead of `|` because of the long line
# length
SourceType: TypeAlias = typing.Union[  # noqa: UP007
    SourceArchive, SourceGit, SourceBzr, SourceSvn, SourceDir, SourceFile,
    SourceScript, SourceInline, SourceShell, SourcePatch, SourceExtraData
]
SourceListType: TypeAlias = list[SourceType]


class Module(BaseModel):
    """Model of the flatpak-manifest Module object """

    model_config = _CONFIG

    name: str
    disabled: bool | None = Field(default=None, exclude_if=_is_none)
    sources: Sequence[SourceType | str]
    secret_env: list[str] | None = Field(default=None, alias='secret-env', exclude_if=_is_none)
    config_opts: list[str] | None = Field(default=None, alias='config-opts', exclude_if=_is_none)
    secret_opts: list[str] | None = Field(default=None, alias='secret-opts', exclude_if=_is_none)
    make_args: list[str] | None = Field(default=None, alias='make-args', exclude_if=_is_none)
    make_install_args: list[str] | None = Field(default=None, alias='make-install-args', exclude_if=_is_none)
    rm_configure: bool | None = Field(default=None, alias='rm-configure', exclude_if=_is_none)
    no_autogen: bool | None = Field(default=None, alias='no-autogen', exclude_if=_is_none)
    no_parallel_make: bool | None = Field(default=None, alias='no-parallel-make', exclude_if=_is_none)
    install_rule: bool | None = Field(default=None, alias='install-rule', exclude_if=_is_none)
    no_make_install: bool | None = Field(default=None, alias='no-make-install', exclude_if=_is_none)
    no_python_timestamp_fix: bool | None = Field(default=None, alias='no-python-timestamp-fix', exclude_if=_is_none)
    # cmake is deprecated and not implemented intentionally
    buildsystem: typing.Literal['autotools', 'cmake', 'make-ninja', 'meson', 'simple', 'qmake']
    builddir: bool | None = Field(default=None, exclude_if=_is_none)
    subdir: str | None = Field(default=None, exclude_if=_is_none)
    build_options: BuildOptions | None = Field(default=None, alias='build-options', exclude_if=_is_none)
    build_commands: list[str] | None = Field(default=None, alias='build-commands', exclude_if=_is_none)
    post_install: list[str] | None = Field(default=None, alias='post-install', exclude_if=_is_none)
    cleanup: list[str] | None = Field(default=None, exclude_if=_is_none)
    ensure_writable: list[str] | None = Field(default=None, alias='ensure-writable', exclude_if=_is_none)
    only_arches: list[str] | None = Field(default=None, alias='only-arches', exclude_if=_is_none)
    skip_arches: list[str] | None = Field(default=None, alias='skip-arches', exclude_if=_is_none)
    cleanup_platform: list[str] | None = Field(default=None, alias='cleanup-platform', exclude_if=_is_none)
    run_tests: bool | None = Field(default=None, alias='run-tests', exclude_if=_is_none)
    test_rule: str | None = Field(default=None, alias='test-rule', exclude_if=_is_none)
    test_commands: list[str] | None = Field(default=None, alias='test-commands', exclude_if=_is_none)
    license_files: list[str] | None = Field(default=None, alias='license-files', exclude_if=_is_none)
    modules: list[Module | str] | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode='after')
    def __validate_simple_buildsystem(self) -> Self:  # pylint: disable=W0238
        if self.buildsystem == 'simple' and not self.build_commands:
            raise ValueError('When "buildsystem" is "simple", "build-commands" must be set', self.build_commands)

        return self


class Extension(BaseModel):
    """Model of the flatpak-manifest Extension object """

    model_config = _CONFIG

    directory: str
    bundle: bool | None = Field(default=None, exclude_if=_is_none)
    remove_after_build: bool | None = Field(default=None, alias='remove-after-build', exclude_if=_is_none)


class Manifest(BaseModel):
    """Model of the flatpak-manifest root object."""

    model_config = _CONFIG

    id: str
    branch: str | None = Field(default=None, exclude_if=_is_none)
    default_branch: str | None = Field(default=None, alias='default-branch', exclude_if=_is_none)
    collection_id: str | None = Field(default=None, alias='collection-id', exclude_if=_is_none)
    extension_tag: str | None = Field(default=None, alias='extension-tag', exclude_if=_is_none)
    token_type: str | None = Field(default=None, alias='token-type', exclude_if=_is_none)
    runtime: str
    runtime_version: str | None = Field(default=None, alias='runtime-version', exclude_if=_is_none)
    sdk: str
    var: str | None = Field(default=None, exclude_if=_is_none)
    metadata: str | None = Field(default=None, exclude_if=_is_none)
    command: str
    build_runtime: bool | None = Field(default=None, alias='build-runtime', exclude_if=_is_none)
    build_extension: bool | None = Field(default=None, alias='build-extension', exclude_if=_is_none)
    separate_locales: bool | None = Field(default=None, alias='separate-locales', exclude_if=_is_none)
    id_platform: str | None = Field(default=None, alias='id-platform', exclude_if=_is_none)
    metadata_platform: str | None = Field(default=None, alias='metadata-platform', exclude_if=_is_none)
    writeable_sdk: bool | None = Field(default=None, alias='writeable-sdk', exclude_if=_is_none)
    appstream_compose: bool | None = Field(default=None, alias='appstream-compose', exclude_if=_is_none)
    sdk_extensions: list[str] | None = Field(default=None, alias='sdk-extensions', exclude_if=_is_none)
    platform_extensions: list[str] | None = Field(default=None, alias='platform-extensions', exclude_if=_is_none)
    base: str | None = Field(default=None, exclude_if=_is_none)
    base_version: str | None = Field(default=None, alias='base-version', exclude_if=_is_none)
    base_extensions: list[str] | None = Field(default=None, alias='base-extensions', exclude_if=_is_none)
    inherit_extensions: list[str] | None = Field(default=None, alias='inherit-extensions', exclude_if=_is_none)
    inherit_sdk_extensions: list[str] | None = Field(default=None, alias='inherit-sdk-extensions', exclude_if=_is_none)
    tags: list[str] | None = Field(default=None, exclude_if=_is_none)
    build_options: BuildOptions | None = Field(default=None, alias='build-options', exclude_if=_is_none)
    modules: list[Module | str]
    add_extensions: dict[str, Extension] | None = Field(default=None, alias='add-extensions', exclude_if=_is_none)
    add_build_extensions: dict[str, Extension] | None = Field(default=None, alias='add-build-extensions', exclude_if=_is_none)
    cleanup: list[str] | None = Field(default=None, exclude_if=_is_none)
    cleanup_commands: list[str] | None = Field(default=None, alias='cleanup-commands', exclude_if=_is_none)
    cleanup_platform_commands: list[str] | None = Field(default=None, alias='cleanup-platform-commands', exclude_if=_is_none)
    prepare_platform_commands: list[str] | None = Field(default=None, alias='prepare-platform-commands', exclude_if=_is_none)
    finish_args: list[str] | None = Field(default=None, alias='finish-args', exclude_if=_is_none)  # TODO: validate these
    rename_desktop_file: str | None = Field(default=None, alias='rename-desktop-file', exclude_if=_is_none)
    rename_appdata_file: str | None = Field(default=None, alias='rename-appdata-file', exclude_if=_is_none)
    rename_mime_file: str | None = Field(default=None, alias='rename-mime-file', exclude_if=_is_none)
    rename_icon: str | None = Field(default=None, alias='rename-icon', exclude_if=_is_none)
    rename_mime_icons: list[str] | None = Field(default=None, alias='rename-mime-icons', exclude_if=_is_none)
    appdata_license: str | None = Field(default=None, alias='appdata-license', exclude_if=_is_none)
    copy_icon: bool | None = Field(default=None, alias='copy-icon', exclude_if=_is_none)
    desktop_file_name_prefix: str | None = Field(default=None, alias='destop-file-name-prefix', exclude_if=_is_none)
    desktop_file_name_suffix: str | None = Field(default=None, alias='destop-file-name-suffix', exclude_if=_is_none)
