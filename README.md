# flatpaker

Script to mostly automate creating flatpaks from published Ren'Py and Linux
builds of RPGMaker MV and MZ. Open to additional support

## What is it?

It's a script that automatically handles much of the task of generating a
flatpak for pre-built projects, including adding patches or mods. You
write a small, simple toml file, fetch the sources, and get a ready to publish
flatpak.

It currently does the following automatically:

- Generates an appstream xml file
- Generates a .desktop file
- Extracts an icon from the game source, and installs it
- patches the game to honor `$XDG_DATA_HOME` for storing game data inside the sandbox (instead of needing `$HOME` access)
- allows local install or publishing to a repo
- allows generating static deltas after building
- sets up the sandbox to allow audio and display, but nothing else

For Ren'Py:
- provides a runtime with up to date renpy and deps, built against the freedesktop Platform libraries.
  using the shared runtime saves space, as well as ensures that all games can be run with Wayland support.
- strips .rpy files to save space (keeping the rpyc files)

For RPG Maker:
- provides a runtime with a newer nwjs installed, saving disk space
- using this nwjs also gives guaranteed wayland support
- It also allows running MV and MZ games that don't ship Linux builds, using the Windows build

## Why?

I like playing Ren'Py and RPG Maker games sometimes. I also don't always trust
random pre-compiled binaries from the internet. Flatpak provides a nice,
convenient way to sandbox applications. It also makes supporting Steam Deck and
Fedora immutable a breeze. But generating flatpaks by hand is a lot of work,
especially when most of the process will be exactly the same for every project.
The use of up-to-date runtimes saves more disk space and allows for the sandbox
to provide even better security by using Wayland instead of X11 (or XWayland).

## How do I use it?

1. Download the compressed project
2. Download any mods or addons (optional)
3. Generate a toml description `flatpaker generate com.developer.game "Game Name" engine archive.zip`
4. Edit the generated description to fill in missing information
5. run `flatpaker build-runtimes --install` (which adds the runtimes and sdks)
6. run `flatpaker build --install *.toml` or `flatpaker build --export --gpg-sign *.toml` (for local install or for export to a shared repo)

### Toml Format

```toml
[common]
  name = 'Game or VN'  # use properly formatted name like "The Cool Adventures of Bob", or "Bob's Quest 7: Lawnmower Confusion"
  reverse_url = 'com.example.JDoe'  # name will be appended
  # "Game" is added automatically
  # used freedesktop menu categories. see: https://specifications.freedesktop.org/menu-spec/latest/apas02.html
  categories = ['Simulation']
  engine = 'renpy8'  # Or 'rpgmaker', 'renpy7', 'renpy7-py3'

[appdata]
  summary = "A short summary, one sentence or so."
  description = """
    A longer description.

    probably on multiple \
    lines
    """

  # This is an optional value for the license of the renpy project itself.
  # If unset it defaults to LicenseRef-Proprietary.
  # if you have specific terms which are not an Open Source license, you can use the form:
  # LicenseRef-Proprietary=https://www.example.com/my-license
  # See: https://spdx.org/specifications for more information
  license = "SPDX identifier"

[appdata.content_rating]
  # optional
  # Uses OARS specifications. See: https://hughsie.github.io/oars/
  # keys should be ids, and the values are must be a rating (as a string):
  # none, mild, moderate, or intense
  language-profanity = "mild"

[appdata.releases]
  # optional
  # in the form "date = version"
  "2023-01-01" = "1.0.0"

# Requires at least one entry
[[sources.archives]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, defaults to 1. How many directory levels to remove from this component
  strip_comonents = 2

  # Optional, will be automatically calculated if not provided, but providing it can speed up building
  sha256 = "abcd..."

  # Optional, will run these shell commands after extracting this archive
  commands = [
    'sed -i s/foo/bar/ extracted_source',
  ]

# Optional
[[sources.patches]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, defaults to 1. How many directory levels to remove from this component
  strip_comonents = 2

# Optional
[[sources.files]]
  # path must be set if this is provided
  path = "relative to toml or absolute path"

  # Optional, if set the file will be installed to this name
  # Does not have to be set for .rpy files that go in the game root directory
  dest = "where to install"

  # Optional, will be automatically calculated if not provided, but providing it can speed up building
  sha256 = "abcd..."

  # Optional, will run these shell commands after this file is added
  commands = [
    'sed -i s@/bin/bash@/usr/bin/env bash@ script.sh',
  ]
```

Sources will be evaluated by:
  1. archives, with their command entry
  2. files, with their command entry
  3. patches

#### Quirks

Additionally, some games have quirks that make them difficult to package. Some
of these quirks can be worked around.

Any quirk starting with `x_` or `x-` is an experimental quirk, and may be
removed at any time. If you find yourself relying on them, please open an issue.

For example:
```toml
[quirks]
  force_window_gui_icon = true
```


##### Generic

  - `x_configure_prologue: string`: A block of shell commands to run after
    unpacking all of the sources and applying patches, but before any build
    steps take place. This is slated for removal as the `commands` argument to archives and files should be able to fix all of this.


##### Renpy

  - `force_window_gui_icon: bool`. Use `game/gui/window_icon.png` instead
    of extracting icons from the exe or icns files. This is generally
    unnecessary, but some games have customized window_icons but not exe icons.

  - `x_renpy_archived_window_gui_icon: string`. Extract a `gui/window_icon.png` file
    from the named archive instead of extracting from the exe or icns files.
    This is generally unnecessary, but see above.


### Configuration

Some options can be given on the command line or via a configuration file.
That file must be written to `$XDG_CONFIG_HOME/flatpaker/config.toml` (if unset
`$XDG_CONFIG_HOME` defaults to `~/.config`).

```toml
[common]
  # A gpg private key to sign with, overwritten by the --gpg option
  gpg-key = "0x123456789"

  # The absolute path to a repo to write to. overwritten by the --repo option
  repo = "/path/to/a/repo/to/export"
```


## What is required?

- python >= 3.9
- python-tomlkit
- flatpak-builder
- flatpak

### Schema

A Json based schema is provided, which can be used with VSCode's EvenBetterToml
extension. It may be useful elsewhere.
