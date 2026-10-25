# Command line

```
mc9 setup PREFIX [--home DIR]   create the sandbox snapshot from a Wine prefix with MC9 installed (Linux)
mc9 doctor                      check dependencies, the snapshot and the location of mc9.exe
mc9 reset                       discard the working Wine prefix (Linux); recreated from the snapshot on next use
mc9 mcp                         run the MCP server on stdio (needs the `mcp` extra)
mc9 version
```

`mc9 doctor` exits with status 1 when something is missing and prints a hint for each problem.
