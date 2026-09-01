-- Shared utilities for the Ariadne notes workflow
local M = {}

-- The vault path used before obsidian.nvim has an active workspace (or if it
-- never gets one). A rawset field, not routed through the __index below.
M.default_vault_path = vim.fn.expand("~/notes")

-- M.vault_path is a computed property reading the active workspace's vault
-- root (obsidian.nvim's Obsidian.dir), so :ObsidianWorkspace switches take
-- effect without a restart.
-- Note names, previews and paths come from note content, not from nvim itself.
-- Escape rather than blank out control characters: a picker keyed on its own
-- rendered rows needs distinct notes to render distinctly, and collapsing every
-- control char to a space makes "a\tb" and "a b" collide, so selecting one row
-- opens the other note. Lua's %c is ASCII-only, so the bidi and zero-width
-- formatting characters -- which can reorder a row on screen and disguise which
-- note it names -- are escaped explicitly.
function M.sanitize(s)
  s = tostring(s or "")
  s = s:gsub("%c", function(c)
    return string.format("<%02X>", c:byte())
  end)
  s = s:gsub("\226\128([\139-\143\168-\174])", function(b)
    return string.format("<U+20%02X>", b:byte() - 0x80)
  end)
  return (s:gsub("\239\187\191", "<U+FEFF>"))
end

-- Render an untrusted note name as a wikilink for writing into a note file.
-- sanitize() escapes control characters, so a name carrying a newline cannot
-- become a line of its own -- which matters because nvim reads a modeline from
-- the last five lines of a file it opens. A name containing a bracket gets no
-- link syntax at all: "]]" would close the wikilink early, forging a link to a
-- note the writer never referenced.
function M.as_wikilink(name)
  local safe = M.sanitize(name)
  if safe:find("[%[%]]") then
    return safe
  end
  return "[[" .. safe .. "]]"
end

-- `vim.cmd("edit " .. fnameescape(path))` is not safe for a path that came from
-- the filesystem: fnameescape does not escape a newline, and nvim_exec2 splits on
-- it first, so anything after it runs as an Ex command. The structured form takes
-- the path as an argument rather than as command text.
--
-- Returns whether it opened anything, so a caller that does something positional
-- next (a split, a put) can bail instead of acting on the wrong buffer.
function M.edit(path)
  if type(path) ~= "string" or path == "" then
    vim.notify("Could not resolve the selected note", vim.log.levels.WARN)
    return false
  end
  vim.cmd.edit({ args = { path } })
  return true
end


-- Seeded once per session from a clock finer than one second: os.time() made two
-- commands run in the same second replay the same draw.
math.randomseed((vim.uv or vim.loop).hrtime())

-- `count` distinct elements of `list`, in random order; fewer only if the list
-- is shorter than that.
function M.sample(list, count)
  local picked, taken = {}, {}
  count = math.min(count, #list)
  while #picked < count do
    local idx = math.random(#list)
    if not taken[idx] then
      taken[idx] = true
      table.insert(picked, list[idx])
    end
  end
  return picked
end

-- Run one of the notes-* CLI tools over the vault and decode its --json output.
--
-- `required` names the top-level keys the caller is about to index; a payload
-- missing any of them fails here rather than at the indexing site. `opts.level`
-- is the severity of a failure -- ERROR for a view the user explicitly asked
-- for, WARN where the caller carries on without the result -- and `opts.context`
-- names what is lost when that happens.
--
-- ariadne-similar is deliberately not routed through this: it runs asynchronously,
-- takes the current note before the vault, and reports its own `error` field.
function M.run_ariadne_tool(tool, extra_argv, required, opts)
  opts = opts or {}
  local level = opts.level or vim.log.levels.ERROR
  local lost = opts.context and (" (" .. opts.context .. ")") or ""
  if vim.fn.executable(tool) == 0 then
    vim.notify(tool .. " not found on PATH (see dotfiles/bin)" .. lost, level)
    return nil
  end

  local argv = { tool, M.vault_path }
  vim.list_extend(argv, extra_argv or {})
  table.insert(argv, "--json")

  local result = vim.system(argv, { text = true }):wait(opts.timeout or 30000)
  local output = result.stdout or ""
  if result.stderr and result.stderr ~= "" then
    vim.notify(tool .. ": " .. M.sanitize(result.stderr), vim.log.levels.WARN)
  end

  local ok, decoded = pcall(vim.json.decode, output)
  if result.code ~= 0 or not ok or type(decoded) ~= "table" then
    local detail = output == "" and "(no output)" or output:sub(1, 200)
    vim.notify("Failed to parse " .. tool .. " output" .. lost .. ": " .. M.sanitize(detail), level)
    return nil
  end
  for _, key in ipairs(required or {}) do
    if type(decoded[key]) ~= "table" then
      vim.notify(tool .. " output has no '" .. key .. "'" .. lost, level)
      return nil
    end
  end
  return decoded
end

-- Write the current buffer to `path`, with the same hazard and the same
-- structured form as M.edit. Returns false without writing when the path is
-- unusable, so a caller that deletes the original next can stop instead.
function M.write(path)
  if type(path) ~= "string" or path == "" then
    vim.notify("Could not resolve the destination path", vim.log.levels.WARN)
    return false
  end
  vim.cmd.write({ args = { path } })
  return true
end

-- nvim reports a buffer's name with symlinks resolved, so a vault configured
-- through one shares no prefix with its own notes: a vault at /var/... yields
-- buffers under /private/var/..., and `~/notes -> ~/Dropbox/notes` does the same.
-- Resolve anything before comparing it with anything else.
function M.resolve(path)
  if type(path) ~= "string" or path == "" then
    return path
  end
  local uv = vim.uv or vim.loop
  local real = uv.fs_realpath(path)
  if real then
    return real
  end
  -- Not on disk yet -- a new note in an unwritten buffer. The symlink is on the
  -- directory, which does exist, so resolving that still places the file.
  local dir = uv.fs_realpath(vim.fn.fnamemodify(path, ":h"))
  return dir and (dir .. "/" .. vim.fn.fnamemodify(path, ":t")) or path
end

-- Whether `path` is a file inside the vault. Both sides resolved, so this is the
-- only correct way to ask; a bare `vim.startswith(path, vault)` is not.
function M.in_vault(path)
  if type(path) ~= "string" or path == "" then
    return false
  end
  return vim.startswith(M.resolve(path), M.resolve(M.vault_path) .. "/")
end

setmetatable(M, {
  __index = function(_, key)
    if key == "vault_path" then
      if Obsidian and Obsidian.dir then
        return tostring(Obsidian.dir)
      end
      return M.default_vault_path
    end
  end,
})

function M.get_note_name(filepath)
  return vim.fn.fnamemodify(filepath, ":t:r")
end

function M.get_note_preview(filepath, max_len)
  max_len = max_len or 50
  local file = io.open(filepath, "r")
  if not file then
    return ""
  end
  -- Skip frontmatter and find first meaningful line
  local in_frontmatter = false
  local preview = ""
  for line in file:lines() do
    if line:match("^---") then
      in_frontmatter = not in_frontmatter
    elseif not in_frontmatter then
      -- Skip headings, empty lines, and links-only lines
      local trimmed = line:gsub("^%s+", ""):gsub("%s+$", "")
      if trimmed ~= "" and not trimmed:match("^#") and not trimmed:match("^%[%[.*%]%]$") then
        preview = trimmed
        break
      end
    end
  end
  file:close()
  if #preview > max_len then
    preview = preview:sub(1, max_len) .. "…"
  end
  return preview
end

function M.get_backlink_context(filepath, note_name, max_len)
  max_len = max_len or 50
  local file = io.open(filepath, "r")
  if not file then
    return ""
  end
  local pattern = "%[%[" .. note_name:gsub("([%-%.%+%[%]%(%)%$%^%%%?%*])", "%%%1")
  for line in file:lines() do
    if line:match(pattern) then
      -- Remove the link itself and clean up
      local context = line:gsub("%[%[[^%]]+%]%]", ""):gsub("^%s+", ""):gsub("%s+$", "")
      file:close()
      if context == "" then
        return "(link only)"
      end
      if #context > max_len then
        context = context:sub(1, max_len) .. "…"
      end
      return context
    end
  end
  file:close()
  return ""
end

-- Find a note file by name (case-insensitive), argv-based so link text from a
-- note buffer can never reach a shell. -quit stops at the first match instead
-- of walking the whole vault on every call.
function M.find_note_file(name)
  local result =
    vim.system({ "find", M.vault_path, "-iname", name .. ".md", "-type", "f", "-print", "-quit" }, { text = true })
      :wait()
  if result.code ~= 0 then
    vim.notify("find failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
    return nil
  end
  return (result.stdout or ""):match("[^\n]+")
end

-- List markdown files under the vault, argv-based for the same reason as
-- find_note_file. opts.maxdepth / opts.name narrow the search (e.g. daily notes).
function M.list_note_files(opts)
  opts = opts or {}
  local argv = { "find", M.vault_path }
  if opts.maxdepth then
    vim.list_extend(argv, { "-maxdepth", tostring(opts.maxdepth) })
  end
  vim.list_extend(argv, { "-name", opts.name or "*.md", "-type", "f" })
  local result = vim.system(argv, { text = true }):wait()
  if result.code ~= 0 then
    vim.notify("find failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
    return {}
  end
  return vim.split(result.stdout or "", "\n", { trimempty = true })
end

-- Find notes containing `search_term` (fixed string), argv-based for the same
-- reason as find_note_file. grep exits 1 for "no match" (not an error).
function M.grep_note_files(search_term, opts)
  opts = opts or {}
  local flags = opts.ignorecase and "-rilF" or "-rlF"
  local result =
    vim.system({ "grep", flags, "--include=*.md", "--", search_term, M.vault_path }, { text = true }):wait()
  if result.code > 1 then
    vim.notify("grep failed: " .. (result.stderr or ""), vim.log.levels.ERROR)
    return {}
  end
  return vim.split(result.stdout or "", "\n", { trimempty = true })
end

function M.get_forward_links(filepath)
  local links = {}
  local seen = {}
  local file = io.open(filepath, "r")
  if not file then
    return links
  end
  local content = file:read("*a")
  file:close()

  -- Match [[wiki links]] and [[wiki links|alias]]
  for link in content:gmatch("%[%[([^%]|]+)") do
    if not seen[link] then
      seen[link] = true
      table.insert(links, { name = link, path = M.find_note_file(link) })
    end
  end

  table.sort(links, function(a, b) return a.name < b.name end)
  return links
end

function M.get_backlinks(filepath)
  local note_name = M.get_note_name(filepath)
  local backlinks = {}

  -- Search for [[note_name using fixed string (matches [[note]] and [[note|alias]])
  local search_term = "[[" .. note_name
  local result = M.grep_note_files(search_term)

  for _, file in ipairs(result) do
    if file ~= filepath then
      table.insert(backlinks, { name = M.get_note_name(file), path = file })
    end
  end
  table.sort(backlinks, function(a, b) return a.name < b.name end)
  return backlinks
end

function M.wrap_line(text, width)
  if #text <= width then
    return { text }
  end
  local lines = {}
  local current = ""
  for word in text:gmatch("%S+") do
    if #current + #word + 1 <= width then
      current = current == "" and word or (current .. " " .. word)
    else
      if current ~= "" then
        table.insert(lines, current)
      end
      current = word
    end
  end
  if current ~= "" then
    table.insert(lines, current)
  end
  return lines
end

function M.get_line_highlight(line)
  if line:match("^#+%s") then
    return "AriadneTransclusionHeader"
  elseif line:match("^%s*[-*]%s") or line:match("^%s*%d+%.%s") then
    return "AriadneTransclusionList"
  elseif line:match("%[%[.+%]%]") or line:match("%[.+%]%(") then
    return "AriadneTransclusionLink"
  elseif line:match("%*%*.+%*%*") or line:match("__.+__") then
    return "AriadneTransclusionBold"
  else
    return "AriadneTransclusionContent"
  end
end

function M.escape_pattern(s)
  return s:gsub("([%-%.%+%[%]%(%)%$%^%%%?%*])", "%%%1")
end

return M
