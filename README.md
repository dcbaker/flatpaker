# renpy2flatpak

Script to mostly automate creating flatpaks from published renpy projects

## What is it?

It's a script that automatically handles much of the task of generating a
flatpak for pre-built renpy projects, including adding patches or mods. You
write a small, simple yaml file, fetch the sources, and get a ready to publish
flatpak.

It currently automatically does the following automatically:

- Generates an appstream xml file
- Generates a .desktop file
- Extracts an icon from the game source, and installs it
- patches the game to honor $XDG_DATA_HOME for storing game data inside the sandbox (instead of needing $HOME access)
- sets up the sandbox to allow audio and display, but nothing else
- recompiles the program when mods are applied
- strips .rpy files to save space (keeping the rpyc files)
- strips windows and macos specific files
- allows local install or publishing to a repo

## Why?

I like playing renpy games sometimes. I also don't always trust random
pre-compiled binaries from the internet. Flatpak provides a nice, convenient
way to sandbox applications. But generating flatpaks by hand is a lot of work,
especially when most of the process will be exactly the same for every renpy
project.

## How do I use it?

1. Download the compressed project
2. Download any mods or addons (optional)
3. Write a yaml description

### Yaml Format

```yaml
common:
  name: Game or VN
  reverse_url: com.example.JDoe  # name will be appended
  categories:
    # used freedesktop menu categories. see: https://specifications.freedesktop.org/menu-spec/latest/apas02.html
    # "Game" is added automatically
    - Simulation
appdata:
  summary: "A short summary"
  description: |
    A longer description.

    probably on multiple lines
  content_rating:
    # Uses OARS specifications. See: https://hughsie.github.io/oars/
    # keys should be ids, and the values must be a rating: none, mild, moderate, or intense
    language-profanity: mild
```
