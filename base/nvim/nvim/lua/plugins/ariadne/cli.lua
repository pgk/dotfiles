-- Reading what the `ariadne-*` tools send back, and rendering it into a picker.
--
-- `utils.run_ariadne_tool` is the *synchronous* runner and stays where it is.
-- This is the part the two async callers share: the payload check and the
-- picker-row helpers. Not the runner -- `similar.lua` and `duplicates.lua` order
-- their argv differently and only one of them announces itself, so an async
-- runner at two callers would be a flag per difference.
local utils = require("plugins.ariadne.utils")

local M = {}

-- vim.json.decode maps a JSON null to vim.NIL, which is truthy -- so `x or 0`
-- passes it straight into string.format and throws.
function M.num(v)
  return type(v) == "number" and v or 0
end

-- The graph the clustering ran on. Many tiny components, or a modularity near
-- zero, means there are no real clusters and any [cluster N] mark is noise.
function M.header_for(shape)
  if type(shape) ~= "table" then
    return nil
  end
  return string.format(
    "%d notes, %d links, %d components, largest %d -- %d clusters, modularity %.3f",
    M.num(shape.notes),
    M.num(shape.edges),
    M.num(shape.components),
    M.num(shape.largest_component),
    M.num(shape.clusters),
    M.num(shape.modularity)
  )
end

-- A note's path as a picker shows it: relative to the vault, sanitized.
-- Both sides resolved, or a symlinked vault strips nothing and every row shows
-- an absolute path.
function M.relative(path, vault)
  local prefix = utils.resolve(vault or utils.vault_path) .. "/"
  return utils.sanitize((utils.resolve(path):gsub("^" .. vim.pesc(prefix), "")))
end

-- Decode an `ariadne-* --json` payload, or explain why it cannot be used.
-- Returns the decoded table, or nil after notifying. The caller keeps its own
-- "nothing found" message, which is the only part that genuinely differs.
function M.decode(label, result, required_key)
  local output = result.stdout or ""
  local ok, decoded = pcall(vim.json.decode, output)
  if not ok or type(decoded) ~= "table" or type(decoded[required_key]) ~= "table" then
    -- Prefer stderr: a crash exits non-zero with an empty stdout, and
    -- "(no output)" hides the reason. Both streams are CLI-derived, so both
    -- get sanitized.
    local stderr = result.stderr or ""
    local detail = output ~= "" and output:sub(1, 200)
      or (stderr ~= "" and stderr:sub(1, 200))
      or ("exit code " .. tostring(result.code))
    vim.notify(label .. " failed: " .. utils.sanitize(detail), vim.log.levels.ERROR)
    return nil
  end
  if not decoded.available then
    -- stderr carries the same reason, so report only the structured one here.
    vim.notify(label .. ": " .. utils.sanitize(decoded.error or "embeddings unavailable"), vim.log.levels.WARN)
    return nil
  end
  -- Surfaced only on the success path, where it is not a duplicate of `error`:
  -- carries the "sending N notes to <endpoint>" egress notice.
  if result.stderr and result.stderr ~= "" then
    vim.notify(label .. ": " .. utils.sanitize(vim.trim(result.stderr)), vim.log.levels.INFO)
  end
  return decoded
end

return M
