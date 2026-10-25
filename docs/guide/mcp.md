# MCP server (AI assistants)

`mc9 mcp` starts a [Model Context Protocol](https://modelcontextprotocol.io) server so an AI assistant (Claude Code, Claude
Desktop, any MCP client) can run MC9 for you: build a circuit from a description, run analyses, read the numbers and look at
MC9's screenshots.

## Set it up

1. Install with the `mcp` extra, inside the virtual environment from the install page:

    ```bash
    pip install "mc9py[mcp] @ git+https://github.com/DontforgetAntaiku/mc9py.git"
    ```

2. Find where the `mc9` program is, because the assistant starts it itself and does not know about your virtual environment:

    ```bash
    which mc9                    # PowerShell: (Get-Command mc9).Source
    # e.g. /home/you/mc9-env/bin/mc9   or   C:\Users\you\mc9-env\Scripts\mc9.exe
    ```

3. **Claude Code**: run this in an ordinary terminal (not in Python), with the path from step 2:

    ```bash
    claude mcp add microcap9 -- /home/you/mc9-env/bin/mc9 mcp
    claude mcp list
    ```

    If `mc9` is on your `PATH` (for example after `pipx install`), `claude mcp add microcap9 -- mc9 mcp` is enough. Without a
    direct path you can also use `python -m mc9 mcp` with the environment's Python.

4. **Claude Desktop and other clients**: add this to the client's config and restart it. Claude Desktop: *Settings ->
   Developer -> Edit Config* (`~/.config/Claude/claude_desktop_config.json` on Linux, `%APPDATA%\Claude\claude_desktop_config.json`
   on Windows):

    ```json
    { "mcpServers": { "microcap9": { "command": "/home/you/mc9-env/bin/mc9", "args": ["mcp"] } } }
    ```

## Tools

| Group | Tools |
|---|---|
| Files | `import_circuit`, `export_circuit` (never overwrites), `list_circuits`, `circuit_info`, `set_component`, `set_analysis` |
| Analyses | `ac_sweep`, `transient`, `dc_sweep`, `operating_point`, `distortion_plot`, `dynamic_dc`, `dynamic_ac` |
| Plot tools | `place_cursors`, `screenshot`, `exit_analysis` |
| Measurements | `measure_bandwidth`, `measure_rin`, `measure_rout`, `measure_thd` |
| Building | `build_schematic` (JSON parts + wires), `build_netlist` (SPICE-like, auto-placed) |
| Housekeeping | `stop_mc9`, `reset_sandbox` |

The server is a thin layer over the Python library, so everything an assistant does is reproducible as a script.
Screenshots are returned as images the assistant can look at.
