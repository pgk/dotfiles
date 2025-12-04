-- Shared utilities for Obsidian integration
local M = {}

M.vault_path = vim.fn.expand("~/notes")

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
      -- Find the actual file path
      local handle = io.popen('find "' .. M.vault_path .. '" -iname "' .. link .. '.md" -type f | head -1')
      if handle then
        local path = handle:read("*a"):gsub("\n", "")
        handle:close()
        if path ~= "" then
          table.insert(links, { name = link, path = path })
        else
          table.insert(links, { name = link, path = nil })
        end
      end
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
  local handle = io.popen('grep -rlF -- "' .. search_term .. '" "' .. M.vault_path .. '" --include="*.md" 2>/dev/null')
  if not handle then
    return backlinks
  end
  local result = handle:read("*a")
  handle:close()

  for file in result:gmatch("[^\n]+") do
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
    return "ObsidianTransclusionHeader"
  elseif line:match("^%s*[-*]%s") or line:match("^%s*%d+%.%s") then
    return "ObsidianTransclusionList"
  elseif line:match("%[%[.+%]%]") or line:match("%[.+%]%(") then
    return "ObsidianTransclusionLink"
  elseif line:match("%*%*.+%*%*") or line:match("__.+__") then
    return "ObsidianTransclusionBold"
  else
    return "ObsidianTransclusionContent"
  end
end

function M.escape_pattern(s)
  return s:gsub("([%-%.%+%[%]%(%)%$%^%%%?%*])", "%%%1")
end

return M
