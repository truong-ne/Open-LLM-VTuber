-- SPDX-License-Identifier: GPL-2.0-or-later
-- Game Lua remains sandboxed. Input is three identifiers, never Lua or WML code.
local ca = {}
local base = "~add-ons/Mao_Wesnoth/"
local function read(name)
    local ok, value = pcall(filesystem.read_file, base .. name)
    if ok and type(value) == "string" then return value end
    return ""
end

local function json(value)
    if type(value) == "string" then
        return '"' .. value:gsub('[%z\1-\31\\"]', function(c)
            return string.format("\\u%04x", string.byte(c))
        end) .. '"'
    elseif type(value) == "number" or type(value) == "boolean" then
        return tostring(value)
    elseif type(value) == "table" then
        local parts = {}
        if value[1] ~= nil or next(value) == nil then
            for _, v in ipairs(value) do parts[#parts + 1] = json(v) end
            return "[" .. table.concat(parts, ",") .. "]"
        end
        for k, v in pairs(value) do parts[#parts + 1] = json(tostring(k)) .. ":" .. json(v) end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    return "null"
end

local function emit(value)
    wesnoth.log("info", "MAO_WESNOTH_V1 " .. json(value), false)
end

local function unit_summary()
    local units = {}
    for _, u in ipairs(wesnoth.units.find_on_map {}) do
        units[#units + 1] = {id=u.id, side=u.side, type=u.type, x=u.x, y=u.y,
            hp=u.hitpoints, max_hp=u.max_hitpoints, moves=u.moves, attacks=u.attacks_left,
            leader=u.canrecruit}
    end
    return units
end

function ca.finish(outcome)
    local session = read("session.txt"):match("^([a-f0-9]+)")
    if session and #session == 32 then
        emit {type="game_end", session=session, request_id="0:0:0",
            outcome=outcome, turn=wesnoth.current.turn, side=1}
    end
end

local function action_list(side)
    local actions = {{id="a0", kind="end_turn"}}
    local own = wesnoth.units.find_on_map {side=side}
    local enemies = wesnoth.units.find_on_map { {"filter_side", { {"enemy_of", {side=side}} }} }
    local target = enemies[1]
    for _, enemy in ipairs(enemies) do if enemy.canrecruit then target = enemy; break end end
    local target_x, target_y = target and target.x or 9, target and target.y or 8
    local function add(a)
        if #actions < 64 then
            a.id = "a" .. #actions
            actions[#actions + 1] = a
        end
    end
    for _, u in ipairs(own) do
        for _, e in ipairs(enemies) do
            if u.attacks_left > 0 then
                local check = ai.check_attack(u, e)
                if check.ok then
                    local att, def = wesnoth.simulate_combat(u, e)
                    add {kind="attack", unit=u.id, target=e.id,
                        forecast={attacker_expected_hp=att.average_hp,
                            defender_expected_hp=def.average_hp,
                            attacker_death_probability=att.hp_chance[0] or 0,
                            defender_death_probability=def.hp_chance[0] or 0}}
                end
            end
        end
    end
    for _, t in ipairs(wesnoth.sides[side].recruit) do
        local recruited_options = 0
        for x=1,12 do for y=1,10 do
            if recruited_options < 4 then
                local check = ai.check_recruit(t, x, y)
                if check.ok and not wesnoth.units.get(x, y) then
                    add {kind="recruit", unit_type=t, x=x, y=y}
                    recruited_options = recruited_options + 1
                end
            end
        end end
    end
    for _, u in ipairs(own) do
        if u.moves > 0 then
            local reach = wesnoth.paths.find_reach(u)
            table.sort(reach, function(a,b)
                local da = math.abs(a[1]-target_x)+math.abs(a[2]-target_y)
                local db = math.abs(b[1]-target_x)+math.abs(b[2]-target_y)
                if da ~= db then return da < db end
                if a[1] ~= b[1] then return a[1] < b[1] end
                return a[2] < b[2]
            end)
            local seen = {}
            local function pick(limit)
                local count = 0
                for _, p in ipairs(reach) do
                    if count >= limit then break end
                    local key = p[1] .. ":" .. p[2]
                    if not seen[key] and not wesnoth.units.get(p[1], p[2]) then
                        local check = ai.check_move(u, p[1], p[2])
                        if check.ok then
                            local adjacent_enemies, adjacent_allies = 0, 0
                            for _, e in ipairs(enemies) do
                                if wesnoth.map.distance_between(p[1],p[2],e.x,e.y) == 1 then
                                    adjacent_enemies = adjacent_enemies + 1
                                end
                            end
                            for _, ally in ipairs(own) do
                                if ally.id ~= u.id and wesnoth.map.distance_between(p[1],p[2],ally.x,ally.y) == 1 then
                                    adjacent_allies = adjacent_allies + 1
                                end
                            end
                            local terrain = wesnoth.current.map[{p[1],p[2]}]
                            add {kind="move", unit=u.id, x=p[1], y=p[2],
                                adjacent_enemies=adjacent_enemies, adjacent_allies=adjacent_allies,
                                defense_percent=u:defense_on(terrain),
                                healing=wesnoth.terrain_types[terrain].healing}
                            seen[key] = true
                            count = count + 1
                        end
                    end
                end
            end
            pick(6)
            -- Include retreat choices instead of offering only forward movement.
            table.sort(reach, function(a,b)
                local da = math.abs(a[1]-2)+math.abs(a[2]-3)
                local db = math.abs(b[1]-2)+math.abs(b[2]-3)
                if da ~= db then return da < db end
                if a[1] ~= b[1] then return a[1] < b[1] end
                return a[2] < b[2]
            end)
            pick(6)
        end
    end
    return actions
end

function ca:evaluation(cfg, data)
    if data.ended_turn == wesnoth.current.turn then return 0 end
    if data.action_turn ~= wesnoth.current.turn then
        data.action_turn = wesnoth.current.turn
        data.action_count = 0
    end
    if (data.action_count or 0) >= 24 then return 0 end
    return 100000
end

function ca:execution(cfg, data)
    local session = read("session.txt"):match("^([a-f0-9]+)")
    if not session or #session ~= 32 then
        data.ended_turn = wesnoth.current.turn
        return
    end
    data.sequence = (data.sequence or 0) + 1
    data.action_count = (data.action_count or 0) + 1
    local side = wesnoth.current.side
    local request = wesnoth.current.turn .. ":" .. side .. ":" .. data.sequence
    local actions = action_list(side)
    emit {type="state", session=session, request_id=request, turn=wesnoth.current.turn,
        side=side, gold=wesnoth.sides[side].gold, units=unit_summary(), actions=actions}
    local chosen
    for _=1,900 do
        local s,r,a = read("command.txt"):match("^([a-f0-9]+) ([%d:]+) (a%d+)%s*$")
        if s == session and r == request then
            for _, item in ipairs(actions) do if item.id == a then chosen = item; break end end
        end
        if chosen then break end
        wesnoth.interface.delay(100)
    end
    if not chosen then
        data.ended_turn = wesnoth.current.turn
        emit {type="result", session=session, request_id=request, action_id="a0",
            status="timeout", confirmed=false}
        return
    end
    local ok, result = pcall(function()
        if chosen.kind == "end_turn" then
            data.ended_turn = wesnoth.current.turn
            return {ok=true}
        elseif chosen.kind == "move" then
            local u = wesnoth.units.get(chosen.unit)
            if u and u.side == side and not wesnoth.units.get(chosen.x, chosen.y)
                and ai.check_move(u, chosen.x, chosen.y).ok then
                local x, y = u.x, u.y
                local moved = ai.move_full(u, chosen.x, chosen.y)
                local after = wesnoth.units.get(chosen.unit)
                return {ok=moved.ok and after and (after.x ~= x or after.y ~= y)}
            end
        elseif chosen.kind == "attack" then
            local u,e = wesnoth.units.get(chosen.unit), wesnoth.units.get(chosen.target)
            if u and e and u.side == side and ai.check_attack(u,e).ok then return ai.attack(u,e) end
        elseif chosen.kind == "recruit" then
            if ai.check_recruit(chosen.unit_type,chosen.x,chosen.y).ok then
                return ai.recruit(chosen.unit_type,chosen.x,chosen.y)
            end
        end
        return {ok=false}
    end)
    local confirmed = ok and result and result.ok or false
    emit {type="result", session=session, request_id=request, action_id=chosen.id,
        kind=chosen.kind, status=confirmed and "completed" or "failed", confirmed=confirmed,
        gold=wesnoth.sides[side].gold, executed=chosen, units=unit_summary()}
    if not confirmed then data.ended_turn = wesnoth.current.turn end
end

return ca
